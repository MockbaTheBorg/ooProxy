from __future__ import annotations

import unittest

import httpx
from fastapi.testclient import TestClient

from modules._server.app import create_app
from modules._server.behavior import BehaviorCache
from modules._server.config import ProxyConfig


class _DummyClient:
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
                    "message": {"role": "assistant", "content": "hello back"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
        }

    async def open_stream_chat(self, body: dict):
        raise AssertionError("Anthropic compatibility should use synthetic downstream streaming")

    async def get_models(self) -> dict:
        return {"data": []}

    async def embeddings(self, body: dict) -> dict:
        return {"data": []}

    async def aclose(self) -> None:
        return None


class _FailingClient(_DummyClient):
    async def chat(self, body: dict) -> dict:
        self.last_chat_body = body
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
        raise httpx.HTTPStatusError("payment required", request=request, response=response)


class V1MessagesCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(ProxyConfig(url="https://example.invalid/v1", key="", port=11434))
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.dummy = _DummyClient()
        self.app.state.client = self.dummy
        self.app.state.behavior = BehaviorCache(path=None)  # in-memory only — no disk state between tests

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)

    def test_non_streaming_message_shape(self) -> None:
        response = self.client.post(
            "/v1/messages?beta=true",
            json={
                "model": "claude-test",
                "max_tokens": 256,
                "messages": [{"role": "user", "content": "hello there"}],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["type"], "message")
        self.assertEqual(payload["role"], "assistant")
        self.assertEqual(payload["content"][0]["type"], "text")
        self.assertEqual(payload["content"][0]["text"], "hello back")
        self.assertEqual(self.dummy.last_chat_body["messages"][-1]["content"], "hello there")

    def test_streaming_message_shape(self) -> None:
        with self.client.stream(
            "POST",
            "/v1/messages?beta=true",
            json={
                "model": "claude-test",
                "max_tokens": 256,
                "stream": True,
                "messages": [{"role": "user", "content": "hello there"}],
            },
        ) as response:
            body = b"".join(response.iter_bytes()).decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: message_start", body)
        self.assertIn("event: content_block_start", body)
        self.assertIn("event: content_block_delta", body)
        self.assertIn("event: message_delta", body)
        self.assertIn("event: message_stop", body)
        self.assertTrue('"text": "hello back"' in body or '"text":"hello back"' in body)

    def test_non_claude_models_suppress_tools_for_trivial_greetings(self) -> None:
        response = self.client.post(
            "/v1/messages?beta=true",
            json={
                "model": "meta/llama-3.3-70b-instruct",
                "max_tokens": 256,
                "messages": [{"role": "user", "content": "hello there"}],
                "tools": [
                    {
                        "name": "Bash",
                        "description": "Run a shell command",
                        "input_schema": {
                            "type": "object",
                            "properties": {"command": {"type": "string"}},
                            "required": ["command"],
                        },
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("tools", self.dummy.last_chat_body)
        self.assertNotIn("tool_choice", self.dummy.last_chat_body)

    def test_non_claude_models_keep_tools_for_actionable_requests(self) -> None:
        response = self.client.post(
            "/v1/messages?beta=true",
            json={
                "model": "meta/llama-3.3-70b-instruct",
                "max_tokens": 256,
                "messages": [{"role": "user", "content": "list the files in the current folder"}],
                "tools": [
                    {
                        "name": "Bash",
                        "description": "Run a shell command",
                        "input_schema": {
                            "type": "object",
                            "properties": {"command": {"type": "string"}},
                            "required": ["command"],
                        },
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("tools", self.dummy.last_chat_body)

    def test_upstream_error_becomes_assistant_message(self) -> None:
        self.app.state.client = _FailingClient()

        response = self.client.post(
            "/v1/messages?beta=true",
            json={
                "model": "claude-test",
                "max_tokens": 256,
                "messages": [{"role": "user", "content": "hello there"}],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["type"], "message")
        self.assertEqual(payload["role"], "assistant")
        self.assertIn("402 Payment Required", payload["content"][0]["text"])
        self.assertIn("requires more credits", payload["content"][0]["text"])

    def test_streaming_upstream_error_becomes_assistant_message_events(self) -> None:
        self.app.state.client = _FailingClient()

        with self.client.stream(
            "POST",
            "/v1/messages?beta=true",
            json={
                "model": "claude-test",
                "max_tokens": 256,
                "stream": True,
                "messages": [{"role": "user", "content": "hello there"}],
            },
        ) as response:
            body = b"".join(response.iter_bytes()).decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: message_start", body)
        self.assertIn("event: content_block_delta", body)
        self.assertIn("402 Payment Required", body)
        self.assertIn("requires more credits", body)


if __name__ == "__main__":
    unittest.main()