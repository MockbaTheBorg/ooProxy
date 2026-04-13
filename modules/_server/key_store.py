"""Weakly obfuscated API key storage under ~/.ooProxy/keys.json."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger("ooproxy")


def _default_store_path() -> Path:
    return Path.home() / ".ooProxy" / "keys.json"


def normalize_endpoint(endpoint: str) -> str:
    raw = str(endpoint or "").strip()
    if not raw:
        return ""
    candidate = raw if "://" in raw or raw.startswith("//") else f"//{raw}"
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").strip().lower()
    if not host:
        return raw.rstrip("/").lower()
    if parsed.port:
        return f"{host}:{parsed.port}"
    return host


def endpoint_from_url(url: str) -> str:
    return normalize_endpoint(url)


def _keystream(seed: str, size: int) -> bytes:
    stream = bytearray()
    counter = 0
    while len(stream) < size:
        block = hashlib.sha256(f"{seed}:{counter}".encode("utf-8")).digest()
        stream.extend(block)
        counter += 1
    return bytes(stream[:size])


def encrypt_key(endpoint: str, value: str) -> str:
    normalized = normalize_endpoint(endpoint)
    payload = value.encode("utf-8")
    secret = _keystream(normalized, len(payload))
    encrypted = bytes(left ^ right for left, right in zip(payload, secret))
    token = base64.urlsafe_b64encode(encrypted).decode("ascii")
    return f"v1:{token}"


def decrypt_key(endpoint: str, value: str) -> str:
    normalized = normalize_endpoint(endpoint)
    if not value.startswith("v1:"):
        raise ValueError("unsupported key encoding")
    encoded = value[3:]
    encrypted = base64.urlsafe_b64decode(encoded.encode("ascii"))
    secret = _keystream(normalized, len(encrypted))
    payload = bytes(left ^ right for left, right in zip(encrypted, secret))
    return payload.decode("utf-8")


class ApiKeyStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = _default_store_path() if path is None else path
        self._data: dict[str, str] = {}
        self._load()

    def get(self, endpoint: str) -> str | None:
        normalized = normalize_endpoint(endpoint)
        if not normalized:
            return None
        value = self._data.get(normalized)
        if value is None:
            return None
        try:
            return decrypt_key(normalized, value)
        except Exception as exc:
            logger.warning("key store: could not decrypt entry for %s: %s", normalized, exc)
            return None

    def set(self, endpoint: str, key: str) -> str:
        normalized = normalize_endpoint(endpoint)
        if not normalized:
            raise ValueError("endpoint is required")
        self._data[normalized] = encrypt_key(normalized, key)
        self._save()
        return normalized

    def delete(self, endpoint: str) -> bool:
        normalized = normalize_endpoint(endpoint)
        if not normalized:
            return False
        removed = self._data.pop(normalized, None) is not None
        if removed:
            self._save()
        return removed

    def hosts(self) -> list[str]:
        return sorted(self._data)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("keys.json must contain a JSON object")
            self._data = {
                normalize_endpoint(endpoint): value
                for endpoint, value in raw.items()
                if normalize_endpoint(str(endpoint)) and isinstance(value, str)
            }
        except Exception as exc:
            logger.warning("key store: could not load %s: %s", self._path, exc)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )