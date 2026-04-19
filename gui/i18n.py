"""Internationalization (i18n) module for the ooProxy GUI.

Usage::

    from gui.i18n import t
    label.setText(t("proxy.status.running"))

The active locale is auto-detected from the system but can be
overridden via ``set_locale("pt_BR")``.
"""

from __future__ import annotations

import locale as _locale
import json
from pathlib import Path
from typing import Any

# ── Locale directory ──────────────────────────────────────────────────
LOCALES_DIR = Path(__file__).resolve().parent / "locales"

# ── Translation dictionaries ─────────────────────────────────────────
_translations: dict[str, dict[str, str]] = {}
_current_locale: str = "en_US"
_fallback_locale: str = "en_US"


def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Flatten a nested dict into dot-separated keys."""
    result: dict[str, str] = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(_flatten(value, full_key))
        else:
            result[full_key] = str(value)
    return result


def _load_locale(locale_code: str) -> dict[str, str]:
    """Load a locale JSON file and return flattened translations."""
    path = LOCALES_DIR / f"{locale_code}.json"
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _flatten(data)
    except Exception:
        return {}


def _detect_system_locale() -> str:
    """Detect the system locale and map to our supported locales."""
    try:
        sys_locale = _locale.getdefaultlocale()[0] or "en_US"
    except Exception:
        sys_locale = "en_US"

    # Map common variants
    if sys_locale.startswith("pt"):
        return "pt_BR"
    return "en_US"


def init() -> None:
    """Initialize the i18n system — load all available locales."""
    global _current_locale

    # Load all locale files
    if LOCALES_DIR.exists():
        for f in LOCALES_DIR.glob("*.json"):
            code = f.stem
            _translations[code] = _load_locale(code)

    # Auto-detect
    _current_locale = _detect_system_locale()
    if _current_locale not in _translations:
        _current_locale = _fallback_locale


def set_locale(locale_code: str) -> None:
    """Switch the active locale."""
    global _current_locale
    if locale_code in _translations:
        _current_locale = locale_code
    elif _fallback_locale in _translations:
        _current_locale = _fallback_locale


def get_locale() -> str:
    """Return the current locale code."""
    return _current_locale


def get_available_locales() -> list[str]:
    """Return list of loaded locale codes."""
    return list(_translations.keys())


def t(key: str, **kwargs: Any) -> str:
    """Translate a key using the current locale.

    Supports ``{placeholder}`` formatting::

        t("proxy.starting_on", url=url, port=port)
    """
    # Try current locale
    translations = _translations.get(_current_locale, {})
    text = translations.get(key)

    # Fallback to en_US
    if text is None:
        fallback = _translations.get(_fallback_locale, {})
        text = fallback.get(key)

    # Ultimate fallback: return the key itself
    if text is None:
        text = key

    # Apply formatting
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass

    return text


# Auto-initialize on import
init()
