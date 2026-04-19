"""Tools controller — discovers and executes tool scripts."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from gui.models.tool_info import ToolInfo, enrich_tool_info
from gui.resources import get_tool_scripts
from gui.workers.tool_runner import ToolRunner


class ToolsController(QObject):
    """Discovers available tools and runs them via ToolRunner."""

    tools_discovered = pyqtSignal(list)  # list[ToolInfo]
    tool_output = pyqtSignal(str, str)  # tool_name, output_line
    tool_finished = pyqtSignal(str, int, str)  # tool_name, exit_code, full_output
    tool_error = pyqtSignal(str, str)  # tool_name, error_text

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tools: list[ToolInfo] = []
        self._active_runner: ToolRunner | None = None
        self._active_tool_name: str = ""

    @property
    def tools(self) -> list[ToolInfo]:
        return list(self._tools)

    def discover(self) -> None:
        """Scan the tools/ directory and emit discovered tools."""
        raw_tools = get_tool_scripts()
        self._tools = [enrich_tool_info(t) for t in raw_tools]
        self.tools_discovered.emit(self._tools)

    def run_tool(self, tool: ToolInfo, args: list[str] | None = None) -> None:
        """Execute a tool — inline for non-interactive, external for interactive."""
        if tool.interactive:
            ToolRunner.run_external(tool.path, args)
            return

        # Run inline with captured output
        if self._active_runner is not None and self._active_runner.is_running():
            self.tool_error.emit(tool.name, "Outra ferramenta já está em execução.")
            return

        self._active_tool_name = tool.name
        self._active_runner = ToolRunner(self)
        self._active_runner.output_received.connect(
            lambda line: self.tool_output.emit(self._active_tool_name, line)
        )
        self._active_runner.error_received.connect(
            lambda line: self.tool_error.emit(self._active_tool_name, line)
        )
        self._active_runner.finished.connect(self._on_tool_finished)
        self._active_runner.run_inline(tool.path, args)

    def cancel_tool(self) -> None:
        """Cancel the currently running tool."""
        if self._active_runner and self._active_runner.is_running():
            self._active_runner.cancel()

    def _on_tool_finished(self, exit_code: int, full_output: str) -> None:
        self.tool_finished.emit(self._active_tool_name, exit_code, full_output)
        self._active_runner = None
