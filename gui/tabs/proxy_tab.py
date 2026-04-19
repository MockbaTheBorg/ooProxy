"""Proxy tab — start/stop controls, status LED, and live log console."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QColor, QPainter, QFont
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QGroupBox,
    QFrame,
    QSizePolicy,
    QFileDialog,
)

from gui.controllers.proxy_controller import ProxyController
from gui.i18n import t
from gui.models.proxy_state import ProxyStatus, STATUS_LABELS
from gui.theme import COLORS, FONTS


class StatusLED(QWidget):
    """Circular LED indicator that changes color based on proxy status."""

    _COLOR_MAP = {
        ProxyStatus.UNKNOWN: COLORS["led_stopped"],
        ProxyStatus.CHECKING: COLORS["led_starting"],
        ProxyStatus.STOPPED: COLORS["led_stopped"],
        ProxyStatus.STARTING: COLORS["led_starting"],
        ProxyStatus.RUNNING: COLORS["led_running"],
        ProxyStatus.STOPPING: COLORS["led_starting"],
        ProxyStatus.ERROR: COLORS["led_error"],
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status = ProxyStatus.UNKNOWN
        self.setFixedSize(18, 18)
        self.setToolTip(STATUS_LABELS[self._status])

    def set_status(self, status: ProxyStatus) -> None:
        self._status = status
        self.setToolTip(STATUS_LABELS[status])
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self._COLOR_MAP.get(self._status, COLORS["led_stopped"]))

        # Outer glow
        glow = QColor(color)
        glow.setAlpha(60)
        painter.setBrush(glow)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(1, 1, 16, 16)

        # Inner circle
        painter.setBrush(color)
        painter.drawEllipse(4, 4, 10, 10)
        painter.end()


class ProxyTab(QWidget):
    """Main proxy management tab with controls and log output."""

    def __init__(self, controller: ProxyController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # ── Status Section ────────────────────────────────────────
        status_group = QGroupBox(t("proxy.status_group"))
        status_layout = QHBoxLayout(status_group)
        status_layout.setSpacing(16)

        # LED + Status label
        self._led = StatusLED()
        status_layout.addWidget(self._led)

        self._status_label = QLabel(t("proxy.checking"))
        self._status_label.setObjectName("label_heading")
        self._status_label.setFont(QFont(FONTS["family"].split(",")[0].strip(), 16, QFont.Weight.Bold))
        status_layout.addWidget(self._status_label)

        status_layout.addStretch()

        # Backend info
        info_frame = QVBoxLayout()
        self._backend_label = QLabel(t("proxy.backend_empty"))
        self._backend_label.setObjectName("label_muted")
        info_frame.addWidget(self._backend_label)

        self._port_label = QLabel(t("proxy.local", port=11434))
        self._port_label.setObjectName("label_muted")
        info_frame.addWidget(self._port_label)

        status_layout.addLayout(info_frame)
        layout.addWidget(status_group)

        # ── Controls Section ──────────────────────────────────────
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(12)

        self._btn_start = QPushButton(t("proxy.btn_start"))
        self._btn_start.setObjectName("btn_primary")
        self._btn_start.setMinimumHeight(40)
        self._btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        controls_layout.addWidget(self._btn_start)

        self._btn_stop = QPushButton(t("proxy.btn_stop"))
        self._btn_stop.setObjectName("btn_danger")
        self._btn_stop.setMinimumHeight(40)
        self._btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_stop.setEnabled(False)
        controls_layout.addWidget(self._btn_stop)

        controls_layout.addStretch()

        self._btn_install = QPushButton(t("proxy.btn_autostart"))
        self._btn_install.setToolTip(t("proxy.btn_autostart"))
        self._btn_install.setMinimumHeight(40)
        self._btn_install.setCursor(Qt.CursorShape.PointingHandCursor)
        controls_layout.addWidget(self._btn_install)

        layout.addLayout(controls_layout)

        # ── Separator ─────────────────────────────────────────────
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"color: {COLORS['border']};")
        layout.addWidget(separator)

        # ── Log Console ───────────────────────────────────────────
        log_header = QHBoxLayout()

        log_label = QLabel(t("proxy.log_console"))
        log_label.setObjectName("label_subheading")
        log_header.addWidget(log_label)

        log_header.addStretch()

        self._btn_export = QPushButton(t("proxy.btn_export"))
        self._btn_export.setToolTip(t("proxy.btn_export_tooltip"))
        self._btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_export.setFixedHeight(28)
        self._btn_export.clicked.connect(self._on_export_clicked)
        log_header.addWidget(self._btn_export)

        self._btn_clear = QPushButton(t("proxy.btn_clear"))
        self._btn_clear.setToolTip(t("proxy.btn_clear_tooltip"))
        self._btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_clear.setFixedHeight(28)
        self._btn_clear.clicked.connect(lambda: self._log_console.clear())
        log_header.addWidget(self._btn_clear)

        layout.addLayout(log_header)

        self._log_console = QPlainTextEdit()
        self._log_console.setReadOnly(True)
        self._log_console.setMaximumBlockCount(2000)
        self._log_console.setPlaceholderText(t("proxy.log_placeholder"))
        self._log_console.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._log_console)

    def _connect_signals(self) -> None:
        # Controller → View
        self._controller.status_changed.connect(self._on_status_changed)
        self._controller.log_received.connect(self._on_log_received)

        # View → Controller
        self._btn_start.clicked.connect(self._on_start_clicked)
        self._btn_stop.clicked.connect(self._on_stop_clicked)
        self._btn_install.clicked.connect(self._on_install_clicked)

    # ── Slots ─────────────────────────────────────────────────────

    @pyqtSlot(object)
    def _on_status_changed(self, status: ProxyStatus) -> None:
        self._led.set_status(status)
        self._status_label.setText(STATUS_LABELS.get(status, t("proxy.status.unknown")))

        is_running = status == ProxyStatus.RUNNING
        is_stopped = status in (ProxyStatus.STOPPED, ProxyStatus.ERROR, ProxyStatus.UNKNOWN)
        is_transitioning = status in (ProxyStatus.STARTING, ProxyStatus.STOPPING, ProxyStatus.CHECKING)

        self._btn_start.setEnabled(is_stopped)
        self._btn_stop.setEnabled(is_running)

        if is_transitioning:
            self._btn_start.setEnabled(False)
            self._btn_stop.setEnabled(False)

        # Color the status label
        color_map = {
            ProxyStatus.RUNNING: COLORS["success"],
            ProxyStatus.ERROR: COLORS["error"],
            ProxyStatus.STARTING: COLORS["warning"],
            ProxyStatus.STOPPING: COLORS["warning"],
        }
        color = color_map.get(status, COLORS["text_primary"])
        self._status_label.setStyleSheet(f"color: {color};")

    @pyqtSlot(str)
    def _on_log_received(self, text: str) -> None:
        self._log_console.appendPlainText(text)

    def _on_start_clicked(self) -> None:
        # Try DPAPI first, using the controller's backend URL from settings
        url = self._controller._url or "https://integrate.api.nvidia.com/v1"
        self._controller.start_proxy_with_dpapi(url)

    def _on_stop_clicked(self) -> None:
        self._controller.stop_proxy()

    def _on_export_clicked(self) -> None:
        """Save the current log contents to a file."""
        from datetime import datetime
        default_name = f"ooproxy_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        path, _ = QFileDialog.getSaveFileName(
            self,
            t("proxy.export_dialog_title"),
            default_name,
            "Log Files (*.log);;Text Files (*.txt);;All Files (*)",
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self._log_console.toPlainText())
                self._log_console.appendPlainText(t("proxy.export_ok", path=path))
            except OSError as e:
                self._log_console.appendPlainText(t("proxy.export_error", error=str(e)))

    def _on_install_clicked(self) -> None:
        # Toggle based on current button text
        if t("proxy.btn_autostart_remove") == self._btn_install.text():
            self._controller.uninstall_startup()
            self._btn_install.setText(t("proxy.btn_autostart"))
        else:
            self._controller.install_startup()
            self._btn_install.setText(t("proxy.btn_autostart_remove"))

    # ── Public API for MainWindow ─────────────────────────────────

    def update_backend_info(self, url: str, port: int) -> None:
        """Update the displayed backend URL and port."""
        self._backend_label.setText(t("proxy.backend", url=url))
        self._port_label.setText(t("proxy.local", port=port))
        self._controller._url = url
        self._controller._port = port

    def set_auto_start_status(self, installed: bool) -> None:
        """Update the auto-start button text."""
        if installed:
            self._btn_install.setText(t("proxy.btn_autostart_remove"))
        else:
            self._btn_install.setText(t("proxy.btn_autostart"))
