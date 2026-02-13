"""
Video and Audio Filters Panel (PySide6)
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QLineEdit, QGroupBox, QFrame
)
from PySide6.QtCore import Signal

from models import AppState


class FiltersPanel(QWidget):
    """Panel for video and audio filters"""
    
    settings_changed = Signal()
    
    def __init__(self, app_state: AppState, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # === Video Filters ===
        video_group = QGroupBox("Video Filters")
        video_layout = QVBoxLayout(video_group)
        
        self.deint_check = QCheckBox("Deinterlace (Yadif)")
        self.deint_check.setChecked(self.app_state.filters.deinterlace)
        video_layout.addWidget(self.deint_check)
        
        self.denoise_check = QCheckBox("Denoise (HQDN3D)")
        self.denoise_check.setChecked(self.app_state.filters.denoise)
        video_layout.addWidget(self.denoise_check)
        
        layout.addWidget(video_group)
        
        # === Audio Filters ===
        audio_group = QGroupBox("Audio Filters")
        audio_layout = QVBoxLayout(audio_group)
        
        vol_layout = QHBoxLayout()
        self.vol_check = QCheckBox("Enable Volume:")
        self.vol_check.setChecked(self.app_state.filters.volume_enabled)
        vol_layout.addWidget(self.vol_check)
        
        self.vol_edit = QLineEdit(str(self.app_state.filters.volume_db))
        self.vol_edit.setMaximumWidth(60)
        self.vol_edit.setEnabled(self.app_state.filters.volume_enabled)
        vol_layout.addWidget(self.vol_edit)
        
        vol_layout.addWidget(QLabel("dB"))
        vol_layout.addStretch()
        audio_layout.addLayout(vol_layout)
        
        layout.addWidget(audio_group)
        
        layout.addStretch()
        
    def connect_signals(self):
        """Connect UI signals to handlers"""
        self.deint_check.toggled.connect(self.on_deint_changed)
        self.denoise_check.toggled.connect(self.on_denoise_changed)
        self.vol_check.toggled.connect(self.on_vol_enabled_changed)
        self.vol_edit.textChanged.connect(self.on_vol_changed)
        
    def on_deint_changed(self, checked):
        """Handle deinterlace checkbox change"""
        self.app_state.filters.deinterlace = checked
        self.settings_changed.emit()
        
    def on_denoise_changed(self, checked):
        """Handle denoise checkbox change"""
        self.app_state.filters.denoise = checked
        self.settings_changed.emit()
        
    def on_vol_enabled_changed(self, checked):
        """Handle volume enabled checkbox change"""
        self.app_state.filters.volume_enabled = checked
        self.vol_edit.setEnabled(checked)
        self.settings_changed.emit()
        
    def on_vol_changed(self, text):
        """Handle volume value change"""
        try:
            self.app_state.filters.volume_db = float(text)
        except ValueError:
            pass
        self.settings_changed.emit()
