"""QProcess wrapper for starting/stopping the ooProxy server.

This worker manages the long-lived ``python ooproxy.py --serve`` process
and emits signals for stdout/stderr lines and lifecycle events.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QProcess, pyqtSignal


class ProxyProcess(QObject):
    """Non-blocking wrapper around the ooproxy.py --serve process."""

    # ── Signals ───────────────────────────────────────────────────────
    output_received = pyqtSignal(str)  # A line from stdout
    error_received = pyqtSignal(str)  # A line from stderr
    process_started = pyqtSignal()  # Process actually started
    process_finished = pyqtSignal(int, str)  # exit_code, exit_status_name

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None

    # ── Public API ────────────────────────────────────────────────────

    def start(self, python_path: str, args: list[str]) -> None:
        """Launch ``python_path`` with the given *args* list.

        Typical call::

            proc.start("C:/.../venv/Scripts/python.exe",
                        ["ooproxy.py", "--serve", "--url", url, "--key", key])
        """
        if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
            return  # Already running

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.started.connect(self._on_started)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

        self._process.start(python_path, args)

    def stop(self, timeout_ms: int = 5000) -> None:
        """Gracefully terminate the process; kill after *timeout_ms*."""
        if self._process is None:
            return
        if self._process.state() == QProcess.ProcessState.NotRunning:
            return

        self._process.terminate()
        if not self._process.waitForFinished(timeout_ms):
            self._process.kill()

    def is_running(self) -> bool:
        """Return True if the managed process is currently running."""
        if self._process is None:
            return False
        return self._process.state() == QProcess.ProcessState.Running

    def pid(self) -> int | None:
        """Return the PID of the running process, or None."""
        if self._process is None:
            return None
        pid_val = self._process.processId()
        return pid_val if pid_val > 0 else None

    # ── Private slots ─────────────────────────────────────────────────

    def _on_stdout(self) -> None:
        if self._process is None:
            return
        data = self._process.readAllStandardOutput()
        text = bytes(data).decode("utf-8", errors="replace")
        for line in text.splitlines():
            if line.strip():
                self.output_received.emit(line)

    def _on_stderr(self) -> None:
        if self._process is None:
            return
        data = self._process.readAllStandardError()
        text = bytes(data).decode("utf-8", errors="replace")
        for line in text.splitlines():
            if line.strip():
                self.error_received.emit(line)

    def _on_started(self) -> None:
        self.process_started.emit()

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        status_name = "NormalExit" if exit_status == QProcess.ExitStatus.NormalExit else "CrashExit"
        self.process_finished.emit(exit_code, status_name)

    def _on_error(self, error: QProcess.ProcessError) -> None:
        error_map = {
            QProcess.ProcessError.FailedToStart: "FailedToStart",
            QProcess.ProcessError.Crashed: "Crashed",
            QProcess.ProcessError.Timedout: "Timedout",
            QProcess.ProcessError.WriteError: "WriteError",
            QProcess.ProcessError.ReadError: "ReadError",
            QProcess.ProcessError.UnknownError: "UnknownError",
        }
        msg = error_map.get(error, "UnknownError")
        self.error_received.emit(f"[QProcess Error] {msg}")
