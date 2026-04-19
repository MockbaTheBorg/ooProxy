"""ooProxy GUI — Application entry point.

Launch with::

    python -m gui.main
"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from gui.main_window import MainWindow


def main() -> int:
    """Create and run the ooProxy GUI application."""
    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("ooProxy Manager")
    app.setOrganizationName("ooProxy")
    app.setApplicationVersion("1.0.0")

    # Prevent quit when last window is hidden (tray keeps running)
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
