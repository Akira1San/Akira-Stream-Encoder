"""
Encoding Settings Panel (PySide6)
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QCheckBox, QSlider, QSpinBox, QLineEdit, QGroupBox,
    QRadioButton, QButtonGroup, QFrame
)
from PySide6.QtCore import Qt, Signal

from models import AppState


class EncodingPanel(QWidget):
    """Panel for encoding settings"""
    
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
        
        # === GPU & Encoder (Vertical Layout) ===
        
        # GPU Checkbox
        self.gpu_check = QCheckBox("Use GPU (NVENC)")
        self.gpu_check.setChecked(self.app_state.encoding.use_gpu)
        self.gpu_check.setToolTip("Enable NVIDIA GPU acceleration for faster encoding.\nRequires NVIDIA graphics card with NVENC support.")
        layout.addWidget(self.gpu_check)
        
        # Encoder Row
        encoder_layout = QHBoxLayout()
        encoder_layout.addWidget(QLabel("Encoder:"))
        self.encoder_combo = QComboBox()
        self.encoder_combo.addItems([
            "h264_nvenc", "hevc_nvenc", "libx264", "libx265"
        ])
        self.encoder_combo.setCurrentText(self.app_state.encoding.encoder)
        self.encoder_combo.setMinimumWidth(140)
        self.encoder_combo.setToolTip("Video codec to use:\nh264_nvenc: H.264 with GPU acceleration\nhevc_nvenc: H.265/HEVC with GPU (smaller files)\nlibx264: H.264 CPU encoding (compatible)\nlibx265: H.265/HEVC CPU (best compression)")
        encoder_layout.addWidget(self.encoder_combo)
        encoder_layout.addStretch()
        layout.addLayout(encoder_layout)
        
        # Video Mode Row
        video_mode_layout = QHBoxLayout()
        video_mode_layout.addWidget(QLabel("Video:"))
        self.video_mode_combo = QComboBox()
        self.video_mode_combo.addItems(["Encode", "Copy"])
        self.video_mode_combo.setCurrentText(self.app_state.encoding.video_mode.capitalize())
        self.video_mode_combo.setMinimumWidth(100)
        self.video_mode_combo.setToolTip("Video processing mode:\nEncode: Re-encode video with selected codec\nCopy: Copy video stream without re-encoding (faster)")
        video_mode_layout.addWidget(self.video_mode_combo)
        video_mode_layout.addStretch()
        layout.addLayout(video_mode_layout)
        
        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # === Resolution & Framerate ===
        res_frame = QFrame()
        res_layout = QHBoxLayout(res_frame)
        res_layout.setContentsMargins(0, 0, 0, 0)
        
        res_layout.addWidget(QLabel("Resolution:"))
        
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems([
            "none", "1920x1080", "1280x720", "720x480",
            "720x404", "720x400", "640x480", "640x368"
        ])
        self.resolution_combo.setCurrentText(self.app_state.encoding.resolution)
        self.resolution_combo.setMinimumWidth(120)
        self.resolution_combo.setToolTip("Output video resolution.\n'none' keeps original resolution.\nLower resolutions create smaller files.")
        res_layout.addWidget(self.resolution_combo)
        
        res_layout.addSpacing(20)
        res_layout.addWidget(QLabel("Framerate:"))
        
        # Framerate - fixed at 23.976 fps
        self.framerate_label = QLabel("23.976 fps")
        self.framerate_label.setStyleSheet("color: gray;")
        self.framerate_label.setToolTip("Framerate is fixed at 23.976 fps (24000/1001)")
        res_layout.addWidget(self.framerate_label)
        
        # Always set framerate to 23.976
        self.app_state.encoding.framerate = "24000/1001"
            
        res_layout.addStretch()
        layout.addWidget(res_frame)
        
        # === Quality (CQ) Slider ===
        cq_layout = QHBoxLayout()
        cq_label_widget = QLabel("Quality (CQ):")
        cq_label_widget.setToolTip("Constant Quality (CQ) setting.\n\nLower values = Higher quality, Larger files\nHigher values = Lower quality, Smaller files\n\nRecommended:\n• 18-20: Visually lossless (archiving)\n• 21-23: High quality (default)\n• 24-26: Good quality (smaller files)\n• 27-30: Acceptable (maximum compression)")
        cq_layout.addWidget(cq_label_widget)
        
        self.cq_slider = QSlider(Qt.Horizontal)
        self.cq_slider.setRange(18, 30)
        self.cq_slider.setValue(self.app_state.encoding.cq)
        self.cq_slider.setTickPosition(QSlider.TicksBelow)
        self.cq_slider.setTickInterval(1)
        self.cq_slider.setToolTip(
            "CQ Value Guide:\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "18-20: Visually Lossless\n"
            "  → Perfect quality, large files\n"
            "  → Use for: Archiving masters\n"
            "\n"
            "21-23: High Quality (Default: 23)\n"
            "  → Great quality, moderate size\n"
            "  → Use for: General encoding\n"
            "\n"
            "24-26: Good Quality\n"
            "  → Good balance, smaller files\n"
            "  → Use for: Streaming, web\n"
            "\n"
            "27-30: Acceptable Quality\n"
            "  → Noticeable artifacts, tiny files\n"
            "  → Use for: Mobile, previews\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "Tip: 23 is FFmpeg default"
        )
        cq_layout.addWidget(self.cq_slider)
        
        self.cq_label = QLabel(str(self.app_state.encoding.cq))
        self.cq_label.setMinimumWidth(30)
        self.cq_label.setToolTip("Current CQ value (see slider tooltip for details)")
        cq_layout.addWidget(self.cq_label)
        
        layout.addLayout(cq_layout)
        
        # === Bitrate Controls ===
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # Bitrate Mode
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Bitrate Mode:"))
        
        self.bitrate_mode_combo = QComboBox()
        self.bitrate_mode_combo.addItems(["CBR (Constant Bitrate)"])
        self.bitrate_mode_combo.setCurrentText(self.app_state.encoding.bitrate_mode)
        self.bitrate_mode_combo.setMinimumWidth(180)
        mode_layout.addWidget(self.bitrate_mode_combo)
        
        mode_layout.addStretch()
        layout.addLayout(mode_layout)
        
        # Target Bitrate
        br_layout = QHBoxLayout()
        br_label = QLabel("Target Bitrate (kbps):")
        br_label.setToolTip("Target bitrate for video encoding.\nHigher values = better quality, larger files\n2000-4000 kbps: Good for 720p\n4000-8000 kbps: Good for 1080p")
        br_layout.addWidget(br_label)
        
        self.bitrate_edit = QLineEdit(self.app_state.encoding.target_bitrate)
        self.bitrate_edit.setMaximumWidth(80)
        self.bitrate_edit.setToolTip("Enter target bitrate in kilobits per second (kbps)")
        br_layout.addWidget(self.bitrate_edit)
        
        br_layout.addStretch()
        layout.addLayout(br_layout)
        
        # Use Original Bitrate
        self.orig_br_check = QCheckBox("Use Original Bitrate (if available)")
        self.orig_br_check.setChecked(self.app_state.encoding.use_original_bitrate)
        self.orig_br_check.setToolTip("Use the original video's bitrate if it can be detected.\nOverrides the target bitrate setting above.")
        layout.addWidget(self.orig_br_check)
        
        # Max Bitrate
        max_br_layout = QHBoxLayout()
        max_br_label = QLabel("Max Bitrate (kbps):")
        max_br_label.setToolTip("Maximum allowed bitrate.\nPrevents bitrate spikes that could cause playback issues.")
        max_br_layout.addWidget(max_br_label)
        
        self.max_br_spin = QSpinBox()
        self.max_br_spin.setRange(500, 50000)
        self.max_br_spin.setValue(self.app_state.encoding.max_bitrate)
        self.max_br_spin.setSingleStep(500)
        self.max_br_spin.setToolTip("Maximum bitrate limit")
        max_br_layout.addWidget(self.max_br_spin)
        
        max_br_layout.addStretch()
        layout.addLayout(max_br_layout)
        
        # === Container Format ===
        container_layout = QHBoxLayout()
        container_label = QLabel("Container:")
        container_label.setToolTip("Output file format/container.\nmp4: Best compatibility (recommended)\nmkv: Supports more codecs and features\navi: Older format, limited codec support")
        container_layout.addWidget(container_label)
        
        self.container_combo = QComboBox()
        self.container_combo.addItems(["mp4", "mkv", "avi"])
        self.container_combo.setCurrentText(self.app_state.encoding.container)
        self.container_combo.setToolTip("Select output container format")
        container_layout.addWidget(self.container_combo)
        
        container_layout.addStretch()
        layout.addLayout(container_layout)
        
        # === Scale Filter Section ===
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line2)
        
        # Scale Mode and Algorithm
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("Scale Mode:"))
        
        self.scale_mode_combo = QComboBox()
        self.scale_mode_combo.addItems(["off", "on"])
        self.scale_mode_combo.setCurrentText(self.app_state.encoding.scale_mode)
        self.scale_mode_combo.setToolTip("Enable/disable advanced scaling algorithms.\nOff: Basic scaling\nOn: Use selected algorithm with quality settings")
        scale_layout.addWidget(self.scale_mode_combo)
        
        scale_layout.addSpacing(20)
        scale_layout.addWidget(QLabel("Algorithm:"))
        
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems(["bilinear", "bicubic", "lanczos", "spline", "area"])
        self.algorithm_combo.setCurrentText(self.app_state.encoding.scale_algorithm)
        self.algorithm_combo.setToolTip("Scaling algorithm:\nBilinear: Fast, basic quality\nBicubic: Good balance of speed/quality\nLanczos: High quality, slower\nSpline: Smooth scaling\nArea: Best for downscaling")
        scale_layout.addWidget(self.algorithm_combo)
        
        scale_layout.addStretch()
        layout.addLayout(scale_layout)
        
        # Scale Quality
        scale_quality_layout = QHBoxLayout()
        scale_quality_layout.addWidget(QLabel("Quality:"))
        
        self.scale_quality_combo = QComboBox()
        self.scale_quality_combo.addItems(["speed", "quality"])
        self.scale_quality_combo.setCurrentText(self.app_state.encoding.scale_quality)
        self.scale_quality_combo.setToolTip("Quality vs Speed trade-off:\nSpeed: Faster processing, standard quality\nQuality: Slower processing, enhanced accuracy")
        scale_quality_layout.addWidget(self.scale_quality_combo)
        
        scale_quality_layout.addStretch()
        layout.addLayout(scale_quality_layout)
        
        # === Fast Split Section ===
        line3 = QFrame()
        line3.setFrameShape(QFrame.HLine)
        line3.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line3)
        
        # Fast Split checkbox
        self.fast_split_check = QCheckBox("Fast Split (No Re-encoding)\nKeeps original format/quality")
        self.fast_split_check.setChecked(self.app_state.split.enabled)
        self.fast_split_check.setToolTip("Split video without re-encoding. Much faster but requires keyframe alignment.")
        layout.addWidget(self.fast_split_check)
        
        # === Advanced Encoding Settings (Collapsible) ===
        line4 = QFrame()
        line4.setFrameShape(QFrame.HLine)
        line4.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line4)
        
        # Advanced settings header with dropdown arrow
        from ui_components import CollapsibleFrame
        advanced_collapsible = CollapsibleFrame("Advanced Encoding Settings")
        advanced_layout = advanced_collapsible.content_layout()
        
        # Profile
        profile_layout = QHBoxLayout()
        profile_layout.addWidget(QLabel("Profile:"))
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(["baseline", "main", "high"])
        self.profile_combo.setCurrentText("main")
        self.profile_combo.setEnabled(False)  # Display only
        self.profile_combo.setToolTip("Video profile (fixed to 'main' for compatibility)")
        profile_layout.addWidget(self.profile_combo)
        profile_layout.addStretch()
        advanced_layout.addLayout(profile_layout)
        
        # Level
        level_layout = QHBoxLayout()
        level_layout.addWidget(QLabel("Level:"))
        self.level_combo = QComboBox()
        self.level_combo.addItems(["3.0", "3.1", "4.0", "4.1", "4.2", "5.0", "5.1"])
        self.level_combo.setCurrentText("4.0")
        self.level_combo.setEnabled(False)  # Display only
        self.level_combo.setToolTip("Video level (fixed to '4.0' for compatibility)")
        level_layout.addWidget(self.level_combo)
        level_layout.addStretch()
        advanced_layout.addLayout(level_layout)
        
        # B-Frames
        bframes_layout = QHBoxLayout()
        bframes_layout.addWidget(QLabel("B-Frames:"))
        self.bframes_combo = QComboBox()
        self.bframes_combo.addItems(["0", "1", "2", "3"])
        self.bframes_combo.setCurrentText("0")
        self.bframes_combo.setEnabled(False)  # Display only
        self.bframes_combo.setToolTip("B-frames count (fixed to '0' for compatibility)")
        bframes_layout.addWidget(self.bframes_combo)
        bframes_layout.addStretch()
        advanced_layout.addLayout(bframes_layout)
        
        # Audio Mode
        audio_mode_layout = QHBoxLayout()
        audio_mode_layout.addWidget(QLabel("Audio Mode:"))
        self.audio_mode_combo = QComboBox()
        self.audio_mode_combo.addItems(["Encode", "Copy"])
        self.audio_mode_combo.setCurrentText(self.app_state.encoding.audio_mode.capitalize())
        self.audio_mode_combo.setMinimumWidth(100)
        self.audio_mode_combo.setToolTip("Audio processing mode:\nEncode: Re-encode audio to AAC (recommended)\nCopy: Copy original audio stream without re-encoding (faster)")
        audio_mode_layout.addWidget(self.audio_mode_combo)
        audio_mode_layout.addStretch()
        advanced_layout.addLayout(audio_mode_layout)
        
        # Audio Sample Rate
        sample_rate_layout = QHBoxLayout()
        sample_rate_layout.addWidget(QLabel("Audio Sample Rate:"))
        self.sample_rate_combo = QComboBox()
        self.sample_rate_combo.addItems(["44100 Hz", "48000 Hz", "96000 Hz"])
        self.sample_rate_combo.setCurrentText("44100 Hz")
        self.sample_rate_combo.setEnabled(False)  # Display only
        self.sample_rate_combo.setToolTip("Audio sample rate (fixed to '44100 Hz' for compatibility)")
        sample_rate_layout.addWidget(self.sample_rate_combo)
        sample_rate_layout.addStretch()
        advanced_layout.addLayout(sample_rate_layout)
        
        # GOP Size
        gop_layout = QHBoxLayout()
        gop_layout.addWidget(QLabel("GOP Size:"))
        self.gop_combo = QComboBox()
        self.gop_combo.addItems(["48", "96", "144", "250"])
        self.gop_combo.setCurrentText("144")
        self.gop_combo.setEnabled(False)  # Display only
        self.gop_combo.setToolTip("Group of Pictures size (fixed to '144' for compatibility)")
        gop_layout.addWidget(self.gop_combo)
        gop_layout.addStretch()
        advanced_layout.addLayout(gop_layout)
        
        layout.addWidget(advanced_collapsible)
        
        layout.addStretch()
        
    def connect_signals(self):
        """Connect UI signals to handlers"""
        self.gpu_check.toggled.connect(self.on_gpu_changed)
        self.encoder_combo.currentTextChanged.connect(self.on_encoder_changed)
        self.video_mode_combo.currentTextChanged.connect(self.on_video_mode_changed)
        self.resolution_combo.currentTextChanged.connect(self.on_resolution_changed)
        # Framerate is fixed at 23.976 fps - no signal connection needed
        self.cq_slider.valueChanged.connect(self.on_cq_changed)
        self.bitrate_mode_combo.currentTextChanged.connect(self.on_bitrate_mode_changed)
        self.bitrate_edit.textChanged.connect(self.on_target_bitrate_changed)
        self.orig_br_check.toggled.connect(self.on_orig_br_changed)
        self.max_br_spin.valueChanged.connect(self.on_max_br_changed)
        self.container_combo.currentTextChanged.connect(self.on_container_changed)
        self.scale_mode_combo.currentTextChanged.connect(self.on_scale_mode_changed)
        self.algorithm_combo.currentTextChanged.connect(self.on_algorithm_changed)
        self.scale_quality_combo.currentTextChanged.connect(self.on_scale_quality_changed)
        self.fast_split_check.toggled.connect(self.on_fast_split_changed)
        self.audio_mode_combo.currentTextChanged.connect(self.on_audio_mode_changed)
        
    def on_gpu_changed(self, checked):
        """Handle GPU checkbox change"""
        self.app_state.encoding.use_gpu = checked
        # Update encoder list based on GPU availability
        current = self.encoder_combo.currentText()
        self.encoder_combo.clear()
        if checked:
            self.encoder_combo.addItems(["h264_nvenc", "hevc_nvenc", "libx264", "libx265"])
        else:
            self.encoder_combo.addItems(["libx264", "libx265"])
        # Try to restore selection
        index = self.encoder_combo.findText(current)
        if index >= 0:
            self.encoder_combo.setCurrentIndex(index)
        self.settings_changed.emit()
        
    def on_encoder_changed(self, text):
        """Handle encoder selection change"""
        self.app_state.encoding.encoder = text
        self.settings_changed.emit()
        
    def on_video_mode_changed(self, text):
        """Handle video mode change (Encode/Copy)"""
        self.app_state.encoding.video_mode = text.lower()
        self.settings_changed.emit()
        
    def on_audio_mode_changed(self, text):
        """Handle audio mode change (Encode/Copy)"""
        self.app_state.encoding.audio_mode = text.lower()
        self.settings_changed.emit()
        
    def on_resolution_changed(self, text):
        """Handle resolution change"""
        self.app_state.encoding.resolution = text
        self.settings_changed.emit()
        
    # Framerate is fixed at 23.976 fps - method removed
    # def on_framerate_changed(self, button):
    #     """Handle framerate selection change"""
    #     value = button.property("value")
    #     self.app_state.encoding.framerate = value
    #     self.settings_changed.emit()
        
    def on_cq_changed(self, value):
        """Handle CQ slider change"""
        self.app_state.encoding.cq = value
        self.cq_label.setText(str(value))
        self.settings_changed.emit()
        
    def on_bitrate_mode_changed(self, text):
        """Handle bitrate mode change"""
        self.app_state.encoding.bitrate_mode = text
        self.settings_changed.emit()
        
    def on_target_bitrate_changed(self, text):
        """Handle target bitrate change"""
        self.app_state.encoding.target_bitrate = text
        self.settings_changed.emit()
        
    def on_orig_br_changed(self, checked):
        """Handle original bitrate checkbox change"""
        self.app_state.encoding.use_original_bitrate = checked
        self.settings_changed.emit()
        
    def on_max_br_changed(self, value):
        """Handle max bitrate change"""
        self.app_state.encoding.max_bitrate = value
        self.settings_changed.emit()
        
    def on_container_changed(self, text):
        """Handle container format change"""
        self.app_state.encoding.container = text
        self.settings_changed.emit()
        
    def on_scale_mode_changed(self, text):
        """Handle scale mode change"""
        self.app_state.encoding.scale_mode = text
        self.settings_changed.emit()
        
    def on_algorithm_changed(self, text):
        """Handle scale algorithm change"""
        self.app_state.encoding.scale_algorithm = text
        self.settings_changed.emit()
        
    def on_scale_quality_changed(self, text):
        """Handle scale quality change"""
        self.app_state.encoding.scale_quality = text
        self.settings_changed.emit()
        
    def on_fast_split_changed(self, checked):
        """Handle fast split checkbox change"""
        self.app_state.split.enabled = checked
        self.settings_changed.emit()
