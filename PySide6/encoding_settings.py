"""
Encoding Settings Panel (PySide6)
"""
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QCheckBox, QSlider, QSpinBox, QLineEdit, QGroupBox,
    QRadioButton, QButtonGroup, QFrame, QPushButton, QFileDialog
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
        
        # Preset Row (changes based on encoder)
        preset_layout = QHBoxLayout()
        self.preset_label = QLabel("Preset:")
        preset_layout.addWidget(self.preset_label)
        
        # GPU Preset (for NVENC)
        self.gpu_preset_combo = QComboBox()
        self.gpu_preset_combo.addItems(["p1", "p2", "p3", "p4", "p5", "p6", "p7"])
        self.gpu_preset_combo.setCurrentText(self.app_state.encoding.gpu_preset)
        self.gpu_preset_combo.setMinimumWidth(100)
        self.gpu_preset_combo.setToolTip(
            "GPU Preset (NVENC):\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "p1: Fastest (lowest quality)\n"
            "p2: Faster\n"
            "p3: Fast\n"
            "p4: Medium (balanced) ← Default\n"
            "p5: Slow\n"
            "p6: Slower\n"
            "p7: Slowest (best quality)"
        )
        preset_layout.addWidget(self.gpu_preset_combo)
        
        # CPU Preset (for libx264/libx265)
        self.cpu_preset_combo = QComboBox()
        self.cpu_preset_combo.addItems([
            "ultrafast", "superfast", "veryfast", "faster", 
            "fast", "medium", "slow", "slower", "veryslow"
        ])
        self.cpu_preset_combo.setCurrentText(self.app_state.encoding.cpu_preset)
        self.cpu_preset_combo.setMinimumWidth(100)
        self.cpu_preset_combo.setToolTip(
            "CPU Preset:\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "ultrafast: Fastest encoding\n"
            "superfast: Very fast\n"
            "veryfast: Fast\n"
            "faster: Faster than medium\n"
            "fast: Fast encoding\n"
            "medium: Balanced ← Default\n"
            "slow: Better compression\n"
            "slower: Even better compression\n"
            "veryslow: Best compression (slowest)"
        )
        preset_layout.addWidget(self.cpu_preset_combo)
        
        # Tune (for CPU encoding - libx264/libx265)
        self.tune_label = QLabel("Tune:")
        preset_layout.addWidget(self.tune_label)
        
        self.cpu_tune_combo = QComboBox()
        self.cpu_tune_combo.addItems([
            "none", "film", "animation", "grain", "fastdecode", "zerolatency"
        ])
        self.cpu_tune_combo.setCurrentText(self.app_state.encoding.cpu_tune)
        self.cpu_tune_combo.setMinimumWidth(100)
        self.cpu_tune_combo.setToolTip(
            "CPU Tune:\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "none: No tune (default)\n"
            "film: Best for movies/TV\n"
            "animation: Better for cartoons\n"
            "grain: Preserves film grain\n"
            "fastdecode: Faster playback\n"
            "zerolatency: Live streaming"
        )
        preset_layout.addWidget(self.cpu_tune_combo)
        
        preset_layout.addStretch()
        layout.addLayout(preset_layout)
        
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
            "original", "1920x1080", "1280x720", "720x480",
            "720x404", "720x400", "640x480", "640x368", "Custom"
        ])
        # Move Custom to end (it's already at end, but ensure it stays)
        current_res = self.app_state.encoding.resolution
        if current_res == "none":
            self.resolution_combo.setCurrentText("original")
        elif current_res == "Custom":
            self.resolution_combo.setCurrentText("Custom")
        else:
            self.resolution_combo.setCurrentText(current_res)
        self.resolution_combo.setMinimumWidth(120)
        self.resolution_combo.setToolTip("Output video resolution.\n'original' keeps original resolution.\n'Custom' allows custom width x height.\nLower resolutions create smaller files.")
        res_layout.addWidget(self.resolution_combo)
        
        # Custom resolution input (width x height)
        self.custom_res_edit = QLineEdit(getattr(self.app_state.encoding, 'custom_resolution', '1280x720'))
        self.custom_res_edit.setMaximumWidth(120)
        self.custom_res_edit.setPlaceholderText("WxH")
        self.custom_res_edit.setToolTip("Custom resolution (e.g., 1920x1080, 854x480)")
        self.custom_res_edit.setEnabled(self.resolution_combo.currentText() == "Custom")
        res_layout.addWidget(QLabel("Custom:"))
        res_layout.addWidget(self.custom_res_edit)
        
        res_layout.addSpacing(20)
             
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
        
        # Set initial state of bitrate input based on original bitrate setting
        if self.app_state.encoding.use_original_bitrate:
            self.bitrate_edit.setEnabled(False)
            self.bitrate_edit.setStyleSheet("color: gray;")
        
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
        self.algorithm_combo.addItems(["bilinear", "bicubic", "lanczos", "spline", "area", "zscale", "scale_cuda", "scale_vulkan", "libplacebo"])
        self.algorithm_combo.setCurrentText(self.app_state.encoding.scale_algorithm)
        self.algorithm_combo.setToolTip(
            "Scaling algorithm:\n"
            "Bilinear: Fast, basic quality\n"
            "Bicubic: Good balance of speed/quality\n"
            "Lanczos: High quality, slower\n"
            "Spline: Smooth scaling\n"
            "Area: Best for downscaling\n"
            "zscale: Modern resizer, better quality\n"
            "scale_cuda: NVIDIA GPU accelerated\n"
            "scale_vulkan: Vulkan/GPU accelerated\n"
            "libplacebo: Advanced GPU with color management"
        )
        scale_layout.addWidget(self.algorithm_combo)
        scale_layout.addStretch()
        layout.addLayout(scale_layout)
        
        # Libplacebo tone mapping options (visible only when libplacebo is selected)
        self.tone_mapping_label = QLabel("Tone Mapping:")
        self.tone_mapping_combo = QComboBox()
        self.tone_mapping_combo.addItems(["none", "bt2390", "bt2446", "reinhard", "mobius", "linear", "clip", "spline"])
        self.tone_mapping_combo.setCurrentText(self.app_state.encoding.libplacebo_tonemapping)
        self.tone_mapping_combo.setToolTip(
            "Tone mapping algorithm (for HDR sources):\n"
            "none: No tone mapping (use for SDR content)\n"
            "bt2390: HDR to SDR - Best quality\n"
            "bt2446: HDR to SDR, improved from bt2390\n"
            "reinhard: Simple reinhard tonemap\n"
            "mobius: Mobius tone mapping\n"
            "linear: Linear tone mapping\n"
            "clip: Simple clip to SDR range\n"
            "spline: Spline tone mapping"
        )
        
        tone_mapping_layout = QHBoxLayout()
        tone_mapping_layout.addWidget(self.tone_mapping_label)
        tone_mapping_layout.addWidget(self.tone_mapping_combo)
        tone_mapping_layout.addStretch()
        layout.addLayout(tone_mapping_layout)
        
        # Hide tone mapping controls initially based on current algorithm
        if self.app_state.encoding.scale_algorithm != "libplacebo":
            self.tone_mapping_label.hide()
            self.tone_mapping_combo.hide()
        
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
        
        # Aspect Ratio Mode (for GPU scalers)
        aspect_layout = QHBoxLayout()
        aspect_layout.addWidget(QLabel("Aspect Ratio:"))
        
        self.aspect_ratio_combo = QComboBox()
        self.aspect_ratio_combo.addItems(["Fit (Preserve)", "Stretch"])
        self.aspect_ratio_combo.setCurrentText("Fit (Preserve)" if self.app_state.encoding.aspect_ratio_mode == "fit" else "Stretch")
        self.aspect_ratio_combo.setToolTip(
            "Aspect ratio handling for scaling:\n"
            "Fit (Preserve): Auto-calculates height to keep original aspect ratio\n"
            "Stretch: Scales to exact dimensions (may distort image)\n"
            "Note: Recommended for GPU scalers (scale_cuda, scale_vulkan)"
        )
        aspect_layout.addWidget(self.aspect_ratio_combo)
        
        aspect_layout.addStretch()
        layout.addLayout(aspect_layout)
        
        # Set initial state of algorithm and quality based on scale mode
        if self.app_state.encoding.scale_mode == "off":
            self.algorithm_combo.setEnabled(False)
            self.scale_quality_combo.setEnabled(False)
            self.algorithm_combo.setStyleSheet("color: gray;")
            self.scale_quality_combo.setStyleSheet("color: gray;")
        
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
        
        # Pixel Format
        pix_fmt_layout = QHBoxLayout()
        pix_fmt_layout.addWidget(QLabel("Pixel Format:"))
        self.pix_fmt_combo = QComboBox()
        self.pix_fmt_combo.addItems(["yuv420p (8-bit)", "yuv420p10le (10-bit)", "yuv444p (8-bit)", "yuv444p10le (10-bit)"])
        current_pix_fmt = getattr(self.app_state.encoding, 'pixel_format', 'yuv420p')
        display_text = f"{current_pix_fmt} (8-bit)" if current_pix_fmt == "yuv420p" else f"{current_pix_fmt} (10-bit)" if current_pix_fmt == "yuv420p10le" else current_pix_fmt
        if "yuv444p10le" in current_pix_fmt:
            display_text = f"{current_pix_fmt} (10-bit)"
        elif "yuv444p" in current_pix_fmt:
            display_text = f"{current_pix_fmt} (8-bit)"
        self.pix_fmt_combo.setCurrentText(display_text)
        self.pix_fmt_combo.setMinimumWidth(140)
        self.pix_fmt_combo.setToolTip(
            "Pixel format for encoding:\n"
            "yuv420p: 8-bit (standard, max compatibility)\n"
            "yuv420p10le: 10-bit (better color, less compatible)\n"
            "yuv444p: 8-bit (no chroma subsampling)\n"
            "yuv444p10le: 10-bit (best color, less compatible)"
        )
        pix_fmt_layout.addWidget(self.pix_fmt_combo)
        pix_fmt_layout.addStretch()
        advanced_layout.addLayout(pix_fmt_layout)
        
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
        
        # Audio Track Selection
        audio_track_layout = QHBoxLayout()
        audio_track_layout.addWidget(QLabel("Audio Track:"))
        self.audio_track_combo = QComboBox()
        self.audio_track_combo.setMinimumWidth(200)
        self.audio_track_combo.setToolTip("Select which audio track to use from the source video.\nShows track number, codec, channels, and language if available.")
        audio_track_layout.addWidget(self.audio_track_combo)
        audio_track_layout.addStretch()
        advanced_layout.addLayout(audio_track_layout)
        
        # External Audio File Selection
        ext_audio_group = QGroupBox("External Audio")
        ext_audio_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #888;
                border-radius: 3px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
            }
        """)
        ext_audio_layout = QVBoxLayout(ext_audio_group)
        
        # Enable external audio checkbox
        self.external_audio_check = QCheckBox("Use External Audio File")
        self.external_audio_check.setToolTip("Load an external audio file to replace the video's embedded audio.\nSupports: MP3, AAC, WAV, FLAC, OGG, M4A, AC3")
        ext_audio_layout.addWidget(self.external_audio_check)
        
        # File selection row
        ext_file_layout = QHBoxLayout()
        self.external_audio_path = QLineEdit()
        self.external_audio_path.setPlaceholderText("No file selected...")
        self.external_audio_path.setReadOnly(True)
        self.external_audio_path.setToolTip("Path to external audio file")
        ext_file_layout.addWidget(self.external_audio_path)
        
        self.browse_audio_btn = QPushButton("Browse...")
        self.browse_audio_btn.setMaximumWidth(80)
        self.browse_audio_btn.setToolTip("Browse for audio file")
        ext_file_layout.addWidget(self.browse_audio_btn)
        
        self.clear_audio_btn = QPushButton("Clear")
        self.clear_audio_btn.setMaximumWidth(60)
        self.clear_audio_btn.setToolTip("Remove external audio")
        self.clear_audio_btn.setEnabled(False)
        ext_file_layout.addWidget(self.clear_audio_btn)
        
        ext_audio_layout.addLayout(ext_file_layout)
        
        # Audio info display
        self.external_audio_info = QLabel("No audio file selected")
        self.external_audio_info.setStyleSheet("color: gray; font-size: 11px;")
        self.external_audio_info.setToolTip("Information about selected external audio file")
        ext_audio_layout.addWidget(self.external_audio_info)
        
        advanced_layout.addWidget(ext_audio_group)
        
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
        
        # Framerate - fixed at 23.976 fps
        framerate_layout = QHBoxLayout()
        framerate_layout.addWidget(QLabel("Framerate:"))
        self.framerate_label = QLabel("23.976 fps")
        self.framerate_label.setStyleSheet("color: gray;")
        self.framerate_label.setToolTip("Framerate is fixed at 23.976 fps (24000/1001)")
        framerate_layout.addWidget(self.framerate_label)
        framerate_layout.addStretch()
        advanced_layout.addLayout(framerate_layout)
        
        # Always set framerate to 23.976
        self.app_state.encoding.framerate = "24000/1001"
        
        layout.addWidget(advanced_collapsible)
        
        layout.addStretch()
        
    def connect_signals(self):
        """Connect UI signals to handlers"""
        self.gpu_check.toggled.connect(self.on_gpu_changed)
        self.encoder_combo.currentTextChanged.connect(self.on_encoder_changed)
        self.video_mode_combo.currentTextChanged.connect(self.on_video_mode_changed)
        self.resolution_combo.currentTextChanged.connect(self.on_resolution_changed)
        self.custom_res_edit.textChanged.connect(self.on_custom_res_changed)
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
        self.tone_mapping_combo.currentTextChanged.connect(self.on_tone_mapping_changed)
        self.aspect_ratio_combo.currentTextChanged.connect(self.on_aspect_ratio_changed)
        self.audio_mode_combo.currentTextChanged.connect(self.on_audio_mode_changed)
        self.audio_track_combo.currentIndexChanged.connect(self.on_audio_track_changed)
        self.gpu_preset_combo.currentTextChanged.connect(self.on_gpu_preset_changed)
        self.cpu_preset_combo.currentTextChanged.connect(self.on_cpu_preset_changed)
        self.cpu_tune_combo.currentTextChanged.connect(self.on_cpu_tune_changed)
        self.pix_fmt_combo.currentTextChanged.connect(self.on_pix_fmt_changed)
        
        # External audio signals
        self.external_audio_check.toggled.connect(self.on_external_audio_toggled)
        self.browse_audio_btn.clicked.connect(self.on_browse_external_audio)
        self.clear_audio_btn.clicked.connect(self.on_clear_external_audio)
        
        # Set initial preset visibility
        self.update_preset_visibility()
        
    def on_audio_track_changed(self, index):
        """Handle audio track selection change"""
        if hasattr(self.app_state.tracks, 'available_audio_tracks'):
            tracks = self.app_state.tracks.available_audio_tracks
            if index >= 0 and index < len(tracks):
                self.app_state.tracks.audio_stream_index = index
                self.settings_changed.emit()
    
    def populate_audio_tracks(self, tracks: list):
        """Populate audio track combo with available tracks"""
        self.audio_track_combo.clear()
        
        if not tracks:
            self.audio_track_combo.addItem("No audio tracks detected")
            self.audio_track_combo.setEnabled(False)
            return
        
        for i, track in enumerate(tracks):
            display_text = f"Track {i+1}"
            if track.title:
                display_text += f" - {track.title}"
            if track.language:
                display_text += f" [{track.language}]"
            display_text += f" ({track.codec}, {track.channels}ch)"
            if track.sample_rate:
                display_text += f", {track.sample_rate}Hz"
            self.audio_track_combo.addItem(display_text)
        
        self.audio_track_combo.setEnabled(True)
        
        # Default to track 1 (index 0) - always use first audio track by default
        default_index = 0
        self.audio_track_combo.setCurrentIndex(default_index)
        self.app_state.tracks.audio_stream_index = default_index
        
    def on_external_audio_toggled(self, checked):
        """Handle external audio checkbox toggle"""
        self.app_state.tracks.external_audio_enabled = checked
        
        # Enable/disable browse and clear buttons based on checkbox state
        self.browse_audio_btn.setEnabled(checked)
        
        # If unchecked and there's a path, keep it but mark as disabled
        if not checked:
            self.external_audio_path.setEnabled(False)
            self.clear_audio_btn.setEnabled(False)
        elif self.app_state.tracks.external_audio_path:
            self.external_audio_path.setEnabled(True)
            self.clear_audio_btn.setEnabled(True)
        
        self.settings_changed.emit()
        
    def on_browse_external_audio(self):
        """Handle browse button click for external audio file"""
        file_filter = "Audio Files (*.mp3 *.aac *.wav *.flac *.ogg *.m4a *.ac3);;All Files (*)"
        
        # Get last directory from app state or use home directory
        last_dir = getattr(self.app_state, 'last_directory', '')
        if not last_dir:
            import os
            last_dir = os.path.expanduser("~")
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select External Audio File",
            last_dir,
            file_filter
        )
        
        if file_path:
            # Save directory for next time
            import os
            self.app_state.last_directory = os.path.dirname(file_path)
            
            # Validate and load the audio file
            self.load_external_audio(file_path)
        
    def load_external_audio(self, file_path: str):
        """Load and validate external audio file"""
        import os
        
        # Check if file exists
        if not os.path.exists(file_path):
            self.external_audio_info.setText("Error: File not found")
            self.external_audio_info.setStyleSheet("color: red; font-size: 11px;")
            return
        
        # Try to get audio info using ffprobe
        audio_info = self.get_external_audio_info(file_path)
        
        if audio_info:
            # Store the path
            self.app_state.tracks.external_audio_path = file_path
            
            # Display file name
            file_name = os.path.basename(file_path)
            self.external_audio_path.setText(file_name)
            self.external_audio_path.setToolTip(file_path)
            
            # Display audio info
            info_text = f"{audio_info.get('codec', 'Unknown').upper()}"
            if audio_info.get('duration'):
                info_text += f", {audio_info['duration']}"
            if audio_info.get('channels'):
                info_text += f", {audio_info['channels']}ch"
            if audio_info.get('sample_rate'):
                info_text += f", {audio_info['sample_rate']}Hz"
            
            self.external_audio_info.setText(info_text)
            self.external_audio_info.setStyleSheet("color: green; font-size: 11px;")
            
            # Store info in app state
            self.app_state.tracks.external_audio_info = info_text
            
            # Enable UI elements
            self.external_audio_path.setEnabled(True)
            self.clear_audio_btn.setEnabled(True)
            self.external_audio_check.setChecked(True)
            self.app_state.tracks.external_audio_enabled = True
            
            self.app_state.log(f"Loaded external audio: {file_name}", "INFO")
            self.settings_changed.emit()
        else:
            self.external_audio_info.setText("Error: Could not read audio info")
            self.external_audio_info.setStyleSheet("color: red; font-size: 11px;")
            
    def get_external_audio_info(self, file_path: str) -> dict:
        """Get information about external audio file using ffprobe"""
        import subprocess
        import json
        
        ffprobe_path = self.app_state.ffprobe_path
        ffmpeg_path = self.app_state.ffmpeg_path
        
        # Try to find ffprobe
        if ffmpeg_path != "ffmpeg" and os.path.exists(ffmpeg_path):
            base_dir = os.path.dirname(ffmpeg_path)
            candidate = os.path.join(base_dir, "ffprobe.exe" if os.name == 'nt' else "ffprobe")
            if os.path.exists(candidate):
                ffprobe_path = candidate
        
        if not ffprobe_path:
            ffprobe_path = "ffprobe"
        
        try:
            cmd = [
                ffprobe_path,
                "-v", "error",
                "-show_entries", "stream=index,codec_name,codec_type,channels,sample_rate:format=duration",
                "-of", "json",
                file_path
            ]
            
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=30
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                # Find audio stream
                audio_stream = None
                for stream in data.get('streams', []):
                    if stream.get('codec_type') == 'audio':
                        audio_stream = stream
                        break
                
                if audio_stream:
                    info = {
                        'codec': audio_stream.get('codec_name', 'unknown'),
                        'channels': audio_stream.get('channels', 0),
                        'sample_rate': audio_stream.get('sample_rate', '')
                    }
                    
                    # Get duration from format
                    if data.get('format') and data['format'].get('duration'):
                        duration_sec = float(data['format']['duration'])
                        mins, secs = divmod(int(duration_sec), 60)
                        hours, mins = divmod(mins, 60)
                        if hours > 0:
                            info['duration'] = f"{hours}:{mins:02d}:{secs:02d}"
                        else:
                            info['duration'] = f"{mins}:{secs:02d}"
                    
                    return info
        except Exception as e:
            self.app_state.log(f"Failed to read audio info: {e}", "WARN")
        
        return None
        
    def on_clear_external_audio(self):
        """Handle clear button click to remove external audio"""
        self.app_state.tracks.external_audio_path = ""
        self.app_state.tracks.external_audio_enabled = False
        self.app_state.tracks.external_audio_info = ""
        
        self.external_audio_path.clear()
        self.external_audio_path.setToolTip("")
        self.external_audio_info.setText("No audio file selected")
        self.external_audio_info.setStyleSheet("color: gray; font-size: 11px;")
        
        self.external_audio_check.setChecked(False)
        self.external_audio_path.setEnabled(False)
        self.clear_audio_btn.setEnabled(False)
        self.browse_audio_btn.setEnabled(False)
        
        self.app_state.log("External audio cleared", "INFO")
        self.settings_changed.emit()
        
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
        self.update_preset_visibility()
        self.settings_changed.emit()
    
    def update_preset_visibility(self):
        """Show correct preset combo based on encoder type"""
        encoder = self.encoder_combo.currentText()
        is_nvenc = "nvenc" in encoder.lower()
        
        # Show GPU preset for NVENC, CPU preset for others
        self.gpu_preset_combo.setVisible(is_nvenc)
        self.cpu_preset_combo.setVisible(not is_nvenc)
        self.tune_label.setVisible(not is_nvenc)
        self.cpu_tune_combo.setVisible(not is_nvenc)
        
        # Update tune options based on encoder (x264 vs x265 have different valid tunes)
        self.update_tune_options()
    
    def update_tune_options(self):
        """Update tune dropdown options based on selected encoder"""
        encoder = self.encoder_combo.currentText()
        current_tune = self.cpu_tune_combo.currentText()
        
        if "x265" in encoder.lower():
            # x265 valid tunes: psnr, ssim, grain, zerolatency, fastdecode, animation
            tune_options = ["none", "psnr", "ssim", "grain", "zerolatency", "fastdecode", "animation"]
        else:
            # x264 valid tunes: film, animation, grain, fastdecode, zerolatency
            tune_options = ["none", "film", "animation", "grain", "fastdecode", "zerolatency"]
        
        self.cpu_tune_combo.clear()
        self.cpu_tune_combo.addItems(tune_options)
        
        # Try to restore previous selection, or default to "none"
        if current_tune in tune_options:
            self.cpu_tune_combo.setCurrentText(current_tune)
        else:
            self.cpu_tune_combo.setCurrentText("none")
            self.app_state.encoding.cpu_tune = "none"
    
    def on_gpu_preset_changed(self, text):
        """Handle GPU preset change"""
        self.app_state.encoding.gpu_preset = text
        self.settings_changed.emit()
    
    def on_cpu_preset_changed(self, text):
        """Handle CPU preset change"""
        self.app_state.encoding.cpu_preset = text
        self.settings_changed.emit()
    
    def on_cpu_tune_changed(self, text):
        """Handle CPU tune change"""
        self.app_state.encoding.cpu_tune = text
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
        if text == "original":
            self.app_state.encoding.resolution = "none"
        elif text == "Custom":
            self.app_state.encoding.resolution = "Custom"
        else:
            self.app_state.encoding.resolution = text
        
        # Enable/disable custom resolution input
        self.custom_res_edit.setEnabled(text == "Custom")
        self.settings_changed.emit()
    
    def on_custom_res_changed(self, text):
        """Handle custom resolution text change"""
        self.app_state.encoding.custom_resolution = text
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
        # Disable target bitrate input when using original
        self.bitrate_edit.setEnabled(not checked)
        if not checked:
            self.bitrate_edit.setStyleSheet("")
        else:
            self.bitrate_edit.setStyleSheet("color: gray;")
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
        
        # Enable/disable algorithm and quality based on scale mode
        if text == "off":
            self.algorithm_combo.setEnabled(False)
            self.scale_quality_combo.setEnabled(False)
            self.algorithm_combo.setStyleSheet("color: gray;")
            self.scale_quality_combo.setStyleSheet("color: gray;")
        else:
            self.algorithm_combo.setEnabled(True)
            self.scale_quality_combo.setEnabled(True)
            self.algorithm_combo.setStyleSheet("")
            self.scale_quality_combo.setStyleSheet("")
        
        self.settings_changed.emit()
        
    def on_algorithm_changed(self, text):
        """Handle scale algorithm change"""
        self.app_state.encoding.scale_algorithm = text
        
        # Show/hide tone mapping controls based on algorithm
        if text == "libplacebo":
            self.tone_mapping_label.show()
            self.tone_mapping_combo.show()
        else:
            self.tone_mapping_label.hide()
            self.tone_mapping_combo.hide()
        
        self.settings_changed.emit()
        
    def on_tone_mapping_changed(self, text):
        """Handle tone mapping algorithm change"""
        self.app_state.encoding.libplacebo_tonemapping = text
        self.settings_changed.emit()
        
    def on_aspect_ratio_changed(self, text):
        """Handle aspect ratio mode change"""
        self.app_state.encoding.aspect_ratio_mode = "fit" if "Fit" in text else "stretch"
        self.settings_changed.emit()
        
    def on_scale_quality_changed(self, text):
        """Handle scale quality change"""
        self.app_state.encoding.scale_quality = text
        self.settings_changed.emit()
        
    def on_pix_fmt_changed(self, text):
        """Handle pixel format change"""
        pix_fmt = text.split()[0]  # Extract just the format name (before the space and bit depth)
        self.app_state.encoding.pixel_format = pix_fmt
        self.settings_changed.emit()
