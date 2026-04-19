"""Generic QProcess wrapper for running PowerShell commands.

Used for:
- DPAPI key encryption / decryption
- Scheduled Task install / uninstall
- Any one-shot PowerShell invocations
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QProcess, pyqtSignal


class PowerShellRunner(QObject):
    """Runs a PowerShell command asynchronously and reports the result."""

    # Emitted when the command finishes (success, stdout, stderr)
    finished = pyqtSignal(bool, str, str)  # ok, stdout, stderr
    # Emitted for incremental output
    output_received = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._stdout_buf: list[str] = []
        self._stderr_buf: list[str] = []

    def run_command(self, command: str) -> None:
        """Execute a PowerShell command string.

        Example::

            runner.run_command("ConvertTo-SecureString 'xxx' | ...")
        """
        self._run(
            "powershell.exe",
            ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        )

    def run_script(self, script_path: str, args: list[str] | None = None) -> None:
        """Execute a .ps1 script file with optional arguments.

        Example::

            runner.run_script("Start-OoProxy.ps1", ["-Install"])
        """
        ps_args = ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path]
        if args:
            ps_args.extend(args)
        self._run("powershell.exe", ps_args)

    def is_running(self) -> bool:
        if self._process is None:
            return False
        return self._process.state() == QProcess.ProcessState.Running

    # ── Internal ──────────────────────────────────────────────────────

    def _run(self, program: str, arguments: list[str]) -> None:
        if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
            return

        self._stdout_buf.clear()
        self._stderr_buf.clear()

        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)
        self._process.start(program, arguments)

    def _on_stdout(self) -> None:
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._stdout_buf.append(data)
        for line in data.splitlines():
            if line.strip():
                self.output_received.emit(line)

    def _on_stderr(self) -> None:
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
        self._stderr_buf.append(data)

    def _on_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        stdout = "".join(self._stdout_buf).strip()
        stderr = "".join(self._stderr_buf).strip()
        self.finished.emit(exit_code == 0, stdout, stderr)

    def _on_error(self, _error: QProcess.ProcessError) -> None:
        stderr = "".join(self._stderr_buf).strip()
        self.finished.emit(False, "", stderr or "QProcess error occurred")
