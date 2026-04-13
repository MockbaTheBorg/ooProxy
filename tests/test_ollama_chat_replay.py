from __future__ import annotations

import json
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

from tools import ollama_chat


class OllamaChatReplayTests(unittest.TestCase):
    def tearDown(self) -> None:
        ollama_chat.CONTINUE_SESSION = False
        ollama_chat.CONTEXT_FILE = ""

    def test_help_text_mentions_redraw(self) -> None:
        with patch("sys.stdout", new_callable=StringIO) as stdout:
            ollama_chat._print_command_help()

        output = stdout.getvalue()
        self.assertIn("/redraw", output)
        self.assertIn("Clear the screen and replay the saved conversation", output)

    def test_load_context_replays_visible_conversation_and_hides_tool_results(self) -> None:
        messages = [
            {"role": "user", "content": "list files"},
            {
                "role": "assistant",
                "content": "I will inspect the folder.",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "list_directory",
                            "arguments": json.dumps({"path": "."}),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_name": "list_directory",
                "tool_call_id": "call_1",
                "content": '{"entries": ["README.md"]}',
            },
            {"role": "assistant", "content": "I found README.md."},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            context_file = f"{tmpdir}/context.json"
            with open(context_file, "w", encoding="utf-8") as handle:
                json.dump(messages, handle)

            ollama_chat.CONTEXT_FILE = context_file
            ollama_chat.CONTINUE_SESSION = False

            with patch("sys.stdout", new_callable=StringIO) as stdout:
                loaded = ollama_chat.load_context()

        output = stdout.getvalue()
        self.assertEqual(loaded, messages)
        self.assertIn("📂 Loaded 3 previous messages.", output)
        self.assertIn(">>>:\nlist files", output)
        self.assertIn("<<<:\nI will inspect the folder.", output)
        self.assertIn("[tool] list_directory({\"path\": \".\"})", output)
        self.assertIn("<<<:\nI found README.md.", output)
        self.assertNotIn('{"entries": ["README.md"]}', output)
        self.assertTrue(ollama_chat.CONTINUE_SESSION)


if __name__ == "__main__":
    unittest.main()