"""
Reusable UI Components for Video Encoder (PySide6)
"""
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QWidget, QToolButton, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class CollapsibleFrame(QFrame):
    """
    A collapsible frame with an arrow button to expand/collapse content.
    PySide6 replacement for the Tkinter CollapsibleFrame.
    """
    
    toggled = Signal(bool)  # Emitted when collapsed/expanded
    
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        
        self._title = title
        self._is_expanded = True
        
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        
        # Main layout
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(5, 5, 5, 5)
        self._main_layout.setSpacing(2)
        
        # Header with toggle button
        self._header = QWidget()
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Toggle button with arrow
        self._toggle_btn = QToolButton()
        self._toggle_btn.setText("▼")
        self._toggle_btn.setFixedSize(24, 24)
        self._toggle_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background: transparent;
                font-weight: bold;
            }
            QToolButton:hover {
                background: #e0e0e0;
                border-radius: 4px;
            }
        """)
        self._toggle_btn.clicked.connect(self.toggle)
        header_layout.addWidget(self._toggle_btn)
        
        # Title label
        self._title_label = QLabel(f"<b>{title}</b>")
        header_layout.addWidget(self._title_label)
        header_layout.addStretch()
        
        self._main_layout.addWidget(self._header)
        
        # Content frame (this will be shown/hidden)
        self._content = QFrame()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(5, 5, 5, 5)
        self._content_layout.setSpacing(5)
        
        self._main_layout.addWidget(self._content)
        
    def toggle(self):
        """Toggle the collapsed/expanded state"""
        if self._is_expanded:
            self.collapse()
        else:
            self.expand()
            
    def expand(self):
        """Expand the frame"""
        self._content.show()
        self._toggle_btn.setText("▼")
        self._is_expanded = True
        self.toggled.emit(True)
        
    def collapse(self):
        """Collapse the frame"""
        self._content.hide()
        self._toggle_btn.setText("▶")
        self._is_expanded = False
        self.toggled.emit(False)
        
    def is_expanded(self) -> bool:
        """Return current expanded state"""
        return self._is_expanded
    
    def content_layout(self) -> QVBoxLayout:
        """Return the content layout for adding widgets"""
        return self._content_layout
    
    def set_title(self, title: str):
        """Update the frame title"""
        self._title = title
        self._title_label.setText(f"<b>{title}</b>")


class ToolTipLabel(QLabel):
    """Label with tooltip support"""
    
    def __init__(self, text: str = "", tooltip: str = "", parent=None):
        super().__init__(text, parent)
        if tooltip:
            self.setToolTip(tooltip)
            self.setStyleSheet("QLabel { text-decoration: underline dotted; }")


class HorizontalLine(QFrame):
    """Simple horizontal separator line"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)


class VerticalLine(QFrame):
    """Simple vertical separator line"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.VLine)
        self.setFrameShadow(QFrame.Sunken)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)


class ValueLabel(QLabel):
    """
    Label that displays a value with optional suffix.
    Useful for showing slider values.
    """
    
    def __init__(self, value=0, suffix="", width=40, parent=None):
        super().__init__(parent)
        self._value = value
        self._suffix = suffix
        self.setFixedWidth(width)
        self.setAlignment(Qt.AlignCenter)
        self.update_display()
        
    def set_value(self, value):
        """Update the displayed value"""
        self._value = value
        self.update_display()
        
    def update_display(self):
        """Refresh the display"""
        if isinstance(self._value, float):
            text = f"{self._value:.2f}{self._suffix}"
        else:
            text = f"{self._value}{self._suffix}"
        self.setText(text)


class SectionHeader(QWidget):
    """A styled header for sections"""
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        
        label = QLabel(f"<b>{title}</b>")
        label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(label)
        
        line = HorizontalLine()
        layout.addWidget(line)
