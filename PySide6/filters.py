"""
Video and Audio Filters Panel (PySide6)
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QLineEdit, QGroupBox, QFrame, QSpinBox, QComboBox, QSlider,
    QPushButton
)
from PySide6.QtCore import Signal, Qt

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

        # Sharpen filter
        self.sharpen_check = QCheckBox("Sharpen (Unsharp)")
        self.sharpen_check.setChecked(self.app_state.filters.sharpen)
        self.sharpen_check.setToolTip(
            "Sharpen video using unsharp mask filter.\n"
            "Adds contrast to edges for increased clarity.\n"
            "Useful for blurry or soft video sources."
        )
        video_layout.addWidget(self.sharpen_check)

        sharpen_layout = QHBoxLayout()
        sharpen_layout.addWidget(QLabel("  Strength:"))
        self.sharpen_amount_slider = QSlider(Qt.Horizontal)
        self.sharpen_amount_slider.setRange(30, 200)
        self.sharpen_amount_slider.setValue(int(self.app_state.filters.sharpen_amount * 100))
        self.sharpen_amount_slider.setMaximumWidth(120)
        self.sharpen_amount_slider.setEnabled(self.app_state.filters.sharpen)
        self.sharpen_amount_slider.setToolTip("Sharpen strength: 0.3 = light, 1.0 = normal, 2.0 = strong")
        sharpen_layout.addWidget(self.sharpen_amount_slider)
        self.sharpen_amount_label = QLabel(f"{self.app_state.filters.sharpen_amount:.1f}")
        sharpen_layout.addWidget(self.sharpen_amount_label)
        sharpen_layout.addStretch()
        video_layout.addLayout(sharpen_layout)

        # CAS filter (Contrast Adaptive Sharpen)
        self.cas_check = QCheckBox("CAS (Contrast Adaptive Sharpen)")
        self.cas_check.setChecked(self.app_state.filters.cas_enabled)
        self.cas_check.setToolTip(
            "CAS is an edge-aware sharpening filter.\n"
            "Better than unsharp - no halos around edges.\n"
            "Useful for improving video clarity."
        )
        video_layout.addWidget(self.cas_check)

        cas_layout = QHBoxLayout()
        cas_layout.addWidget(QLabel("  Strength:"))
        self.cas_strength_slider = QSlider(Qt.Horizontal)
        self.cas_strength_slider.setRange(0, 100)
        self.cas_strength_slider.setValue(int(self.app_state.filters.cas_strength * 100))
        self.cas_strength_slider.setMaximumWidth(120)
        self.cas_strength_slider.setEnabled(self.app_state.filters.cas_enabled)
        self.cas_strength_slider.setToolTip("CAS strength: 0.0 = off, 1.0 = normal, 2.0+ = strong")
        cas_layout.addWidget(self.cas_strength_slider)
        self.cas_strength_label = QLabel(f"{self.app_state.filters.cas_strength:.1f}")
        cas_layout.addWidget(self.cas_strength_label)
        cas_layout.addStretch()
        video_layout.addLayout(cas_layout)

        # Deblock filter
        self.deblock_check = QCheckBox("Deblock")
        self.deblock_check.setChecked(self.app_state.filters.deblock)
        self.deblock_check.setToolTip(
            "Reduce block artifacts from compression.\n"
            "Good for low-quality or highly compressed video.\n"
            "Uses FFmpeg's deblock filter."
        )
        video_layout.addWidget(self.deblock_check)

        deblock_layout = QHBoxLayout()
        deblock_layout.addWidget(QLabel("  Strength:"))
        self.deblock_strength_slider = QSlider(Qt.Horizontal)
        self.deblock_strength_slider.setRange(10, 100)
        self.deblock_strength_slider.setValue(int(self.app_state.filters.deblock_strength * 100))
        self.deblock_strength_slider.setMaximumWidth(120)
        self.deblock_strength_slider.setEnabled(self.app_state.filters.deblock)
        self.deblock_strength_slider.setToolTip("Deblock strength: 0.1 = light, 0.5 = normal, 1.0 = strong")
        deblock_layout.addWidget(self.deblock_strength_slider)
        self.deblock_strength_label = QLabel(f"{self.app_state.filters.deblock_strength:.1f}")
        deblock_layout.addWidget(self.deblock_strength_label)
        deblock_layout.addStretch()
        video_layout.addLayout(deblock_layout)

        # === Smart Crop (Black Bar Removal) ===
        smart_crop_group = QGroupBox("Smart Crop (Black Bar Removal)")
        smart_crop_layout = QVBoxLayout(smart_crop_group)

        self.smart_crop_check = QCheckBox("Enable Smart Crop")
        self.smart_crop_check.setChecked(self.app_state.filters.smart_crop_enabled)
        self.smart_crop_check.setToolTip(
            "Automatically detect and remove black bars from video edges.\n"
            "Uses FFmpeg's cropdetect filter to find black borders.\n"
            "Perfect for removing letterbox/pillarbox bars from videos."
        )
        smart_crop_layout.addWidget(self.smart_crop_check)

        # Mode selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))
        self.smart_crop_mode_combo = QComboBox()
        self.smart_crop_mode_combo.addItems(["Auto Detect", "Manual"])
        self.smart_crop_mode_combo.setCurrentText("Auto Detect" if self.app_state.filters.smart_crop_mode == "auto" else "Manual")
        self.smart_crop_mode_combo.setEnabled(self.app_state.filters.smart_crop_enabled)
        self.smart_crop_mode_combo.setToolTip(
            "Auto Detect: Uses preset crop values (adjustable below)\n"
            "Manual: Use exact crop values with custom X/Y offsets"
        )
        mode_layout.addWidget(self.smart_crop_mode_combo)
        mode_layout.addStretch()
        smart_crop_layout.addLayout(mode_layout)

        # Manual crop dimensions
        manual_layout = QHBoxLayout()
        manual_layout.addWidget(QLabel("Width:"))
        self.smart_crop_w_spin = QSpinBox()
        self.smart_crop_w_spin.setRange(16, 9999)  # Min 16 for codec compatibility
        self.smart_crop_w_spin.setValue(self.app_state.filters.smart_crop_w or 640)
        self.smart_crop_w_spin.setMaximumWidth(70)
        self.smart_crop_w_spin.setToolTip("Crop width (min: 16)")
        self.smart_crop_w_spin.setEnabled(self.app_state.filters.smart_crop_enabled)
        manual_layout.addWidget(self.smart_crop_w_spin)

        manual_layout.addWidget(QLabel("Height:"))
        self.smart_crop_h_spin = QSpinBox()
        self.smart_crop_h_spin.setRange(16, 9999)  # Min 16 for codec compatibility
        self.smart_crop_h_spin.setValue(self.app_state.filters.smart_crop_h or 480)
        self.smart_crop_h_spin.setMaximumWidth(70)
        self.smart_crop_h_spin.setToolTip("Crop height (min: 16)")
        self.smart_crop_h_spin.setEnabled(self.app_state.filters.smart_crop_enabled)
        manual_layout.addWidget(self.smart_crop_h_spin)
        manual_layout.addStretch()
        smart_crop_layout.addLayout(manual_layout)

        # Crop offset
        offset_layout = QHBoxLayout()
        offset_layout.addWidget(QLabel("X Offset:"))
        self.smart_crop_x_spin = QSpinBox()
        self.smart_crop_x_spin.setRange(0, 9999)
        self.smart_crop_x_spin.setValue(self.app_state.filters.smart_crop_x)
        self.smart_crop_x_spin.setMaximumWidth(70)
        self.smart_crop_x_spin.setToolTip("Horizontal offset for crop (usually 0 for centered)")
        self.smart_crop_x_spin.setEnabled(self.app_state.filters.smart_crop_enabled and self.app_state.filters.smart_crop_mode == "manual")
        offset_layout.addWidget(self.smart_crop_x_spin)

        offset_layout.addWidget(QLabel("Y Offset:"))
        self.smart_crop_y_spin = QSpinBox()
        self.smart_crop_y_spin.setRange(0, 9999)
        self.smart_crop_y_spin.setValue(self.app_state.filters.smart_crop_y)
        self.smart_crop_y_spin.setMaximumWidth(70)
        self.smart_crop_y_spin.setToolTip("Vertical offset for crop (usually 0 for centered)")
        self.smart_crop_y_spin.setEnabled(self.app_state.filters.smart_crop_enabled and self.app_state.filters.smart_crop_mode == "manual")
        offset_layout.addWidget(self.smart_crop_y_spin)
        offset_layout.addStretch()
        smart_crop_layout.addLayout(offset_layout)

        # Show preview
        self.smart_crop_preview_check = QCheckBox("Show Crop Preview (Green Border)")
        self.smart_crop_preview_check.setChecked(self.app_state.filters.smart_crop_show_preview)
        self.smart_crop_preview_check.setToolTip(
            "Show a green rectangle indicating the crop area.\n"
            "Useful for verifying the crop region before encoding."
        )
        self.smart_crop_preview_check.setEnabled(self.app_state.filters.smart_crop_enabled)
        smart_crop_layout.addWidget(self.smart_crop_preview_check)

        video_layout.addWidget(smart_crop_group)


        # === Aspect Ratio Conversion ===
        ar_group = QGroupBox("Aspect Ratio Converter")
        ar_layout = QVBoxLayout(ar_group)

        self.ar_check = QCheckBox("Enable AR Conversion")
        self.ar_check.setChecked(self.app_state.filters.ar_convert_enabled)
        self.ar_check.setToolTip(
            "Convert video to a different aspect ratio.\n"
            "Useful for converting 4:3 to 16:9 or vice versa."
        )
        ar_layout.addWidget(self.ar_check)

        # Target AR
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Target Aspect Ratio:"))
        self.ar_target_combo = QComboBox()
        self.ar_target_combo.addItems(["16:9 (Widescreen)", "4:3 (Standard)", "1:1 (Square)", "2.35:1 (Cinemascope)"])
        self.ar_target_combo.setCurrentText(self.app_state.filters.ar_target.replace(":", ":") + " (Widescreen)" if self.app_state.filters.ar_target == "16:9" else 
                                        self.app_state.filters.ar_target.replace(":", ":") + " (Standard)" if self.app_state.filters.ar_target == "4:3" else
                                        self.app_state.filters.ar_target.replace(":", ":") + " (Square)" if self.app_state.filters.ar_target == "1:1" else
                                        self.app_state.filters.ar_target.replace(":", ":") + " (Cinemascope)")
        self.ar_target_combo.setEnabled(self.app_state.filters.ar_convert_enabled)
        target_layout.addWidget(self.ar_target_combo)
        target_layout.addStretch()
        ar_layout.addLayout(target_layout)

        # Method
        method_layout = QHBoxLayout()
        method_layout.addWidget(QLabel("Method:"))
        self.ar_method_combo = QComboBox()
        self.ar_method_combo.addItems(["Crop (cut edges)", "Pad (black bars)", "Stretch (distort)", "Scale (2-step)"])
        self.ar_method_combo.setCurrentText(self.app_state.filters.ar_method.replace("crop", "Crop (cut edges)").replace("pad", "Pad (black bars)").replace("stretch", "Stretch (distort)").replace("scale_2step", "Scale (2-step)"))
        self.ar_method_combo.setEnabled(self.app_state.filters.ar_convert_enabled)
        self.ar_method_combo.setToolTip(
            "Crop: Cut edges to fit target AR (may lose video content)\n"
            "Pad: Add black bars to reach target AR\n"
            "Stretch: Stretch to fit (may distort image)"
        )
        method_layout.addWidget(self.ar_method_combo)
        method_layout.addStretch()
        ar_layout.addLayout(method_layout)

        video_layout.addWidget(ar_group)

        # === Delogo (Logo Removal) ===
        delogo_group = QGroupBox("Logo / Watermark Removal")
        delogo_layout = QVBoxLayout(delogo_group)
        
        self.delogo_check = QCheckBox("Enable Delogo Filter")
        self.delogo_check.setChecked(self.app_state.filters.delogo_enabled)
        self.delogo_check.setToolTip(
            "Apply delogo filter to remove TV channel logos, watermarks, or static overlays.\n"
            "Uses FFmpeg's delogo filter to blur a specified rectangular area.\n\n"
            "Tip: Use a small 'band' value for sharp logo edges, higher for soft edges."
        )
        delogo_layout.addWidget(self.delogo_check)
        
        # Position controls
        pos_layout = QHBoxLayout()
        pos_layout.addWidget(QLabel("Position:"))
        
        pos_layout.addWidget(QLabel("X:"))
        self.delogo_x_spin = QSpinBox()
        self.delogo_x_spin.setRange(0, 9999)
        self.delogo_x_spin.setValue(self.app_state.filters.delogo_x)
        self.delogo_x_spin.setMaximumWidth(70)
        self.delogo_x_spin.setToolTip("X coordinate of the logo area (top-left corner)")
        self.delogo_x_spin.setEnabled(self.app_state.filters.delogo_enabled)
        pos_layout.addWidget(self.delogo_x_spin)
        
        pos_layout.addWidget(QLabel("Y:"))
        self.delogo_y_spin = QSpinBox()
        self.delogo_y_spin.setRange(0, 9999)
        self.delogo_y_spin.setValue(self.app_state.filters.delogo_y)
        self.delogo_y_spin.setMaximumWidth(70)
        self.delogo_y_spin.setToolTip("Y coordinate of the logo area (top-left corner)")
        self.delogo_y_spin.setEnabled(self.app_state.filters.delogo_enabled)
        pos_layout.addWidget(self.delogo_y_spin)
        
        pos_layout.addStretch()
        delogo_layout.addLayout(pos_layout)
        
        # Size controls
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Size:"))
        
        size_layout.addWidget(QLabel("W:"))
        self.delogo_w_spin = QSpinBox()
        self.delogo_w_spin.setRange(1, 9999)
        self.delogo_w_spin.setValue(self.app_state.filters.delogo_w)
        self.delogo_w_spin.setMaximumWidth(70)
        self.delogo_w_spin.setToolTip("Width of the logo area")
        self.delogo_w_spin.setEnabled(self.app_state.filters.delogo_enabled)
        size_layout.addWidget(self.delogo_w_spin)
        
        size_layout.addWidget(QLabel("H:"))
        self.delogo_h_spin = QSpinBox()
        self.delogo_h_spin.setRange(1, 9999)
        self.delogo_h_spin.setValue(self.app_state.filters.delogo_h)
        self.delogo_h_spin.setMaximumWidth(70)
        self.delogo_h_spin.setToolTip("Height of the logo area")
        self.delogo_h_spin.setEnabled(self.app_state.filters.delogo_enabled)
        size_layout.addWidget(self.delogo_h_spin)
        
        size_layout.addStretch()
        delogo_layout.addLayout(size_layout)
        
        # Band (edge softness)
        band_layout = QHBoxLayout()
        band_layout.addWidget(QLabel("Band (softness):"))
        self.delogo_band_spin = QSpinBox()
        self.delogo_band_spin.setRange(0, 20)
        self.delogo_band_spin.setValue(self.app_state.filters.delogo_band)
        self.delogo_band_spin.setMaximumWidth(60)
        self.delogo_band_spin.setToolTip(
            "Band size for edge smoothing.\n"
            "0 = sharp edges\n"
            "1-5 = slight blur\n"
            "10+ = heavy blur\n\n"
            "Use lower values for sharp logo edges."
        )
        self.delogo_band_spin.setEnabled(self.app_state.filters.delogo_enabled)
        band_layout.addWidget(self.delogo_band_spin)
        
        band_layout.addStretch()
        delogo_layout.addLayout(band_layout)
        
        # Show preview rectangle
        self.delogo_show_check = QCheckBox("Show Preview Rectangle")
        self.delogo_show_check.setChecked(getattr(self.app_state.filters, 'delogo_show', False))
        self.delogo_show_check.setToolTip(
            "Show a red rectangle outline on the video\nto help position the delogo area correctly.\n\n"
            "The rectangle will appear during encoding."
        )
        self.delogo_show_check.setEnabled(self.app_state.filters.delogo_enabled)
        delogo_layout.addWidget(self.delogo_show_check)
        
        video_layout.addWidget(delogo_group)
        
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
        
        # Dynamic Audio Normalizer
        self.dynnorm_check = QCheckBox("Dynamic Normalizer (dynaudnorm)")
        self.dynnorm_check.setChecked(self.app_state.filters.audio_dynnorm)
        self.dynnorm_check.setToolTip(
            "Dynamically normalize audio volume.\n"
            "Best for videos with quiet dialogue and loud music.\n"
            "Automatically boosts quiet parts and reduces loud parts."
        )
        audio_layout.addWidget(self.dynnorm_check)
        
        # Audio Compressor
        self.compressor_check = QCheckBox("Audio Compressor (acompressor)")
        self.compressor_check.setChecked(self.app_state.filters.audio_compressor)
        self.compressor_check.setToolTip(
            "Reduce dynamic range of audio.\n"
            "Makes quiet sounds louder and loud sounds quieter.\n"
            "Good for dialogue clarity in movies/TV shows."
        )
        audio_layout.addWidget(self.compressor_check)
        
        # Audio Delay / Sync
        delay_layout = QHBoxLayout()
        self.audio_delay_check = QCheckBox("Audio Delay:")
        self.audio_delay_check.setChecked(self.app_state.filters.audio_delay_enabled)
        self.audio_delay_check.setToolTip(
            "Delay audio to sync with video.\n"
            "Use when audio plays ahead of video.\n"
            "Values: 100-500ms for minor sync, 1000ms+ for major offset."
        )
        delay_layout.addWidget(self.audio_delay_check)
        
        self.audio_delay_spin = QSpinBox()
        self.audio_delay_spin.setRange(0, 10000)
        self.audio_delay_spin.setValue(self.app_state.filters.audio_delay_ms)
        self.audio_delay_spin.setSuffix(" ms")
        self.audio_delay_spin.setSingleStep(50)
        self.audio_delay_spin.setEnabled(self.app_state.filters.audio_delay_enabled)
        self.audio_delay_spin.setMinimumWidth(100)
        self.audio_delay_spin.setToolTip(
            "Delay in milliseconds (0 = no delay).\n"
            "Common values:\n"
            "  100ms: Very slight sync fix\n"
            "  250ms: Minor offset\n"
            "  500ms: Notable offset\n"
            "  1000ms: Audio is ~1 second ahead\n"
            "  2000ms+: Major offset"
        )
        delay_layout.addWidget(self.audio_delay_spin)
        delay_layout.addStretch()
        audio_layout.addLayout(delay_layout)
        
        layout.addWidget(audio_group)
        
        # Reset button
        reset_layout = QHBoxLayout()
        reset_layout.addStretch()
        self.reset_btn = QPushButton("Reset All Filters")
        self.reset_btn.clicked.connect(self.reset_filters)
        self.reset_btn.setToolTip("Reset all video and audio filters to default values")
        reset_layout.addWidget(self.reset_btn)
        reset_layout.addStretch()
        layout.addLayout(reset_layout)
        
        layout.addStretch()
        
    def connect_signals(self):
        """Connect UI signals to handlers"""
        self.deint_check.toggled.connect(self.on_deint_changed)
        self.denoise_check.toggled.connect(self.on_denoise_changed)
        self.sharpen_check.toggled.connect(self.on_sharpen_changed)
        self.sharpen_amount_slider.valueChanged.connect(self.on_sharpen_amount_changed)
        self.cas_check.toggled.connect(self.on_cas_changed)
        self.cas_strength_slider.valueChanged.connect(self.on_cas_strength_changed)
        self.deblock_check.toggled.connect(self.on_deblock_changed)
        self.deblock_strength_slider.valueChanged.connect(self.on_deblock_strength_changed)
        # Smart Crop signals
        self.smart_crop_check.toggled.connect(self.on_smart_crop_changed)
        self.smart_crop_mode_combo.currentTextChanged.connect(self.on_smart_crop_mode_changed)
        self.smart_crop_w_spin.valueChanged.connect(self.on_smart_crop_w_changed)
        self.smart_crop_h_spin.valueChanged.connect(self.on_smart_crop_h_changed)
        self.smart_crop_x_spin.valueChanged.connect(self.on_smart_crop_x_changed)
        self.smart_crop_y_spin.valueChanged.connect(self.on_smart_crop_y_changed)
        self.smart_crop_preview_check.toggled.connect(self.on_smart_crop_preview_changed)
        # Aspect ratio signals
        self.ar_check.toggled.connect(self.on_ar_changed)
        self.ar_target_combo.currentTextChanged.connect(self.on_ar_target_changed)
        self.ar_method_combo.currentTextChanged.connect(self.on_ar_method_changed)
        # Delogo signals
        self.delogo_check.toggled.connect(self.on_delogo_changed)
        self.delogo_x_spin.valueChanged.connect(self.on_delogo_x_changed)
        self.delogo_y_spin.valueChanged.connect(self.on_delogo_y_changed)
        self.delogo_w_spin.valueChanged.connect(self.on_delogo_w_changed)
        self.delogo_h_spin.valueChanged.connect(self.on_delogo_h_changed)
        self.delogo_band_spin.valueChanged.connect(self.on_delogo_band_changed)
        self.delogo_show_check.toggled.connect(self.on_delogo_show_changed)
        # Audio signals
        self.audio_denoise_check.toggled.connect(self.on_audio_denoise_changed)
        self.vol_check.toggled.connect(self.on_vol_enabled_changed)
        self.vol_edit.textChanged.connect(self.on_vol_changed)
        self.dynnorm_check.toggled.connect(self.on_dynnorm_changed)
        self.compressor_check.toggled.connect(self.on_compressor_changed)
        self.audio_delay_check.toggled.connect(self.on_audio_delay_changed)
        self.audio_delay_spin.valueChanged.connect(self.on_audio_delay_value_changed)
        
    def on_deint_changed(self, checked):
        """Handle deinterlace checkbox change"""
        self.app_state.filters.deinterlace = checked
        self.settings_changed.emit()
        
    def on_denoise_changed(self, checked):
        """Handle denoise checkbox change"""
        self.app_state.filters.denoise = checked
        self.settings_changed.emit()

    def on_sharpen_changed(self, checked):
        """Handle sharpen checkbox change"""
        self.app_state.filters.sharpen = checked
        self.sharpen_amount_slider.setEnabled(checked)
        if checked:
            self.cas_check.setChecked(False)
            self.app_state.filters.cas_enabled = False
            self.cas_strength_slider.setEnabled(False)
        self.settings_changed.emit()

    def on_sharpen_amount_changed(self, value):
        """Handle sharpen amount slider change"""
        self.app_state.filters.sharpen_amount = value / 100.0
        self.sharpen_amount_label.setText(f"{self.app_state.filters.sharpen_amount:.1f}")
        self.settings_changed.emit()

    def on_cas_changed(self, checked):
        """Handle CAS checkbox change"""
        self.app_state.filters.cas_enabled = checked
        self.cas_strength_slider.setEnabled(checked)
        if checked:
            self.sharpen_check.setChecked(False)
            self.app_state.filters.sharpen = False
            self.sharpen_amount_slider.setEnabled(False)
        self.settings_changed.emit()

    def on_cas_strength_changed(self, value):
        """Handle CAS strength slider change"""
        self.app_state.filters.cas_strength = value / 100.0
        self.cas_strength_label.setText(f"{self.app_state.filters.cas_strength:.1f}")
        self.settings_changed.emit()

    def on_deblock_changed(self, checked):
        """Handle deblock checkbox change"""
        self.app_state.filters.deblock = checked
        self.deblock_strength_slider.setEnabled(checked)
        self.settings_changed.emit()

    def on_deblock_strength_changed(self, value):
        """Handle deblock strength slider change"""
        self.app_state.filters.deblock_strength = value / 100.0
        self.deblock_strength_label.setText(f"{self.app_state.filters.deblock_strength:.1f}")
        self.settings_changed.emit()

    # Smart Crop handlers
    def on_smart_crop_changed(self, checked):
        """Handle smart crop checkbox change"""
        self.app_state.filters.smart_crop_enabled = checked
        # Enable/disable controls
        self.smart_crop_mode_combo.setEnabled(checked)
        self.smart_crop_preview_check.setEnabled(checked)
        is_manual = self.smart_crop_mode_combo.currentText() == "Manual"
        # Width/height always editable (preset in auto, exact in manual)
        self.smart_crop_w_spin.setEnabled(checked)
        self.smart_crop_h_spin.setEnabled(checked)
        # X/Y offset only in manual mode (auto centers automatically)
        self.smart_crop_x_spin.setEnabled(checked and is_manual)
        self.smart_crop_y_spin.setEnabled(checked and is_manual)
        self.settings_changed.emit()

    def on_smart_crop_mode_changed(self, text):
        """Handle smart crop mode change"""
        self.app_state.filters.smart_crop_mode = "auto" if text == "Auto Detect" else "manual"
        is_manual = text == "Manual"
        is_enabled = self.smart_crop_check.isChecked()
        # Width/height always editable, X/Y only in manual mode
        self.smart_crop_x_spin.setEnabled(is_enabled and is_manual)
        self.smart_crop_y_spin.setEnabled(is_enabled and is_manual)
        self.settings_changed.emit()

    def on_smart_crop_w_changed(self, value):
        """Handle smart crop width change"""
        self.app_state.filters.smart_crop_w = value
        self.settings_changed.emit()

    def on_smart_crop_h_changed(self, value):
        """Handle smart crop height change"""
        self.app_state.filters.smart_crop_h = value
        self.settings_changed.emit()

    def on_smart_crop_x_changed(self, value):
        """Handle smart crop x offset change"""
        self.app_state.filters.smart_crop_x = value
        self.settings_changed.emit()

    def on_smart_crop_y_changed(self, value):
        """Handle smart crop y offset change"""
        self.app_state.filters.smart_crop_y = value
        self.settings_changed.emit()

    def on_smart_crop_preview_changed(self, checked):
        """Handle smart crop preview checkbox change"""
        self.app_state.filters.smart_crop_show_preview = checked
        self.settings_changed.emit()

    # Aspect Ratio conversion handlers
    def on_ar_changed(self, checked):
        """Handle AR conversion checkbox change"""
        self.app_state.filters.ar_convert_enabled = checked
        # Enable/disable controls
        self.ar_target_combo.setEnabled(checked)
        self.ar_method_combo.setEnabled(checked)
        self.settings_changed.emit()

    def on_ar_target_changed(self, text):
        """Handle AR target change"""
        # Extract just the AR part (e.g., "16:9" from "16:9 (Widescreen)")
        ar = text.split()[0] if text else "16:9"
        self.app_state.filters.ar_target = ar
        self.settings_changed.emit()

    def on_ar_method_changed(self, text):
        """Handle AR method change"""
        # Extract method from text
        if "Crop" in text:
            method = "crop"
        elif "Pad" in text:
            method = "pad"
        elif "Scale" in text:
            method = "scale_2step"
        else:
            method = "stretch"
        self.app_state.filters.ar_method = method
        self.settings_changed.emit()

    def on_delogo_changed(self, checked):
        """Handle delogo checkbox change"""
        self.app_state.filters.delogo_enabled = checked
        # Enable/disable spin boxes
        self.delogo_x_spin.setEnabled(checked)
        self.delogo_y_spin.setEnabled(checked)
        self.delogo_w_spin.setEnabled(checked)
        self.delogo_h_spin.setEnabled(checked)
        self.delogo_band_spin.setEnabled(checked)
        self.delogo_show_check.setEnabled(checked)
        self.settings_changed.emit()
        
    def on_delogo_x_changed(self, value):
        """Handle delogo X position change"""
        self.app_state.filters.delogo_x = value
        self.settings_changed.emit()
        
    def on_delogo_y_changed(self, value):
        """Handle delogo Y position change"""
        self.app_state.filters.delogo_y = value
        self.settings_changed.emit()
        
    def on_delogo_w_changed(self, value):
        """Handle delogo width change"""
        self.app_state.filters.delogo_w = value
        self.settings_changed.emit()
        
    def on_delogo_h_changed(self, value):
        """Handle delogo height change"""
        self.app_state.filters.delogo_h = value
        self.settings_changed.emit()
        
    def on_delogo_band_changed(self, value):
        """Handle delogo band (edge softness) change"""
        self.app_state.filters.delogo_band = value
        self.settings_changed.emit()
        
    def on_delogo_show_changed(self, checked):
        """Handle delogo show preview rectangle change"""
        self.app_state.filters.delogo_show = checked
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
    
    def on_dynnorm_changed(self, checked):
        """Handle dynamic normalizer checkbox change"""
        self.app_state.filters.audio_dynnorm = checked
        self.settings_changed.emit()
    
    def on_compressor_changed(self, checked):
        """Handle audio compressor checkbox change"""
        self.app_state.filters.audio_compressor = checked
        self.settings_changed.emit()
        
    def on_audio_delay_changed(self, checked):
        self.app_state.filters.audio_delay_enabled = checked
        self.audio_delay_spin.setEnabled(checked)
        self.settings_changed.emit()
    
    def on_audio_delay_value_changed(self, value):
        self.app_state.filters.audio_delay_ms = value
        self.settings_changed.emit()
        
    def reset_filters(self):
        """Reset all filter settings to defaults"""
        # Video filters
        self.app_state.filters.deinterlace = False
        self.app_state.filters.denoise = False
        self.app_state.filters.sharpen = False
        self.app_state.filters.sharpen_amount = 1.0
        self.app_state.filters.cas_enabled = False
        self.app_state.filters.cas_strength = 0.0
        self.app_state.filters.deblock = False
        self.app_state.filters.deblock_strength = 0.5
        
        # Smart Crop
        self.app_state.filters.smart_crop_enabled = False
        self.app_state.filters.smart_crop_mode = "auto"
        self.app_state.filters.smart_crop_w = 640
        self.app_state.filters.smart_crop_h = 480
        self.app_state.filters.smart_crop_x = 0
        self.app_state.filters.smart_crop_y = 0
        self.app_state.filters.smart_crop_show_preview = False
        
        # Aspect Ratio
        self.app_state.filters.ar_convert_enabled = False
        self.app_state.filters.ar_target = "16:9"
        self.app_state.filters.ar_method = "crop"
        
        # Delogo
        self.app_state.filters.delogo_enabled = False
        self.app_state.filters.delogo_x = 0
        self.app_state.filters.delogo_y = 0
        self.app_state.filters.delogo_w = 100
        self.app_state.filters.delogo_h = 30
        self.app_state.filters.delogo_band = 1
        self.app_state.filters.delogo_show = False
        
        # Audio filters
        self.app_state.filters.audio_denoise = False
        self.app_state.filters.volume_enabled = False
        self.app_state.filters.volume_db = 0.0
        self.app_state.filters.audio_dynnorm = False
        self.app_state.filters.audio_compressor = False
        self.app_state.filters.audio_delay_enabled = False
        self.app_state.filters.audio_delay_ms = 0
        
        # Update UI controls
        self.deint_check.setChecked(False)
        self.denoise_check.setChecked(False)
        self.sharpen_check.setChecked(False)
        self.sharpen_amount_slider.setValue(100)
        self.sharpen_amount_label.setText("1.0")
        self.sharpen_amount_slider.setEnabled(False)
        self.cas_check.setChecked(False)
        self.cas_strength_slider.setValue(0)
        self.cas_strength_label.setText("0.0")
        self.cas_strength_slider.setEnabled(False)
        self.deblock_check.setChecked(False)
        self.deblock_strength_slider.setValue(50)
        self.deblock_strength_label.setText("0.5")
        self.deblock_strength_slider.setEnabled(False)
        
        self.smart_crop_check.setChecked(False)
        self.smart_crop_mode_combo.setCurrentText("Auto Detect")
        self.smart_crop_w_spin.setValue(640)
        self.smart_crop_h_spin.setValue(480)
        self.smart_crop_x_spin.setValue(0)
        self.smart_crop_y_spin.setValue(0)
        self.smart_crop_preview_check.setChecked(False)
        self.smart_crop_mode_combo.setEnabled(False)
        self.smart_crop_w_spin.setEnabled(False)
        self.smart_crop_h_spin.setEnabled(False)
        self.smart_crop_x_spin.setEnabled(False)
        self.smart_crop_y_spin.setEnabled(False)
        self.smart_crop_preview_check.setEnabled(False)
        
        self.ar_check.setChecked(False)
        self.ar_target_combo.setCurrentText("16:9 (Widescreen)")
        self.ar_method_combo.setCurrentText("Crop (cut edges)")
        self.ar_target_combo.setEnabled(False)
        self.ar_method_combo.setEnabled(False)
        
        self.delogo_check.setChecked(False)
        self.delogo_x_spin.setValue(0)
        self.delogo_y_spin.setValue(0)
        self.delogo_w_spin.setValue(100)
        self.delogo_h_spin.setValue(30)
        self.delogo_band_spin.setValue(1)
        self.delogo_show_check.setChecked(False)
        self.delogo_x_spin.setEnabled(False)
        self.delogo_y_spin.setEnabled(False)
        self.delogo_w_spin.setEnabled(False)
        self.delogo_h_spin.setEnabled(False)
        self.delogo_band_spin.setEnabled(False)
        self.delogo_show_check.setEnabled(False)
        
        self.audio_denoise_check.setChecked(False)
        self.vol_check.setChecked(False)
        self.vol_edit.setText("0.0")
        self.vol_edit.setEnabled(False)
        self.dynnorm_check.setChecked(False)
        self.compressor_check.setChecked(False)
        self.audio_delay_check.setChecked(False)
        self.audio_delay_spin.setValue(0)
        self.audio_delay_spin.setEnabled(False)
        
        self.app_state.log("Filters reset to defaults", "INFO")
        self.settings_changed.emit()
