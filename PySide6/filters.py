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
        self.deint_check.setToolTip("Remove interlacing artifacts from video.\nUse for interlaced sources (e.g., old DVDs, TV captures).\nOutput will be progressive.")
        video_layout.addWidget(self.deint_check)
        
        self.denoise_check = QCheckBox("Denoise (HQDN3D)")
        self.denoise_check.setChecked(self.app_state.filters.denoise)
        self.denoise_check.setToolTip("Reduce video noise/grain using HQDN3D filter.\nGood for grainy or noisy sources.\nMay slightly soften the image.")
        video_layout.addWidget(self.denoise_check)
        
        layout.addWidget(video_group)
        
        # === Audio Filters ===
        audio_group = QGroupBox("Audio Filters")
        audio_layout = QVBoxLayout(audio_group)
        
        # Audio Denoise
        self.audio_denoise_check = QCheckBox("Audio Denoise (afftdn)")
        self.audio_denoise_check.setChecked(self.app_state.filters.audio_denoise)
        self.audio_denoise_check.setToolTip(
            "Reduce background noise in audio using FFT-based denoising.\n"
            "Best for removing hiss, static, or background noise.\n"
            "Uses preset settings optimized for general use."
        )
        audio_layout.addWidget(self.audio_denoise_check)
        
        vol_layout = QHBoxLayout()
        self.vol_check = QCheckBox("Enable Volume:")
        self.vol_check.setChecked(self.app_state.filters.volume_enabled)
        self.vol_check.setToolTip("Adjust audio volume level.")
        vol_layout.addWidget(self.vol_check)
        
        self.vol_edit = QLineEdit(str(self.app_state.filters.volume_db))
        self.vol_edit.setMaximumWidth(60)
        self.vol_edit.setEnabled(self.app_state.filters.volume_enabled)
        self.vol_edit.setToolTip(
            "Volume adjustment in decibels (dB):\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "+10 dB = ~3x louder\n"
            "+6 dB = ~2x louder\n"
            "+3 dB = ~1.4x louder\n"
            " 0 dB = no change\n"
            "-3 dB = ~0.7x quieter\n"
            "-6 dB = ~0.5x quieter\n"
            "-10 dB = ~0.3x quieter\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "Examples: 3, -5, 10, -10"
        )
        vol_layout.addWidget(self.vol_edit)
        
        vol_layout.addWidget(QLabel("dB"))
        vol_layout.addStretch()
        audio_layout.addLayout(vol_layout)
        
        # Volume examples label
        vol_info = QLabel("Examples: +3 (louder), -5 (quieter)")
        vol_info.setStyleSheet("color: gray; font-size: 10px;")
        audio_layout.addWidget(vol_info)
        
        layout.addWidget(audio_group)
        
        layout.addStretch()
        
    def connect_signals(self):
        """Connect UI signals to handlers"""
        self.deint_check.toggled.connect(self.on_deint_changed)
        self.denoise_check.toggled.connect(self.on_denoise_changed)
        self.audio_denoise_check.toggled.connect(self.on_audio_denoise_changed)
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
        
    def on_audio_denoise_changed(self, checked):
        """Handle audio denoise checkbox change"""
        self.app_state.filters.audio_denoise = checked
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
