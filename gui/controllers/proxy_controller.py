"""Proxy controller — orchestrates ProxyProcess + HealthChecker.

This is the business-logic layer between the ProxyTab (view) and the
background workers.  It holds the canonical proxy state and emits
``status_changed`` / ``log_received`` signals that the view binds to.
"""

from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from gui.models.proxy_state import ProxyStatus
from gui.resources import get_python_path, get_ooproxy_script, OOPROXY_KEYS_FILE
from gui.workers.health_checker import HealthChecker
from gui.workers.powershell_runner import PowerShellRunner
from gui.workers.proxy_process import ProxyProcess


class ProxyController(QObject):
    """Central controller for proxy lifecycle management."""

    status_changed = pyqtSignal(object)  # ProxyStatus
    log_received = pyqtSignal(str)  # Log line for the console

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._status = ProxyStatus.UNKNOWN
        self._process = ProxyProcess(self)
        self._health = HealthChecker(parent=self)
        self._ps_runner = PowerShellRunner(self)

        # Wire process signals
        self._process.output_received.connect(self._on_output)
        self._process.error_received.connect(self._on_output)
        self._process.process_started.connect(self._on_process_started)
        self._process.process_finished.connect(self._on_process_finished)

        # Wire health checker
        self._health.status_changed.connect(self._on_health_changed)

        # Current config (set before start)
        self._url: str = ""
        self._key: str = ""
        self._port: int = 11434

    # ── Public API ────────────────────────────────────────────────────

    def get_status(self) -> ProxyStatus:
        return self._status

    def initial_check(self) -> None:
        """Perform a one-shot health check at startup, then begin polling."""
        self._set_status(ProxyStatus.CHECKING)
        alive = self._health.check_once()
        if alive:
            self._set_status(ProxyStatus.RUNNING)
        else:
            self._set_status(ProxyStatus.STOPPED)
        # Start continuous polling
        self._health.start()

    def start_proxy(self, url: str, key: str, port: int = 11434) -> None:
        """Start the proxy server via QProcess."""
        if self._process.is_running():
            self.log_received.emit("[WARN] Proxy já está rodando.")
            return

        self._url = url
        self._port = port
        self._key = key

        self._set_status(ProxyStatus.STARTING)
        self.log_received.emit(f"Iniciando proxy → {url} (porta {port})")

        python = get_python_path()
        script = get_ooproxy_script()
        args = [script, "--serve", "--url", url, "--port", str(port)]
        if key:
            args.extend(["--key", key])
        self._process.start(python, args)

    def start_proxy_with_dpapi(self, url: str, port: int = 11434) -> None:
        """Resolve the DPAPI key first, then start the proxy.

        Reads the encrypted key from ~/.ooproxy/keys, decrypts via
        PowerShell, and passes it to ``start_proxy()``.
        """
        self._url = url
        self._port = port
        self._set_status(ProxyStatus.STARTING)
        self.log_received.emit("Resolvendo chave DPAPI…")

        encrypted = self._read_dpapi_encrypted_key(url)
        if not encrypted:
            self.log_received.emit("[INFO] Chave DPAPI não encontrada. Iniciando proxy (fallback via keys.json ativado)...")
            self.start_proxy(self._url, "", self._port)
            return

        # Decrypt via PowerShell
        ps_cmd = (
            f"$s = ConvertTo-SecureString '{encrypted}';"
            f"$b = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($s);"
            f"try {{ [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($b) }}"
            f"finally {{ [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) }}"
        )

        # Connect to the runner (one-shot)
        self._ps_runner.finished.connect(self._on_dpapi_decrypted)
        self._ps_runner.run_command(ps_cmd)

    def stop_proxy(self) -> None:
        """Gracefully stop the proxy."""
        if not self._process.is_running():
            return
        self._set_status(ProxyStatus.STOPPING)
        self.log_received.emit("Parando proxy…")
        self._process.stop(timeout_ms=5000)

    def install_startup(self) -> None:
        """Register the ooProxy scheduled task via PowerShell."""
        from gui.resources import get_ps1_script
        self.log_received.emit("Registrando auto-start no Windows…")
        runner = PowerShellRunner(self)
        runner.finished.connect(
            lambda ok, out, err: self.log_received.emit(
                f"[OK] Auto-start registrado." if ok else f"[ERRO] {err}"
            )
        )
        runner.run_script(get_ps1_script(), ["-Install"])

    def uninstall_startup(self) -> None:
        """Remove the ooProxy scheduled task via PowerShell."""
        from gui.resources import get_ps1_script
        self.log_received.emit("Removendo auto-start…")
        runner = PowerShellRunner(self)
        runner.finished.connect(
            lambda ok, out, err: self.log_received.emit(
                f"[OK] Auto-start removido." if ok else f"[ERRO] {err}"
            )
        )
        runner.run_script(get_ps1_script(), ["-Uninstall"])

    def shutdown(self) -> None:
        """Clean up resources — call on application quit."""
        self._health.stop()
        if self._process.is_running():
            self._process.stop(timeout_ms=3000)

    # ── Private helpers ───────────────────────────────────────────────

    def _set_status(self, status: ProxyStatus) -> None:
        if status != self._status:
            self._status = status
            self.status_changed.emit(status)

    def _read_dpapi_encrypted_key(self, url: str) -> str | None:
        """Read the DPAPI-encrypted key from ~/.ooproxy/keys for the given URL."""
        if not OOPROXY_KEYS_FILE.exists():
            return None
        try:
            data = json.loads(OOPROXY_KEYS_FILE.read_text(encoding="utf-8"))
            if data.get("version") != "v2-dpapi":
                return None
            entries = data.get("entries", {})
            # Try to match by normalized endpoint
            from urllib.parse import urlparse
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            if parsed.port:
                endpoint = f"{host}:{parsed.port}"
            else:
                endpoint = host
            # Look for matching entry
            encrypted = entries.get(endpoint)
            if encrypted:
                return encrypted
            # Fall back to first entry
            if entries:
                return next(iter(entries.values()))
            return None
        except Exception:
            return None

    def _on_dpapi_decrypted(self, ok: bool, stdout: str, stderr: str) -> None:
        """Called after PowerShell decrypts the DPAPI key."""
        # Disconnect to avoid repeat firings
        try:
            self._ps_runner.finished.disconnect(self._on_dpapi_decrypted)
        except TypeError:
            pass

        if not ok or not stdout.strip():
            self.log_received.emit(f"[ERRO] Falha ao decriptar chave DPAPI: {stderr}")
            self._set_status(ProxyStatus.ERROR)
            return

        plain_key = stdout.strip()
        self.start_proxy(self._url, plain_key, self._port)
        # Clear from Python memory
        plain_key = ""  # noqa: F841

    def _on_output(self, text: str) -> None:
        # Suppress health-check noise (GET / and HEAD / from the checker)
        stripped = text.strip()
        if any(pattern in stripped for pattern in (
            '"GET / HTTP',
            '"HEAD / HTTP',
            "GET / 200",
            "HEAD / 200",
        )):
            return
        self.log_received.emit(text)

    def _on_process_started(self) -> None:
        self.log_received.emit("Processo do proxy iniciado.")

    def _on_process_finished(self, exit_code: int, exit_status: str) -> None:
        if exit_status == "CrashExit" or exit_code != 0:
            self.log_received.emit(f"[ERRO] Proxy encerrado (code={exit_code}, status={exit_status})")
            self._set_status(ProxyStatus.ERROR)
        else:
            self.log_received.emit("Proxy encerrado normalmente.")
            self._set_status(ProxyStatus.STOPPED)

    def _on_health_changed(self, alive: bool) -> None:
        """React to health-check transitions."""
        if alive and self._status in (ProxyStatus.STARTING, ProxyStatus.CHECKING, ProxyStatus.UNKNOWN):
            self._set_status(ProxyStatus.RUNNING)
            self.log_received.emit("Health-check: proxy está respondendo ✓")
        elif not alive and self._status == ProxyStatus.RUNNING:
            # Proxy was running but stopped responding
            if not self._process.is_running():
                self._set_status(ProxyStatus.STOPPED)
                self.log_received.emit("Health-check: proxy parou de responder.")
