"""
Color Correction (EQ) Panel (PySide6)
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QSlider, QPushButton, QFrame, QComboBox, QFileDialog,
    QGroupBox, QSpinBox
)
from PySide6.QtCore import Qt, Signal, QTimer
import os

from models import AppState


class ColorCorrectionPanel(QWidget):
    """Panel for color correction (EQ) settings"""
    
    settings_changed = Signal()
    
    def __init__(self, app_state: AppState, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        
        self.setup_ui()
        self.connect_signals()
        
        # Connect engine change signal
        self.app_state.media_engine_changed.connect(self.update_engine_state)
        
        # Defer initial call to let Qt finish widget initialization first
        QTimer.singleShot(0, self.update_engine_state)
        
    def setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # === Top Controls ===
        top_layout = QHBoxLayout()
        
        self.enable_check = QCheckBox("Enable Color Correction")
        self.enable_check.setChecked(self.app_state.eq.enabled)
        top_layout.addWidget(self.enable_check)
        
        top_layout.addStretch()
        
        reset_btn = QPushButton("Reset All")
        reset_btn.clicked.connect(self.reset_defaults)
        top_layout.addWidget(reset_btn)
        
        layout.addLayout(top_layout)
        
        # === Sliders ===
        # Brightness
        self.brightness_slider = self.create_slider(
            "Brightness", self.app_state.eq.brightness,
            -0.10, 0.10, 0.00,
            "Adjusts black level. VHS tapes rarely need more than +/- 0.05."
        )
        layout.addLayout(self.brightness_slider['layout'])
        
        # Contrast
        self.contrast_slider = self.create_slider(
            "Contrast", self.app_state.eq.contrast,
            0.80, 1.30, 1.00,
            "Increases separation between dark and bright areas. Too much will crush VHS shadow detail."
        )
        layout.addLayout(self.contrast_slider['layout'])
        
        # Saturation
        self.saturation_slider = self.create_slider(
            "Saturation", self.app_state.eq.saturation,
            0.70, 1.10, 1.00,
            "Color intensity. High values can cause VHS color bleeding."
        )
        layout.addLayout(self.saturation_slider['layout'])
        
        # Gamma
        self.gamma_slider = self.create_slider(
            "Gamma", self.app_state.eq.gamma,
            0.90, 1.10, 1.00,
            "Adjusts midtone brightness without affecting black/white points."
        )
        layout.addLayout(self.gamma_slider['layout'])
        
        # === RGB Gamma Section ===
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # Link RGB checkbox
        self.link_rgb_check = QCheckBox("Link RGB Gamma (White Balance)")
        self.link_rgb_check.setChecked(True)
        layout.addWidget(self.link_rgb_check)
        
        # RGB Sliders
        self.gamma_r_slider = self.create_slider(
            "R Gamma", self.app_state.eq.gamma_r,
            0.95, 1.05, 1.00
        )
        layout.addLayout(self.gamma_r_slider['layout'])
        
        self.gamma_g_slider = self.create_slider(
            "G Gamma", self.app_state.eq.gamma_g,
            0.95, 1.05, 1.00
        )
        layout.addLayout(self.gamma_g_slider['layout'])
        
        self.gamma_b_slider = self.create_slider(
            "B Gamma", self.app_state.eq.gamma_b,
            0.95, 1.05, 1.00
        )
        layout.addLayout(self.gamma_b_slider['layout'])
        
        # === White Balance Section (colorbalance filter) ===
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line2)
        
        # White Balance enable checkbox
        self.wb_enable_check = QCheckBox("Enable White Balance")
        self.wb_enable_check.setChecked(self.app_state.eq.white_balance_enabled)
        self.wb_enable_check.setToolTip(
            "Adjust white balance using colorbalance filter.\n"
            "Similar to Shotcut's White Balance filter.\n"
            "Use presets for quick adjustments or manual mode for fine control."
        )
        layout.addWidget(self.wb_enable_check)
        
        # Preset selector for white balance
        wb_preset_layout = QHBoxLayout()
        wb_preset_layout.addWidget(QLabel("Preset:"))
        self.wb_preset_combo = QComboBox()
        self.wb_preset_combo.addItems(["Simple (All Tones)", "Shadows", "Midtones", "Highlights"])
        self.wb_preset_combo.setCurrentIndex(0)
        self.wb_preset_combo.setEnabled(self.app_state.eq.white_balance_enabled)
        self.wb_preset_combo.setToolTip(
            "Simple: Affects all tonal ranges equally\n"
            "Shadows: Adjusts dark areas\n"
            "Midtones: Adjusts middle brightness\n"
            "Highlights: Adjusts bright areas"
        )
        wb_preset_layout.addWidget(self.wb_preset_combo)
        wb_preset_layout.addStretch()
        layout.addLayout(wb_preset_layout)
        
        # White Balance sliders (R, G, B for current preset)
        self.wb_r_slider = self.create_slider(
            "Red", self.app_state.eq.wb_shadows_r if self.app_state.eq.white_balance_enabled else 0.0,
            -1.0, 1.0, 0.0,
            "Red balance: negative = more cyan, positive = more red"
        )
        layout.addLayout(self.wb_r_slider['layout'])
        
        self.wb_g_slider = self.create_slider(
            "Green", self.app_state.eq.wb_shadows_g if self.app_state.eq.white_balance_enabled else 0.0,
            -1.0, 1.0, 0.0,
            "Green balance: negative = more magenta, positive = more green"
        )
        layout.addLayout(self.wb_g_slider['layout'])
        
        self.wb_b_slider = self.create_slider(
            "Blue", self.app_state.eq.wb_shadows_b if self.app_state.eq.white_balance_enabled else 0.0,
            -1.0, 1.0, 0.0,
            "Blue balance: negative = more yellow, positive = more blue"
        )
        layout.addLayout(self.wb_b_slider['layout'])
        
        # Enable/disable WB sliders based on enable state
        self._set_wb_sliders_enabled(self.app_state.eq.white_balance_enabled)

        # === Colorization Section (B&W → Color) ===
        line3 = QFrame()
        line3.setFrameShape(QFrame.HLine)
        line3.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line3)

        # Enable checkbox
        self.colorize_check = QCheckBox("Enable Colorization (B&W → Color)")
        self.colorize_check.setChecked(self.app_state.colorization.enabled)
        self.colorize_check.setToolTip(
            "Add color to black and white video using non-AI methods.\n"
            "Tint: Uniform color tint (sepia, blue, etc.)\n"
            "Pseudocolor: Map brightness levels to colors\n"
            "LUT: Apply a color lookup table (.cube file)"
        )
        layout.addWidget(self.colorize_check)

        # Method selector
        method_layout = QHBoxLayout()
        method_layout.addWidget(QLabel("Method:"))
        self.colorize_method_combo = QComboBox()
        self.colorize_method_combo.addItems(["Tint", "Pseudocolor", "LUT"])
        self.colorize_method_combo.setCurrentText(
            {"tint": "Tint", "pseudocolor": "Pseudocolor", "lut": "LUT"}
            .get(self.app_state.colorization.method, "Tint")
        )
        self.colorize_method_combo.setEnabled(self.app_state.colorization.enabled)
        self.colorize_method_combo.setToolTip(
            "Tint: Applies a uniform color tint based on hue/saturation\n"
            "Pseudocolor: Maps grayscale luminance to a color gradient\n"
            "LUT: Uses a 3D LUT file for color transformation"
        )
        method_layout.addWidget(self.colorize_method_combo)
        method_layout.addStretch()
        layout.addLayout(method_layout)

        # ---- Tint Controls ----
        self.tint_group = QGroupBox("Tint Settings")
        tint_layout = QVBoxLayout(self.tint_group)

        # Color preset combo
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("Preset:"))
        self.tint_preset_combo = QComboBox()
        self.tint_preset_combo.addItems([
            "Sepia", "Warm", "Cool", "Blue", "Green", "Red", "Purple"
        ])
        self.tint_preset_combo.setToolTip(
            "Quick tint presets:\n"
            "Sepia: Classic warm brown (30°)\n"
            "Warm: Golden hour look (15°)\n"
            "Cool: Blue/cold tone (200°)\n"
            "Blue: Classic blue cast (240°)\n"
            "Green: Green tint (120°)\n"
            "Red: Red/pink tone (0°)\n"
            "Purple: Purple/violet cast (280°)"
        )
        self.tint_preset_combo.setEnabled(self.app_state.colorization.enabled)
        preset_layout.addWidget(self.tint_preset_combo)
        preset_layout.addStretch()
        tint_layout.addLayout(preset_layout)

        # Hue slider
        c = self.app_state.colorization
        self.colorize_hue_slider = self.create_slider(
            "Hue", c.tint_hue, 0.0, 360.0, 30.0,
            "Tint color hue angle (0-360°).\n0=Red, 120=Green, 240=Blue, 360=Red"
        )
        tint_layout.addLayout(self.colorize_hue_slider['layout'])

        # Saturation slider
        self.colorize_sat_slider = self.create_slider(
            "Saturation", c.tint_saturation, 0.0, 2.0, 0.6,
            "Color saturation of the tint.\n0=Gray, 0.5=Pastel, 1.0=Full, 2.0=Oversaturated"
        )
        tint_layout.addLayout(self.colorize_sat_slider['layout'])

        # Strength slider
        self.colorize_strength_slider = self.create_slider(
            "Strength", c.tint_strength, 0.0, 1.0, 1.0,
            "How much tint to apply.\n0=Original, 0.5=Partial, 1.0=Full tint"
        )
        tint_layout.addLayout(self.colorize_strength_slider['layout'])

        self.tint_group.setEnabled(self.app_state.colorization.enabled and c.method == "tint")
        layout.addWidget(self.tint_group)

        # ---- Pseudocolor Controls ----
        self.pseudocolor_group = QGroupBox("Pseudocolor Settings")
        pc_layout = QVBoxLayout(self.pseudocolor_group)

        pc_preset_row = QHBoxLayout()
        pc_preset_row.addWidget(QLabel("Preset:"))
        self.pc_preset_combo = QComboBox()
        presets = [
            "rainbow", "rainbow_compressed", "rainbow4", "stripes",
            "heat_stripe", "heat", "cool", "cold_warm",
            "magma", "inferno", "plasma", "viridis", "turbo"
        ]
        self.pc_preset_combo.addItems(presets)
        idx = presets.index(c.pseudocolor_preset) if c.pseudocolor_preset in presets else 0
        self.pc_preset_combo.setCurrentIndex(idx)
        self.pc_preset_combo.setEnabled(self.app_state.colorization.enabled)
        self.pc_preset_combo.setToolTip(
            "Color gradient preset for pseudocolor mapping.\n"
            "Rainbow: Full spectrum (most colorful)\n"
            "Heat: Infrared camera style\n"
            "Cool: Blue/cyan tones\n"
            "Viridis: Perceptually uniform"
        )
        pc_preset_row.addWidget(self.pc_preset_combo)
        pc_preset_row.addStretch()
        pc_layout.addLayout(pc_preset_row)

        self.pc_opacity_slider = self.create_slider(
            "Opacity", c.pseudocolor_opacity, 0.0, 1.0, 1.0,
            "Opacity of the pseudocolor overlay.\n"
            "1.0 = Full color, 0.0 = Original grayscale"
        )
        pc_layout.addLayout(self.pc_opacity_slider['layout'])

        self.pseudocolor_group.setEnabled(self.app_state.colorization.enabled and c.method == "pseudocolor")
        layout.addWidget(self.pseudocolor_group)

        # ---- LUT Controls ----
        self.lut_group = QGroupBox("LUT Settings")
        lut_layout = QVBoxLayout(self.lut_group)

        # Type selector
        lut_type_row = QHBoxLayout()
        lut_type_row.addWidget(QLabel("Type:"))
        self.lut_type_combo = QComboBox()
        self.lut_type_combo.addItems(["lut3d", "lutrgb", "lutyuv"])
        lut_type_map = {"lut3d": "lut3d", "lutrgb": "lutrgb", "lutyuv": "lutyuv"}
        self.lut_type_combo.setCurrentText(lut_type_map.get(c.lut_type, "lut3d"))
        self.lut_type_combo.setEnabled(self.app_state.colorization.enabled)
        self.lut_type_combo.setToolTip(
            "lut3d: 3D LUT from .cube file (most common)\n"
            "lutrgb: Per-channel RGB lookup table\n"
            "lutyuv: Per-channel YUV lookup table"
        )
        lut_type_row.addWidget(self.lut_type_combo)
        lut_type_row.addStretch()
        lut_layout.addLayout(lut_type_row)

        # File browser
        lut_file_row = QHBoxLayout()
        self.lut_path_label = QLabel(c.lut_path if c.lut_path else "No LUT file selected")
        self.lut_path_label.setWordWrap(True)
        self.lut_path_label.setStyleSheet("color: gray; font-size: 10px;")
        lut_file_row.addWidget(self.lut_path_label, 1)
        self.lut_browse_btn = QPushButton("Browse...")
        self.lut_browse_btn.setEnabled(self.app_state.colorization.enabled)
        self.lut_browse_btn.setToolTip("Select a .cube 3D LUT file")
        lut_file_row.addWidget(self.lut_browse_btn)
        lut_layout.addLayout(lut_file_row)

        self.lut_group.setEnabled(self.app_state.colorization.enabled and c.method == "lut")
        layout.addWidget(self.lut_group)

        # === AI Colorization Section ===
        line4 = QFrame()
        line4.setFrameShape(QFrame.HLine)
        line4.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line4)

        self.ai_enable_check = QCheckBox("Enable AI Colorization")
        self.ai_enable_check.setChecked(self.app_state.ai_colorization.enabled)
        self.ai_enable_check.setToolTip(
            "Deep learning-based colorization using PyTorch.\n"
            "ECCV16: Lightweight, runs on CPU/GPU (~15-60 fps)\n"
            "DeOldify: Premium, GPU only (~8-12 fps)"
        )
        layout.addWidget(self.ai_enable_check)

        self.ai_group = QGroupBox("AI Colorization Settings")
        ai_layout = QVBoxLayout(self.ai_group)

        # Engine selector
        engine_row = QHBoxLayout()
        engine_row.addWidget(QLabel("Engine:"))
        self.ai_engine_combo = QComboBox()
        self.ai_engine_combo.addItems(["ECCV16 (Lightweight)", "DeOldify (Premium)"])
        self.ai_engine_combo.setCurrentText("ECCV16 (Lightweight)")
        self.ai_engine_combo.setToolTip(
            "ECCV16: Small CNN, runs on CPU/GPU, plausible colors, washed-out\n"
            "DeOldify: ResNet U-Net, GPU only, vibrant colors, requires fastai"
        )
        engine_row.addWidget(self.ai_engine_combo)
        engine_row.addStretch()
        ai_layout.addLayout(engine_row)

        # Device selector
        device_row = QHBoxLayout()
        device_row.addWidget(QLabel("Device:"))
        self.ai_device_combo = QComboBox()
        self.ai_device_combo.addItems(["cuda:0 (GPU)", "cpu (CPU)"])
        self.ai_device_combo.setCurrentText(
            "cuda:0 (GPU)" if "cuda" in self.app_state.ai_colorization.gpu_device else "cpu (CPU)"
        )
        self.ai_device_combo.setToolTip("GPU: Fast inference with CUDA\nCPU: Slower but compatible")
        device_row.addWidget(self.ai_device_combo)
        device_row.addStretch()
        ai_layout.addLayout(device_row)

        # Saturation slider
        self.ai_sat_slider = self.create_slider(
            "Saturation", self.app_state.ai_colorization.saturation,
            0.1, 2.0, 1.0,
            "Color saturation boost after AI colorization.\n"
            "1.0 = No change, 0.1 = Desaturated, 2.0 = Vibrant"
        )
        ai_layout.addLayout(self.ai_sat_slider['layout'])

        # Batch Size and FP16 in one row
        batch_fp16_row = QHBoxLayout()
        batch_fp16_row.addWidget(QLabel("Batch Size:"))
        self.ai_batch_spin = QSpinBox()
        self.ai_batch_spin.setRange(1, 128)
        self.ai_batch_spin.setValue(self.app_state.ai_colorization.batch_size)
        self.ai_batch_spin.setToolTip(
            "Frames processed simultaneously on GPU.\n"
            "Higher = faster but uses more VRAM.\n"
            "8 is safe for ECCV16 on 8GB+ GPUs."
        )
        batch_fp16_row.addWidget(self.ai_batch_spin)
        batch_fp16_row.addStretch()
        self.ai_fp16_check = QCheckBox("FP16 (Half Precision)")
        self.ai_fp16_check.setChecked(self.app_state.ai_colorization.fp16)
        self.ai_fp16_check.setToolTip(
            "Use half-precision (float16) for ~2x faster inference.\n"
            "Only applies to GPU mode."
        )
        batch_fp16_row.addWidget(self.ai_fp16_check)
        ai_layout.addLayout(batch_fp16_row)

        self.ai_group.setEnabled(self.app_state.ai_colorization.enabled)
        layout.addWidget(self.ai_group)

        layout.addStretch()
        
    def create_slider(self, label_text, value, min_val, max_val, default_val, tooltip=""):
        """Helper to create a labeled slider with value display"""
        layout = QHBoxLayout()
        
        # Label
        label = QLabel(label_text)
        label.setMinimumWidth(80)
        if tooltip:
            label.setToolTip(tooltip)
        layout.addWidget(label)
        
        # Min value label
        min_label = QLabel(f"{min_val:.2f}")
        min_label.setStyleSheet("font-size: 8px;")
        layout.addWidget(min_label)
        
        # Slider
        slider = QSlider(Qt.Horizontal)
        
        # Convert float to int for slider (multiply by 100)
        multiplier = 100
        slider.setRange(int(min_val * multiplier), int(max_val * multiplier))
        slider.setValue(int(value * multiplier))
        slider.setProperty("multiplier", multiplier)
        slider.setProperty("default_value", default_val)
        layout.addWidget(slider)
        
        # Max value label
        max_label = QLabel(f"{max_val:.2f}")
        max_label.setStyleSheet("font-size: 8px;")
        layout.addWidget(max_label)
        
        # Value label
        value_label = QLabel(f"{value:.2f}")
        value_label.setMinimumWidth(40)
        layout.addWidget(value_label)
        
        return {
            'layout': layout,
            'slider': slider,
            'value_label': value_label
        }
        
    def connect_signals(self):
        """Connect UI signals to handlers"""
        self.enable_check.toggled.connect(self.on_enable_changed)
        
        # Connect sliders
        self.brightness_slider['slider'].valueChanged.connect(
            lambda v: self.on_slider_changed(v, self.brightness_slider, 'brightness')
        )
        self.contrast_slider['slider'].valueChanged.connect(
            lambda v: self.on_slider_changed(v, self.contrast_slider, 'contrast')
        )
        self.saturation_slider['slider'].valueChanged.connect(
            lambda v: self.on_slider_changed(v, self.saturation_slider, 'saturation')
        )
        self.gamma_slider['slider'].valueChanged.connect(
            lambda v: self.on_slider_changed(v, self.gamma_slider, 'gamma')
        )
        self.gamma_r_slider['slider'].valueChanged.connect(
            lambda v: self.on_rgb_slider_changed(v, self.gamma_r_slider, 'gamma_r')
        )
        self.gamma_g_slider['slider'].valueChanged.connect(
            lambda v: self.on_rgb_slider_changed(v, self.gamma_g_slider, 'gamma_g')
        )
        self.gamma_b_slider['slider'].valueChanged.connect(
            lambda v: self.on_rgb_slider_changed(v, self.gamma_b_slider, 'gamma_b')
        )
        
        # White Balance signals
        self.wb_enable_check.toggled.connect(self.on_wb_enable_changed)
        self.wb_preset_combo.currentIndexChanged.connect(self.on_wb_preset_changed)
        self.wb_r_slider['slider'].valueChanged.connect(
            lambda v: self.on_wb_slider_changed(v, self.wb_r_slider, 'wb_r')
        )
        self.wb_g_slider['slider'].valueChanged.connect(
            lambda v: self.on_wb_slider_changed(v, self.wb_g_slider, 'wb_g')
        )
        self.wb_b_slider['slider'].valueChanged.connect(
            lambda v: self.on_wb_slider_changed(v, self.wb_b_slider, 'wb_b')
        )
        
        # Colorization signals
        self.colorize_check.toggled.connect(self.on_colorize_enabled_changed)
        self.colorize_method_combo.currentTextChanged.connect(self.on_colorize_method_changed)
        # Tint controls
        self.colorize_hue_slider['slider'].valueChanged.connect(
            lambda v: self.on_colorize_slider_changed(v, self.colorize_hue_slider, 'tint_hue')
        )
        self.colorize_sat_slider['slider'].valueChanged.connect(
            lambda v: self.on_colorize_slider_changed(v, self.colorize_sat_slider, 'tint_saturation')
        )
        self.colorize_strength_slider['slider'].valueChanged.connect(
            lambda v: self.on_colorize_slider_changed(v, self.colorize_strength_slider, 'tint_strength')
        )
        # Tint preset combo
        self.tint_preset_combo.currentTextChanged.connect(self.on_tint_preset_changed)
        # Pseudocolor controls
        self.pc_preset_combo.currentTextChanged.connect(self.on_pc_preset_changed)
        self.pc_opacity_slider['slider'].valueChanged.connect(
            lambda v: self.on_colorize_slider_changed(v, self.pc_opacity_slider, 'pseudocolor_opacity')
        )
        # LUT controls
        self.lut_type_combo.currentTextChanged.connect(self.on_lut_type_changed)
        self.lut_browse_btn.clicked.connect(self.on_lut_browse)
        
        # AI Colorization signals
        self.ai_enable_check.toggled.connect(self.on_ai_enable_changed)
        self.ai_engine_combo.currentTextChanged.connect(self.on_ai_engine_changed)
        self.ai_device_combo.currentTextChanged.connect(self.on_ai_device_changed)
        self.ai_sat_slider['slider'].valueChanged.connect(
            lambda v: self.on_ai_slider_changed(v, self.ai_sat_slider, 'saturation')
        )
        self.ai_batch_spin.valueChanged.connect(self.on_ai_batch_changed)
        self.ai_fp16_check.toggled.connect(self.on_ai_fp16_changed)
        
    def update_engine_state(self):
        """Disable/enable EQ UI controls based on current backend's supported_filters()."""
        try:
            support = self.app_state.backend.supported_filters()
        except Exception as e:
            support = {}
            self.app_state.log(f"[ColorCorrection] supported_filters() failed: {e}", "WARN")
        engine = self.app_state.media_engine
        is_gst = engine == "gstreamer"
        has_eq = any([
            support.get('eq_brightness', True),
            support.get('eq_contrast', True),
            support.get('eq_saturation', True),
            support.get('eq_gamma', True),
        ])
        
        self._set_enabled_with_tip(
            self.enable_check,
            has_eq,
            "Color Correction (EQ)" if is_gst else ""
        )
        
        # EQ sliders: disable individually per support
        eq_enabled = self.app_state.eq.enabled
        self._set_slider_enabled_with_tip(
            self.brightness_slider, eq_enabled and support.get('eq_brightness', True),
            "Brightness (videobalance)" if is_gst else ""
        )
        self._set_slider_enabled_with_tip(
            self.contrast_slider, eq_enabled and support.get('eq_contrast', True),
            "Contrast (videobalance)" if is_gst else ""
        )
        self._set_slider_enabled_with_tip(
            self.saturation_slider, eq_enabled and support.get('eq_saturation', True),
            "Saturation (videobalance)" if is_gst else ""
        )
        self._set_slider_enabled_with_tip(
            self.gamma_slider, eq_enabled and support.get('eq_gamma', True),
            "Gamma (gamma element)" if is_gst else ""
        )
        self._set_slider_enabled_with_tip(
            self.gamma_r_slider, eq_enabled and support.get('eq_gamma', True),
            "RGB Gamma" if is_gst else ""
        )
        self._set_slider_enabled_with_tip(
            self.gamma_g_slider, eq_enabled and support.get('eq_gamma', True),
            "RGB Gamma" if is_gst else ""
        )
        self._set_slider_enabled_with_tip(
            self.gamma_b_slider, eq_enabled and support.get('eq_gamma', True),
            "RGB Gamma" if is_gst else ""
        )

        # White balance
        self._set_enabled_with_tip(
            self.wb_enable_check,
            support.get('white_balance', True),
            "White Balance (colorbalance)" if is_gst else ""
        )
        wb_en = support.get('white_balance', True) and self.app_state.eq.white_balance_enabled
        self.wb_preset_combo.setEnabled(wb_en)
        self._set_slider_enabled_with_tip(self.wb_r_slider, wb_en, "WB Red" if is_gst else "")
        self._set_slider_enabled_with_tip(self.wb_g_slider, wb_en, "WB Green" if is_gst else "")
        self._set_slider_enabled_with_tip(self.wb_b_slider, wb_en, "WB Blue" if is_gst else "")

        # Colorization
        colorize_supported = support.get('colorization', False)
        self._set_enabled_with_tip(
            self.colorize_check, colorize_supported,
            "Colorization" if is_gst else ""
        )
        cz_en = colorize_supported and self.app_state.colorization.enabled
        self.colorize_method_combo.setEnabled(cz_en)
        method = self.app_state.colorization.method
        self.tint_group.setEnabled(cz_en and method == "tint")
        self.pseudocolor_group.setEnabled(cz_en and method == "pseudocolor")
        self.lut_group.setEnabled(cz_en and method == "lut")
        is_tint = cz_en and method == "tint"
        self.tint_preset_combo.setEnabled(is_tint)
        self.colorize_hue_slider['slider'].setEnabled(is_tint)
        self.colorize_sat_slider['slider'].setEnabled(is_tint)
        self.colorize_strength_slider['slider'].setEnabled(is_tint)
        # Pseudocolor controls
        is_pc = cz_en and method == "pseudocolor"
        self.pc_preset_combo.setEnabled(is_pc)
        self.pc_opacity_slider['slider'].setEnabled(is_pc)
        # LUT controls
        is_lut = cz_en and method == "lut"
        self.lut_type_combo.setEnabled(is_lut)
        self.lut_browse_btn.setEnabled(is_lut)

        # AI Colorization
        ai_supported = support.get('ai_colorization', False)
        self._set_enabled_with_tip(
            self.ai_enable_check, ai_supported,
            "AI Colorization" if is_gst else ""
        )
        ai_en = ai_supported and self.app_state.ai_colorization.enabled
        self.ai_group.setEnabled(ai_en)
        self.ai_engine_combo.setEnabled(ai_en)
        self.ai_device_combo.setEnabled(ai_en)
        self.ai_sat_slider['slider'].setEnabled(ai_en)
        self.ai_batch_spin.setEnabled(ai_en)
        self.ai_fp16_check.setEnabled(ai_en and "cuda" in self.app_state.ai_colorization.gpu_device)

    def _set_enabled_with_tip(self, widget, supported, feature_name):
        """Set a widget's enabled state; if not supported, append note to tooltip."""
        widget.setEnabled(supported)
        if supported:
            return
        note = f"\n\n⚠ Not supported by {self.app_state.media_engine.upper()} engine. Switch to FFmpeg."
        current = widget.toolTip()
        if note not in current:
            widget.setToolTip(current + note)

    def _set_slider_enabled_with_tip(self, slider_dict, enabled, feature_name):
        """Set a slider group's enabled state; append engine note to label tooltip."""
        slider_dict['slider'].setEnabled(enabled)
        label = slider_dict['layout'].itemAt(0).widget()
        if enabled:
            return
        note = f"\n\n⚠ Not supported by {self.app_state.media_engine.upper()} engine. Switch to FFmpeg."
        current = label.toolTip()
        if note not in current:
            label.setToolTip(current + note)

    def on_enable_changed(self, checked):
        """Handle enable checkbox change"""
        self.app_state.eq.enabled = checked
        self.update_engine_state()
        self.settings_changed.emit()
        
    def on_slider_changed(self, value, slider_dict, attr_name):
        """Handle slider value change"""
        multiplier = slider_dict['slider'].property("multiplier")
        float_value = value / multiplier
        
        slider_dict['value_label'].setText(f"{float_value:.2f}")
        setattr(self.app_state.eq, attr_name, float_value)
        self.settings_changed.emit()
        
    def on_rgb_slider_changed(self, value, slider_dict, attr_name):
        """Handle RGB slider value change"""
        multiplier = slider_dict['slider'].property("multiplier")
        float_value = value / multiplier
        
        slider_dict['value_label'].setText(f"{float_value:.2f}")
        setattr(self.app_state.eq, attr_name, float_value)
        
        # If linking is enabled, sync other RGB sliders
        if self.link_rgb_check.isChecked():
            self.sync_rgb_sliders(attr_name, float_value)
            
        self.settings_changed.emit()
        
    def sync_rgb_sliders(self, source_attr, value):
        """Sync RGB slider values when linked"""
        rgb_sliders = {
            'gamma_r': self.gamma_r_slider,
            'gamma_g': self.gamma_g_slider,
            'gamma_b': self.gamma_b_slider
        }
        
        for attr, slider_dict in rgb_sliders.items():
            if attr != source_attr:
                multiplier = slider_dict['slider'].property("multiplier")
                slider_dict['slider'].blockSignals(True)
                slider_dict['slider'].setValue(int(value * multiplier))
                slider_dict['slider'].blockSignals(False)
                slider_dict['value_label'].setText(f"{value:.2f}")
                setattr(self.app_state.eq, attr, value)
                
    def _set_wb_sliders_enabled(self, enabled):
        """Enable/disable white balance sliders based on enable state"""
        self.wb_preset_combo.setEnabled(enabled)
        self.wb_r_slider['slider'].setEnabled(enabled)
        self.wb_g_slider['slider'].setEnabled(enabled)
        self.wb_b_slider['slider'].setEnabled(enabled)
        
    def on_wb_enable_changed(self, checked):
        """Handle white balance enable checkbox change"""
        self.app_state.eq.white_balance_enabled = checked
        self._set_wb_sliders_enabled(checked)
        self._update_wb_labels()
        self.settings_changed.emit()
        
    def on_wb_preset_changed(self, index):
        """Handle white balance preset change"""
        # Update slider labels and values based on preset
        self._update_wb_labels()
        self._load_wb_values_for_preset(index)
        self.settings_changed.emit()
        
    def _update_wb_labels(self):
        """Update white balance slider labels based on current preset"""
        preset = self.wb_preset_combo.currentIndex()
        
        if preset == 0:  # Simple (All Tones)
            # Use shadows as the active values
            self._set_slider_label(self.wb_r_slider, "Red", self.app_state.eq.wb_shadows_r)
            self._set_slider_label(self.wb_g_slider, "Green", self.app_state.eq.wb_shadows_g)
            self._set_slider_label(self.wb_b_slider, "Blue", self.app_state.eq.wb_shadows_b)
        elif preset == 1:  # Shadows
            self._set_slider_label(self.wb_r_slider, "Red (Shadows)", self.app_state.eq.wb_shadows_r)
            self._set_slider_label(self.wb_g_slider, "Green (Shadows)", self.app_state.eq.wb_shadows_g)
            self._set_slider_label(self.wb_b_slider, "Blue (Shadows)", self.app_state.eq.wb_shadows_b)
        elif preset == 2:  # Midtones
            self._set_slider_label(self.wb_r_slider, "Red (Midtones)", self.app_state.eq.wb_midtones_r)
            self._set_slider_label(self.wb_g_slider, "Green (Midtones)", self.app_state.eq.wb_midtones_g)
            self._set_slider_label(self.wb_b_slider, "Blue (Midtones)", self.app_state.eq.wb_midtones_b)
        elif preset == 3:  # Highlights
            self._set_slider_label(self.wb_r_slider, "Red (Highlights)", self.app_state.eq.wb_highlights_r)
            self._set_slider_label(self.wb_g_slider, "Green (Highlights)", self.app_state.eq.wb_highlights_g)
            self._set_slider_label(self.wb_b_slider, "Blue (Highlights)", self.app_state.eq.wb_highlights_b)
            
    def _set_slider_label(self, slider_dict, label_text, value):
        """Update a slider's label and value display"""
        label = slider_dict['layout'].itemAt(0).widget()
        if label:
            label.setText(label_text)
        slider_dict['value_label'].setText(f"{value:.2f}")
        
    def _load_wb_values_for_preset(self, preset):
        """Load white balance values for the selected preset into sliders"""
        multiplier = 100  # Same as regular sliders
        
        if preset == 0:  # Simple - show shadows values
            r_val = self.app_state.eq.wb_shadows_r
            g_val = self.app_state.eq.wb_shadows_g
            b_val = self.app_state.eq.wb_shadows_b
        elif preset == 1:  # Shadows
            r_val = self.app_state.eq.wb_shadows_r
            g_val = self.app_state.eq.wb_shadows_g
            b_val = self.app_state.eq.wb_shadows_b
        elif preset == 2:  # Midtones
            r_val = self.app_state.eq.wb_midtones_r
            g_val = self.app_state.eq.wb_midtones_g
            b_val = self.app_state.eq.wb_midtones_b
        else:  # Highlights
            r_val = self.app_state.eq.wb_highlights_r
            g_val = self.app_state.eq.wb_highlights_g
            b_val = self.app_state.eq.wb_highlights_b
            
        self.wb_r_slider['slider'].blockSignals(True)
        self.wb_r_slider['slider'].setValue(int(r_val * multiplier))
        self.wb_r_slider['value_label'].setText(f"{r_val:.2f}")
        self.wb_r_slider['slider'].blockSignals(False)
        
        self.wb_g_slider['slider'].blockSignals(True)
        self.wb_g_slider['slider'].setValue(int(g_val * multiplier))
        self.wb_g_slider['value_label'].setText(f"{g_val:.2f}")
        self.wb_g_slider['slider'].blockSignals(False)
        
        self.wb_b_slider['slider'].blockSignals(True)
        self.wb_b_slider['slider'].setValue(int(b_val * multiplier))
        self.wb_b_slider['value_label'].setText(f"{b_val:.2f}")
        self.wb_b_slider['slider'].blockSignals(False)
        
    def on_wb_slider_changed(self, value, slider_dict, attr_name):
        """Handle white balance slider value change"""
        multiplier = slider_dict['slider'].property("multiplier")
        float_value = value / multiplier
        
        slider_dict['value_label'].setText(f"{float_value:.2f}")
        
        # Map the simple attr_name to actual model attributes based on preset
        preset = self.wb_preset_combo.currentIndex()
        
        if preset == 0:  # Simple - apply to all tones
            self.app_state.eq.wb_shadows_r = float_value if attr_name == 'wb_r' else self.app_state.eq.wb_shadows_r
            self.app_state.eq.wb_shadows_g = float_value if attr_name == 'wb_g' else self.app_state.eq.wb_shadows_g
            self.app_state.eq.wb_shadows_b = float_value if attr_name == 'wb_b' else self.app_state.eq.wb_shadows_b
            # Also apply to midtones and highlights for simple mode
            if attr_name == 'wb_r':
                self.app_state.eq.wb_midtones_r = float_value
                self.app_state.eq.wb_highlights_r = float_value
            elif attr_name == 'wb_g':
                self.app_state.eq.wb_midtones_g = float_value
                self.app_state.eq.wb_highlights_g = float_value
            elif attr_name == 'wb_b':
                self.app_state.eq.wb_midtones_b = float_value
                self.app_state.eq.wb_highlights_b = float_value
        elif preset == 1:  # Shadows
            if attr_name == 'wb_r':
                self.app_state.eq.wb_shadows_r = float_value
            elif attr_name == 'wb_g':
                self.app_state.eq.wb_shadows_g = float_value
            elif attr_name == 'wb_b':
                self.app_state.eq.wb_shadows_b = float_value
        elif preset == 2:  # Midtones
            if attr_name == 'wb_r':
                self.app_state.eq.wb_midtones_r = float_value
            elif attr_name == 'wb_g':
                self.app_state.eq.wb_midtones_g = float_value
            elif attr_name == 'wb_b':
                self.app_state.eq.wb_midtones_b = float_value
        elif preset == 3:  # Highlights
            if attr_name == 'wb_r':
                self.app_state.eq.wb_highlights_r = float_value
            elif attr_name == 'wb_g':
                self.app_state.eq.wb_highlights_g = float_value
            elif attr_name == 'wb_b':
                self.app_state.eq.wb_highlights_b = float_value
                
        self.settings_changed.emit()

    # ---- Colorization Handlers ----

    def on_colorize_enabled_changed(self, checked):
        """Handle colorization enable checkbox change"""
        self.app_state.colorization.enabled = checked
        self.update_engine_state()
        self.settings_changed.emit()

    def on_colorize_method_changed(self, text):
        """Handle colorization method change"""
        method_map = {"Tint": "tint", "Pseudocolor": "pseudocolor", "LUT": "lut"}
        self.app_state.colorization.method = method_map.get(text, "tint")
        self.update_engine_state()
        self.settings_changed.emit()

    def on_colorize_slider_changed(self, value, slider_dict, attr_name):
        """Handle colorization slider value change"""
        multiplier = slider_dict['slider'].property("multiplier")
        float_value = value / multiplier
        slider_dict['value_label'].setText(f"{float_value:.2f}")
        setattr(self.app_state.colorization, attr_name, float_value)
        self.settings_changed.emit()

    def on_tint_preset_changed(self, text):
        """Handle tint preset combo change"""
        presets = {
            "Sepia":  (30, 0.6, 1.0),
            "Warm":   (15, 0.5, 0.8),
            "Cool":   (200, 0.5, 0.8),
            "Blue":   (240, 0.7, 0.9),
            "Green":  (120, 0.6, 0.8),
            "Red":    (0, 0.6, 0.8),
            "Purple": (280, 0.5, 0.8),
        }
        hue, saturation, strength = presets.get(text, (30, 0.6, 1.0))
        self.app_state.colorization.tint_hue = hue
        self.app_state.colorization.tint_saturation = saturation
        self.app_state.colorization.tint_strength = strength
        # Update slider positions
        for attr, sdict in [
            ('tint_hue', self.colorize_hue_slider),
            ('tint_saturation', self.colorize_sat_slider),
            ('tint_strength', self.colorize_strength_slider),
        ]:
            m = sdict['slider'].property("multiplier")
            val = getattr(self.app_state.colorization, attr)
            sdict['slider'].blockSignals(True)
            sdict['slider'].setValue(int(val * m))
            sdict['slider'].blockSignals(False)
            sdict['value_label'].setText(f"{val:.2f}")
        self.settings_changed.emit()

    def on_pc_preset_changed(self, text):
        """Handle pseudocolor preset change"""
        self.app_state.colorization.pseudocolor_preset = text
        self.settings_changed.emit()

    def on_lut_type_changed(self, text):
        """Handle LUT type change"""
        self.app_state.colorization.lut_type = text
        self.settings_changed.emit()

    def on_lut_browse(self):
        """Browse for a LUT file"""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select LUT File", "",
            "LUT Files (*.cube *.3dl *.dat);;All Files (*)"
        )
        if path:
            self.app_state.colorization.lut_path = path
            self.lut_path_label.setText(os.path.basename(path))
            self.lut_path_label.setStyleSheet("color: white; font-size: 10px;")
            self.settings_changed.emit()

    # ---- AI Colorization Handlers ----

    def on_ai_enable_changed(self, checked):
        """Handle AI colorization enable checkbox change"""
        self.app_state.ai_colorization.enabled = checked
        self.update_engine_state()
        self.settings_changed.emit()

    def on_ai_engine_changed(self, text):
        """Handle AI engine selection change"""
        engine_map = {
            "ECCV16 (Lightweight)": "eccv16",
            "DeOldify (Premium)": "deoldify",
        }
        self.app_state.ai_colorization.engine = engine_map.get(text, "eccv16")
        self.settings_changed.emit()

    def on_ai_device_changed(self, text):
        """Handle AI device selection change"""
        device_map = {
            "cuda:0 (GPU)": "cuda:0",
            "cpu (CPU)": "cpu",
        }
        self.app_state.ai_colorization.gpu_device = device_map.get(text, "cuda:0")
        self.ai_fp16_check.setEnabled(
            self.app_state.ai_colorization.enabled and "cuda" in self.app_state.ai_colorization.gpu_device
        )
        self.settings_changed.emit()

    def on_ai_slider_changed(self, value, slider_dict, attr_name):
        """Handle AI slider value change"""
        multiplier = slider_dict['slider'].property("multiplier")
        float_value = value / multiplier
        slider_dict['value_label'].setText(f"{float_value:.2f}")
        setattr(self.app_state.ai_colorization, attr_name, float_value)
        self.settings_changed.emit()

    def on_ai_batch_changed(self, value):
        """Handle AI batch size change"""
        self.app_state.ai_colorization.batch_size = value
        self.settings_changed.emit()

    def on_ai_fp16_changed(self, checked):
        """Handle AI FP16 checkbox change"""
        self.app_state.ai_colorization.fp16 = checked
        self.settings_changed.emit()

    def reset_defaults(self):
        """Reset all EQ settings to defaults"""
        self.app_state.eq.brightness = 0.0
        self.app_state.eq.contrast = 1.0
        self.app_state.eq.saturation = 1.0
        self.app_state.eq.gamma = 1.0
        self.app_state.eq.gamma_r = 1.0
        self.app_state.eq.gamma_g = 1.0
        self.app_state.eq.gamma_b = 1.0
        
        # Reset white balance
        self.app_state.eq.white_balance_enabled = False
        self.app_state.eq.wb_shadows_r = 0.0
        self.app_state.eq.wb_shadows_g = 0.0
        self.app_state.eq.wb_shadows_b = 0.0
        self.app_state.eq.wb_midtones_r = 0.0
        self.app_state.eq.wb_midtones_g = 0.0
        self.app_state.eq.wb_midtones_b = 0.0
        self.app_state.eq.wb_highlights_r = 0.0
        self.app_state.eq.wb_highlights_g = 0.0
        self.app_state.eq.wb_highlights_b = 0.0
        
        # Update sliders
        for slider_dict in [self.brightness_slider, self.contrast_slider, 
                           self.saturation_slider, self.gamma_slider]:
            default = slider_dict['slider'].property("default_value")
            multiplier = slider_dict['slider'].property("multiplier")
            slider_dict['slider'].setValue(int(default * multiplier))
            
        for slider_dict in [self.gamma_r_slider, self.gamma_g_slider, self.gamma_b_slider]:
            multiplier = slider_dict['slider'].property("multiplier")
            slider_dict['slider'].setValue(int(1.0 * multiplier))
        
        # Reset white balance UI
        self.wb_enable_check.setChecked(False)
        self.wb_preset_combo.setCurrentIndex(0)
        self._set_wb_sliders_enabled(False)
        for slider_dict in [self.wb_r_slider, self.wb_g_slider, self.wb_b_slider]:
            multiplier = slider_dict['slider'].property("multiplier")
            slider_dict['slider'].setValue(0)
            slider_dict['value_label'].setText("0.00")

        # Reset colorization
        self.app_state.colorization.enabled = False
        self.app_state.colorization.method = "tint"
        self.app_state.colorization.tint_hue = 30.0
        self.app_state.colorization.tint_saturation = 0.6
        self.app_state.colorization.tint_strength = 1.0
        self.app_state.colorization.pseudocolor_preset = "rainbow"
        self.app_state.colorization.pseudocolor_opacity = 1.0
        self.app_state.colorization.lut_path = ""
        self.app_state.colorization.lut_type = "lut3d"
        # Update UI
        self.colorize_check.setChecked(False)
        self.colorize_method_combo.setCurrentText("Tint")
        # Tint combo + sliders
        self.tint_preset_combo.setCurrentText("Sepia")
        for slider_dict in [
            self.colorize_hue_slider,
            self.colorize_sat_slider,
            self.colorize_strength_slider
        ]:
            m = slider_dict['slider'].property("multiplier")
            d = slider_dict['slider'].property("default_value")
            slider_dict['slider'].blockSignals(True)
            slider_dict['slider'].setValue(int(d * m))
            slider_dict['slider'].blockSignals(False)
            slider_dict['value_label'].setText(f"{d:.2f}")
        # Pseudocolor
        self.pc_preset_combo.setCurrentText("rainbow")
        m_op = self.pc_opacity_slider['slider'].property("multiplier")
        self.pc_opacity_slider['slider'].blockSignals(True)
        self.pc_opacity_slider['slider'].setValue(int(1.0 * m_op))
        self.pc_opacity_slider['slider'].blockSignals(False)
        self.pc_opacity_slider['value_label'].setText("1.00")
        # LUT
        self.lut_type_combo.setCurrentText("lut3d")
        self.lut_path_label.setText("No LUT file selected")
        self.lut_path_label.setStyleSheet("color: gray; font-size: 10px;")
        # Reset AI colorization
        self._reset_ai_colorization()
        # Re-apply engine state
        self.update_engine_state()
            
        self.settings_changed.emit()
        self.app_state.log("EQ settings reset to defaults", "INFO")

    # ── AI Colorization Reset ──

    def _reset_ai_colorization(self):
        """Reset AI colorization settings to defaults"""
        ai = self.app_state.ai_colorization
        ai.enabled = False
        ai.engine = "eccv16"
        ai.saturation = 1.0
        ai.fp16 = True
        ai.gpu_device = "cuda:0"
        ai.batch_size = 8
        # Update UI
        self.ai_enable_check.setChecked(False)
        self.ai_engine_combo.setCurrentText("ECCV16 (Lightweight)")
        self.ai_device_combo.setCurrentText("cuda:0 (GPU)")
        self.ai_fp16_check.setChecked(True)
        self.ai_batch_spin.setValue(8)
        m_sat = self.ai_sat_slider['slider'].property("multiplier")
        self.ai_sat_slider['slider'].blockSignals(True)
        self.ai_sat_slider['slider'].setValue(int(1.0 * m_sat))
        self.ai_sat_slider['slider'].blockSignals(False)
        self.ai_sat_slider['value_label'].setText("1.00")