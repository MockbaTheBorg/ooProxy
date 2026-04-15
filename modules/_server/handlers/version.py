"""Handler for GET /api/version."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse, PlainTextResponse

from ooproxy_version import OLLAMA_COMPAT_VERSION, OO_PROXY_VERSION_TAG


async def version_handler(request: Request) -> JSONResponse:
    return JSONResponse({"version": OLLAMA_COMPAT_VERSION, "ooproxy_version": OO_PROXY_VERSION_TAG})


async def root_handler(request: Request) -> PlainTextResponse:
    return PlainTextResponse("Ollama is running")
