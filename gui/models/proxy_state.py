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


# Human-readable labels for the status bar and LED tooltip
STATUS_LABELS: dict[ProxyStatus, str] = {
    ProxyStatus.UNKNOWN: "Desconhecido",
    ProxyStatus.CHECKING: "Verificando…",
    ProxyStatus.STOPPED: "Parado",
    ProxyStatus.STARTING: "Iniciando…",
    ProxyStatus.RUNNING: "Rodando",
    ProxyStatus.STOPPING: "Parando…",
    ProxyStatus.ERROR: "Erro",
}


@dataclass
class ProxyInfo:
    """Snapshot of the current proxy state shown in the UI."""

    status: ProxyStatus = ProxyStatus.UNKNOWN
    backend_url: str = ""
    local_port: int = 11434
    pid: int | None = None
    error_message: str = ""
    log_lines: list[str] = field(default_factory=list)
