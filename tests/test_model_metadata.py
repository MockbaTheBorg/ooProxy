from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from modules._server.app import create_app
from modules._server.config import ProxyConfig
from modules._server.translate.models import openai_model_to_ollama_show, openai_models_to_ollama_tags


class ModelMetadataTranslationTests(unittest.TestCase):
    def test_openai_models_to_ollama_tags_uses_provider_metadata(self) -> None:
        tags = openai_models_to_ollama_tags(
            {
                "data": [
                    {
                        "id": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                        "created": 1710000000,
                        "organization": "Meta",
                        "owned_by": "Meta",
                        "type": "chat",
                        "context_length": 131072,
                        "family": "llama",
                        "families": ["llama"],
                        "format": "openai",
                        "parameter_size": "70B",
                        "quantization_level": "fp16",
                    }
                ]
            }
        )

        model = tags["models"][0]
        self.assertEqual(model["details"]["family"], "llama")
        self.assertEqual(model["details"]["families"], ["llama"])
        self.assertEqual(model["details"]["format"], "openai")
        self.assertEqual(model["details"]["parameter_size"], "70B")
        self.assertEqual(model["details"]["quantization_level"], "fp16")

    def test_openai_model_to_ollama_show_uses_context_length_and_capabilities(self) -> None:
        payload = openai_model_to_ollama_show(
            "togethercomputer/m2-bert-80M-8k-retrieval",
            entry={
                "type": "embedding",
                "context_length": 8192,
                "family": "bert",
                "families": ["bert"],
                "format": "openai",
            },
        )

        self.assertEqual(payload["details"]["family"], "bert")
        self.assertEqual(payload["model_info"]["bert.context_length"], 8192)
        self.assertEqual(payload["capabilities"], ["embedding"])


class _MetadataClient:
    async def get_models(self) -> dict:
        return {
            "data": [
                {
                    "id": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                    "type": "chat",
                    "context_length": 131072,
                    "family": "llama",
                    "families": ["llama"],
                    "format": "openai",
                    "parameter_size": "70B",
                }
            ]
        }

    async def chat(self, body: dict) -> dict:
        return {"choices": []}

    async def open_stream_chat(self, body: dict):
        raise NotImplementedError

    async def embeddings(self, body: dict) -> dict:
        return {"data": []}

    async def aclose(self) -> None:
        return None


class ModelMetadataRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(ProxyConfig(url="https://example.invalid/v1", key="", port=11434))
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.app.state.client = _MetadataClient()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)

    def test_api_show_uses_remote_model_metadata(self) -> None:
        response = self.client.post(
            "/api/show",
            json={"model": "meta-llama/Llama-3.3-70B-Instruct-Turbo"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["details"]["family"], "llama")
        self.assertEqual(payload["details"]["parameter_size"], "70B")
        self.assertEqual(payload["model_info"]["llama.context_length"], 131072)


if __name__ == "__main__":
    unittest.main()