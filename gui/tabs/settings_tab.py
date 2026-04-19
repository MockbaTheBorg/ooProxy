"""Settings tab — backend URL, local port, and API key management."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QSpinBox,
    QComboBox,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QFrame,
    QSizePolicy,
)

from gui.controllers.settings_controller import SettingsController
from gui.i18n import t
from gui.models.app_settings import KNOWN_BACKENDS
from gui.theme import COLORS, FONTS


class SettingsTab(QWidget):
    """Configuration panel for backend URL, port, and API keys."""

    def __init__(self, controller: SettingsController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # ── Backend Configuration ─────────────────────────────────
        backend_group = QGroupBox(t("settings.backend_group"))
        bg_layout = QVBoxLayout(backend_group)
        bg_layout.setSpacing(12)

        # Language selector
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel(t("settings.language")))
        self._lang_combo = QComboBox()
        self._lang_combo.addItem(t("settings.lang_auto"), "auto")
        self._lang_combo.addItem(t("settings.lang_en"), "en_US")
        self._lang_combo.addItem(t("settings.lang_pt"), "pt_BR")
        lang_row.addWidget(self._lang_combo, 1)
        bg_layout.addLayout(lang_row)

        # Preset selector
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel(t("settings.preset")))
        self._preset_combo = QComboBox()
        self._preset_combo.addItem(t("settings.preset_custom"))
        for b in KNOWN_BACKENDS:
            self._preset_combo.addItem(f"{b['name']}", b["url"])
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_row.addWidget(self._preset_combo, 1)
        bg_layout.addLayout(preset_row)

        # URL input
        url_row = QHBoxLayout()
        url_row.addWidget(QLabel(t("settings.url_label")))
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText(t("settings.url_placeholder"))
        url_row.addWidget(self._url_input, 1)
        bg_layout.addLayout(url_row)

        # Port input
        port_row = QHBoxLayout()
        port_row.addWidget(QLabel(t("settings.port_label")))
        self._port_input = QSpinBox()
        self._port_input.setRange(1024, 65535)
        self._port_input.setValue(11434)
        port_row.addWidget(self._port_input)
        port_row.addStretch()

        self._btn_save_config = QPushButton(t("settings.btn_save"))
        self._btn_save_config.setObjectName("btn_primary")
        self._btn_save_config.setCursor(Qt.CursorShape.PointingHandCursor)
        port_row.addWidget(self._btn_save_config)
        bg_layout.addLayout(port_row)

        layout.addWidget(backend_group)

        # ── Separator ─────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        layout.addWidget(sep)

        # ── API Keys ──────────────────────────────────────────────
        keys_group = QGroupBox(t("settings.keys_group"))
        kg_layout = QVBoxLayout(keys_group)
        kg_layout.setSpacing(12)

        # Add key form
        form_row = QHBoxLayout()
        form_row.setSpacing(8)

        self._endpoint_input = QLineEdit()
        self._endpoint_input.setPlaceholderText(t("settings.endpoint_placeholder"))
        form_row.addWidget(self._endpoint_input, 2)

        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText(t("settings.key_placeholder"))
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_row.addWidget(self._key_input, 3)

        self._btn_add_key = QPushButton(t("settings.btn_add_key"))
        self._btn_add_key.setObjectName("btn_primary")
        self._btn_add_key.setCursor(Qt.CursorShape.PointingHandCursor)
        form_row.addWidget(self._btn_add_key)

        kg_layout.addLayout(form_row)

        # Keys table
        self._keys_table = QTableWidget()
        self._keys_table.setColumnCount(3)
        self._keys_table.setHorizontalHeaderLabels([
            t("settings.table_endpoint"),
            t("settings.table_status"),
            t("settings.table_actions"),
        ])
        self._keys_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._keys_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._keys_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._keys_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._keys_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._keys_table.verticalHeader().setVisible(False)
        kg_layout.addWidget(self._keys_table)

        layout.addWidget(keys_group)

        # ── Feedback Label ────────────────────────────────────────
        self._feedback_label = QLabel("")
        self._feedback_label.setObjectName("label_muted")
        self._feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._feedback_label)

        layout.addStretch()

    def _connect_signals(self) -> None:
        # Controller → View
        self._controller.settings_loaded.connect(self._on_settings_loaded)
        self._controller.key_saved.connect(self._on_key_result)
        self._controller.key_deleted.connect(self._on_key_result)
        self._controller.message.connect(self._show_feedback)
        self._controller.startup_status.connect(self._on_startup_status)

        # View → Controller
        self._btn_save_config.clicked.connect(self._on_save_config)
        self._btn_add_key.clicked.connect(self._on_add_key)

    # ── Slots ─────────────────────────────────────────────────────

    @pyqtSlot(object)
    def _on_settings_loaded(self, settings) -> None:
        self._url_input.setText(settings.backend_url)
        self._port_input.setValue(settings.local_port)
        lang_index = self._lang_combo.findData(settings.language)
        if lang_index >= 0:
            self._lang_combo.setCurrentIndex(lang_index)
        self._refresh_keys_table()

    @pyqtSlot(bool, str)
    def _on_key_result(self, ok: bool, msg: str) -> None:
        color = COLORS["success"] if ok else COLORS["error"]
        self._feedback_label.setStyleSheet(f"color: {color};")
        self._feedback_label.setText(msg)
        if ok:
            self._endpoint_input.clear()
            self._key_input.clear()
            self._refresh_keys_table()

    @pyqtSlot(bool)
    def _on_startup_status(self, installed: bool) -> None:
        # Forward to proxy tab via main window
        pass

    def _on_preset_changed(self, index: int) -> None:
        if index > 0:
            url = self._preset_combo.itemData(index)
            if url:
                self._url_input.setText(url)

    def _on_save_config(self) -> None:
        url = self._url_input.text().strip()
        port = self._port_input.value()
        lang = self._lang_combo.currentData()
        if url:
            self._controller.save_backend_url(url)
        self._controller.save_port(port)
        self._controller.save_language(lang)
        self._show_feedback(t("settings.config_saved"))

    def _on_add_key(self) -> None:
        endpoint = self._endpoint_input.text().strip()
        key = self._key_input.text().strip()
        self._controller.add_key(endpoint, key)

    def _refresh_keys_table(self) -> None:
        keys = self._controller.settings.keys
        self._keys_table.setRowCount(len(keys))
        for row, entry in enumerate(keys):
            # Endpoint
            self._keys_table.setItem(row, 0, QTableWidgetItem(entry.endpoint))
            # Status
            status_item = QTableWidgetItem(t("settings.key_status_dpapi"))
            status_item.setForeground(Qt.GlobalColor.green)
            self._keys_table.setItem(row, 1, status_item)
            # Delete button
            btn_del = QPushButton(t("settings.btn_delete_key"))
            btn_del.setObjectName("btn_danger")
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.setFixedHeight(28)
            endpoint = entry.endpoint  # Capture for lambda
            btn_del.clicked.connect(lambda checked, ep=endpoint: self._confirm_delete(ep))
            self._keys_table.setCellWidget(row, 2, btn_del)

    def _confirm_delete(self, endpoint: str) -> None:
        reply = QMessageBox.question(
            self,
            t("settings.confirm_delete_title"),
            t("settings.confirm_delete_msg", endpoint=endpoint),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._controller.delete_key(endpoint)

    def _show_feedback(self, text: str) -> None:
        self._feedback_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        self._feedback_label.setText(text)

    # ── Public ────────────────────────────────────────────────────

    def get_current_url(self) -> str:
        return self._url_input.text().strip()

    def get_current_port(self) -> int:
        return self._port_input.value()
