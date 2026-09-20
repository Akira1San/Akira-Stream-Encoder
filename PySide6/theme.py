"""
Central application theme (dark / light) - PySide6 / Fusion based.

No extra dependencies: the dark theme is a Fusion QPalette plus a
small QSS patch for tooltips, disabled states and log contrast.
"""
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt

THEME_DARK = "dark"
THEME_LIGHT = "light"
THEMES = (THEME_DARK, THEME_LIGHT)
DEFAULT_THEME = THEME_DARK


def normalize_theme(name) -> str:
    """Coerce any stored value to a known theme name (defaults to dark)."""
    name = str(name or "").strip().lower()
    return name if name in THEMES else DEFAULT_THEME


def is_dark(app=None) -> bool:
    """True when the app currently uses a dark window background."""
    app = app or QApplication.instance()
    if app is None:
        return True
    return app.palette().color(QPalette.Window).lightness() < 128


def build_dark_palette() -> QPalette:
    """Fusion-friendly dark palette."""
    dark = QColor(53, 53, 53)
    darker = QColor(35, 35, 35)
    normal = QColor(68, 68, 68)
    text = QColor(224, 224, 224)
    disabled_text = QColor(127, 127, 127)
    highlight = QColor(42, 130, 218)
    highlighted_text = QColor(255, 255, 255)

    palette = QPalette()
    palette.setColor(QPalette.Window, dark)
    palette.setColor(QPalette.WindowText, text)
    palette.setColor(QPalette.Base, darker)
    palette.setColor(QPalette.AlternateBase, dark)
    palette.setColor(QPalette.ToolTipBase, QColor(66, 66, 66))
    palette.setColor(QPalette.ToolTipText, text)
    palette.setColor(QPalette.Text, text)
    palette.setColor(QPalette.Button, normal)
    palette.setColor(QPalette.ButtonText, text)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, highlight)
    palette.setColor(QPalette.Highlight, highlight)
    palette.setColor(QPalette.HighlightedText, highlighted_text)
    palette.setColor(QPalette.Disabled, QPalette.Text, disabled_text)
    palette.setColor(QPalette.Disabled, QPalette.WindowText, disabled_text)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, disabled_text)
    return palette


DARK_STYLESHEET = """
QToolTip { color: #e0e0e0; background-color: #424242; border: 1px solid #666666; }
QGroupBox { font-weight: bold; }
QTextEdit:disabled, QLineEdit:disabled, QComboBox:disabled { color: #7f7f7f; }
"""


def apply_theme(app, name) -> str:
    """Apply 'dark' or 'light' to the QApplication. Returns the theme used."""
    theme = normalize_theme(name)
    app.setStyle("Fusion")
    if theme == THEME_DARK:
        app.setPalette(build_dark_palette())
        app.setStyleSheet(DARK_STYLESHEET)
    else:
        app.setPalette(app.style().standardPalette())
        app.setStyleSheet("")
    return theme


def log_colors(dark: bool) -> dict:
    """Log level colors readable on the given theme."""
    if dark:
        return {
            "INFO": "#E0E0E0",
            "WARN": "#FFB347",
            "ERROR": "#FF6B6B",
            "SUCCESS": "#7FD67F",
            "TIMESTAMP": "#AAAAAA",
        }
    return {
        "INFO": "#000000",
        "WARN": "#FF8C00",
        "ERROR": "#FF0000",
        "SUCCESS": "#008000",
        "TIMESTAMP": "#666666",
    }


def muted_color(dark: bool) -> str:
    """Muted info-label color readable on both themes."""
    return "#9AA0A6" if dark else "#666666"


def list_item_color(kind: str, dark: bool):
    """QColor for special file-list entries (image_seq / dvd)."""
    from PySide6.QtGui import QColor as _QColor

    if kind == "image_seq":
        return _QColor("#4CAF50") if dark else Qt.darkGreen
    if kind == "dvd":
        return _QColor("#CE93D8") if dark else Qt.darkMagenta
    return None
