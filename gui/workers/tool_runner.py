"""QProcess wrapper for running tool scripts from tools/.

Non-interactive tools have their output captured and emitted via signals.
Interactive tools (like ollama_chat.py) are launched in an external
terminal window.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QObject, QProcess, pyqtSignal

from gui.resources import get_python_path


class ToolRunner(QObject):
    """Executes a tool script and reports output."""

    output_received = pyqtSignal(str)  # stdout line
    error_received = pyqtSignal(str)  # stderr line
    finished = pyqtSignal(int, str)  # exit_code, stdout_full

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._stdout_buf: list[str] = []

    def run_inline(self, script_path: str, args: list[str] | None = None) -> None:
        """Run a tool script with output captured in the GUI."""
        if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
            return  # Already running

        self._stdout_buf.clear()
        python = get_python_path()

        self._process = QProcess(self)
        
        # Enforce UTF-8 so emojis don't crash the script in Windows (cp1252)
        env = self._process.processEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        self._process.setProcessEnvironment(env)

        # Set working directory to the project root
        project_root = str(Path(script_path).resolve().parents[1])
        self._process.setWorkingDirectory(project_root)

        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)

        cmd_args = [script_path]
        if args:
            cmd_args.extend(args)
        self._process.start(python, cmd_args)

    @staticmethod
    def run_external(script_path: str, args: list[str] | None = None) -> None:
        """Launch the tool in an external terminal (for interactive TUIs).

        On Windows, opens a new ``cmd.exe`` window.
        """
        python = get_python_path()
        cmd_parts = [python, script_path]
        if args:
            cmd_parts.extend(args)

        if sys.platform == "win32":
            # Use 'start' to open a new console window
            cmd_str = " ".join(f'"{p}"' for p in cmd_parts)
            subprocess.Popen(
                f'start "ooProxy Tool" cmd /k {cmd_str}',
                shell=True,
                cwd=str(Path(script_path).resolve().parents[1]),
            )
        else:
            # Fallback for non-Windows (e.g. xterm)
            subprocess.Popen(cmd_parts, cwd=str(Path(script_path).resolve().parents[1]))

    def is_running(self) -> bool:
        if self._process is None:
            return False
        return self._process.state() == QProcess.ProcessState.Running

    def cancel(self) -> None:
        """Kill the running tool process."""
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()

    # ── Private ───────────────────────────────────────────────────────

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
        for line in data.splitlines():
            if line.strip():
                self.error_received.emit(line)

    def _on_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        full_output = "".join(self._stdout_buf).strip()
        self.finished.emit(exit_code, full_output)
