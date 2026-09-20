"""
Video Encoder - PySide6 Port
Main entry point for the application.
"""
import sys
import os

# Add the PySide6 folder to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from main_window import MainWindow
from theme import DEFAULT_THEME, apply_theme


def _stored_theme():
    """Read the saved theme from settings.json (dark by default)."""
    try:
        import json
        settings_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "settings.json",
        )
        with open(settings_path, "r") as f:
            return json.load(f).get("theme", DEFAULT_THEME)
    except Exception:
        return DEFAULT_THEME


def main():
    """Application entry point"""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("VideoEncoder")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("VideoEncoder")
    
    # Set application-wide font
    font = QFont("Segoe UI", 9)
    app.setFont(font)
    
    # Set Fusion style for consistent cross-platform look + saved theme
    apply_theme(app, _stored_theme())
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
