"""Proxy state enums and data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class ProxyStatus(Enum):
    """Lifecycle states for the proxy process."""

    UNKNOWN = auto()
    CHECKING = auto()
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    ERROR = auto()


# i18n key mapping for status labels
_STATUS_I18N_KEYS: dict[ProxyStatus, str] = {
    ProxyStatus.UNKNOWN: "proxy.status.unknown",
    ProxyStatus.CHECKING: "proxy.status.checking",
    ProxyStatus.STOPPED: "proxy.status.stopped",
    ProxyStatus.STARTING: "proxy.status.starting",
    ProxyStatus.RUNNING: "proxy.status.running",
    ProxyStatus.STOPPING: "proxy.status.stopping",
    ProxyStatus.ERROR: "proxy.status.error",
}


def get_status_label(status: ProxyStatus) -> str:
    """Return the translated label for the given proxy status."""
    from gui.i18n import t
    key = _STATUS_I18N_KEYS.get(status, "proxy.status.unknown")
    return t(key)


# Backward-compatible dict-like access (for existing code)
class _StatusLabelsProxy:
    """Dict-like object that resolves translations dynamically."""

    def __getitem__(self, status: ProxyStatus) -> str:
        return get_status_label(status)

    def get(self, status: ProxyStatus, default: str = "Unknown") -> str:
        result = get_status_label(status)
        return result if result != _STATUS_I18N_KEYS.get(status) else default


STATUS_LABELS = _StatusLabelsProxy()


@dataclass
class ProxyInfo:
    """Snapshot of the current proxy state shown in the UI."""

    status: ProxyStatus = ProxyStatus.UNKNOWN
    backend_url: str = ""
    local_port: int = 11434
    pid: int | None = None
    error_message: str = ""
    log_lines: list[str] = field(default_factory=list)
