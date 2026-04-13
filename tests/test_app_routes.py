from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from modules._server.app import create_app
from modules._server.config import ProxyConfig


class AppRouteCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(ProxyConfig(url="https://example.invalid/v1", key="", port=11434))
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)

    def test_api_status_reports_ready_when_client_is_initialized(self) -> None:
        response = self.client.get("/api/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready"})

    def test_api_status_reports_not_ready_when_client_is_missing(self) -> None:
        original_client = self.app.state.client
        self.app.state.client = None
        try:
            response = self.client.get("/api/status")
        finally:
            self.app.state.client = original_client

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"status": "not ready", "reason": "client not initialized"},
        )


if __name__ == "__main__":
    unittest.main()