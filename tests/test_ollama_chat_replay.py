from __future__ import annotations

import json
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

from rich.console import Console

from tools import ollama_chat


class OllamaChatReplayTests(unittest.TestCase):
    def tearDown(self) -> None:
        ollama_chat.CONTINUE_SESSION = False
        ollama_chat.CONTEXT_FILE = ""

    def test_help_text_mentions_redraw(self) -> None:
        with patch("tools.ollama_chat.render_markdown_to_terminal") as render_markdown, \
             patch("sys.stdout", new_callable=StringIO) as stdout:
            ollama_chat._print_command_help()

        render_markdown.assert_called_once()
        output = render_markdown.call_args.args[0]
        self.assertIn("| Command | Action |", output)
        self.assertIn("/redraw", output)
        self.assertIn("Clear the screen and replay the saved conversation", output)
        self.assertEqual(stdout.getvalue(), "\n")

    def test_markdown_renderer_trims_rich_padding_lines(self) -> None:
        buffer = StringIO()
        console = Console(file=buffer, force_terminal=False, width=100)

        ollama_chat.render_markdown_to_terminal(
            "\n".join([
                "| Name | Source | Mode | Description |",
                "| --- | --- | --- | --- |",
                "| alpha | builtin | read-only | Alpha tool |",
            ]),
            console=console,
        )

        output_lines = buffer.getvalue().splitlines()
        self.assertTrue(output_lines)
        self.assertEqual(output_lines[0].strip(), "Name   Source   Mode       Description")
        self.assertEqual(output_lines[-1].strip(), "alpha  builtin  read-only  Alpha tool")
        self.assertTrue(all(line.strip() for line in output_lines))

    def test_turn_separator_uses_horizontal_rule_renderer(self) -> None:
        with patch("tools.ollama_chat.render_horizontal_rule") as render_rule:
            ollama_chat._print_turn_separator()

        render_rule.assert_called_once_with()

    def test_horizontal_rule_uses_configured_character(self) -> None:
        buffer = StringIO()
        console = Console(file=buffer, force_terminal=False, width=20)

        ollama_chat.render_horizontal_rule(console=console)

        output = buffer.getvalue().strip()
        self.assertTrue(output)
        self.assertEqual(set(output), {ollama_chat.TURN_SEPARATOR_CHAR})

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
        self.assertIn(">>> list files", output)
        self.assertIn("I will inspect the folder.", output)
        self.assertIn("[tool] list_directory({\"path\": \".\"})", output)
        self.assertIn("I found README.md.", output)
        self.assertIn(ollama_chat.TURN_SEPARATOR_CHAR * 10, output)
        self.assertNotIn("============================================================", output)
        self.assertNotIn('{"entries": ["README.md"]}', output)
        self.assertTrue(ollama_chat.CONTINUE_SESSION)


if __name__ == "__main__":
    unittest.main()