"""Global theme for the ooProxy GUI — palette, fonts, and stylesheet."""

from __future__ import annotations

# ── Color Palette ──────────────────────────────────────────────────────
# Dark theme inspired by modern IDE dashboards.

COLORS = {
    # Backgrounds
    "bg_primary": "#0d1117",
    "bg_secondary": "#161b22",
    "bg_surface": "#1c2128",
    "bg_elevated": "#21262d",
    "bg_hover": "#292e36",
    # Borders
    "border": "#30363d",
    "border_light": "#3d444d",
    # Text
    "text_primary": "#e6edf3",
    "text_secondary": "#8b949e",
    "text_muted": "#6e7681",
    # Accent
    "accent": "#58a6ff",
    "accent_hover": "#79c0ff",
    "accent_pressed": "#388bfd",
    # Status
    "success": "#3fb950",
    "success_bg": "#0d2818",
    "warning": "#d29922",
    "warning_bg": "#2a1f05",
    "error": "#f85149",
    "error_bg": "#300a0a",
    "info": "#58a6ff",
    # Proxy status LED
    "led_running": "#3fb950",
    "led_stopped": "#6e7681",
    "led_starting": "#d29922",
    "led_error": "#f85149",
}

# ── Typography ─────────────────────────────────────────────────────────

FONTS = {
    "family": "Segoe UI, Inter, -apple-system, sans-serif",
    "mono": "Cascadia Code, Consolas, monospace",
    "size_xs": "11px",
    "size_sm": "12px",
    "size_base": "13px",
    "size_lg": "15px",
    "size_xl": "18px",
    "size_2xl": "22px",
}

# ── Spacing & Radius ──────────────────────────────────────────────────

RADIUS = "6px"
RADIUS_LG = "10px"
SPACING = {
    "xs": "4px",
    "sm": "8px",
    "md": "12px",
    "lg": "16px",
    "xl": "24px",
}


def build_stylesheet() -> str:
    """Return the full QSS stylesheet string for the application."""
    c = COLORS
    f = FONTS
    s = SPACING

    return f"""
    /* ── Global Reset ─────────────────────────────────────────── */
    * {{
        margin: 0;
        padding: 0;
    }}

    QMainWindow, QDialog {{
        background-color: {c['bg_primary']};
        color: {c['text_primary']};
        font-family: {f['family']};
        font-size: {f['size_base']};
    }}

    /* ── Tab Widget ───────────────────────────────────────────── */
    QTabWidget::pane {{
        border: 1px solid {c['border']};
        border-radius: {RADIUS};
        background-color: {c['bg_secondary']};
        padding: {s['md']};
    }}

    QTabBar::tab {{
        background-color: {c['bg_surface']};
        color: {c['text_secondary']};
        border: 1px solid {c['border']};
        border-bottom: none;
        padding: {s['sm']} {s['lg']};
        margin-right: 2px;
        border-top-left-radius: {RADIUS};
        border-top-right-radius: {RADIUS};
        font-size: {f['size_base']};
        min-width: 100px;
    }}

    QTabBar::tab:selected {{
        background-color: {c['bg_secondary']};
        color: {c['accent']};
        border-bottom: 2px solid {c['accent']};
        font-weight: 600;
    }}

    QTabBar::tab:hover:!selected {{
        background-color: {c['bg_hover']};
        color: {c['text_primary']};
    }}

    /* ── Push Buttons ─────────────────────────────────────────── */
    QPushButton {{
        background-color: {c['bg_elevated']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: {RADIUS};
        padding: {s['sm']} {s['lg']};
        font-size: {f['size_base']};
        font-weight: 500;
        min-height: 28px;
    }}

    QPushButton:hover {{
        background-color: {c['bg_hover']};
        border-color: {c['border_light']};
    }}

    QPushButton:pressed {{
        background-color: {c['bg_surface']};
    }}

    QPushButton:disabled {{
        color: {c['text_muted']};
        background-color: {c['bg_surface']};
        border-color: {c['border']};
    }}

    QPushButton#btn_primary {{
        background-color: {c['accent_pressed']};
        color: #ffffff;
        border: none;
    }}

    QPushButton#btn_primary:hover {{
        background-color: {c['accent']};
    }}

    QPushButton#btn_primary:pressed {{
        background-color: {c['accent_pressed']};
    }}

    QPushButton#btn_danger {{
        background-color: {c['error_bg']};
        color: {c['error']};
        border: 1px solid {c['error']};
    }}

    QPushButton#btn_danger:hover {{
        background-color: #4a1010;
    }}

    /* ── Line Edit / Text Edit ────────────────────────────────── */
    QLineEdit, QSpinBox {{
        background-color: {c['bg_surface']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: {RADIUS};
        padding: {s['sm']} {s['md']};
        font-size: {f['size_base']};
        selection-background-color: {c['accent_pressed']};
    }}

    QLineEdit:focus, QSpinBox:focus {{
        border-color: {c['accent']};
    }}

    QPlainTextEdit {{
        background-color: {c['bg_primary']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: {RADIUS};
        padding: {s['sm']};
        font-family: {f['mono']};
        font-size: {f['size_sm']};
        selection-background-color: {c['accent_pressed']};
    }}

    QTextBrowser {{
        background-color: {c['bg_primary']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: {RADIUS};
        padding: {s['md']};
        font-size: {f['size_base']};
    }}

    /* ── Labels ───────────────────────────────────────────────── */
    QLabel {{
        color: {c['text_primary']};
        font-size: {f['size_base']};
    }}

    QLabel#label_heading {{
        font-size: {f['size_xl']};
        font-weight: 700;
        color: {c['text_primary']};
    }}

    QLabel#label_subheading {{
        font-size: {f['size_lg']};
        font-weight: 600;
        color: {c['text_secondary']};
    }}

    QLabel#label_muted {{
        color: {c['text_muted']};
        font-size: {f['size_sm']};
    }}

    /* ── Table Widget ─────────────────────────────────────────── */
    QTableWidget {{
        background-color: {c['bg_surface']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: {RADIUS};
        gridline-color: {c['border']};
        font-size: {f['size_sm']};
    }}

    QTableWidget::item {{
        padding: {s['sm']};
    }}

    QTableWidget::item:selected {{
        background-color: {c['accent_pressed']};
    }}

    QHeaderView::section {{
        background-color: {c['bg_elevated']};
        color: {c['text_secondary']};
        border: 1px solid {c['border']};
        padding: {s['sm']};
        font-weight: 600;
        font-size: {f['size_sm']};
    }}

    /* ── Group Box ────────────────────────────────────────────── */
    QGroupBox {{
        border: 1px solid {c['border']};
        border-radius: {RADIUS};
        margin-top: 12px;
        padding: {s['lg']};
        padding-top: 28px;
        font-weight: 600;
        color: {c['text_secondary']};
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 {s['sm']};
        color: {c['text_secondary']};
    }}

    /* ── Scroll Bars ──────────────────────────────────────────── */
    QScrollBar:vertical {{
        background-color: {c['bg_primary']};
        width: 10px;
        border: none;
    }}

    QScrollBar::handle:vertical {{
        background-color: {c['border']};
        border-radius: 5px;
        min-height: 30px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {c['border_light']};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    QScrollBar:horizontal {{
        background-color: {c['bg_primary']};
        height: 10px;
        border: none;
    }}

    QScrollBar::handle:horizontal {{
        background-color: {c['border']};
        border-radius: 5px;
        min-width: 30px;
    }}

    /* ── ComboBox ──────────────────────────────────────────────── */
    QComboBox {{
        background-color: {c['bg_surface']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: {RADIUS};
        padding: {s['sm']} {s['md']};
        font-size: {f['size_base']};
    }}

    QComboBox:hover {{
        border-color: {c['border_light']};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {c['bg_elevated']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        selection-background-color: {c['accent_pressed']};
    }}

    /* ── Menu (System Tray) ───────────────────────────────────── */
    QMenu {{
        background-color: {c['bg_elevated']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: {RADIUS};
        padding: {s['xs']};
    }}

    QMenu::item {{
        padding: {s['sm']} {s['xl']};
        border-radius: 4px;
    }}

    QMenu::item:selected {{
        background-color: {c['accent_pressed']};
    }}

    /* ── Tool Tip ──────────────────────────────────────────────── */
    QToolTip {{
        background-color: {c['bg_elevated']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        padding: {s['xs']} {s['sm']};
        font-size: {f['size_sm']};
    }}

    /* ── Status Bar ───────────────────────────────────────────── */
    QStatusBar {{
        background-color: {c['bg_secondary']};
        color: {c['text_muted']};
        border-top: 1px solid {c['border']};
        font-size: {f['size_sm']};
    }}
    """
