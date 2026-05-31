"""
Subtitles Panel (PySide6)
"""
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QComboBox, QSlider, QPushButton, QColorDialog, QSpinBox,
    QFileDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from models import AppState


class SubtitlesPanel(QWidget):
    """Panel for subtitle settings"""
    
    settings_changed = Signal()
    refresh_subtitles = Signal()  # Signal to request subtitle folder scan
    dvd_subtitle_changed = Signal()  # Signal when DVD subtitle selection changes
    
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
        
        # DVD Subtitle Track Selection (shown only for DVD sources)
        self.dvd_subtitle_group = QWidget()
        dvd_layout = QVBoxLayout(self.dvd_subtitle_group)
        dvd_layout.setContentsMargins(0, 0, 0, 0)
        
        dvd_sub_layout = QHBoxLayout()
        dvd_sub_layout.addWidget(QLabel("DVD Subtitle Track:"))
        
        self.dvd_subtitle_combo = QComboBox()
        self.dvd_subtitle_combo.setMinimumWidth(200)
        self.dvd_subtitle_combo.setToolTip("Select which DVD subtitle track to burn into video")
        dvd_sub_layout.addWidget(self.dvd_subtitle_combo)
        
        dvd_sub_layout.addStretch()
        dvd_layout.addLayout(dvd_sub_layout)
        
        # DVD subtitle info label
        self.dvd_info_label = QLabel("")
        self.dvd_info_label.setStyleSheet("color: gray; font-size: 10px; font-style: italic;")
        dvd_layout.addWidget(self.dvd_info_label)
        
        # HandBrake availability label
        self.hb_avail_label = QLabel("")
        self.hb_avail_label.setStyleSheet("font-size: 10px; font-style: italic;")
        dvd_layout.addWidget(self.hb_avail_label)
        
        self.dvd_subtitle_group.setLayout(dvd_layout)
        layout.addWidget(self.dvd_subtitle_group)
        
        # Initially hide DVD subtitle selector
        self.dvd_subtitle_group.hide()
        
        # Info label
        preview_info = QLabel("Preview supports .srt only | Encoding supports all formats")
        preview_info.setStyleSheet("color: gray; font-size: 10px; font-style: italic;")
        layout.addWidget(preview_info)
        
        # Subtitle File Selector
        sub_file_layout = QHBoxLayout()
        sub_file_layout.addWidget(QLabel("Subtitle:"))
        
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

        self.load_ext_btn = QPushButton("...")
        self.load_ext_btn.setToolTip("Load external subtitle file from a different folder")
        self.load_ext_btn.setMaximumWidth(30)
        self.load_ext_btn.clicked.connect(self.on_load_external_clicked)
        sub_file_layout.addWidget(self.load_ext_btn)

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
        
        # Shadow controls
        shadow_header_layout = QHBoxLayout()
        self.shadow_check = QCheckBox("Enable Shadow")
        self.shadow_check.setChecked(self.app_state.subtitles.shadow_enabled)
        self.shadow_check.setToolTip("Add shadow effect to subtitles")
        shadow_header_layout.addWidget(self.shadow_check)
        shadow_header_layout.addStretch()
        layout.addLayout(shadow_header_layout)
        
        # Shadow color
        shadow_color_layout = QHBoxLayout()
        shadow_color_layout.addWidget(QLabel("Shadow Color:"))
        self.shadow_color_btn = QPushButton("Shadow")
        self.shadow_color_btn.setStyleSheet(f"background-color: {self.app_state.subtitles.shadow_color}")
        shadow_color_layout.addWidget(self.shadow_color_btn)
        shadow_color_layout.addStretch()
        layout.addLayout(shadow_color_layout)
        
        # Shadow offset X
        shadow_offset_x_layout = QHBoxLayout()
        shadow_offset_x_layout.addWidget(QLabel("Shadow Offset X:"))
        self.shadow_x_slider = QSlider(Qt.Horizontal)
        self.shadow_x_slider.setRange(0, 10)
        self.shadow_x_slider.setValue(self.app_state.subtitles.shadow_offset_x)
        self.shadow_x_slider.setMaximumWidth(80)
        shadow_offset_x_layout.addWidget(self.shadow_x_slider)
        self.shadow_x_label = QLabel(str(self.app_state.subtitles.shadow_offset_x))
        self.shadow_x_label.setMinimumWidth(20)
        shadow_offset_x_layout.addWidget(self.shadow_x_label)
        shadow_offset_x_layout.addStretch()
        layout.addLayout(shadow_offset_x_layout)

        # Shadow offset Y
        shadow_offset_y_layout = QHBoxLayout()
        shadow_offset_y_layout.addWidget(QLabel("Shadow Offset Y:"))
        self.shadow_y_slider = QSlider(Qt.Horizontal)
        self.shadow_y_slider.setRange(0, 10)
        self.shadow_y_slider.setValue(self.app_state.subtitles.shadow_offset_y)
        self.shadow_y_slider.setMaximumWidth(80)
        shadow_offset_y_layout.addWidget(self.shadow_y_slider)
        self.shadow_y_label = QLabel(str(self.app_state.subtitles.shadow_offset_y))
        self.shadow_y_label.setMinimumWidth(20)
        shadow_offset_y_layout.addWidget(self.shadow_y_label)
        shadow_offset_y_layout.addStretch()
        layout.addLayout(shadow_offset_y_layout)
        
        # Shadow opacity
        shadow_op_layout = QHBoxLayout()
        shadow_op_layout.addWidget(QLabel("Shadow Opacity:"))
        self.shadow_op_slider = QSlider(Qt.Horizontal)
        self.shadow_op_slider.setRange(0, 10)
        self.shadow_op_slider.setValue(int(self.app_state.subtitles.shadow_opacity * 10))
        shadow_op_layout.addWidget(self.shadow_op_slider)
        self.shadow_op_label = QLabel(f"{self.app_state.subtitles.shadow_opacity:.1f}")
        self.shadow_op_label.setMinimumWidth(30)
        shadow_op_layout.addWidget(self.shadow_op_label)
        shadow_op_layout.addStretch()
        layout.addLayout(shadow_op_layout)
        
        layout.addStretch()
        
    def connect_signals(self):
        """Connect UI signals to handlers"""
        self.burn_check.toggled.connect(self.on_burn_changed)
        self.subtitle_combo.currentTextChanged.connect(self.on_subtitle_changed)
        self.dvd_subtitle_combo.currentIndexChanged.connect(self.on_dvd_subtitle_changed)
        self.font_combo.currentTextChanged.connect(self.on_font_changed)
        self.size_slider.valueChanged.connect(self.on_size_changed)
        self.position_combo.currentTextChanged.connect(self.on_position_changed)
        self.v_offset_slider.valueChanged.connect(self.on_v_offset_changed)
        self.text_color_btn.clicked.connect(self.on_text_color_clicked)
        self.outline_color_btn.clicked.connect(self.on_outline_color_clicked)
        self.bg_color_btn.clicked.connect(self.on_bg_color_clicked)
        self.ol_slider.valueChanged.connect(self.on_outline_width_changed)
        self.bg_op_slider.valueChanged.connect(self.on_bg_opacity_changed)
        # HandBrake availability
        self.app_state.handbrake_available_changed.connect(self.on_handbrake_available_changed)
        self.on_handbrake_available_changed(self.app_state.handbrake_available)
        
        # Shadow controls
        self.shadow_check.toggled.connect(self.on_shadow_changed)
        self.shadow_color_btn.clicked.connect(self.on_shadow_color_clicked)
        self.shadow_x_slider.valueChanged.connect(self.on_shadow_offset_x_changed)
        self.shadow_y_slider.valueChanged.connect(self.on_shadow_offset_y_changed)
        self.shadow_op_slider.valueChanged.connect(self.on_shadow_opacity_changed)
        
    def on_burn_changed(self, checked):
        """Handle burn checkbox change"""
        self.app_state.subtitles.burn_subs = checked
        self.settings_changed.emit()
    
    def on_dvd_subtitle_changed(self, index):
        """Handle DVD subtitle track selection change"""
        sub_idx = self.dvd_subtitle_combo.currentData()
        if sub_idx is not None:
            self.app_state.dvd.selected_subtitle_index = sub_idx
            # Auto-enable burn subtitles when a DVD subtitle is selected
            if sub_idx >= 0:
                self.burn_check.setChecked(True)
            self.dvd_subtitle_changed.emit()
            self.settings_changed.emit()
    
    def on_handbrake_available_changed(self, available):
        """Update HandBrake availability label"""
        if available:
            self.hb_avail_label.setText("HandBrakeCLI ✓ — DVD subtitle burning supported")
            self.hb_avail_label.setStyleSheet("color: green; font-size: 10px; font-style: italic;")
        else:
            self.hb_avail_label.setText("HandBrakeCLI ✗ — DVD subtitles will be skipped")
            self.hb_avail_label.setStyleSheet("color: red; font-size: 10px; font-style: italic;")

    def update_dvd_subtitles(self):
        """Update DVD subtitle combobox based on current DVD source"""
        if self.app_state.dvd.is_dvd_source and self.app_state.dvd.subtitle_tracks:
            # Show DVD subtitle selector
            self.dvd_subtitle_group.show()
            
            # Populate combobox
            self.dvd_subtitle_combo.blockSignals(True)
            self.dvd_subtitle_combo.clear()
            self.dvd_subtitle_combo.addItem("None (no subtitles)", -1)
            
            for sub in self.app_state.dvd.subtitle_tracks:
                lang = sub.get('language', 'unknown')
                sub_idx = sub.get('sub_index', sub.get('index', 0))
                display = f"Track {sub_idx}: {lang}"
                self.dvd_subtitle_combo.addItem(display, sub_idx)
            
            # Restore selection
            current_idx = self.app_state.dvd.selected_subtitle_index
            for i in range(self.dvd_subtitle_combo.count()):
                if self.dvd_subtitle_combo.itemData(i) == current_idx:
                    self.dvd_subtitle_combo.setCurrentIndex(i)
                    break
            
            self.dvd_subtitle_combo.blockSignals(False)
            
            # Update info label
            self.dvd_info_label.setText(
                f"DVD subtitles are bitmap-based and will be burned into the video. "
                f"{len(self.app_state.dvd.subtitle_tracks)} track(s) available."
            )
        else:
            # Hide DVD subtitle selector for non-DVD sources
            self.dvd_subtitle_group.hide()
    
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

    def on_load_external_clicked(self):
        """Handle load external subtitle button click"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Subtitle File",
            "",
            "Subtitle Files (*.srt *.ass *.ssa *.sub);;All Files (*)"
        )
        if not file_path:
            return

        for i in range(self.subtitle_combo.count()):
            if self.subtitle_combo.itemData(i) == file_path:
                self.subtitle_combo.setCurrentIndex(i)
                return

        self.subtitle_combo.blockSignals(True)
        self.subtitle_combo.addItem(os.path.basename(file_path), file_path)
        self.subtitle_combo.setCurrentIndex(self.subtitle_combo.count() - 1)
        self.subtitle_combo.blockSignals(False)

        self.app_state.subtitles.selected_subtitle = file_path
        self.settings_changed.emit()
        
    def set_subtitle_files(self, files: list):
        """Populate the subtitle combobox with found files"""
        current_selection = self.app_state.subtitles.selected_subtitle
        
        self.subtitle_combo.blockSignals(True)
        self.subtitle_combo.clear()
        self.subtitle_combo.addItem("(Auto-detect)", "")  # Default
        
        for f in files:
            # Add file with full path as data
            self.subtitle_combo.addItem(os.path.basename(f), f)
        
        # If there's a saved external subtitle not in the scanned folder,
        # add it so the selection is preserved across refreshes
        if current_selection and current_selection not in files and os.path.exists(current_selection):
            self.subtitle_combo.addItem(os.path.basename(current_selection), current_selection)
        
        # Auto-select: prioritize .srt files
        if self.subtitle_combo.count() > 1:
            # Find first .srt file
            srt_index = -1
            for i in range(1, self.subtitle_combo.count()):  # Start from 1 (skip auto-detect)
                if self.subtitle_combo.itemText(i).lower().endswith('.srt'):
                    srt_index = i
                    break
            
            # If saved selection exists and still available, use it
            if current_selection:
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
            
            # Update selected_subtitle in AppState (signals are blocked,
            # so on_subtitle_changed won't fire)
            self.app_state.subtitles.selected_subtitle = self.subtitle_combo.currentData() or ""
        
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
    
    def on_shadow_changed(self, checked):
        """Handle shadow enable checkbox change"""
        self.app_state.subtitles.shadow_enabled = checked
        self.settings_changed.emit()
        
    def on_shadow_color_clicked(self):
        """Handle shadow color button click"""
        color = QColorDialog.getColor(
            QColor(self.app_state.subtitles.shadow_color),
            self,
            "Select Shadow Color"
        )
        if color.isValid():
            self.app_state.subtitles.shadow_color = color.name()
            self.shadow_color_btn.setStyleSheet(f"background-color: {color.name()}")
            self.settings_changed.emit()
            
    def on_shadow_offset_x_changed(self, value):
        """Handle shadow offset X change"""
        self.app_state.subtitles.shadow_offset_x = value
        self.shadow_x_label.setText(str(value))
        self.settings_changed.emit()
        
    def on_shadow_offset_y_changed(self, value):
        """Handle shadow offset Y change"""
        self.app_state.subtitles.shadow_offset_y = value
        self.shadow_y_label.setText(str(value))
        self.settings_changed.emit()
        
    def on_shadow_opacity_changed(self, value):
        """Handle shadow opacity change"""
        opacity = value / 10.0
        self.app_state.subtitles.shadow_opacity = opacity
        self.shadow_op_label.setText(f"{opacity:.1f}")
        self.settings_changed.emit()
