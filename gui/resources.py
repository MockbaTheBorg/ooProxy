"""Centralized resource paths and icon helpers for the ooProxy GUI."""

from __future__ import annotations

import os
from pathlib import Path

# Project root is two levels up from gui/resources.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
GUI_DIR = Path(__file__).resolve().parent
TOOLS_DIR = PROJECT_ROOT / "tools"
MODULES_DIR = PROJECT_ROOT / "modules"
ENDPOINTS_DIR = PROJECT_ROOT / "endpoints"

# User-level config directories
OOPROXY_DIR = Path.home() / ".ooproxy"
OOPROXY_KEYS_FILE = OOPROXY_DIR / "keys"
OOPROXY_LOG_FILE = OOPROXY_DIR / "startup.log"

# Legacy key store (v1 XOR)
LEGACY_KEYS_DIR = Path.home() / ".ooProxy"
LEGACY_KEYS_FILE = LEGACY_KEYS_DIR / "keys.json"

# Application icon
ICON_PATH = GUI_DIR / "icon.png"

# Python executable (prefer venv)
VENV_PYTHON = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"


def get_python_path() -> str:
    """Return the path to the Python interpreter (venv-aware)."""
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return "python"


def get_ooproxy_script() -> str:
    """Return the path to the main ooproxy.py CLI host."""
    return str(PROJECT_ROOT / "ooproxy.py")


def get_ps1_script() -> str:
    """Return the path to Start-OoProxy.ps1."""
    return str(PROJECT_ROOT / "Start-OoProxy.ps1")


def get_tool_scripts() -> list[dict[str, str]]:
    """Discover tool scripts in the tools/ directory.

    Returns a list of dicts with 'name', 'filename', and 'path' keys.
    """
    tools = []
    if not TOOLS_DIR.exists():
        return tools
    for entry in sorted(TOOLS_DIR.iterdir()):
        if entry.suffix == ".py" and not entry.name.startswith("_"):
            # Derive a human label from the filename
            label = entry.stem.replace("_", " ").title()
            tools.append({
                "name": label,
                "filename": entry.name,
                "path": str(entry),
            })
    return tools
