from __future__ import annotations

import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from modules._server.config import ProxyConfig
from modules._server.key_store import ApiKeyStore, decrypt_key, encrypt_key, normalize_endpoint
from tools import ollama_keys


class ApiKeyStoreTests(unittest.TestCase):
    def test_encrypt_round_trip_uses_endpoint_as_seed(self) -> None:
        endpoint = "api.example.com:8443"
        token = encrypt_key(endpoint, "sk-secret")

        self.assertNotEqual(token, "sk-secret")
        self.assertEqual(decrypt_key(endpoint, token), "sk-secret")
        with self.assertRaises(Exception):
            decrypt_key("other.example.com", token)

    def test_store_persists_obfuscated_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "keys.json"
            store = ApiKeyStore(path)

            endpoint = store.set("https://API.EXAMPLE.com:8443/v1", "sk-secret")
            raw = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(endpoint, "api.example.com:8443")
            self.assertEqual(list(raw), ["api.example.com:8443"])
            self.assertNotEqual(raw[endpoint], "sk-secret")
            self.assertEqual(ApiKeyStore(path).get("api.example.com:8443"), "sk-secret")

    def test_proxy_config_uses_store_when_no_key_was_passed(self) -> None:
        store = ApiKeyStore(Path(tempfile.gettempdir()) / "unused-keys.json")
        store.set("api.example.com", "sk-stored")
        args = SimpleNamespace(url="https://api.example.com/v1", key=None, port=11434)

        with patch("modules._server.config.ApiKeyStore", return_value=store):
            config = ProxyConfig.from_args(args)

        self.assertEqual(config.key, "sk-stored")

    def test_explicit_and_env_keys_keep_precedence(self) -> None:
        store = ApiKeyStore(Path(tempfile.gettempdir()) / "unused-keys.json")
        store.set("api.example.com", "sk-stored")

        with patch("modules._server.config.ApiKeyStore", return_value=store), \
             patch.dict("os.environ", {"OPENAI_API_KEY": "sk-env"}, clear=False):
            env_config = ProxyConfig.from_args(SimpleNamespace(url="https://api.example.com/v1", key=None, port=11434))

        with patch("modules._server.config.ApiKeyStore", return_value=store):
            explicit_config = ProxyConfig.from_args(SimpleNamespace(url="https://api.example.com/v1", key="sk-arg", port=11434))

        self.assertEqual(env_config.key, "sk-env")
        self.assertEqual(explicit_config.key, "sk-arg")


class OllamaKeysToolTests(unittest.TestCase):
    def test_tool_can_store_read_list_and_delete_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = ApiKeyStore(Path(tmp_dir) / "keys.json")

            with patch("tools.ollama_keys.ApiKeyStore", return_value=store), \
                 patch("sys.stdout", new_callable=StringIO) as stdout, \
                 patch("sys.stderr", new_callable=StringIO) as stderr:
                self.assertEqual(ollama_keys.main(["--host", "api.example.com", "--key", "sk-live"]), 0)
                self.assertIn("stored key for api.example.com", stdout.getvalue())

                stdout.truncate(0)
                stdout.seek(0)
                self.assertEqual(ollama_keys.main(["--host", "https://api.example.com/v1"]), 0)
                self.assertEqual(stdout.getvalue().strip(), "sk-live")

                stdout.truncate(0)
                stdout.seek(0)
                self.assertEqual(ollama_keys.main([]), 0)
                self.assertEqual(stdout.getvalue().strip(), "api.example.com")

                stdout.truncate(0)
                stdout.seek(0)
                self.assertEqual(ollama_keys.main(["--host", "api.example.com", "--delete"]), 0)
                self.assertIn("deleted key for api.example.com", stdout.getvalue())
                self.assertEqual(store.hosts(), [])
                self.assertEqual(stderr.getvalue(), "")

    def test_tool_returns_error_for_missing_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = ApiKeyStore(Path(tmp_dir) / "keys.json")

            with patch("tools.ollama_keys.ApiKeyStore", return_value=store), \
                 patch("sys.stderr", new_callable=StringIO) as stderr:
                self.assertEqual(ollama_keys.main(["--host", "missing.example.com"]), 1)

            self.assertIn("no stored key for missing.example.com", stderr.getvalue())


class NormalizeEndpointTests(unittest.TestCase):
    def test_normalize_endpoint_accepts_host_or_url(self) -> None:
        self.assertEqual(normalize_endpoint("api.example.com"), "api.example.com")
        self.assertEqual(normalize_endpoint("API.EXAMPLE.com:8443"), "api.example.com:8443")
        self.assertEqual(normalize_endpoint("https://API.EXAMPLE.com:8443/v1"), "api.example.com:8443")