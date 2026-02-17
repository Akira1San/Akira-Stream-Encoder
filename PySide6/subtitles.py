"""
Subtitles Panel (PySide6)
"""
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QComboBox, QSlider, QPushButton, QColorDialog, QSpinBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from models import AppState


class SubtitlesPanel(QWidget):
    """Panel for subtitle settings"""
    
    settings_changed = Signal()
    refresh_subtitles = Signal()  # Signal to request subtitle folder scan
    
    def __init__(self, app_state: AppState, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Burn checkbox
        self.burn_check = QCheckBox("Burn Subtitles into Video")
        self.burn_check.setChecked(self.app_state.subtitles.burn_subs)
        self.burn_check.setToolTip(
            "Burn subtitles directly into video (permanent).\n"
            "Supported formats: .srt, .ass, .ssa, .sub\n\n"
            "Note: Preview only shows .srt subtitles.\n"
            "Encoding works with all formats."
        )
        layout.addWidget(self.burn_check)
        
        # Info label
        preview_info = QLabel("Preview supports .srt only | Encoding supports all formats")
        preview_info.setStyleSheet("color: gray; font-size: 10px; font-style: italic;")
        layout.addWidget(preview_info)
        
        # Subtitle File Selector
        sub_file_layout = QHBoxLayout()
        sub_file_layout.addWidget(QLabel("Subtitle File:"))
        
        self.subtitle_combo = QComboBox()
        self.subtitle_combo.setMinimumWidth(200)
        self.subtitle_combo.setToolTip("Select subtitle file to burn into video")
        self.subtitle_combo.addItem("(Auto-detect)", "")  # Default: auto-detect
        sub_file_layout.addWidget(self.subtitle_combo)
        
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setToolTip("Scan folder for subtitle files")
        self.refresh_btn.setMaximumWidth(30)
        self.refresh_btn.clicked.connect(self.on_refresh_clicked)
        sub_file_layout.addWidget(self.refresh_btn)
        
        sub_file_layout.addStretch()
        layout.addLayout(sub_file_layout)
        
        # Font & Size row
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("Font:"))
        
        self.font_combo = QComboBox()
        self.font_combo.addItems(["Arial", "Courier", "Times", "Helvetica", "Verdana"])
        self.font_combo.setCurrentText(self.app_state.subtitles.font)
        self.font_combo.setMinimumWidth(100)
        font_layout.addWidget(self.font_combo)
        
        font_layout.addSpacing(20)
        font_layout.addWidget(QLabel("Size:"))
        
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(10, 50)
        self.size_slider.setValue(self.app_state.subtitles.size)
        self.size_slider.setMaximumWidth(100)
        font_layout.addWidget(self.size_slider)
        
        self.size_label = QLabel(str(self.app_state.subtitles.size))
        self.size_label.setMinimumWidth(25)
        font_layout.addWidget(self.size_label)
        
        font_layout.addStretch()
        layout.addLayout(font_layout)
        
        # Position
        pos_layout = QHBoxLayout()
        pos_layout.addWidget(QLabel("Position:"))
        
        self.position_combo = QComboBox()
        self.position_combo.addItems(["bottom", "top", "center"])
        self.position_combo.setCurrentText(self.app_state.subtitles.position)
        pos_layout.addWidget(self.position_combo)
        
        pos_layout.addSpacing(20)
        pos_layout.addWidget(QLabel("V-Offset:"))
        
        self.v_offset_slider = QSlider(Qt.Horizontal)
        self.v_offset_slider.setRange(0, 200)
        self.v_offset_slider.setValue(self.app_state.subtitles.vertical_offset)
        self.v_offset_slider.setMaximumWidth(100)
        self.v_offset_slider.setToolTip(
            "Vertical offset in pixels (for letterboxed videos):\n"
            "0 = default position\n"
            "Higher = move subtitles down into black bars\n\n"
            "Use this when subtitles appear above black bars."
        )
        pos_layout.addWidget(self.v_offset_slider)
        
        self.v_offset_label = QLabel(str(self.app_state.subtitles.vertical_offset))
        self.v_offset_label.setMinimumWidth(25)
        pos_layout.addWidget(self.v_offset_label)
        
        pos_layout.addStretch()
        layout.addLayout(pos_layout)
        
        # Color buttons
        color_layout = QHBoxLayout()
        
        self.text_color_btn = QPushButton("Text Color")
        self.text_color_btn.setStyleSheet(f"background-color: {self.app_state.subtitles.color}")
        color_layout.addWidget(self.text_color_btn)
        
        self.outline_color_btn = QPushButton("Outline Color")
        self.outline_color_btn.setStyleSheet(f"background-color: {self.app_state.subtitles.outline_color}")
        color_layout.addWidget(self.outline_color_btn)
        
        self.bg_color_btn = QPushButton("BG Color")
        self.bg_color_btn.setStyleSheet(f"background-color: {self.app_state.subtitles.bg_color}")
        color_layout.addWidget(self.bg_color_btn)
        
        color_layout.addStretch()
        layout.addLayout(color_layout)
        
        # Outline Width
        ol_layout = QHBoxLayout()
        ol_layout.addWidget(QLabel("Outline Width:"))
        
        self.ol_slider = QSlider(Qt.Horizontal)
        self.ol_slider.setRange(0, 5)
        self.ol_slider.setValue(self.app_state.subtitles.outline_width)
        ol_layout.addWidget(self.ol_slider)
        
        self.ol_label = QLabel(str(self.app_state.subtitles.outline_width))
        self.ol_label.setMinimumWidth(20)
        ol_layout.addWidget(self.ol_label)
        
        layout.addLayout(ol_layout)
        
        # BG Opacity
        bg_layout = QHBoxLayout()
        bg_layout.addWidget(QLabel("BG Opacity:"))
        
        self.bg_op_slider = QSlider(Qt.Horizontal)
        self.bg_op_slider.setRange(0, 10)
        self.bg_op_slider.setValue(int(self.app_state.subtitles.bg_opacity * 10))
        bg_layout.addWidget(self.bg_op_slider)
        
        self.bg_op_label = QLabel(f"{self.app_state.subtitles.bg_opacity:.1f}")
        self.bg_op_label.setMinimumWidth(30)
        bg_layout.addWidget(self.bg_op_label)
        
        layout.addLayout(bg_layout)
        
        layout.addStretch()
        
    def connect_signals(self):
        """Connect UI signals to handlers"""
        self.burn_check.toggled.connect(self.on_burn_changed)
        self.subtitle_combo.currentTextChanged.connect(self.on_subtitle_changed)
        self.font_combo.currentTextChanged.connect(self.on_font_changed)
        self.size_slider.valueChanged.connect(self.on_size_changed)
        self.position_combo.currentTextChanged.connect(self.on_position_changed)
        self.v_offset_slider.valueChanged.connect(self.on_v_offset_changed)
        self.text_color_btn.clicked.connect(self.on_text_color_clicked)
        self.outline_color_btn.clicked.connect(self.on_outline_color_clicked)
        self.bg_color_btn.clicked.connect(self.on_bg_color_clicked)
        self.ol_slider.valueChanged.connect(self.on_outline_width_changed)
        self.bg_op_slider.valueChanged.connect(self.on_bg_opacity_changed)
        
    def on_burn_changed(self, checked):
        """Handle burn checkbox change"""
        self.app_state.subtitles.burn_subs = checked
        self.settings_changed.emit()
        
    def on_subtitle_changed(self, text):
        """Handle subtitle file selection change"""
        # Get the file path from the combo box data (stored at index 0)
        index = self.subtitle_combo.currentIndex()
        data = self.subtitle_combo.currentData()
        self.app_state.subtitles.selected_subtitle = data if data else ""
        self.settings_changed.emit()
    
    def on_refresh_clicked(self):
        """Handle refresh button click"""
        self.refresh_subtitles.emit()
        
    def set_subtitle_files(self, files: list):
        """Populate the subtitle combobox with found files"""
        current_selection = self.app_state.subtitles.selected_subtitle
        
        self.subtitle_combo.blockSignals(True)
        self.subtitle_combo.clear()
        self.subtitle_combo.addItem("(Auto-detect)", "")  # Default
        
        for f in files:
            # Add file with full path as data
            self.subtitle_combo.addItem(os.path.basename(f), f)
        
        # Auto-select: prioritize .srt files
        if files:
            # Find first .srt file
            srt_index = -1
            for i in range(1, self.subtitle_combo.count()):  # Start from 1 (skip auto-detect)
                if self.subtitle_combo.itemText(i).lower().endswith('.srt'):
                    srt_index = i
                    break
            
            # If saved selection exists and still available, use it
            if current_selection and current_selection in files:
                for i in range(1, self.subtitle_combo.count()):
                    if self.subtitle_combo.itemData(i) == current_selection:
                        self.subtitle_combo.setCurrentIndex(i)
                        break
            elif srt_index > 0:
                # Auto-select first .srt found
                self.subtitle_combo.setCurrentIndex(srt_index)
            else:
                # Just select first file found
                self.subtitle_combo.setCurrentIndex(1)
        
        self.subtitle_combo.blockSignals(False)
    
    def get_selected_subtitle(self) -> str:
        """Get the currently selected subtitle path"""
        return self.subtitle_combo.currentData() or ""
        
    def on_font_changed(self, text):
        """Handle font change"""
        self.app_state.subtitles.font = text
        self.settings_changed.emit()
        
    def on_size_changed(self, value):
        """Handle size slider change"""
        self.app_state.subtitles.size = value
        self.size_label.setText(str(value))
        self.settings_changed.emit()
        
    def on_position_changed(self, text):
        """Handle position change"""
        self.app_state.subtitles.position = text
        self.settings_changed.emit()
    
    def on_v_offset_changed(self, value):
        """Handle vertical offset change"""
        self.app_state.subtitles.vertical_offset = value
        self.v_offset_label.setText(str(value))
        self.settings_changed.emit()
        
    def on_text_color_clicked(self):
        """Handle text color button click"""
        color = QColorDialog.getColor(
            QColor(self.app_state.subtitles.color),
            self,
            "Select Text Color"
        )
        if color.isValid():
            self.app_state.subtitles.color = color.name()
            self.text_color_btn.setStyleSheet(f"background-color: {color.name()}")
            self.settings_changed.emit()
            
    def on_outline_color_clicked(self):
        """Handle outline color button click"""
        color = QColorDialog.getColor(
            QColor(self.app_state.subtitles.outline_color),
            self,
            "Select Outline Color"
        )
        if color.isValid():
            self.app_state.subtitles.outline_color = color.name()
            self.outline_color_btn.setStyleSheet(f"background-color: {color.name()}")
            self.settings_changed.emit()
            
    def on_bg_color_clicked(self):
        """Handle background color button click"""
        color = QColorDialog.getColor(
            QColor(self.app_state.subtitles.bg_color),
            self,
            "Select Background Color"
        )
        if color.isValid():
            self.app_state.subtitles.bg_color = color.name()
            self.bg_color_btn.setStyleSheet(f"background-color: {color.name()}")
            self.settings_changed.emit()
            
    def on_outline_width_changed(self, value):
        """Handle outline width change"""
        self.app_state.subtitles.outline_width = value
        self.ol_label.setText(str(value))
        self.settings_changed.emit()
        
    def on_bg_opacity_changed(self, value):
        """Handle background opacity change"""
        opacity = value / 10.0
        self.app_state.subtitles.bg_opacity = opacity
        self.bg_op_label.setText(f"{opacity:.1f}")
        self.settings_changed.emit()
