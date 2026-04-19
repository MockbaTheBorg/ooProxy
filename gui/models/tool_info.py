"""Tool information model — metadata for discoverable tools."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ToolInfo:
    """Represents a single tool script discovered in tools/."""

    name: str  # Human-readable label (e.g. "Ollama Chat")
    filename: str  # Script filename (e.g. "ollama_chat.py")
    path: str  # Absolute path to the script
    description: str = ""  # Short description shown on the card
    interactive: bool = False  # If True, opens in external terminal

    # Icons are mapped by known filenames
    icon_char: str = "🔧"  # Emoji fallback for the card


# Pre-configured metadata for known tools
TOOL_METADATA: dict[str, dict] = {
    "ollama_chat.py": {
        "description": "Chat interativo com modelos via API Ollama-compatível",
        "interactive": True,
        "icon_char": "💬",
    },
    "ollama_keys.py": {
        "description": "Gerenciar chaves de API armazenadas localmente",
        "interactive": False,
        "icon_char": "🔑",
    },
    "ollama_list_models.py": {
        "description": "Listar modelos disponíveis no servidor remoto",
        "interactive": False,
        "icon_char": "📋",
    },
}


def enrich_tool_info(raw: dict[str, str]) -> ToolInfo:
    """Merge discovered tool dict with known metadata to build a ToolInfo."""
    meta = TOOL_METADATA.get(raw["filename"], {})
    return ToolInfo(
        name=raw["name"],
        filename=raw["filename"],
        path=raw["path"],
        description=meta.get("description", ""),
        interactive=meta.get("interactive", False),
        icon_char=meta.get("icon_char", "🔧"),
    )
