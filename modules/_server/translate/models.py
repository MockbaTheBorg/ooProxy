"""Translate OpenAI model list to Ollama tags format."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

_FAMILY_KEYWORDS = [
    "llama", "mistral", "gemma", "phi", "qwen", "falcon", "mpt",
    "starcoder", "codellama", "deepseek", "mixtral", "vicuna", "alpaca",
]

_EMBEDDING_KEYWORDS = ["embed", "bge", "e5-", "rerank", "retrieval", "minilm"]

# Models known to have limited (4K) context — everything else defaults to 128K
_SMALL_CONTEXT_KEYWORDS = ["llama2", "llama-2", "llama2-", "codellama-"]

# Models that are completion-capable but unlikely to support tool-calling
# (code-only, older LLMs, reward models)
_NO_TOOLS_KEYWORDS = [
    "llama2", "llama-2", "reward", "starcoder", "codellama",
    "fuyu", "vision", "vl-", "-vl", "image", "audio",
]


def _infer_family(model_id: str) -> str:
    lower = model_id.lower()
    for kw in _FAMILY_KEYWORDS:
        if kw in lower:
            return kw
    return "unknown"


def _infer_context_length(model_id: str) -> int:
    lower = model_id.lower()
    if any(kw in lower for kw in _SMALL_CONTEXT_KEYWORDS):
        return 4096
    # Check for explicit context hints in name
    if "128k" in lower:
        return 131072
    if "32k" in lower:
        return 32768
    if "8k" in lower:
        return 8192
    # Default: 128K for modern models
    return 131072


def _infer_capabilities(model_id: str) -> list[str]:
    lower = model_id.lower()
    if any(kw in lower for kw in _EMBEDDING_KEYWORDS):
        return ["embedding"]
    caps = ["completion"]
    if not any(kw in lower for kw in _NO_TOOLS_KEYWORDS):
        caps.append("tools")
    return caps


def _string_value(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _int_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
    return None


def _entry_family(entry: dict, model_id: str) -> str:
    family = _string_value(entry.get("family"))
    if family:
        return family
    families = entry.get("families")
    if isinstance(families, list):
        for item in families:
            family = _string_value(item)
            if family:
                return family
    return _infer_family(model_id)


def _entry_families(entry: dict, family: str) -> list[str]:
    families = entry.get("families")
    if isinstance(families, list):
        normalized = [_string_value(item) for item in families if _string_value(item)]
        if normalized:
            return normalized
    return [family]


def _entry_context_length(entry: dict, model_id: str) -> int:
    context_length = _int_value(entry.get("context_length"))
    if context_length:
        return context_length
    model_info = entry.get("model_info")
    if isinstance(model_info, dict):
        for key, value in model_info.items():
            if str(key).endswith(".context_length"):
                context_length = _int_value(value)
                if context_length:
                    return context_length
    return _infer_context_length(model_id)


def _entry_capabilities(entry: dict, model_id: str) -> list[str]:
    raw_caps = entry.get("capabilities")
    if isinstance(raw_caps, list):
        capabilities = [_string_value(item) for item in raw_caps if _string_value(item)]
        if capabilities:
            return capabilities

    model_type = _string_value(entry.get("type")).lower()
    if model_type in {"embedding", "rerank"}:
        return ["embedding"]
    return _infer_capabilities(model_id)


def _entry_details(entry: dict, model_id: str) -> dict:
    family = _entry_family(entry, model_id)
    return {
        "parent_model": _string_value(entry.get("parent_model")),
        "format": _string_value(entry.get("format")) or "gguf",
        "family": family,
        "families": _entry_families(entry, family),
        "parameter_size": _string_value(entry.get("parameter_size")),
        "quantization_level": _string_value(entry.get("quantization_level")),
    }


def _created_to_iso(created: int | None) -> str:
    if not created:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return datetime.fromtimestamp(created, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _digest_for(model_id: str) -> str:
    # Stable placeholder digest derived from the model name
    h = abs(hash(model_id)) % (16 ** 12)
    return f"sha256:{h:012x}{'0' * 52}"


def openai_models_to_ollama_tags(data: dict) -> dict:
    """Convert GET /v1/models response to Ollama /api/tags format."""
    models = []
    for entry in data.get("data", []):
        model_id = entry.get("id", "")
        details = _entry_details(entry, model_id)
        models.append({
            "name": model_id,
            "model": model_id,
            "modified_at": _string_value(entry.get("modified_at")) or _created_to_iso(entry.get("created")),
            "size": 0,
            "digest": _string_value(entry.get("digest")) or _digest_for(model_id),
            "details": details,
        })
    return {"models": models}


def openai_model_to_ollama_show(model_id: str, entry: dict | None = None) -> dict:
    """Synthesize an Ollama /api/show response for a given model ID."""
    entry = entry or {}
    details = _entry_details(entry, model_id)
    family = details["family"]
    context_length = _entry_context_length(entry, model_id)
    return {
        "modelfile": f"# Synthesized by ooProxy\nFROM {model_id}\n",
        "parameters": "",
        "template": "{{ .System }}\n{{ .Prompt }}",
        "details": details,
        "model_info": {
            "general.architecture": family,
            f"{family}.context_length": context_length,
        },
        "capabilities": _entry_capabilities(entry, model_id),
    }
