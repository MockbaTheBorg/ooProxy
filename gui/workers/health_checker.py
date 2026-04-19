"""Health-check thread that periodically polls the proxy endpoint.

Emits ``status_changed(bool)`` — True when the proxy is reachable, False
otherwise.  Runs in a dedicated QThread to avoid blocking the UI.
"""

from __future__ import annotations

import urllib.request
import urllib.error
from PyQt6.QtCore import QThread, pyqtSignal


class HealthChecker(QThread):
    """Periodically pings the proxy to check liveness."""

    status_changed = pyqtSignal(bool)  # True = proxy is alive

    def __init__(
        self,
        url: str = "http://127.0.0.1:11434/",
        interval_s: int = 30,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._url = url
        self._interval_s = interval_s
        self._running = True
        self._last_status: bool | None = None

    @property
    def url(self) -> str:
        return self._url

    @url.setter
    def url(self, value: str) -> None:
        self._url = value

    def run(self) -> None:
        """Thread main loop — polls until ``stop()`` is called."""
        while self._running:
            alive = self._ping()
            # Only emit on state changes (or first check)
            if alive != self._last_status:
                self._last_status = alive
                self.status_changed.emit(alive)
            # Use QThread's msleep for interruptability
            self.msleep(self._interval_s * 1000)

    def stop(self) -> None:
        """Signal the thread to exit its loop."""
        self._running = False
        self.wait(2000)

    def check_once(self) -> bool:
        """Perform a single synchronous health check (for init)."""
        return self._ping()

    def _ping(self) -> bool:
        """Send an HTTP HEAD and return True on any 2xx/3xx response.

        Uses HEAD instead of GET to minimise proxy log noise.
        """
        try:
            req = urllib.request.Request(self._url, method="HEAD")
            req.add_header("User-Agent", "ooProxy-HealthCheck")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return 200 <= resp.status < 400
        except Exception:
            return False
