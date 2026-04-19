"""Tools tab — card grid for available tool scripts."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QGroupBox,
    QFrame,
    QSizePolicy,
    QScrollArea,
)

from gui.controllers.tools_controller import ToolsController
from gui.i18n import t
from gui.models.tool_info import ToolInfo
from gui.theme import COLORS, FONTS, RADIUS


class ToolCard(QFrame):
    """A clickable card representing a single tool."""

    def __init__(self, tool: ToolInfo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tool = tool
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(120)
        self.setMinimumWidth(200)
        self.setStyleSheet(f"""
            ToolCard {{
                background-color: {COLORS['bg_surface']};
                border: 1px solid {COLORS['border']};
                border-radius: {RADIUS};
                padding: 12px;
            }}
            ToolCard:hover {{
                background-color: {COLORS['bg_hover']};
                border-color: {COLORS['accent']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(12, 12, 12, 12)

        # Icon + Name row
        header = QHBoxLayout()
        icon_label = QLabel(tool.icon_char)
        icon_label.setFont(QFont(FONTS["family"].split(",")[0].strip(), 20))
        header.addWidget(icon_label)

        name_label = QLabel(tool.name)
        name_label.setFont(QFont(FONTS["family"].split(",")[0].strip(), 13, QFont.Weight.Bold))
        name_label.setStyleSheet(f"color: {COLORS['text_primary']};")
        header.addWidget(name_label)
        header.addStretch()

        if tool.interactive:
            badge = QLabel(t("tools.badge_terminal"))
            badge.setStyleSheet(
                f"color: {COLORS['warning']}; font-size: 10px; "
                f"background-color: {COLORS['warning_bg']}; "
                f"padding: 2px 6px; border-radius: 3px;"
            )
            header.addWidget(badge)

        layout.addLayout(header)

        # Description
        desc_label = QLabel(tool.description or t("tools.no_description"))
        desc_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        layout.addStretch()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        # Emit click via parent tab
        if event.button() == Qt.MouseButton.LeftButton:
            parent_tab = self._find_parent_tab()
            if parent_tab:
                parent_tab._on_tool_clicked(self.tool)
        super().mousePressEvent(event)

    def _find_parent_tab(self) -> ToolsTab | None:
        widget = self.parent()
        while widget is not None:
            if isinstance(widget, ToolsTab):
                return widget
            widget = widget.parent()
        return None


class ToolsTab(QWidget):
    """Grid of tool cards with an output panel."""

    def __init__(self, controller: ToolsController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # ── Header ────────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel(t("tools.title"))
        title.setObjectName("label_heading")
        title.setFont(QFont(FONTS["family"].split(",")[0].strip(), 16, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        self._btn_refresh = QPushButton(t("tools.btn_refresh"))
        self._btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_refresh.clicked.connect(self._controller.discover)
        header.addWidget(self._btn_refresh)

        layout.addLayout(header)

        # ── Tool Cards Grid (scrollable) ──────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background-color: transparent;")

        self._grid_container = QWidget()
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setSpacing(12)
        scroll.setWidget(self._grid_container)
        layout.addWidget(scroll)

        # ── Separator ─────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        layout.addWidget(sep)

        # ── Output Panel ──────────────────────────────────────────
        output_header = QHBoxLayout()
        output_label = QLabel(t("tools.output_title"))
        output_label.setObjectName("label_subheading")
        output_header.addWidget(output_label)
        output_header.addStretch()

        self._btn_cancel = QPushButton(t("tools.btn_cancel"))
        self._btn_cancel.setObjectName("btn_danger")
        self._btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_cancel.setEnabled(False)
        self._btn_cancel.clicked.connect(self._controller.cancel_tool)
        output_header.addWidget(self._btn_cancel)

        layout.addLayout(output_header)

        self._output_console = QPlainTextEdit()
        self._output_console.setReadOnly(True)
        self._output_console.setMaximumBlockCount(1000)
        self._output_console.setPlaceholderText(t("tools.output_placeholder"))
        self._output_console.setMaximumHeight(200)
        layout.addWidget(self._output_console)

    def _connect_signals(self) -> None:
        self._controller.tools_discovered.connect(self._on_tools_discovered)
        self._controller.tool_output.connect(self._on_tool_output)
        self._controller.tool_error.connect(self._on_tool_error)
        self._controller.tool_finished.connect(self._on_tool_finished)

    # ── Slots ─────────────────────────────────────────────────────

    @pyqtSlot(list)
    def _on_tools_discovered(self, tools: list[ToolInfo]) -> None:
        # Clear existing cards
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Populate grid (3 columns)
        cols = 3
        for idx, tool in enumerate(tools):
            card = ToolCard(tool, self._grid_container)
            self._grid_layout.addWidget(card, idx // cols, idx % cols)

        if not tools:
            empty = QLabel(t("tools.empty"))
            empty.setStyleSheet(f"color: {COLORS['text_muted']}; padding: 40px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid_layout.addWidget(empty, 0, 0, 1, cols)

    @pyqtSlot(str, str)
    def _on_tool_output(self, name: str, line: str) -> None:
        self._output_console.appendPlainText(line)

    @pyqtSlot(str, str)
    def _on_tool_error(self, name: str, error: str) -> None:
        self._output_console.appendPlainText(t("tools.error_prefix", error=error))

    @pyqtSlot(str, int, str)
    def _on_tool_finished(self, name: str, exit_code: int, output: str) -> None:
        if exit_code == 0:
            status = t("tools.finished_ok")
        else:
            status = t("tools.finished_error", code=exit_code)
        self._output_console.appendPlainText(
            f"\n{t('tools.finished', name=name, status=status)}"
        )
        self._btn_cancel.setEnabled(False)

    def _on_tool_clicked(self, tool: ToolInfo) -> None:
        if not tool.interactive:
            self._output_console.clear()
            self._output_console.appendPlainText(t("tools.running", name=tool.name) + "\n")
            self._btn_cancel.setEnabled(True)
        self._controller.run_tool(tool)
