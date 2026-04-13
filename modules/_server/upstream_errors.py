"""Helpers for converting upstream API failures into assistant-style replies."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from http import HTTPStatus

import httpx

from modules._server.translate.response import (
    openai_chat_to_anthropic_message,
    openai_chat_to_ollama,
    openai_chat_to_responses,
    openai_generate_to_ollama,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def _extract_message_from_payload(payload: object) -> str | None:
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            for key in ("message", "detail", "error"):
                value = error.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        for key in ("message", "detail", "error", "title"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _response_detail(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except (ValueError, json.JSONDecodeError):
        payload = None
    detail = _extract_message_from_payload(payload)
    if detail:
        return detail
    text = response.text.strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text
    return _extract_message_from_payload(payload) or text


def assistant_error_text(exc: Exception, model: str | None = None) -> str:
    """Return a plain assistant message describing the upstream failure."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        detail = _response_detail(exc.response)
        try:
            phrase = HTTPStatus(status).phrase
        except ValueError:
            phrase = ""

        if status == 404 and model:
            return (
                f"I couldn't use model {model} because the upstream API returned 404 Not Found. "
                "It may be listed by the provider but not actually available to this account. "
                "Please choose a different model."
            )

        prefix = f"I couldn't complete that request because the upstream API returned {status}"
        if phrase:
            prefix = f"{prefix} {phrase}"
        if detail:
            if detail.lower() in prefix.lower():
                return prefix + "."
            return f"{prefix}. {detail}"
        return prefix + "."

    if isinstance(exc, httpx.RequestError):
        detail = str(exc).strip() or type(exc).__name__
        return f"I couldn't complete that request because the upstream API connection failed. {detail}"

    detail = str(exc).strip() or type(exc).__name__
    return f"I couldn't complete that request because an upstream error occurred. {detail}"


def synthetic_openai_chat_completion(model: str, text: str) -> dict:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:16]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def synthetic_ollama_chat(model: str, text: str) -> dict:
    return openai_chat_to_ollama(synthetic_openai_chat_completion(model, text), model)


def synthetic_ollama_generate(model: str, text: str) -> dict:
    return openai_generate_to_ollama(synthetic_openai_chat_completion(model, text), model)


def synthetic_responses_payload(
    request_body: dict,
    response_id: str,
    text: str,
    *,
    previous_response_id: str | None = None,
) -> dict:
    payload, _ = openai_chat_to_responses(
        synthetic_openai_chat_completion(request_body["model"], text),
        request_body,
        response_id,
        previous_response_id=previous_response_id,
    )
    return payload


def synthetic_anthropic_message(request_body: dict, text: str) -> dict:
    return openai_chat_to_anthropic_message(
        synthetic_openai_chat_completion(request_body["model"], text),
        request_body,
    )


async def iter_openai_error_stream(
    model: str,
    text: str,
    *,
    include_role: bool = True,
) -> AsyncIterator[bytes]:
    cid = f"chatcmpl-{uuid.uuid4().hex[:16]}"
    created = int(time.time())

    def _chunk(delta: dict, finish_reason: str | None = None) -> bytes:
        payload = {
            "id": cid,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        return f"data: {json.dumps(payload)}\n\n".encode()

    if include_role:
        yield _chunk({"role": "assistant", "content": ""})
    yield _chunk({"content": text})
    yield _chunk({}, finish_reason="stop")
    yield b"data: [DONE]\n\n"


async def iter_ollama_chat_error_stream(model: str, text: str) -> AsyncIterator[bytes]:
    yield (
        json.dumps(
            {
                "model": model,
                "created_at": _now_iso(),
                "message": {"role": "assistant", "content": text},
                "done": False,
            }
        )
        + "\n"
    ).encode()
    yield (
        json.dumps(
            {
                "model": model,
                "created_at": _now_iso(),
                "message": {"role": "assistant", "content": ""},
                "done": True,
                "done_reason": "stop",
                "eval_count": 0,
                "prompt_eval_count": 0,
                "total_duration": 0,
                "load_duration": 0,
                "prompt_eval_duration": 0,
                "eval_duration": 0,
            }
        )
        + "\n"
    ).encode()


async def iter_ollama_generate_error_stream(model: str, text: str) -> AsyncIterator[bytes]:
    yield (
        json.dumps(
            {
                "model": model,
                "created_at": _now_iso(),
                "response": text,
                "done": False,
            }
        )
        + "\n"
    ).encode()
    yield (
        json.dumps(
            {
                "model": model,
                "created_at": _now_iso(),
                "response": "",
                "done": True,
                "done_reason": "stop",
                "eval_count": 0,
                "prompt_eval_count": 0,
                "total_duration": 0,
                "load_duration": 0,
                "prompt_eval_duration": 0,
                "eval_duration": 0,
            }
        )
        + "\n"
    ).encode()