"""Help tab — displays project documentation rendered from Markdown."""

from __future__ import annotations

import re
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTextBrowser,
)

from gui.i18n import t
from gui.resources import PROJECT_ROOT
from gui.theme import COLORS, FONTS


def _markdown_to_html(md: str) -> str:
    """Minimal Markdown → HTML converter for the help tab.

    Handles headings, bold, italic, code, links, lists, horizontal
    rules, and fenced code blocks.  No external dependency required.
    """
    lines = md.split("\n")
    html_lines: list[str] = []
    in_code_block = False
    in_list = False

    for line in lines:
        # Fenced code blocks
        if line.strip().startswith("```"):
            if in_code_block:
                html_lines.append("</code></pre>")
                in_code_block = False
            else:
                html_lines.append(
                    f'<pre style="background-color:{COLORS["bg_surface"]};'
                    f'padding:12px;border-radius:6px;border:1px solid {COLORS["border"]};'
                    f'font-family:{FONTS["mono"]};font-size:12px;'
                    f'color:{COLORS["text_primary"]};">'
                    f"<code>"
                )
                in_code_block = True
            continue

        if in_code_block:
            html_lines.append(line.replace("<", "&lt;").replace(">", "&gt;"))
            continue

        stripped = line.strip()

        # Horizontal rule
        if stripped in ("---", "***", "___"):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f'<hr style="border-color:{COLORS["border"]};">')
            continue

        # Headings
        heading_match = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if heading_match:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            level = len(heading_match.group(1))
            text = heading_match.group(2)
            sizes = {1: "22px", 2: "18px", 3: "15px", 4: "14px", 5: "13px", 6: "12px"}
            size = sizes.get(level, "13px")
            color = COLORS["accent"] if level <= 2 else COLORS["text_primary"]
            margin = "20px 0 10px 0" if level <= 2 else "14px 0 6px 0"
            html_lines.append(
                f'<h{level} style="color:{color};font-size:{size};margin:{margin};">'
                f"{_inline_format(text)}</h{level}>"
            )
            continue

        # Unordered list
        list_match = re.match(r"^[-*+]\s+(.*)", stripped)
        if list_match:
            if not in_list:
                html_lines.append(f'<ul style="margin-left:20px;color:{COLORS["text_primary"]};">')
                in_list = True
            html_lines.append(f"<li>{_inline_format(list_match.group(1))}</li>")
            continue

        # Close open list if we hit a non-list line
        if in_list and not stripped:
            html_lines.append("</ul>")
            in_list = False

        # Empty line → paragraph break
        if not stripped:
            html_lines.append("<br>")
            continue

        # Regular paragraph
        html_lines.append(f'<p style="color:{COLORS["text_primary"]};">{_inline_format(stripped)}</p>')

    if in_list:
        html_lines.append("</ul>")
    if in_code_block:
        html_lines.append("</code></pre>")

    return "\n".join(html_lines)


def _inline_format(text: str) -> str:
    """Apply inline Markdown formatting (bold, italic, code, links)."""
    # Inline code
    text = re.sub(
        r"`([^`]+)`",
        rf'<code style="background-color:{COLORS["bg_surface"]};'
        rf'padding:2px 5px;border-radius:3px;font-family:{FONTS["mono"]};'
        rf'font-size:12px;color:{COLORS["accent"]};">\1</code>',
        text,
    )
    # Bold
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    # Italic
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    # Links
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        rf'<a href="\2" style="color:{COLORS["accent"]};">\1</a>',
        text,
    )
    return text


class HelpTab(QWidget):
    """Read-only documentation panel rendered from README.md."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._load_content()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel(t("help.title"))
        title.setObjectName("label_heading")
        title.setFont(QFont(FONTS["family"].split(",")[0].strip(), 16, QFont.Weight.Bold))
        layout.addWidget(title)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setStyleSheet(
            f"QTextBrowser {{ "
            f"background-color: {COLORS['bg_primary']}; "
            f"color: {COLORS['text_primary']}; "
            f"border: 1px solid {COLORS['border']}; "
            f"border-radius: 6px; "
            f"padding: 16px; "
            f"font-family: {FONTS['family']}; "
            f"font-size: {FONTS['size_base']}; "
            f"line-height: 1.6; "
            f"}}"
        )
        layout.addWidget(self._browser)

    def _load_content(self) -> None:
        readme = PROJECT_ROOT / "README.md"
        if readme.exists():
            md = readme.read_text(encoding="utf-8")
            html = _markdown_to_html(md)
            self._browser.setHtml(html)
        else:
            self._browser.setHtml(
                f'<p style="color:{COLORS["text_muted"]};">'
                f"{t('help.readme_missing')}</p>"
            )
