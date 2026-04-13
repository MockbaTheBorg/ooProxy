"""Proxy configuration dataclass and loader."""

from __future__ import annotations

import os
from dataclasses import dataclass

from modules._server.key_store import ApiKeyStore, endpoint_from_url

_DEFAULT_URL = "https://integrate.api.nvidia.com/v1"
_DEFAULT_PORT = 11434


@dataclass
class ProxyConfig:
    url: str
    key: str
    port: int

    @classmethod
    def from_args(cls, args) -> "ProxyConfig":
        url = getattr(args, "url", None) or os.environ.get("OPENAI_BASE_URL") or _DEFAULT_URL
        key = getattr(args, "key", None) or os.environ.get("OPENAI_API_KEY") or ""
        if not key:
            key = ApiKeyStore().get(endpoint_from_url(url)) or ""
        port = getattr(args, "port", None) or _DEFAULT_PORT
        return cls(url=url.rstrip("/"), key=key, port=int(port))
