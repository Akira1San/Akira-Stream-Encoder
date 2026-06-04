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
    upscaling_active = Signal(bool)
    
    def __init__(self, app_state: AppState, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self._upscale_controller = None
        
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Engine selector
        engine_layout = QHBoxLayout()
        engine_label = QLabel("Engine:")
        engine_label.setStyleSheet("font-weight: bold;")
        engine_layout.addWidget(engine_label)
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["FFmpeg", "GStreamer"])
        current = self.app_state.media_engine
        self.engine_combo.setCurrentIndex(0 if current == "ffmpeg" else 1)
        self.engine_combo.setMinimumWidth(120)
        engine_layout.addWidget(self.engine_combo)
        self.engine_indicator = QLabel("FFmpeg")
        self.engine_indicator.setStyleSheet("color: #4CAF50; font-weight: bold;")
        engine_layout.addWidget(self.engine_indicator)
        engine_layout.addStretch()
        layout.addLayout(engine_layout)

        # === GPU & Encoder (Vertical Layout) ===
        
        # GPU Checkbox
        self.gpu_check = QCheckBox("Use GPU (NVENC)")
        self.gpu_check.setChecked(self.app_state.encoding.use_gpu)
        self.gpu_check.setToolTip("Enable NVIDIA GPU acceleration for faster encoding.\nRequires NVIDIA graphics card with NVENC support.")
        layout.addWidget(self.gpu_check)
        
        # Video Track Selection
        video_track_layout = QHBoxLayout()
        video_track_layout.addWidget(QLabel("Video Track:"))
        self.video_track_combo = QComboBox()
        self.video_track_combo.setMinimumWidth(200)
        self.video_track_combo.setToolTip("Select which video track to use from the source video.\nShows track number, codec, and resolution.")
        video_track_layout.addWidget(self.video_track_combo)
        video_track_layout.addStretch()
        layout.addLayout(video_track_layout)
        
        # Encoder Row
        encoder_layout = QHBoxLayout()
        encoder_layout.addWidget(QLabel("Encoder:"))
        self.encoder_combo = QComboBox()
        self.encoder_combo.addItems([
            "h264_nvenc", "hevc_nvenc", "libx264", "libx265", "mpeg2video"
        ])
        self.encoder_combo.setCurrentText(self.app_state.encoding.encoder)
        self.encoder_combo.setMinimumWidth(140)
        self.encoder_combo.setToolTip("Video codec to use:\nh264_nvenc: H.264 with GPU acceleration\nhevc_nvenc: H.265/HEVC with GPU (smaller files)\nlibx264: H.264 CPU encoding (compatible)\nlibx265: H.265/HEVC CPU (best compression)\nmpeg2video: MPEG-2 for DVD/legacy compatibility")
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
            "p4: Medium (balanced)\n"
            "p5: Slow (good quality) ← Default\n"
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
        self.sync_audio_btn = QPushButton("Auto")
        self.sync_audio_btn.setToolTip("Set audio mode (Advanced section) to match current video mode")
        self.sync_audio_btn.setFixedWidth(50)
        video_mode_layout.addWidget(self.sync_audio_btn)
        video_mode_layout.addStretch()
        layout.addLayout(video_mode_layout)
        
        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # === Resolution & Framerate ===
        res_layout = QHBoxLayout()
        res_layout.addWidget(QLabel("Resolution:"))

        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems([
            "original", "1920x1080", "1280x720", "NTSC (720x480)", "PAL (720x576)",
            "720x480", "720x404", "720x400", "640x480", "640x368", "Custom"
        ])
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
        res_layout.addStretch()
        layout.addLayout(res_layout)

        custom_layout = QHBoxLayout()
        custom_layout.addWidget(QLabel("Custom:"))
        self.custom_res_edit = QLineEdit(getattr(self.app_state.encoding, 'custom_resolution', '1280x720'))
        self.custom_res_edit.setMaximumWidth(120)
        self.custom_res_edit.setPlaceholderText("WxH")
        self.custom_res_edit.setToolTip("Custom resolution (e.g., 1920x1080, 854x480)")
        self.custom_res_edit.setEnabled(self.resolution_combo.currentText() == "Custom")
        custom_layout.addWidget(self.custom_res_edit)
        custom_layout.addStretch()
        layout.addLayout(custom_layout)
        
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
        
        # Checkboxes row: Original Bitrate | Max Bitrate
        checkboxes_layout = QHBoxLayout()

        self.orig_br_check = QCheckBox("Original Bitrate")
        self.orig_br_check.setChecked(self.app_state.encoding.use_original_bitrate)
        self.orig_br_check.setToolTip("Use the original video's bitrate if it can be detected.\nOverrides the target bitrate setting above.")
        checkboxes_layout.addWidget(self.orig_br_check)

        self.use_max_br_check = QCheckBox("Max Bitrate")
        self.use_max_br_check.setChecked(self.app_state.encoding.use_max_bitrate)
        self.use_max_br_check.setToolTip("Enable max bitrate limit.\nWhen enabled, the encoder can spike up to the max bitrate value below.")
        checkboxes_layout.addWidget(self.use_max_br_check)

        checkboxes_layout.addStretch()
        layout.addLayout(checkboxes_layout)

        # Bitrate inputs row: Target Bitrate | Max Bitrate
        br_inputs_layout = QHBoxLayout()

        br_label = QLabel("Target Bitrate:")
        br_label.setToolTip("Target bitrate for video encoding.\nHigher values = better quality, larger files\n2000-4000 kbps: Good for 720p\n4000-8000 kbps: Good for 1080p")
        br_inputs_layout.addWidget(br_label)

        self.bitrate_edit = QLineEdit(self.app_state.encoding.target_bitrate)
        self.bitrate_edit.setMaximumWidth(80)
        self.bitrate_edit.setToolTip("Enter target bitrate in kilobits per second (kbps)")
        br_inputs_layout.addWidget(self.bitrate_edit)

        max_br_label = QLabel("  Max Bitrate:")
        max_br_label.setToolTip("Maximum allowed bitrate.\nPrevents bitrate spikes that could cause playback issues.")
        br_inputs_layout.addWidget(max_br_label)

        self.max_br_spin = QSpinBox()
        self.max_br_spin.setRange(500, 50000)
        self.max_br_spin.setValue(self.app_state.encoding.max_bitrate)
        self.max_br_spin.setSingleStep(500)
        self.max_br_spin.setToolTip("Maximum bitrate limit")
        br_inputs_layout.addWidget(self.max_br_spin)

        br_inputs_layout.addStretch()
        layout.addLayout(br_inputs_layout)

        # Set initial state of bitrate input and max bitrate spin
        if self.app_state.encoding.use_original_bitrate:
            self.bitrate_edit.setEnabled(False)
            self.bitrate_edit.setStyleSheet("color: gray;")
        self.max_br_spin.setEnabled(self.app_state.encoding.use_max_bitrate)

        # === Target File Size ===
        target_size_layout = QHBoxLayout()
        target_size_label = QLabel("Target File Size (MB):")
        target_size_label.setToolTip("Enter desired output file size in MB.\nClick 'Calculate' to automatically set the bitrate to match this size.")
        target_size_layout.addWidget(target_size_label)
        
        self.target_size_spin = QSpinBox()
        self.target_size_spin.setRange(10, 50000)
        self.target_size_spin.setValue(700)
        self.target_size_spin.setSingleStep(50)
        self.target_size_spin.setSuffix(" MB")
        self.target_size_spin.setMaximumWidth(100)
        self.target_size_spin.setToolTip("Desired output file size in megabytes")
        target_size_layout.addWidget(self.target_size_spin)
        
        self.calc_size_btn = QPushButton("Calculate Bitrate")
        self.calc_size_btn.setToolTip("Calculate target bitrate from file size and video duration.\nRequires an input video to be loaded.")
        target_size_layout.addWidget(self.calc_size_btn)
        
        target_size_layout.addStretch()
        layout.addLayout(target_size_layout)
        
        # === Container Format ===
        container_layout = QHBoxLayout()
        container_label = QLabel("Container:")
        container_label.setToolTip("Output file format/container.\nmp4: Best compatibility (recommended)\nmkv: Supports more codecs and features\navi: Older format, limited codec support\nmpg: MPEG Program Stream (DVD/VOB compatible)\nvob: DVD VOB container")
        container_layout.addWidget(container_label)
        
        self.container_combo = QComboBox()
        self.container_combo.addItems(["mp4", "mkv", "avi", "mpg", "vob"])
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
        scale_layout.addStretch()
        layout.addLayout(scale_layout)

        algo_layout = QHBoxLayout()
        self.algo_label = QLabel("Algorithm:")
        algo_layout.addWidget(self.algo_label)

        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems(["bilinear", "bicubic", "lanczos", "spline", "area", "zscale", "scale_cuda", "scale_vulkan", "libplacebo"])
        self.algorithm_combo.setCurrentText(self.app_state.encoding.scale_algorithm)
        self.algorithm_combo.setToolTip(
            "<html><div style='white-space:nowrap; padding:4px;'>"
            "<b>FFmpeg scaling algorithm</b><br>"
            "<hr>"
            "bilinear — Fast, basic quality<br>"
            "bicubic — Good balance of speed/quality<br>"
            "lanczos — High quality, slower<br>"
            "spline — Smooth scaling<br>"
            "area — Best for downscaling<br>"
            "zscale — Modern resizer, better quality<br>"
            "scale_cuda — NVIDIA GPU accelerated<br>"
            "scale_vulkan — Vulkan/GPU accelerated<br>"
            "libplacebo — Advanced GPU with color management"
            "</div></html>"
        )
        algo_layout.addWidget(self.algorithm_combo)
        algo_layout.addStretch()
        layout.addLayout(algo_layout)
        
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
        
        # GStreamer-specific scale algorithm combo (visible only in GStreamer mode)
        self.gst_algo_label = QLabel("GST Algorithm:")
        self.gst_algorithm_combo = QComboBox()
        self.gst_algorithm_combo.addItems([
            "nearest-neighbour", "bilinear", "4-tap", "lanczos",
            "bilinear2", "sinc", "hermite", "spline", "catrom", "mitchell"
        ])
        self.gst_algorithm_combo.setCurrentText(self.app_state.encoding.gst_scale_algorithm)
        self.gst_algorithm_combo.setToolTip(
            "<html><div style='white-space:nowrap; padding:4px;'>"
            "<b>GStreamer videoscale method</b><br>"
            "<hr>"
            "catrom — Sharp bicubic, best for upscaling (recommended)<br>"
            "lanczos — High quality, good alternative<br>"
            "bilinear — Fast, basic quality<br>"
            "nearest-neighbour — Fastest, pixelated<br>"
            "spline — Smooth scaling<br>"
            "mitchell — Softer than catrom, less ringing<br>"
            "4-tap — 4-tap bicubic<br>"
            "hermite — Hermite interpolation<br>"
            "sinc — Windowed sinc<br>"
            "bilinear2 — Improved bilinear"
            "</div></html>"
        )
        gst_algo_layout = QHBoxLayout()
        gst_algo_layout.addWidget(self.gst_algo_label)
        gst_algo_layout.addWidget(self.gst_algorithm_combo)
        gst_algo_layout.addStretch()
        layout.addLayout(gst_algo_layout)
        
        # Hide GStreamer algo controls initially based on engine
        if self.app_state.media_engine != "gstreamer":
            self.gst_algo_label.hide()
            self.gst_algorithm_combo.hide()
        
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
            self.gst_algorithm_combo.setEnabled(False)
            self.scale_quality_combo.setEnabled(False)
            self.algorithm_combo.setStyleSheet("color: gray;")
            self.gst_algorithm_combo.setStyleSheet("color: gray;")
            self.scale_quality_combo.setStyleSheet("color: gray;")
        
        # === AI Upscaling Section ===
        line_ai = QFrame()
        line_ai.setFrameShape(QFrame.HLine)
        line_ai.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line_ai)
        
        self.ai_enabled_check = QCheckBox("AI Upscaling")
        self.ai_enabled_check.setChecked(self.app_state.ai_upscaling.enabled)
        self.ai_enabled_check.setToolTip("Enable AI-powered upscaling using Real-ESRGAN or Anime4K.\nExtract → Upscale → Recombine pipeline.")
        layout.addWidget(self.ai_enabled_check)
        
        # AI Upscaling Group
        self.ai_group = QGroupBox()
        ai_group_layout = QVBoxLayout(self.ai_group)
        ai_group_layout.setSpacing(5)
        
        # Upscaler row
        upscaler_row = QHBoxLayout()
        upscaler_row.addWidget(QLabel("Upscaler:"))
        self.ai_upscaler_combo = QComboBox()
        from config import UPSCALING_MODELS
        for key, info in UPSCALING_MODELS.items():
            self.ai_upscaler_combo.addItem(info["label"], key)
        self.ai_upscaler_combo.setCurrentIndex(0)
        self.ai_upscaler_combo.setToolTip(
            "Select the AI upscaling engine:\n"
            "• Real-ESRGAN — Neural network, best quality, 4 models\n"
            "• Anime4K — Shader-based, very fast, 3 presets"
        )
        upscaler_row.addWidget(self.ai_upscaler_combo)
        upscaler_row.addStretch()
        ai_group_layout.addLayout(upscaler_row)
        
        # Model row (alone to avoid stretching)
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model:"))
        self.ai_model_combo = QComboBox()
        self.ai_model_combo.setMinimumWidth(300)
        self.ai_model_combo.setToolTip(
            "AI upscaling model:\n"
            "• realesrgan-x4plus — General purpose (default)\n"
            "• realesrnet-x4plus — Faster, slightly lower quality\n"
            "• realesrgan-x4plus-anime — Optimized for anime\n"
            "• reales-animevideov3 — Lightweight anime video\n\n"
            "Anime4K models:\n"
            "• A — Fastest\n"
            "• B — Balanced\n"
            "• C — Best quality"
        )
        model_row.addWidget(self.ai_model_combo)
        model_row.addStretch()
        ai_group_layout.addLayout(model_row)
        
        # Scale + Tile Size on same row
        scale_tile_row = QHBoxLayout()
        scale_tile_row.addWidget(QLabel("Scale:"))
        self.ai_scale_combo = QComboBox()
        self.ai_scale_combo.setToolTip("Upscaling factor:\n2x = double resolution\n3x = triple resolution\n4x = quadruple resolution")
        scale_tile_row.addWidget(self.ai_scale_combo)
        scale_tile_row.addSpacing(15)
        scale_tile_row.addWidget(QLabel("Tile Size:"))
        self.ai_tile_spin = QSpinBox()
        self.ai_tile_spin.setRange(0, 1024)
        self.ai_tile_spin.setValue(self.app_state.ai_upscaling.tile_size)
        self.ai_tile_spin.setSingleStep(32)
        self.ai_tile_spin.setSuffix(" px  (0 = auto)")
        self.ai_tile_spin.setToolTip(
            "Tile size for GPU memory management.\n"
            "Smaller = less VRAM usage, slower\n"
            "Larger = more VRAM, faster\n"
            "0 = auto-detect best tile size.\n\n"
            "Recommended:\n"
            "• 128-256 for 4GB VRAM\n"
            "• 256-512 for 8GB+ VRAM\n"
            "• 0 for auto"
        )
        scale_tile_row.addWidget(self.ai_tile_spin)
        scale_tile_row.addStretch()
        ai_group_layout.addLayout(scale_tile_row)
        
        # Part duration
        part_row = QHBoxLayout()
        part_row.addWidget(QLabel("Part Duration:"))
        self.ai_part_combo = QComboBox()
        self.ai_part_combo.addItems(["1 min", "5 min"])
        self.ai_part_combo.setCurrentText(f"{self.app_state.ai_upscaling.part_duration_minutes} min")
        self.ai_part_combo.setToolTip(
            "Duration of each frame part.\n"
            "Shorter parts = more resumable but more folders.\n"
            "• 1 min — Good for long videos, fine-grained resume\n"
            "• 5 min — Fewer parts, faster overall"
        )
        part_row.addWidget(self.ai_part_combo)
        part_row.addStretch()
        ai_group_layout.addLayout(part_row)
        
        # Frames directory
        frames_dir_row = QHBoxLayout()
        frames_dir_row.addWidget(QLabel("Frames Dir:"))
        self.ai_frames_dir_edit = QLineEdit(self.app_state.ai_upscaling.frames_dir)
        self.ai_frames_dir_edit.setPlaceholderText("Auto (next to source video)")
        self.ai_frames_dir_edit.setReadOnly(True)
        self.ai_frames_dir_edit.setToolTip("Directory where extracted frame parts will be stored.\nLeave empty for auto (next to source video).")
        frames_dir_row.addWidget(self.ai_frames_dir_edit)
        self.ai_browse_frames_btn = QPushButton("Browse...")
        self.ai_browse_frames_btn.setMaximumWidth(80)
        self.ai_browse_frames_btn.setToolTip("Choose a custom directory for frame storage")
        frames_dir_row.addWidget(self.ai_browse_frames_btn)
        ai_group_layout.addLayout(frames_dir_row)

        # Single image upscale
        single_img_row = QHBoxLayout()
        self.ai_upscale_img_btn = QPushButton("Upscale Single Image")
        self.ai_upscale_img_btn.setToolTip(
            "Upscale a single image file (not from a video).\n"
            "Uses the current model and scale settings."
        )
        single_img_row.addWidget(self.ai_upscale_img_btn)
        single_img_row.addStretch()
        ai_group_layout.addLayout(single_img_row)
        
        # ── Pipeline Buttons ──
        pipeline_line = QFrame()
        pipeline_line.setFrameShape(QFrame.HLine)
        pipeline_line.setFrameShadow(QFrame.Sunken)
        ai_group_layout.addWidget(pipeline_line)
        
        # Extract
        extract_row = QHBoxLayout()
        self.ai_extract_btn = QPushButton("1. Extract Frames")
        self.ai_extract_btn.setToolTip(
            "Step 1: Split video into parts and extract PNG frames.\n"
            "Each part is stored in its own folder (e.g., 001_00m-01m/).\n"
            "Existing parts are skipped (resume-friendly)."
        )
        extract_row.addWidget(self.ai_extract_btn)
        self.ai_extract_status = QLabel("Waiting...")
        self.ai_extract_status.setStyleSheet("color: gray;")
        self.ai_extract_status.setToolTip("Status of frame extraction")
        extract_row.addWidget(self.ai_extract_status)
        extract_row.addStretch()
        ai_group_layout.addLayout(extract_row)
        
        # Part selector + Upscale Part
        upscale_part_row = QHBoxLayout()
        self.ai_part_combo_selector = QComboBox()
        self.ai_part_combo_selector.setMinimumWidth(180)
        self.ai_part_combo_selector.setToolTip("Select a specific part folder to upscale individually")
        upscale_part_row.addWidget(QLabel("Part:"))
        upscale_part_row.addWidget(self.ai_part_combo_selector)
        self.ai_upscale_part_btn = QPushButton("2a. Upscale Part")
        self.ai_upscale_part_btn.setToolTip(
            "Upscale only the selected part.\n"
            "Useful for testing or resuming from a specific point.\n"
            "Creates a *_upscaled/ mirror folder."
        )
        upscale_part_row.addWidget(self.ai_upscale_part_btn)
        self.ai_test_frame_btn = QPushButton("Test")
        self.ai_test_frame_btn.setMaximumWidth(60)
        self.ai_test_frame_btn.setToolTip(
            "Upscale only the first frame of the selected part for a quick test.\n"
            "Result is saved next to the original frame."
        )
        upscale_part_row.addWidget(self.ai_test_frame_btn)
        upscale_part_row.addStretch()
        ai_group_layout.addLayout(upscale_part_row)
        
        # Upscale All + progress
        upscale_all_row = QHBoxLayout()
        self.ai_upscale_all_btn = QPushButton("2b. Upscale All (remaining)")
        self.ai_upscale_all_btn.setToolTip(
            "Upscale all parts that haven't been processed yet.\n"
            "Skips parts that already have a *_upscaled/ folder.\n"
            "This is the main upscaling step — runs the AI model on each frame."
        )
        upscale_all_row.addWidget(self.ai_upscale_all_btn)
        self.ai_upscale_progress = QLabel("")
        self.ai_upscale_progress.setStyleSheet("color: gray;")
        self.ai_upscale_progress.setToolTip("Progress of batch upscaling")
        upscale_all_row.addWidget(self.ai_upscale_progress)
        upscale_all_row.addStretch()
        ai_group_layout.addLayout(upscale_all_row)
        
        # Recombine
        recombine_row = QHBoxLayout()
        self.ai_recombine_btn = QPushButton("3. Recombine Video")
        self.ai_recombine_btn.setToolTip(
            "Step 3: Combine all upscaled frame parts into a single video file.\n"
            "Each *_upscaled/ folder is encoded to a temp MP4, then all are concatenated.\n"
            "Result is saved as <video>_ai_upscaled.mp4 in the frames directory."
        )
        recombine_row.addWidget(self.ai_recombine_btn)
        self.ai_recombine_status = QLabel("Waiting...")
        self.ai_recombine_status.setStyleSheet("color: gray;")
        self.ai_recombine_status.setToolTip("Status of video recombination")
        recombine_row.addWidget(self.ai_recombine_status)
        recombine_row.addStretch()
        ai_group_layout.addLayout(recombine_row)
        
        # Cleanup checkbox
        self.ai_cleanup_check = QCheckBox("Clean up temp frames after encode")
        self.ai_cleanup_check.setChecked(self.app_state.ai_upscaling.cleanup_temp)
        self.ai_cleanup_check.setToolTip(
            "Delete all extracted and upscaled frame files after encoding completes.\n"
            "Saves disk space but requires re-extraction if you want to upscale again."
        )
        ai_group_layout.addWidget(self.ai_cleanup_check)
        
        # Hide group initially if not enabled
        self.ai_group.setVisible(self.app_state.ai_upscaling.enabled)
        self._populate_ai_models()
        self._populate_ai_scales()
        
        layout.addWidget(self.ai_group)
        
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
        self.profile_combo.setToolTip("Video profile (default: main; DVD: main)")
        profile_layout.addWidget(self.profile_combo)
        profile_layout.addStretch()
        advanced_layout.addLayout(profile_layout)
        
        # Level
        level_layout = QHBoxLayout()
        level_layout.addWidget(QLabel("Level:"))
        self.level_combo = QComboBox()
        self.level_combo.addItems(["3.0", "3.1", "4.0", "4.1", "4.2", "5.0", "5.1"])
        self.level_combo.setCurrentText("4.0")
        self.level_combo.setToolTip("Video level — not used by mpeg2video (default: 4.0; DVD: N/A)")
        level_layout.addWidget(self.level_combo)
        level_layout.addStretch()
        advanced_layout.addLayout(level_layout)
        
        # B-Frames
        bframes_layout = QHBoxLayout()
        bframes_layout.addWidget(QLabel("B-Frames:"))
        self.bframes_combo = QComboBox()
        self.bframes_combo.addItems(["0", "1", "2", "3"])
        self.bframes_combo.setCurrentText("0")
        self.bframes_combo.setToolTip("Number of B-frames between I/P frames (default: 0; DVD: 2)")
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
        self.audio_mode_combo.setToolTip("Audio processing mode:\nEncode: Re-encode audio (see Audio Codec selection)\nCopy: Copy original audio stream without re-encoding (faster)")
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
        
        # Audio Codec Selection
        audio_codec_layout = QHBoxLayout()
        audio_codec_layout.addWidget(QLabel("Audio Codec:"))
        self.audio_codec_combo = QComboBox()
        self.audio_codec_combo.addItems(["aac", "mp2", "ac3", "mp3"])
        self.audio_codec_combo.setCurrentText(self.app_state.encoding.audio_codec)
        self.audio_codec_combo.setMinimumWidth(100)
        self.audio_codec_combo.setToolTip("Audio codec to use when Audio Mode is set to Encode.\naac: Best compatibility (default)\nmp2: MPEG-1 Audio Layer II (DVD compatible)\nac3: Dolby Digital (DVD compatible)\nmp3: MPEG-1 Audio Layer III")
        audio_codec_layout.addWidget(self.audio_codec_combo)
        audio_codec_layout.addStretch()
        advanced_layout.addLayout(audio_codec_layout)
        
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
        self.sample_rate_combo.setToolTip("Audio sample rate in Hz (default: 44100; DVD: 48000)")
        sample_rate_layout.addWidget(self.sample_rate_combo)
        sample_rate_layout.addStretch()
        advanced_layout.addLayout(sample_rate_layout)
        
        # GOP Size
        gop_layout = QHBoxLayout()
        gop_layout.addWidget(QLabel("GOP Size:"))
        self.gop_combo = QComboBox()
        self.gop_combo.addItems(["48", "96", "144", "250"])
        self.gop_combo.setCurrentText("144")
        self.gop_combo.setToolTip("Keyframe interval (GOP size). Lower = better seeking (default: 144; DVD: 12)")
        gop_layout.addWidget(self.gop_combo)
        gop_layout.addStretch()
        advanced_layout.addLayout(gop_layout)
        
        # Framerate selector
        self.framerate_values = {
            "23.976 fps": "24000/1001",
            "25 fps (PAL)": "25/1",
            "29.97 fps (NTSC)": "30000/1001",
            "30 fps": "30/1",
            "50 fps": "50/1",
            "59.94 fps": "60000/1001",
            "60 fps": "60/1",
        }
        framerate_layout = QHBoxLayout()
        framerate_layout.addWidget(QLabel("Framerate:"))
        self.framerate_combo = QComboBox()
        self.framerate_combo.addItems(list(self.framerate_values.keys()))
        current_fps = self.app_state.encoding.framerate
        current_display = "23.976 fps"
        for display, value in self.framerate_values.items():
            if value == current_fps:
                current_display = display
                break
        self.framerate_combo.setCurrentText(current_display)
        self.framerate_combo.setToolTip("Output framerate.\nNTSC/PAL auto-set when those resolution standards are selected.")
        framerate_layout.addWidget(self.framerate_combo)
        framerate_layout.addStretch()
        advanced_layout.addLayout(framerate_layout)
        
        layout.addWidget(advanced_collapsible)
        
        layout.addStretch()
        
    def connect_signals(self):
        """Connect UI signals to handlers"""
        self.app_state.media_engine_changed.connect(self.on_engine_changed)
        self.engine_combo.currentIndexChanged.connect(self.on_engine_combo_changed)
        self.gpu_check.toggled.connect(self.on_gpu_changed)
        self.video_track_combo.currentIndexChanged.connect(self.on_video_track_changed)
        self.encoder_combo.currentTextChanged.connect(self.on_encoder_changed)
        self.video_mode_combo.currentTextChanged.connect(self.on_video_mode_changed)
        self.sync_audio_btn.clicked.connect(self.on_sync_audio)
        self.resolution_combo.currentTextChanged.connect(self.on_resolution_changed)
        self.custom_res_edit.textChanged.connect(self.on_custom_res_changed)
        self.framerate_combo.currentTextChanged.connect(self.on_framerate_changed)
        self.cq_slider.valueChanged.connect(self.on_cq_changed)
        self.bitrate_mode_combo.currentTextChanged.connect(self.on_bitrate_mode_changed)
        self.bitrate_edit.textChanged.connect(self.on_target_bitrate_changed)
        self.orig_br_check.toggled.connect(self.on_orig_br_changed)
        self.use_max_br_check.toggled.connect(self.on_use_max_br_changed)
        self.calc_size_btn.clicked.connect(self.on_calculate_target_size)
        self.max_br_spin.valueChanged.connect(self.on_max_br_changed)
        self.container_combo.currentTextChanged.connect(self.on_container_changed)
        self.scale_mode_combo.currentTextChanged.connect(self.on_scale_mode_changed)
        self.algorithm_combo.currentTextChanged.connect(self.on_algorithm_changed)
        self.gst_algorithm_combo.currentTextChanged.connect(self.on_gst_algorithm_changed)
        self.scale_quality_combo.currentTextChanged.connect(self.on_scale_quality_changed)
        self.tone_mapping_combo.currentTextChanged.connect(self.on_tone_mapping_changed)
        self.aspect_ratio_combo.currentTextChanged.connect(self.on_aspect_ratio_changed)
        self.audio_mode_combo.currentTextChanged.connect(self.on_audio_mode_changed)
        self.audio_track_combo.currentIndexChanged.connect(self.on_audio_track_changed)
        self.audio_codec_combo.currentTextChanged.connect(self.on_audio_codec_changed)
        self.gpu_preset_combo.currentTextChanged.connect(self.on_gpu_preset_changed)
        self.cpu_preset_combo.currentTextChanged.connect(self.on_cpu_preset_changed)
        self.cpu_tune_combo.currentTextChanged.connect(self.on_cpu_tune_changed)
        self.pix_fmt_combo.currentTextChanged.connect(self.on_pix_fmt_changed)
        self.profile_combo.currentTextChanged.connect(self.on_profile_changed)
        self.level_combo.currentTextChanged.connect(self.on_level_changed)
        self.bframes_combo.currentTextChanged.connect(self.on_bframes_changed)
        self.sample_rate_combo.currentTextChanged.connect(self.on_sample_rate_changed)
        self.gop_combo.currentTextChanged.connect(self.on_gop_changed)
        
        # External audio signals
        self.external_audio_check.toggled.connect(self.on_external_audio_toggled)
        self.browse_audio_btn.clicked.connect(self.on_browse_external_audio)
        self.clear_audio_btn.clicked.connect(self.on_clear_external_audio)
        
        # AI Upscaling signals
        self.ai_enabled_check.toggled.connect(self.on_ai_enabled_toggled)
        self.ai_upscaler_combo.currentIndexChanged.connect(self.on_ai_upscaler_changed)
        self.ai_model_combo.currentTextChanged.connect(self.on_ai_model_changed)
        self.ai_scale_combo.currentTextChanged.connect(self.on_ai_scale_changed)
        self.ai_tile_spin.valueChanged.connect(self.on_ai_tile_changed)
        self.ai_part_combo.currentTextChanged.connect(self.on_ai_part_changed)
        self.ai_browse_frames_btn.clicked.connect(self.on_ai_browse_frames)
        self.ai_extract_btn.clicked.connect(self.on_ai_extract_frames)
        self.ai_upscale_part_btn.clicked.connect(self.on_ai_upscale_part)
        self.ai_test_frame_btn.clicked.connect(self.on_ai_test_frame)
        self.ai_upscale_img_btn.clicked.connect(self.on_ai_upscale_single_image)
        self.ai_upscale_all_btn.clicked.connect(self.on_ai_upscale_all)
        self.ai_recombine_btn.clicked.connect(self.on_ai_recombine)
        self.ai_cleanup_check.toggled.connect(self.on_ai_cleanup_changed)
        
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

    def on_video_track_changed(self, index):
        """Handle video track selection change"""
        if hasattr(self.app_state.tracks, 'available_video_tracks'):
            tracks = self.app_state.tracks.available_video_tracks
            if index >= 0 and index < len(tracks):
                self.app_state.tracks.video_stream_index = index
                self.settings_changed.emit()

    def populate_video_tracks(self, tracks: list):
        """Populate video track combo with available tracks"""
        self.video_track_combo.clear()

        if not tracks:
            self.video_track_combo.addItem("No video tracks detected")
            self.video_track_combo.setEnabled(False)
            return

        for i, track in enumerate(tracks):
            display_text = f"Track {i+1}"
            if track.title:
                display_text += f" - {track.title}"
            if track.language:
                display_text += f" [{track.language}]"
            display_text += f" ({track.codec}"
            if track.width and track.height:
                display_text += f", {track.width}x{track.height}"
            if track.fps:
                try:
                    parts = track.fps.split('/')
                    if len(parts) == 2:
                        num, den = float(parts[0]), float(parts[1])
                        if den > 0:
                            display_text += f", {num/den:.2f}fps"
                except (ValueError, ZeroDivisionError):
                    pass
            display_text += ")"
            self.video_track_combo.addItem(display_text)

        self.video_track_combo.setEnabled(True)

        # Default to track 1 (index 0)
        default_index = 0
        self.video_track_combo.setCurrentIndex(default_index)
        self.app_state.tracks.video_stream_index = default_index

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
        """Get information about external audio file via backend"""
        try:
            return self.app_state.backend.get_external_audio_info(file_path)
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
        
    def on_engine_changed(self, engine):
        idx = 0 if engine == "ffmpeg" else 1
        if self.engine_combo.currentIndex() != idx:
            self.engine_combo.setCurrentIndex(idx)
        self.engine_indicator.setText("GStreamer" if engine == "gstreamer" else "FFmpeg")
        self.engine_indicator.setStyleSheet(
            "color: #2196F3; font-weight: bold;" if engine == "gstreamer" else "color: #4CAF50; font-weight: bold;"
        )
        is_gst = engine == "gstreamer"
        self.algo_label.setText("GST Algorithm:" if is_gst else "Algorithm:")
        self.algorithm_combo.setVisible(not is_gst)
        self.gst_algo_label.setVisible(is_gst)
        self.gst_algorithm_combo.setVisible(is_gst)

    def on_engine_combo_changed(self, index):
        engine = "gstreamer" if index == 1 else "ffmpeg"
        self.app_state.media_engine = engine

    def on_gpu_changed(self, checked):
        """Handle GPU checkbox change"""
        self.app_state.encoding.use_gpu = checked
        # Update encoder list based on GPU availability
        current = self.encoder_combo.currentText()
        self.encoder_combo.clear()
        if checked:
            self.encoder_combo.addItems(["h264_nvenc", "hevc_nvenc", "libx264", "libx265", "mpeg2video"])
        else:
            self.encoder_combo.addItems(["libx264", "libx265", "mpeg2video"])
        # Try to restore selection
        index = self.encoder_combo.findText(current)
        if index >= 0:
            self.encoder_combo.setCurrentIndex(index)
        self.settings_changed.emit()
        
    def on_encoder_changed(self, text):
        """Handle encoder selection change"""
        self.app_state.encoding.encoder = text
        if text == "mpeg2video":
            self.container_combo.setCurrentText("mpg")
            self.app_state.encoding.container = "mpg"
            self.audio_codec_combo.setCurrentText("mp2")
            self.app_state.encoding.audio_codec = "mp2"
            self.bframes_combo.setCurrentText("2")
            self.app_state.encoding.bframes = "2"
            self.gop_combo.setCurrentText("12")
            self.app_state.encoding.gop_size = "12"
        elif self.app_state.encoding.container in ("mpg", "vob"):
            self.container_combo.setCurrentText("mp4")
            self.app_state.encoding.container = "mp4"
            self.audio_codec_combo.setCurrentText("aac")
            self.app_state.encoding.audio_codec = "aac"
            self.bframes_combo.setCurrentText("0")
            self.app_state.encoding.bframes = "0"
            self.gop_combo.setCurrentText("144")
            self.app_state.encoding.gop_size = "144"
            self.level_combo.setCurrentText("4.0")
            self.app_state.encoding.level = "4.0"
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
        
    def on_sync_audio(self):
        """One-shot: set audio mode to match current video mode"""
        self.audio_mode_combo.setCurrentText(self.video_mode_combo.currentText())
        
    def on_audio_mode_changed(self, text):
        """Handle audio mode change (Encode/Copy)"""
        self.app_state.encoding.audio_mode = text.lower()
        self.settings_changed.emit()
        
    def on_audio_codec_changed(self, text):
        """Handle audio codec selection change"""
        self.app_state.encoding.audio_codec = text
        self.settings_changed.emit()
        
    def on_resolution_changed(self, text):
        """Handle resolution change"""
        if text == "original":
            self.app_state.encoding.resolution = "none"
        elif text == "Custom":
            self.app_state.encoding.resolution = "Custom"
        elif text == "NTSC (720x480)":
            self.app_state.encoding.resolution = "720x480"
            self.app_state.encoding.framerate = "30000/1001"
            self.framerate_combo.setCurrentText("29.97 fps (NTSC)")
        elif text == "PAL (720x576)":
            self.app_state.encoding.resolution = "720x576"
            self.app_state.encoding.framerate = "25/1"
            self.framerate_combo.setCurrentText("25 fps (PAL)")
        else:
            self.app_state.encoding.resolution = text
        
        # Enable/disable custom resolution input
        self.custom_res_edit.setEnabled(text == "Custom")
        self.settings_changed.emit()
    
    def on_custom_res_changed(self, text):
        """Handle custom resolution text change"""
        self.app_state.encoding.custom_resolution = text
        self.settings_changed.emit()
        
    def on_framerate_changed(self, text):
        """Handle framerate selection change"""
        self.app_state.encoding.framerate = self.framerate_values.get(text, "24000/1001")
        self.settings_changed.emit()
        
    def on_cq_changed(self, value):
        """Handle CQ slider change"""
        self.app_state.encoding.cq = value
        self.cq_label.setText(str(value))
        # CQ mode is mutually exclusive with bitrate mode.
        # Clear the target bitrate and uncheck "Use Original Bitrate"
        # so the backend knows to use CQ (const-quality) instead of CBR.
        self.app_state.encoding.target_bitrate = ""
        self.app_state.encoding.use_original_bitrate = False
        self.orig_br_check.setChecked(False)
        self.bitrate_edit.setText("")
        self.bitrate_edit.setEnabled(True)
        self.bitrate_edit.setStyleSheet("")
        self.settings_changed.emit()
        
    def on_bitrate_mode_changed(self, text):
        """Handle bitrate mode change"""
        self.app_state.encoding.bitrate_mode = text
        self.settings_changed.emit()
        
    def on_target_bitrate_changed(self, text):
        """Handle target bitrate change"""
        self.app_state.encoding.target_bitrate = text
        if text and text.isdigit() and int(text) > 0:
            self.app_state.encoding.cq = 23
            self.cq_slider.setValue(23)
            self.cq_label.setText("23")
        self.settings_changed.emit()
        
    def on_orig_br_changed(self, checked):
        """Handle original bitrate checkbox change"""
        self.app_state.encoding.use_original_bitrate = checked
        if checked:
            self.app_state.encoding.cq = 23
            self.cq_slider.setValue(23)
            self.cq_label.setText("23")
        # Disable target bitrate input when using original
        self.bitrate_edit.setEnabled(not checked)
        if not checked:
            self.bitrate_edit.setStyleSheet("")
        else:
            self.bitrate_edit.setStyleSheet("color: gray;")
        self.settings_changed.emit()
        
    def on_calculate_target_size(self):
        """Calculate target bitrate from desired file size and video duration"""
        target_mb = self.target_size_spin.value()
        if target_mb <= 0:
            return

        input_files = self.app_state.input_files
        if not input_files:
            self.app_state.log("No input file loaded. Load a video first.", "WARN")
            return

        input_path = input_files[0]
        duration = self.app_state.backend.get_duration(input_path)
        if duration <= 0:
            self.app_state.log("Could not determine video duration.", "WARN")
            return

        total_bitrate = target_mb * 8192 / duration
        audio_bitrate = 128
        video_bitrate = int(total_bitrate) - audio_bitrate
        if video_bitrate < 50:
            self.app_state.log(f"Calculated bitrate too low ({video_bitrate} kbps). Increase target size.", "WARN")
            return

        self.app_state.encoding.target_bitrate = str(video_bitrate)
        self.app_state.encoding.use_original_bitrate = False
        self.app_state.encoding.cq = 23
        self.cq_slider.setValue(23)
        self.cq_label.setText("23")
        self.orig_br_check.setChecked(False)
        self.bitrate_edit.setText(str(video_bitrate))
        self.bitrate_edit.setEnabled(True)
        self.bitrate_edit.setStyleSheet("")
        self.app_state.log(f"Set bitrate to {video_bitrate} kbps for ~{target_mb} MB target (duration: {duration:.0f}s)", "INFO")
        self.settings_changed.emit()

    def on_max_br_changed(self, value):
        """Handle max bitrate change"""
        self.app_state.encoding.max_bitrate = value
        self.settings_changed.emit()

    def on_use_max_br_changed(self, checked):
        """Handle max bitrate checkbox change"""
        self.app_state.encoding.use_max_bitrate = checked
        self.max_br_spin.setEnabled(checked)
        self.settings_changed.emit()
        
    def on_container_changed(self, text):
        """Handle container format change"""
        self.app_state.encoding.container = text
        self.settings_changed.emit()
        
    def on_scale_mode_changed(self, text):
        """Handle scale mode change"""
        self.app_state.encoding.scale_mode = text
        is_gst = self.app_state.media_engine == "gstreamer"
        
        # Enable/disable algorithm and quality based on scale mode
        if text == "off":
            self.algorithm_combo.setEnabled(False)
            self.gst_algorithm_combo.setEnabled(False)
            self.scale_quality_combo.setEnabled(False)
            self.algorithm_combo.setStyleSheet("color: gray;")
            self.gst_algorithm_combo.setStyleSheet("color: gray;")
            self.scale_quality_combo.setStyleSheet("color: gray;")
        else:
            self.algorithm_combo.setEnabled(not is_gst)
            self.gst_algorithm_combo.setEnabled(is_gst)
            self.scale_quality_combo.setEnabled(True)
            self.algorithm_combo.setStyleSheet("" if not is_gst else "color: gray;")
            self.gst_algorithm_combo.setStyleSheet("" if is_gst else "color: gray;")
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
        
    def on_gst_algorithm_changed(self, text):
        self.app_state.encoding.gst_scale_algorithm = text
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

    def on_profile_changed(self, text):
        """Handle profile change"""
        self.app_state.encoding.profile = text
        self.settings_changed.emit()

    def on_level_changed(self, text):
        """Handle level change"""
        self.app_state.encoding.level = text
        self.settings_changed.emit()

    def on_bframes_changed(self, text):
        """Handle B-frames change"""
        self.app_state.encoding.bframes = text
        self.settings_changed.emit()

    def on_sample_rate_changed(self, text):
        """Handle audio sample rate change"""
        rate = text.split()[0]
        self.app_state.encoding.audio_sample_rate = rate
        self.settings_changed.emit()

    def on_gop_changed(self, text):
        """Handle GOP size change"""
        self.app_state.encoding.gop_size = text
        self.settings_changed.emit()

    # ── AI Upscaling Helpers ──────────────────────────────────────

    def _populate_ai_models(self):
        import os
        from config import UPSCALING_MODELS, REALESRGAN_NCNN, ANIME4K_NCNN
        key = self.ai_upscaler_combo.currentData()
        info = UPSCALING_MODELS.get(key, {})
        self.ai_model_combo.clear()

        binary = ""
        if key == "realesrgan":
            binary = self.app_state.realesrgan_path or REALESRGAN_NCNN
        elif key == "anime4k":
            binary = self.app_state.anime4k_path or ANIME4K_NCNN
        model_dir = os.path.join(os.path.dirname(binary), "models") if binary else ""

        for model_key, desc in info.get("models", []):
            if model_dir and os.path.isdir(model_dir):
                model_bin = os.path.join(model_dir, f"{model_key}.bin")
                if not os.path.isfile(model_bin):
                    continue
            self.ai_model_combo.addItem(f"{model_key} — {desc}", model_key)

        default = info.get("default_model", "")
        idx = self.ai_model_combo.findData(default)
        if idx >= 0:
            self.ai_model_combo.setCurrentIndex(idx)
        self.app_state.ai_upscaling.upscaler = key

    def _populate_ai_scales(self):
        from config import UPSCALING_MODELS
        key = self.ai_upscaler_combo.currentData()
        info = UPSCALING_MODELS.get(key, {})
        self.ai_scale_combo.clear()
        for s in info.get("scales", [4]):
            self.ai_scale_combo.addItem(f"{s}x", s)

    def _refresh_part_list(self):
        self.ai_part_combo_selector.clear()
        ai = self.app_state.ai_upscaling
        if not ai.frames_dir:
            self.app_state.log("No frames directory set", "WARN")
            return
        parts = self.app_state.backend.get_part_dirs(ai.frames_dir)
        if parts:
            self.ai_part_combo_selector.addItems(parts)
        else:
            self.app_state.log(f"No part folders found in: {ai.frames_dir}", "WARN")

    def on_ai_enabled_toggled(self, checked):
        self.app_state.ai_upscaling.enabled = checked
        self.ai_group.setVisible(checked)
        self.settings_changed.emit()

    def on_ai_upscaler_changed(self, index):
        self._populate_ai_models()
        self._populate_ai_scales()
        self.settings_changed.emit()

    def on_ai_model_changed(self, text):
        self.app_state.ai_upscaling.model = self.ai_model_combo.currentData()
        self.settings_changed.emit()

    def on_ai_scale_changed(self, text):
        self.app_state.ai_upscaling.scale = self.ai_scale_combo.currentData()
        self.settings_changed.emit()

    def on_ai_tile_changed(self, value):
        self.app_state.ai_upscaling.tile_size = value
        self.settings_changed.emit()

    def on_ai_part_changed(self, text):
        minutes = int(text.split()[0])
        self.app_state.ai_upscaling.part_duration_minutes = minutes
        self.settings_changed.emit()

    def on_ai_cleanup_changed(self, checked):
        self.app_state.ai_upscaling.cleanup_temp = checked
        self.settings_changed.emit()

    def on_ai_browse_frames(self):
        import os
        folder = QFileDialog.getExistingDirectory(self, "Select Frames Directory")
        if folder:
            self.ai_frames_dir_edit.setText(folder)
            self.app_state.ai_upscaling.frames_dir = folder
            self.app_state.log(f"Frames directory set to: {folder}", "INFO")
            self._refresh_part_list()

    def _make_controller(self):
        from controller import VideoController
        return VideoController(self.app_state)

    def on_ai_extract_frames(self):
        import os
        import threading

        input_files = self.app_state.input_files
        if not input_files:
            self.app_state.log("No input file loaded.", "WARN")
            return

        input_path = input_files[0]
        controller = self._make_controller()

        self.ai_extract_btn.setEnabled(False)
        self.ai_extract_status.setText("Extracting...")
        self.ai_extract_status.setStyleSheet("color: orange;")

        def run():
            result = controller.extract_frames(input_path)
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._on_extract_done(result))

        thread = threading.Thread(target=run)
        thread.start()

    def _on_extract_done(self, result):
        self.ai_extract_btn.setEnabled(True)
        if result:
            ai = self.app_state.ai_upscaling
            self.ai_extract_status.setText(f"Done ✓ ({ai.total_parts} parts)")
            self.ai_extract_status.setStyleSheet("color: green;")
            self.ai_frames_dir_edit.setText(ai.frames_dir)
            self._refresh_part_list()
        else:
            self.ai_extract_status.setText("Failed ✗")
            self.ai_extract_status.setStyleSheet("color: red;")

    def on_ai_upscale_part(self):
        import threading
        part = self.ai_part_combo_selector.currentText()
        if not part:
            self.app_state.log("No part selected", "WARN")
            return

        self._upscale_controller = self._make_controller()

        self.ai_upscale_part_btn.setEnabled(False)
        self.ai_upscale_part_btn.setText("Upscaling...")
        self.upscaling_active.emit(True)

        controller = self._upscale_controller

        def run():
            result = controller.upscale_part(part)
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._on_upscale_part_done(result))

        thread = threading.Thread(target=run)
        thread.start()

    def _on_upscale_part_done(self, result):
        self.ai_upscale_part_btn.setEnabled(True)
        self.ai_upscale_part_btn.setText("2a. Upscale Part")
        self._upscale_controller = None
        self.upscaling_active.emit(False)
        if result:
            self.app_state.log("Part upscaled successfully", "SUCCESS")
        else:
            self.app_state.log("Part upscale failed", "ERROR")

    def on_ai_test_frame(self):
        import os, shutil, threading
        part = self.ai_part_combo_selector.currentText()
        if not part:
            self.app_state.log("No part selected for test", "WARN")
            return

        ai = self.app_state.ai_upscaling
        if not ai.frames_dir:
            self.app_state.log("No frames directory set", "WARN")
            return

        src_dir = os.path.join(ai.frames_dir, part)
        first_frame = os.path.join(src_dir, "frame_00000001.png")
        if not os.path.isfile(first_frame):
            self.app_state.log(f"No frame_00000001.png found in {part}", "ERROR")
            return

        self.ai_test_frame_btn.setEnabled(False)
        self.ai_test_frame_btn.setText("Test...")

        def run():
            import subprocess
            from config import REALESRGAN_NCNN, ANIME4K_NCNN
            if ai.upscaler == "realesrgan":
                binary = self.app_state.realesrgan_path or REALESRGAN_NCNN
            elif ai.upscaler == "anime4k":
                binary = self.app_state.anime4k_path or ANIME4K_NCNN
            else:
                self.app_state.log(f"Unknown upscaler: {ai.upscaler}", "ERROR")
                self._finish_test_frame()
                return

            if not os.path.isfile(binary):
                self.app_state.log(f"Upscaler binary not found: {binary}", "ERROR")
                self._finish_test_frame()
                return

            model_dir = os.path.join(os.path.dirname(binary), "models")
            model_bin = os.path.join(model_dir, f"{ai.model}.bin")
            if not os.path.isfile(model_bin):
                self.app_state.log(f"Model not found: {model_bin}. Available models: {os.listdir(model_dir)}", "ERROR")
                self._finish_test_frame()
                return

            test_dir = os.path.join(ai.frames_dir, f"__test_{part}")
            os.makedirs(test_dir, exist_ok=True)
            test_frame = os.path.join(test_dir, "frame_00000001.png")
            shutil.copy2(first_frame, test_frame)

            out_dir = os.path.join(ai.frames_dir, f"__test_{part}_{ai.upscaler}.png")
            os.makedirs(out_dir, exist_ok=True)

            cmd = [binary, "-i", test_dir, "-o", out_dir, "-s", str(ai.scale),
                   "-n", ai.model, "-m", model_dir, "-g", "0", "-v", "-f", "png"]
            self.app_state.log(f"Running: {' '.join(cmd)}", "INFO")

            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                for line in iter(proc.stderr.readline, ''):
                    line = line.strip()
                    if line and "%" in line and not line.startswith("["):
                        self.app_state.log(f"📷 test: {line}", "INFO")
                proc.wait()
            except Exception as e:
                self.app_state.log(f"Test upscale error: {e}", "ERROR")
                self._finish_test_frame()
                return

            result_file = os.path.join(out_dir, "frame_00000001.png")
            if proc.returncode == 0 and os.path.isfile(result_file):
                self.app_state.log(f"Test result: {result_file}", "SUCCESS")
                subprocess.Popen(["xdg-open", result_file])
            else:
                self.app_state.log("Test upscale failed", "ERROR")

            shutil.rmtree(test_dir, ignore_errors=True)
            self._finish_test_frame()

        thread = threading.Thread(target=run)
        thread.start()

    def _finish_test_frame(self):
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._reset_test_frame_btn())

    def _reset_test_frame_btn(self):
        self.ai_test_frame_btn.setEnabled(True)
        self.ai_test_frame_btn.setText("Test")

    def on_ai_upscale_single_image(self):
        from PySide6.QtWidgets import QFileDialog
        ai = self.app_state.ai_upscaling

        src_path, _ = QFileDialog.getOpenFileName(
            self, "Select an image to upscale", "",
            "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if not src_path:
            return

        import os
        base, ext = os.path.splitext(src_path)
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save upscaled image as",
            f"{base}_{ai.scale}x.png",
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;WebP (*.webp)"
        )
        if not out_path:
            return

        self.app_state.log(f"Upscaling single image: {src_path} → {out_path}", "INFO")
        self.ai_upscale_img_btn.setEnabled(False)
        self.ai_upscale_img_btn.setText("Upscaling...")

        import threading
        thread = threading.Thread(target=self._run_single_upscale, args=(src_path, out_path))
        thread.start()

    def _run_single_upscale(self, src_path: str, out_path: str):
        import subprocess, os
        from PySide6.QtCore import QTimer
        from config import REALESRGAN_NCNN, ANIME4K_NCNN

        ai = self.app_state.ai_upscaling
        out_format = os.path.splitext(out_path)[1].lstrip(".")

        if ai.upscaler == "realesrgan":
            binary = self.app_state.realesrgan_path or REALESRGAN_NCNN
        elif ai.upscaler == "anime4k":
            binary = self.app_state.anime4k_path or ANIME4K_NCNN
        else:
            self.app_state.log(f"Unknown upscaler: {ai.upscaler}", "ERROR")
            QTimer.singleShot(0, self._reset_upscale_img_btn)
            return

        if not os.path.isfile(binary):
            self.app_state.log(f"Upscaler binary not found: {binary}", "ERROR")
            QTimer.singleShot(0, self._reset_upscale_img_btn)
            return

        model_dir = os.path.join(os.path.dirname(binary), "models")
        model_bin = os.path.join(model_dir, f"{ai.model}.bin")
        if not os.path.isfile(model_bin):
            self.app_state.log(f"Model not found: {model_bin}. Check your model selection.", "ERROR")
            QTimer.singleShot(0, self._reset_upscale_img_btn)
            return

        cmd = [binary, "-i", src_path, "-o", out_path,
               "-s", str(ai.scale), "-n", ai.model, "-m", model_dir, "-g", "0",
               "-f", out_format]
        if ai.tile_size > 0:
            cmd.extend(["-t", str(ai.tile_size)])

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for line in iter(proc.stderr.readline, ''):
                line = line.strip()
                if line and "%" in line and not line.startswith("["):
                    self.app_state.log(f"📷 upscale: {line}", "INFO")
            proc.wait()
        except Exception as e:
            self.app_state.log(f"Upscale error: {e}", "ERROR")
            QTimer.singleShot(0, self._reset_upscale_img_btn)
            return

        if proc.returncode == 0 and os.path.isfile(out_path):
            self.app_state.log(f"Upscaled image saved: {out_path}", "SUCCESS")
            subprocess.Popen(["xdg-open", out_path])
        else:
            self.app_state.log("Upscale failed", "ERROR")

        QTimer.singleShot(0, self._reset_upscale_img_btn)

    def _reset_upscale_img_btn(self):
        self.ai_upscale_img_btn.setEnabled(True)
        self.ai_upscale_img_btn.setText("Upscale Single Image")

    def on_ai_upscale_all(self):
        import threading

        self._upscale_controller = self._make_controller()
        controller = self._upscale_controller

        self.ai_upscale_all_btn.setEnabled(False)
        self.ai_upscale_all_btn.setText("Upscaling...")
        self.upscaling_active.emit(True)

        def run():
            result = controller.upscale_frames()
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._on_upscale_all_done(result))

        thread = threading.Thread(target=run)
        thread.start()

    def _on_upscale_all_done(self, result):
        self.ai_upscale_all_btn.setEnabled(True)
        self.ai_upscale_all_btn.setText("2b. Upscale All (remaining)")
        self._upscale_controller = None
        self.upscaling_active.emit(False)
        ai = self.app_state.ai_upscaling
        if result:
            self.ai_upscale_progress.setText("Complete ✓")
            self.ai_upscale_progress.setStyleSheet("color: green;")
            ai.frames_upscaled = True
        else:
            self.ai_upscale_progress.setText("Failed ✗")
            self.ai_upscale_progress.setStyleSheet("color: red;")

    @property
    def is_upscaling(self):
        return self._upscale_controller is not None and self._upscale_controller.is_encoding

    def cancel_upscale(self):
        if self._upscale_controller:
            self._upscale_controller.cancel_upscale()

    def reset_upscale_buttons(self):
        self._upscale_controller = None
        self.ai_upscale_part_btn.setEnabled(True)
        self.ai_upscale_part_btn.setText("2a. Upscale Part")
        self.ai_upscale_all_btn.setEnabled(True)
        self.ai_upscale_all_btn.setText("2b. Upscale All (remaining)")
        self.ai_test_frame_btn.setEnabled(True)
        self.ai_test_frame_btn.setText("Test")
        self.ai_upscale_img_btn.setEnabled(True)
        self.ai_upscale_img_btn.setText("Upscale Single Image")
        self.upscaling_active.emit(False)

    def on_ai_recombine(self):
        import threading

        controller = self._make_controller()

        self.ai_recombine_btn.setEnabled(False)
        self.ai_recombine_status.setText("Recombining...")
        self.ai_recombine_status.setStyleSheet("color: orange;")

        def run():
            result = controller.recombine_frames()
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._on_recombine_done(result))

        thread = threading.Thread(target=run)
        thread.start()

    def _on_recombine_done(self, output_path):
        self.ai_recombine_btn.setEnabled(True)
        if output_path:
            self.ai_recombine_status.setText("Done ✓")
            self.ai_recombine_status.setStyleSheet("color: green;")
        else:
            self.ai_recombine_status.setText("Failed ✗")
            self.ai_recombine_status.setStyleSheet("color: red;")
