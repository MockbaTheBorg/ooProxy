from __future__ import annotations

import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient

from modules._server.app import create_app
from modules._server.config import ProxyConfig


def _payment_required_error() -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://example.invalid/v1/chat/completions")
    response = httpx.Response(
        402,
        request=request,
        json={
            "error": {
                "message": "This request requires more credits, or fewer max_tokens.",
                "code": 402,
            }
        },
    )
    return httpx.HTTPStatusError("payment required", request=request, response=response)


class _FailingClient:
    async def chat(self, body: dict) -> dict:
        raise _payment_required_error()

    async def open_stream_chat(self, body: dict):
        raise _payment_required_error()

    @asynccontextmanager
    async def stream_chat(self, body: dict):
        raise _payment_required_error()
        yield

    async def get_models(self) -> dict:
        return {"data": []}

    async def embeddings(self, body: dict) -> dict:
        return {"data": []}

    async def aclose(self) -> None:
        return None


class _RecordingClient:
    def __init__(self) -> None:
        self.last_chat_body: dict | None = None

    async def chat(self, body: dict) -> dict:
        self.last_chat_body = body
        return {
            "id": "chatcmpl_test",
            "object": "chat.completion",
            "created": 1,
            "model": body["model"],
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "profile fallback worked"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 2, "completion_tokens": 2, "total_tokens": 4},
        }

    async def open_stream_chat(self, body: dict):
        raise AssertionError("profile should force synthetic streaming without opening an upstream SSE stream")

    @asynccontextmanager
    async def stream_chat(self, body: dict):
        raise AssertionError("not used")
        yield

    async def get_models(self) -> dict:
        return {"data": []}

    async def embeddings(self, body: dict) -> dict:
        return {"data": []}

    async def aclose(self) -> None:
        return None


class ApiErrorResponseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(ProxyConfig(url="https://example.invalid/v1", key="", port=11434))
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.app.state.client = _FailingClient()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)

    def test_api_chat_non_streaming_returns_assistant_error_message(self) -> None:
        response = self.client.post(
            "/api/chat",
            json={
                "model": "demo",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["done"])
        self.assertIn("402 Payment Required", payload["message"]["content"])
        self.assertIn("requires more credits", payload["message"]["content"])

    def test_api_chat_streaming_returns_assistant_error_message(self) -> None:
        with self.client.stream(
            "POST",
            "/api/chat",
            json={
                "model": "demo",
                "stream": True,
                "messages": [{"role": "user", "content": "hello"}],
            },
        ) as response:
            body = b"".join(response.iter_bytes()).decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("402 Payment Required", body)
        self.assertIn("requires more credits", body)
        self.assertIn('"done": true', body)

    def test_api_generate_non_streaming_returns_assistant_error_message(self) -> None:
        response = self.client.post(
            "/api/generate",
            json={
                "model": "demo",
                "prompt": "hello",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["done"])
        self.assertIn("402 Payment Required", payload["response"])
        self.assertIn("requires more credits", payload["response"])

    def test_v1_chat_non_streaming_returns_assistant_error_message(self) -> None:
        response = self.client.post(
            "/v1/chat/completions",
            json={
                "model": "demo",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["choices"][0]["message"]["role"], "assistant")
        self.assertIn("402 Payment Required", payload["choices"][0]["message"]["content"])
        self.assertIn("requires more credits", payload["choices"][0]["message"]["content"])

    def test_v1_chat_streaming_returns_assistant_error_message(self) -> None:
        with self.client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": "demo",
                "stream": True,
                "messages": [{"role": "user", "content": "hello"}],
            },
        ) as response:
            body = b"".join(response.iter_bytes()).decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("data: ", body)
        self.assertIn("402 Payment Required", body)
        self.assertIn("requires more credits", body)

    def test_v1_chat_profile_defaults_shape_request_before_send(self) -> None:
        recording = _RecordingClient()
        self.app.state.client = recording
        self.app.state.endpoint_profile = SimpleNamespace(
            chat_streaming="ndjson",
            chat_tools="native",
            chat_system_prompt="unsupported",
            behavior_defaults={},
        )

        with self.client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": "demo",
                "stream": True,
                "messages": [
                    {"role": "system", "content": "You are terse."},
                    {"role": "user", "content": "hello"},
                ],
                "tools": [{"type": "function", "function": {"name": "Search", "parameters": {"type": "object", "properties": {}, "required": []}}}],
                "tool_choice": "auto",
            },
        ) as response:
            body = b"".join(response.iter_bytes()).decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("profile fallback worked", body)
        self.assertFalse(recording.last_chat_body.get("stream", False))
        self.assertNotIn("tools", recording.last_chat_body)
        self.assertNotIn("tool_choice", recording.last_chat_body)
        self.assertEqual([message["role"] for message in recording.last_chat_body["messages"]], ["user"])


if __name__ == "__main__":
    unittest.main()