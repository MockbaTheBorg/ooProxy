"""Handler for POST /api/chat."""

from __future__ import annotations

import logging

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from modules._server.translate.request import chat_to_openai, direct_display_tool_reply
from modules._server.translate.response import openai_chat_to_ollama
from modules._server.translate.stream import sse_to_ndjson
from modules._server.upstream_errors import (
    assistant_error_text,
    iter_ollama_chat_error_stream,
    synthetic_ollama_chat,
)

logger = logging.getLogger("ooproxy")

_TOOL_ERRORS = (
    "tool choice requires",
    "tool_choice",
    "tools",
    "function_call",
    "enable-auto-tool-choice",
    "tool-call-parser",
)


def _strip_tools(body: dict) -> dict:
    return {k: v for k, v in body.items() if k not in ("tools", "tool_choice")}


def _strip_auto_tool_choice(body: dict) -> dict:
    tool_choice = body.get("tool_choice")
    if tool_choice == "auto":
        return {k: v for k, v in body.items() if k != "tool_choice"}
    if isinstance(tool_choice, dict) and tool_choice.get("type") == "auto":
        return {k: v for k, v in body.items() if k != "tool_choice"}
    return body


def _apply_native_request_flags(body: dict, flags: dict[str, bool]) -> dict:
    current = body
    if flags.get("strip_tool_choice_auto"):
        current = _strip_auto_tool_choice(current)
    if flags.get("strip_tools"):
        current = _strip_tools(current)
    return current


def _is_tool_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(pattern in msg for pattern in _TOOL_ERRORS)


def _native_behavior_flags(request: Request, model: str) -> dict[str, bool]:
    flags: dict[str, bool] = {}
    endpoint_profile = getattr(request.app.state, "endpoint_profile", None)
    if endpoint_profile is not None:
        flags.update(getattr(endpoint_profile, "behavior_defaults", {}) or {})
    behavior = getattr(request.app.state, "behavior", None)
    base_url = getattr(request.app.state, "base_url", "")
    if behavior and base_url and model:
        flags.update(behavior.get_flags(base_url, model))
    return flags


async def _record_native_behavior_flags(request: Request, model: str, observed_flags: set[str]) -> None:
    behavior = getattr(request.app.state, "behavior", None)
    base_url = getattr(request.app.state, "base_url", "")
    if not behavior or not base_url or not model:
        return
    for flag in sorted(observed_flags):
        await behavior.record(base_url, model, flag)


async def _native_open_stream_with_retries(
    request: Request,
    client,
    body: dict,
    *,
    model: str,
    behavior_flags: dict[str, bool],
) -> tuple[httpx.Response, set[str]]:
    current = body
    observed_flags: set[str] = set()
    stripped_tools = behavior_flags.get("strip_tools", False)
    while True:
        try:
            return await client.open_stream_chat(current), observed_flags
        except httpx.HTTPStatusError as exc:
            if not stripped_tools and _is_tool_error(exc) and "tools" in current:
                logger.info("api/chat retrying without tools for model=%s", model)
                current = _strip_tools(current)
                stripped_tools = True
                observed_flags.add("strip_tools")
                continue
            raise


async def _native_chat_with_retries(
    request: Request,
    client,
    body: dict,
    *,
    model: str,
    behavior_flags: dict[str, bool],
) -> tuple[dict, set[str]]:
    current = body
    observed_flags: set[str] = set()
    stripped_tools = behavior_flags.get("strip_tools", False)
    while True:
        try:
            return await client.chat(current), observed_flags
        except httpx.HTTPStatusError as exc:
            if not stripped_tools and _is_tool_error(exc) and "tools" in current:
                logger.info("api/chat retrying without tools for model=%s", model)
                current = _strip_tools(current)
                stripped_tools = True
                observed_flags.add("strip_tools")
                continue
            raise


async def chat_handler(request: Request) -> StreamingResponse | JSONResponse:
    """POST /api/chat — translate and proxy to remote chat completions."""
    body = await request.json()
    client = request.app.state.client
    model = body.get("model", "")
    streaming = body.get("stream", False)
    behavior_flags = _native_behavior_flags(request, model)
    direct_reply = direct_display_tool_reply(body)

    if direct_reply is not None:
        if streaming:
            return StreamingResponse(iter_ollama_chat_error_stream(model, direct_reply), media_type="application/x-ndjson")
        return JSONResponse(synthetic_ollama_chat(model, direct_reply))

    openai_body = _apply_native_request_flags(chat_to_openai(body), behavior_flags)

    logger.info("api/chat model=%s stream=%s msgs=%d",
                model, streaming, len(body.get("messages", [])))
    logger.debug(
        "api/chat final upstream keys=%s tools=%s tool_choice=%r",
        sorted(openai_body.keys()),
        "tools" in openai_body,
        openai_body.get("tool_choice"),
    )

    if streaming:
        async def generate():
            observed_flags: set[str] = set()
            try:
                upstream, retry_flags = await _native_open_stream_with_retries(
                    request,
                    client,
                    openai_body,
                    model=model,
                    behavior_flags=behavior_flags,
                )
                observed_flags.update(retry_flags)
                async for chunk in sse_to_ndjson(
                    upstream.aiter_lines(),
                    model,
                    behavior_flags=behavior_flags,
                    observed_flags=observed_flags,
                ):
                    yield chunk
                await upstream.aclose()
                if observed_flags:
                    await _record_native_behavior_flags(request, model, observed_flags)
            except Exception as exc:
                logger.error("api/chat upstream error model=%s: %s", model, exc)
                async for chunk in iter_ollama_chat_error_stream(model, assistant_error_text(exc, model)):
                    yield chunk

        return StreamingResponse(generate(), media_type="application/x-ndjson")

    try:
        data, observed_flags = await _native_chat_with_retries(
            request,
            client,
            openai_body,
            model=model,
            behavior_flags=behavior_flags,
        )
    except Exception as exc:
        logger.error("api/chat upstream error model=%s: %s", model, exc)
        return JSONResponse(synthetic_ollama_chat(model, assistant_error_text(exc, model)))
    usage = data.get("usage") or {}
    finish = ((data.get("choices") or [{}])[0]).get("finish_reason", "?")
    logger.info("api/chat ← model=%s finish=%s prompt=%d compl=%d",
                model, finish,
                usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
    translated = openai_chat_to_ollama(
        data,
        model,
        behavior_flags=behavior_flags,
        observed_flags=observed_flags,
    )
    if observed_flags:
        await _record_native_behavior_flags(request, model, observed_flags)
    return JSONResponse(translated)
