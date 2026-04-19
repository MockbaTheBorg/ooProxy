"""Main window — QMainWindow with tabs, status bar, and system tray."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QCloseEvent, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QStatusBar,
    QSystemTrayIcon,
    QMenu,
    QLabel,
    QWidget,
)

from gui.controllers.proxy_controller import ProxyController
from gui.controllers.settings_controller import SettingsController
from gui.controllers.tools_controller import ToolsController
from gui.i18n import t
from gui.models.proxy_state import ProxyStatus, STATUS_LABELS
from gui.resources import ICON_PATH
from gui.tabs.proxy_tab import ProxyTab
from gui.tabs.settings_tab import SettingsTab
from gui.tabs.tools_tab import ToolsTab
from gui.tabs.help_tab import HelpTab
from gui.theme import COLORS, FONTS, build_stylesheet


class MainWindow(QMainWindow):
    """Root window of the ooProxy GUI application."""

    WINDOW_TITLE = "ooProxy Manager"
    WINDOW_MIN_WIDTH = 900
    WINDOW_MIN_HEIGHT = 650

    def __init__(self) -> None:
        super().__init__()
        self._tray_icon: QSystemTrayIcon | None = None
        self._force_quit = False

        # ── Controllers ───────────────────────────────────────────
        self._proxy_ctrl = ProxyController(self)
        self._settings_ctrl = SettingsController(self)
        self._tools_ctrl = ToolsController(self)

        self._setup_window()
        self._setup_tabs()
        self._setup_status_bar()
        self._setup_tray_icon()
        self._connect_cross_tab_signals()
        self._initialize()

    # ── Setup ─────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setMinimumSize(self.WINDOW_MIN_WIDTH, self.WINDOW_MIN_HEIGHT)
        self.resize(1024, 720)

        # Set application icon
        self._app_icon = QIcon(str(ICON_PATH)) if ICON_PATH.exists() else QIcon()
        self.setWindowIcon(self._app_icon)

        # Apply global stylesheet
        app = QApplication.instance()
        if app:
            app.setStyleSheet(build_stylesheet())
            app.setWindowIcon(self._app_icon)

    def _setup_tabs(self) -> None:
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        # Create tab instances
        self._proxy_tab = ProxyTab(self._proxy_ctrl)
        self._settings_tab = SettingsTab(self._settings_ctrl)
        self._tools_tab = ToolsTab(self._tools_ctrl)
        self._help_tab = HelpTab()

        # Add tabs with translated labels
        self._tabs.addTab(self._proxy_tab, t("tabs.proxy"))
        self._tabs.addTab(self._settings_tab, t("tabs.settings"))
        self._tabs.addTab(self._tools_tab, t("tabs.tools"))
        self._tabs.addTab(self._help_tab, t("tabs.help"))

        self.setCentralWidget(self._tabs)

    def _setup_status_bar(self) -> None:
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._status_label = QLabel(t("statusbar.initializing"))
        self._status_label.setStyleSheet(f"color: {COLORS['text_muted']}; padding: 0 8px;")
        self._status_bar.addWidget(self._status_label)

        self._status_bar.addPermanentWidget(
            QLabel(t("statusbar.footer", port=11434))
        )

    def _setup_tray_icon(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self._tray_icon = QSystemTrayIcon(self)
        self._tray_icon.setIcon(self._app_icon)
        self._tray_icon.setToolTip("ooProxy Manager")

        # Context menu
        tray_menu = QMenu()

        action_show = QAction(t("tray.show_hide"), self)
        action_show.triggered.connect(self._toggle_visibility)
        tray_menu.addAction(action_show)

        tray_menu.addSeparator()

        action_stop = QAction(t("tray.stop_proxy"), self)
        action_stop.triggered.connect(self._proxy_ctrl.stop_proxy)
        tray_menu.addAction(action_stop)

        tray_menu.addSeparator()

        action_quit = QAction(t("tray.quit"), self)
        action_quit.triggered.connect(self._quit_app)
        tray_menu.addAction(action_quit)

        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _connect_cross_tab_signals(self) -> None:
        """Wire signals that span across tabs/controllers."""
        # Proxy status → status bar
        self._proxy_ctrl.status_changed.connect(self._update_status_bar)

        # Settings loaded → update proxy tab info & auto-start button
        self._settings_ctrl.settings_loaded.connect(self._on_settings_loaded)
        self._settings_ctrl.startup_status.connect(
            self._proxy_tab.set_auto_start_status
        )

    def _initialize(self) -> None:
        """Run startup logic after the window is shown."""
        # Load settings
        self._settings_ctrl.load_settings()
        # Discover tools
        self._tools_ctrl.discover()
        # Check proxy health (delayed slightly to let the UI render first)
        QTimer.singleShot(200, self._proxy_ctrl.initial_check)

    # ── Slots ─────────────────────────────────────────────────────

    def _update_status_bar(self, status: ProxyStatus) -> None:
        label = STATUS_LABELS.get(status, t("proxy.status.unknown"))
        color_map = {
            ProxyStatus.RUNNING: COLORS["success"],
            ProxyStatus.ERROR: COLORS["error"],
            ProxyStatus.STARTING: COLORS["warning"],
            ProxyStatus.STOPPING: COLORS["warning"],
        }
        color = color_map.get(status, COLORS["text_muted"])
        self._status_label.setText(t("statusbar.proxy_status", status=label))
        self._status_label.setStyleSheet(f"color: {color}; padding: 0 8px;")

        # Update tray tooltip
        if self._tray_icon:
            self._tray_icon.setToolTip(f"ooProxy — {label}")

    def _on_settings_loaded(self, settings) -> None:
        """Push loaded settings to the proxy tab."""
        self._proxy_tab.update_backend_info(settings.backend_url, settings.local_port)

    def _toggle_visibility(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle_visibility()

    def _quit_app(self) -> None:
        """Fully quit the application (stop proxy, clean up, exit)."""
        self._force_quit = True
        self._proxy_ctrl.shutdown()
        if self._tray_icon:
            self._tray_icon.hide()
        QApplication.instance().quit()

    # ── Overrides ─────────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Minimize to tray on close (unless force quit)."""
        if self._force_quit or self._tray_icon is None:
            self._proxy_ctrl.shutdown()
            event.accept()
        else:
            event.ignore()
            self.hide()
            if self._tray_icon:
                self._tray_icon.showMessage(
                    t("tray.minimized_title"),
                    t("tray.minimized_msg"),
                    QSystemTrayIcon.MessageIcon.Information,
                    2000,
                )
