from __future__ import annotations

import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tools import ollama_chat


def _tool_entry(name: str, *, command: str, description: str = "test tool") -> dict:
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "command": command,
    }


class OllamaChatToolLoadingTests(unittest.TestCase):
    def tearDown(self) -> None:
        ollama_chat.TOOL_REGISTRY = ollama_chat._build_tool_registry()
        ollama_chat.TOOL_SCHEMAS = ollama_chat._build_tool_schemas()
        ollama_chat.EXTERNAL_TOOL_FILES = []
        ollama_chat.TOOL_LOAD_EVENTS = []
        ollama_chat.TOOL_LOAD_SUMMARY_SHOWN = False

    def test_discovers_global_then_local_then_explicit_tool_files(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as cwd_dir, tempfile.TemporaryDirectory() as extra_dir:
            global_tools = Path(home_dir) / ".ooProxy" / "tools"
            local_tools = Path(cwd_dir) / ".ooProxy" / "tools"
            global_tools.mkdir(parents=True)
            local_tools.mkdir(parents=True)

            global_file = global_tools / "a.json"
            local_file = local_tools / "b.json"
            explicit_file = Path(extra_dir) / "c.json"

            global_file.write_text(json.dumps([_tool_entry("global_tool", command="printf global")]), encoding="utf-8")
            local_file.write_text(json.dumps([_tool_entry("local_tool", command="printf local")]), encoding="utf-8")
            explicit_file.write_text(json.dumps([_tool_entry("explicit_tool", command="printf explicit")]), encoding="utf-8")

            with patch("tools.ollama_chat.Path.home", return_value=Path(home_dir)), \
                 patch("tools.ollama_chat.os.getcwd", return_value=cwd_dir):
                discovered = ollama_chat.discover_tool_definition_files([str(explicit_file)])

            self.assertEqual(
                discovered,
                [str(global_file.resolve()), str(local_file.resolve()), str(explicit_file.resolve())],
            )

    def test_local_tool_overrides_global_and_builtin_tools(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as cwd_dir:
            global_tools = Path(home_dir) / ".ooProxy" / "tools"
            local_tools = Path(cwd_dir) / ".ooProxy" / "tools"
            global_tools.mkdir(parents=True)
            local_tools.mkdir(parents=True)

            (global_tools / "global.json").write_text(
                json.dumps([
                    _tool_entry("list_directory", command="printf global-list", description="global override"),
                    _tool_entry("shared_tool", command="printf global-shared", description="global shared"),
                ]),
                encoding="utf-8",
            )
            (local_tools / "local.json").write_text(
                json.dumps([
                    _tool_entry("shared_tool", command="printf local-shared", description="local shared"),
                ]),
                encoding="utf-8",
            )

            with patch("tools.ollama_chat.Path.home", return_value=Path(home_dir)), \
                 patch("tools.ollama_chat.os.getcwd", return_value=cwd_dir):
                ollama_chat.configure_tool_registry([])

            self.assertEqual(
                ollama_chat.TOOL_REGISTRY["list_directory"]["description"],
                "global override",
            )
            self.assertEqual(
                ollama_chat.TOOL_REGISTRY["shared_tool"]["description"],
                "local shared",
            )
            self.assertEqual(
                ollama_chat.EXTERNAL_TOOL_FILES,
                [
                    str((global_tools / "global.json").resolve()),
                    str((local_tools / "local.json").resolve()),
                ],
            )

    def test_tool_load_summary_reports_overrides_once(self) -> None:
        ollama_chat.TOOL_LOAD_EVENTS = [
            {
                "name": "shared_tool",
                "source": "/tmp/local.json",
                "status": "override",
                "previous_source": "builtin",
            },
            {
                "name": "new_tool",
                "source": "/tmp/global.json",
                "status": "add",
                "previous_source": "",
            },
        ]
        ollama_chat.TOOL_LOAD_SUMMARY_SHOWN = False

        with patch("sys.stdout", new_callable=StringIO) as stdout:
            ollama_chat._print_tool_load_summary()
            ollama_chat._print_tool_load_summary()

        output = stdout.getvalue()
        self.assertEqual(output.count("🧰 Added 2 tool definition(s):"), 1)
        self.assertIn("shared_tool [/tmp/local.json] overriding builtin", output)
        self.assertIn("new_tool [/tmp/global.json]", output)


if __name__ == "__main__":
    unittest.main()