"""Settings controller — reads/writes app configuration and API keys.

Uses PowerShell (DPAPI) for key operations as decided in the spec.
"""

from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from gui.i18n import t
from gui.models.app_settings import AppSettings, KeyEntry, KNOWN_BACKENDS
from gui.resources import OOPROXY_DIR, OOPROXY_KEYS_FILE
from gui.workers.powershell_runner import PowerShellRunner


class SettingsController(QObject):
    """Manages app settings and DPAPI key operations."""

    settings_loaded = pyqtSignal(object)  # AppSettings
    key_saved = pyqtSignal(bool, str)  # ok, message
    key_deleted = pyqtSignal(bool, str)  # ok, message
    startup_status = pyqtSignal(bool)  # is_installed
    message = pyqtSignal(str)  # General feedback

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = AppSettings()
        self._ps_runner = PowerShellRunner(self)

    @property
    def settings(self) -> AppSettings:
        return self._settings

    # ── Load / Save ───────────────────────────────────────────────────

    def load_settings(self) -> None:
        """Load settings from the DPAPI keys file."""
        if not OOPROXY_KEYS_FILE.exists():
            self._settings = AppSettings()
            self._try_migrate_legacy_keys()
            self.settings_loaded.emit(self._settings)

            # Check if scheduled task exists
            self._check_startup_status()
            return

        try:
            raw = json.loads(OOPROXY_KEYS_FILE.read_text(encoding="utf-8"))
            url = raw.get("url", self._settings.backend_url)
            lang = raw.get("language", "auto")
            entries = raw.get("entries", {})

            keys = []
            for endpoint, encrypted in entries.items():
                keys.append(KeyEntry(endpoint=endpoint, key_encrypted=encrypted))

            self._settings.backend_url = url
            self._settings.language = lang
            self._settings.keys = keys
        except Exception as exc:
            self.message.emit(t("settings.load_error", error=str(exc)))

        # Check if scheduled task exists
        self._check_startup_status()
        self.settings_loaded.emit(self._settings)

    def save_backend_url(self, url: str) -> None:
        """Update the backend URL in settings."""
        self._settings.backend_url = url.rstrip("/")
        self._persist_keys()
        self.message.emit(t("settings.url_updated", url=url))

    def save_port(self, port: int) -> None:
        """Update the local port."""
        self._settings.local_port = port
        self.message.emit(t("settings.port_updated", port=port))

    def save_language(self, lang: str) -> None:
        """Update the UI language."""
        self._settings.language = lang
        self._persist_keys()
        self.message.emit(t("settings.restart_required"))

    # ── Key Management (DPAPI via PowerShell) ─────────────────────────

    def add_key(self, endpoint: str, plain_key: str) -> None:
        """Encrypt a key using DPAPI and save it."""
        if not endpoint or not plain_key:
            self.key_saved.emit(False, t("settings.key_required"))
            return

        # Escape single quotes for PowerShell
        escaped = plain_key.replace("'", "''")

        ps_cmd = (
            f"$s = ConvertTo-SecureString '{escaped}' -AsPlainText -Force;"
            f"ConvertFrom-SecureString $s"
        )

        runner = PowerShellRunner(self)
        runner.finished.connect(
            lambda ok, out, err: self._on_key_encrypted(ok, out, err, endpoint)
        )
        runner.run_command(ps_cmd)

    def delete_key(self, endpoint: str) -> None:
        """Remove a key entry for the given endpoint."""
        before = len(self._settings.keys)
        self._settings.keys = [k for k in self._settings.keys if k.endpoint != endpoint]
        if len(self._settings.keys) < before:
            self._persist_keys()
            self.key_deleted.emit(True, t("settings.key_deleted", endpoint=endpoint))
        else:
            self.key_deleted.emit(False, t("settings.key_not_found", endpoint=endpoint))

    def get_endpoints(self) -> list[str]:
        """Return list of configured endpoints."""
        return [k.endpoint for k in self._settings.keys]

    # ── Scheduled Task ────────────────────────────────────────────────

    def _check_startup_status(self) -> None:
        """Check if the ooProxy-AutoStart scheduled task exists."""
        runner = PowerShellRunner(self)
        runner.finished.connect(self._on_startup_checked)
        runner.run_command(
            "Get-ScheduledTask -TaskName 'ooProxy-AutoStart' -ErrorAction SilentlyContinue | "
            "Select-Object -ExpandProperty State"
        )

    def _on_startup_checked(self, ok: bool, stdout: str, stderr: str) -> None:
        is_installed = ok and stdout.strip().lower() in ("ready", "running")
        self._settings.auto_start_enabled = is_installed
        self.startup_status.emit(is_installed)

    # ── Private helpers ───────────────────────────────────────────────

    def _on_key_encrypted(self, ok: bool, stdout: str, stderr: str, endpoint: str) -> None:
        if not ok or not stdout.strip():
            self.key_saved.emit(False, t("settings.key_encrypt_error", error=stderr))
            return

        encrypted = stdout.strip()

        # Update or add entry
        found = False
        for key_entry in self._settings.keys:
            if key_entry.endpoint == endpoint:
                key_entry.key_encrypted = encrypted
                found = True
                break
        if not found:
            self._settings.keys.append(KeyEntry(endpoint=endpoint, key_encrypted=encrypted))

        self._persist_keys()
        self.key_saved.emit(True, t("settings.key_saved", endpoint=endpoint))

    def _persist_keys(self) -> None:
        """Write the current keys to the DPAPI keys file."""
        OOPROXY_DIR.mkdir(parents=True, exist_ok=True)

        entries = {}
        for k in self._settings.keys:
            entries[k.endpoint] = k.key_encrypted

        data = {
            "version": "v2-dpapi",
            "url": self._settings.backend_url,
            "language": self._settings.language,
            "entries": entries,
        }

        OOPROXY_KEYS_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _try_migrate_legacy_keys(self) -> None:
        """Attempt to read legacy keys.json and import them via DPAPI."""
        try:
            from modules._server.key_store import KeyStore
            ks = KeyStore()
            legacy_keys = ks.list_keys()
            if not legacy_keys:
                return

            self.message.emit(t("settings.migrating_keys"))
            for endpoint in legacy_keys:
                plain_key = ks.get_key(endpoint)
                if plain_key:
                    self.add_key(endpoint, plain_key)
        except Exception as e:
            self.message.emit(t("settings.migrate_error", error=str(e)))
