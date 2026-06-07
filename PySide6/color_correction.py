"""
Color Correction (EQ) Panel (PySide6)
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QSlider, QPushButton, QFrame, QComboBox, QFileDialog,
    QGroupBox, QSpinBox, QListWidget, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, QTimer
import os

from models import AppState
from ui_components import CollapsibleFrame


class ColorCorrectionPanel(QWidget):
    """Panel for color correction (EQ) settings"""
    
    settings_changed = Signal()
    _ai_single_done = Signal()
    _batch_folder_done = Signal()
    _extract_done = Signal()
    _recombine_done = Signal()
    
    def __init__(self, app_state: AppState, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        
        self.setup_ui()
        self._cached_colorizer = None
        self._folder_video_map = {}  # folder_path → original_video_path
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

        # === 1. EQ Section (Collapsible, closed by default) ===
        self.eq_frame = CollapsibleFrame("EQ")
        eq_layout = self.eq_frame.content_layout()

        # Brightness
        self.brightness_slider = self.create_slider(
            "Brightness", self.app_state.eq.brightness,
            -0.10, 0.10, 0.00,
            "Adjusts black level. VHS tapes rarely need more than +/- 0.05."
        )
        eq_layout.addLayout(self.brightness_slider['layout'])

        # Contrast
        self.contrast_slider = self.create_slider(
            "Contrast", self.app_state.eq.contrast,
            0.80, 1.30, 1.00,
            "Increases separation between dark and bright areas. Too much will crush VHS shadow detail."
        )
        eq_layout.addLayout(self.contrast_slider['layout'])

        # Saturation
        self.saturation_slider = self.create_slider(
            "Saturation", self.app_state.eq.saturation,
            0.70, 1.10, 1.00,
            "Color intensity. High values can cause VHS color bleeding."
        )
        eq_layout.addLayout(self.saturation_slider['layout'])

        # Gamma
        self.gamma_slider = self.create_slider(
            "Gamma", self.app_state.eq.gamma,
            0.90, 1.10, 1.00,
            "Adjusts midtone brightness without affecting black/white points."
        )
        eq_layout.addLayout(self.gamma_slider['layout'])

        # === RGB Gamma Section ===
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        eq_layout.addWidget(line)

        # Link RGB checkbox
        self.link_rgb_check = QCheckBox("Link RGB Gamma (White Balance)")
        self.link_rgb_check.setChecked(True)
        eq_layout.addWidget(self.link_rgb_check)

        # RGB Sliders
        self.gamma_r_slider = self.create_slider(
            "R Gamma", self.app_state.eq.gamma_r,
            0.95, 1.05, 1.00
        )
        eq_layout.addLayout(self.gamma_r_slider['layout'])

        self.gamma_g_slider = self.create_slider(
            "G Gamma", self.app_state.eq.gamma_g,
            0.95, 1.05, 1.00
        )
        eq_layout.addLayout(self.gamma_g_slider['layout'])

        self.gamma_b_slider = self.create_slider(
            "B Gamma", self.app_state.eq.gamma_b,
            0.95, 1.05, 1.00
        )
        eq_layout.addLayout(self.gamma_b_slider['layout'])

        layout.addWidget(self.eq_frame)
        self.eq_frame.collapse()

        # === 2. White Balance Section (Collapsible, closed by default) ===
        self.wb_frame = CollapsibleFrame("White Balance")
        wb_layout = self.wb_frame.content_layout()

        # White Balance enable checkbox
        self.wb_enable_check = QCheckBox("Enable White Balance")
        self.wb_enable_check.setChecked(self.app_state.eq.white_balance_enabled)
        self.wb_enable_check.setToolTip(
            "Adjust white balance using colorbalance filter.\n"
            "Similar to Shotcut's White Balance filter.\n"
            "Use presets for quick adjustments or manual mode for fine control."
        )
        wb_layout.addWidget(self.wb_enable_check)

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
        wb_layout.addLayout(wb_preset_layout)

        # White Balance sliders (R, G, B for current preset)
        self.wb_r_slider = self.create_slider(
            "Red", self.app_state.eq.wb_shadows_r if self.app_state.eq.white_balance_enabled else 0.0,
            -1.0, 1.0, 0.0,
            "Red balance: negative = more cyan, positive = more red"
        )
        wb_layout.addLayout(self.wb_r_slider['layout'])

        self.wb_g_slider = self.create_slider(
            "Green", self.app_state.eq.wb_shadows_g if self.app_state.eq.white_balance_enabled else 0.0,
            -1.0, 1.0, 0.0,
            "Green balance: negative = more magenta, positive = more green"
        )
        wb_layout.addLayout(self.wb_g_slider['layout'])

        self.wb_b_slider = self.create_slider(
            "Blue", self.app_state.eq.wb_shadows_b if self.app_state.eq.white_balance_enabled else 0.0,
            -1.0, 1.0, 0.0,
            "Blue balance: negative = more yellow, positive = more blue"
        )
        wb_layout.addLayout(self.wb_b_slider['layout'])

        # Enable/disable WB sliders based on enable state
        self._set_wb_sliders_enabled(self.app_state.eq.white_balance_enabled)

        layout.addWidget(self.wb_frame)
        self.wb_frame.collapse()

        # === 3. Colorization Section (Collapsible, closed by default) ===
        self.cz_frame = CollapsibleFrame("Colorization")
        cz_layout = self.cz_frame.content_layout()

        # ---- Non-AI Colorization ----
        self.colorize_check = QCheckBox("Enable Colorization (B&W → Color)")
        self.colorize_check.setChecked(self.app_state.colorization.enabled)
        self.colorize_check.setToolTip(
            "Add color to black and white video using non-AI methods.\n"
            "Tint: Uniform color tint (sepia, blue, etc.)\n"
            "Pseudocolor: Map brightness levels to colors\n"
            "LUT: Apply a color lookup table (.cube file)"
        )
        cz_layout.addWidget(self.colorize_check)

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
        cz_layout.addLayout(method_layout)

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
        cz_layout.addWidget(self.tint_group)

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
        cz_layout.addWidget(self.pseudocolor_group)

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
        cz_layout.addWidget(self.lut_group)

        layout.addWidget(self.cz_frame)
        self.cz_frame.collapse()

        # === 4. AI Colorization Section (Collapsible, closed by default) ===
        self.ai_frame = CollapsibleFrame("AI Colorization")
        ai_layout = self.ai_frame.content_layout()

        self.ai_enable_check = QCheckBox("Enable AI Colorization")
        self.ai_enable_check.setChecked(self.app_state.ai_colorization.enabled)
        self.ai_enable_check.setToolTip(
            "Deep learning-based colorization using PyTorch.\n"
            "ECCV16: Lightweight, runs on CPU/GPU (~15-60 fps)\n"
            "DeOldify: Premium, GPU only (~8-12 fps)"
        )
        ai_layout.addWidget(self.ai_enable_check)

        self.ai_group = QGroupBox("AI Colorization Settings")
        ai_group_layout = QVBoxLayout(self.ai_group)

        # Engine selector
        engine_row = QHBoxLayout()
        engine_row.addWidget(QLabel("Engine:"))
        self.ai_engine_combo = QComboBox()
        self.ai_engine_combo.addItems(["ECCV16 (Lightweight)", "SIGGRAPH17 (Balanced)", "DeOldify (Premium)"])
        current_engine = self.app_state.ai_colorization.engine
        idx = self.ai_engine_combo.findText(current_engine)
        if idx >= 0:
            self.ai_engine_combo.setCurrentIndex(idx)
        else:
            self.ai_engine_combo.setCurrentIndex(0)
        self.ai_engine_combo.setToolTip(
            "ECCV16: Small CNN, runs on CPU/GPU, plausible colors, washed-out\n"
            "SIGGRAPH17: Medium UNet, runs on CPU/GPU, better quality, richer colors\n"
            "DeOldify: ResNet U-Net, GPU only, vibrant colors, requires fastai"
        )
        engine_row.addWidget(self.ai_engine_combo)
        engine_row.addStretch()
        ai_group_layout.addLayout(engine_row)

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
        ai_group_layout.addLayout(device_row)

        # DeOldify-specific: model variant + render factor
        self.ai_deoldify_widgets = []

        mv_row = QHBoxLayout()
        mv_row.addWidget(QLabel("DeOldify Model:"))
        self.ai_deoldify_model_combo = QComboBox()
        self.ai_deoldify_model_combo.addItems(["Video (ResNet101)", "Artistic (ResNet34)", "Stable (ResNet101)"])
        current_mv = getattr(self.app_state.ai_colorization, 'deoldify_model', 'video')
        mv_idx = {"video": 0, "artistic": 1, "stable": 2}.get(current_mv, 0)
        self.ai_deoldify_model_combo.setCurrentIndex(mv_idx)
        self.ai_deoldify_model_combo.setToolTip(
            "Video: Best for video, temporal coherence (834 MB)\n"
            "Artistic: Best for artistic stills (243 MB)\n"
            "Stable: Balanced quality (834 MB)"
        )
        mv_row.addWidget(self.ai_deoldify_model_combo)
        mv_row.addStretch()
        ai_group_layout.addLayout(mv_row)
        self.ai_deoldify_widgets.append(self.ai_deoldify_model_combo)

        rf_row = QHBoxLayout()
        rf_row.addWidget(QLabel("Render Factor:"))
        self.ai_render_factor_spin = QSpinBox()
        self.ai_render_factor_spin.setRange(10, 45)
        self.ai_render_factor_spin.setValue(getattr(self.app_state.ai_colorization, 'render_factor', 21))
        self.ai_render_factor_spin.setToolTip(
            "Base resolution multiplier (render_factor * 16 = px).\n"
            "Higher = better quality but slower.\n"
            "21 = 336px (default), 30 = 480px, 45 = 720px"
        )
        rf_row.addWidget(self.ai_render_factor_spin)
        rf_row.addStretch()
        ai_group_layout.addLayout(rf_row)
        self.ai_deoldify_widgets.append(self.ai_render_factor_spin)

        # Color correct strength slider (DeOldify-only)
        self.ai_cc_slider = self.create_slider(
            "Color Correct",
            getattr(self.app_state.ai_colorization, 'color_correct_strength', 0.5),
            0.0, 1.0, 0.5,
            "Reduce inherent model color cast in YUV space.\n"
            "0.0 = No correction, 0.5 = Half (default), 1.0 = Full neutralization"
        )
        ai_group_layout.addLayout(self.ai_cc_slider['layout'])
        self.ai_deoldify_widgets.append(self.ai_cc_slider['slider'])

        # Saturation slider
        self.ai_sat_slider = self.create_slider(
            "Saturation", self.app_state.ai_colorization.saturation,
            0.1, 2.0, 1.0,
            "Color saturation boost after AI colorization.\n"
            "1.0 = No change, 0.1 = Desaturated, 2.0 = Vibrant"
        )
        ai_group_layout.addLayout(self.ai_sat_slider['layout'])

        # Contrast slider
        self.ai_contrast_slider = self.create_slider(
            "Contrast", self.app_state.ai_colorization.contrast,
            0.5, 2.0, 1.0,
            "Contrast adjustment after colorization.\n"
            "1.0 = No change, 0.5 = Lower contrast, 2.0 = Higher contrast"
        )
        ai_group_layout.addLayout(self.ai_contrast_slider['layout'])

        # Denoise slider
        self.ai_denoise_slider = self.create_slider(
            "Denoise", self.app_state.ai_colorization.denoise,
            0.0, 5.0, 0.0,
            "Light bilateral denoise after colorization.\n"
            "0 = Off, 1-2 = Light, 3-5 = Strong. Helps reduce artifacts."
        )
        ai_group_layout.addLayout(self.ai_denoise_slider['layout'])

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
        ai_group_layout.addLayout(batch_fp16_row)

        # Show/hide DeOldify widgets based on initial engine
        is_deoldify = self.app_state.ai_colorization.engine == "deoldify"
        for w in self.ai_deoldify_widgets:
            w.setVisible(is_deoldify)

        # ── Pipeline Buttons ──
        pipeline_line = QFrame()
        pipeline_line.setFrameShape(QFrame.HLine)
        pipeline_line.setFrameShadow(QFrame.Sunken)
        ai_group_layout.addWidget(pipeline_line)

        # Item list (single images + folders)
        item_row = QHBoxLayout()
        self.ai_item_list = QListWidget()
        self.ai_item_list.setMinimumHeight(120)
        self.ai_item_list.setAlternatingRowColors(True)
        item_row.addWidget(self.ai_item_list)
        btn_col = QVBoxLayout()
        self.ai_load_btn = QPushButton("Load")
        self.ai_load_btn.setToolTip("Add image files to the list")
        self.ai_load_folder_btn = QPushButton("Load Folder")
        self.ai_load_folder_btn.setToolTip("Add a folder of PNG frames")
        self.ai_extract_btn = QPushButton("Extract")
        self.ai_extract_btn.setToolTip(
            "Extract PNG frames from a video into a folder.\n"
            "The folder is added to the list."
        )
        self.ai_remove_btn = QPushButton("Remove")
        self.ai_remove_btn.setToolTip("Remove selected item from list")
        self.ai_colorize_btn = QPushButton("Colorize")
        self.ai_colorize_btn.setToolTip(
            "Colorize the selected item.\n"
            "If it's an image: saves to ai_colorized/ folder.\n"
            "If it's a folder: colorizes all PNGs inside."
        )
        self.ai_recombine_btn = QPushButton("Recombine")
        self.ai_recombine_btn.setToolTip(
            "Recombine colorized folder frames into a video with audio.\n"
            "For folders extracted from a video."
        )
        btn_col.addWidget(self.ai_load_btn)
        btn_col.addWidget(self.ai_load_folder_btn)
        btn_col.addWidget(self.ai_extract_btn)
        btn_col.addWidget(self.ai_remove_btn)
        btn_col.addWidget(self.ai_colorize_btn)
        btn_col.addWidget(self.ai_recombine_btn)
        btn_col.addStretch()
        item_row.addLayout(btn_col)
        ai_group_layout.addLayout(item_row)
        self.ai_item_progress = QLabel("")
        self.ai_item_progress.setStyleSheet("color: gray;")
        ai_group_layout.addWidget(self.ai_item_progress)

        # Cancel button for pipeline operations
        cancel_row = QHBoxLayout()
        self.ai_cancel_btn = QPushButton("Cancel")
        self.ai_cancel_btn.setEnabled(False)
        self.ai_cancel_btn.setStyleSheet(
            "QPushButton { background-color: #c0392b; color: white; font-weight: bold; }"
        )
        self.ai_cancel_btn.setToolTip("Cancel the current AI colorization operation")
        cancel_row.addStretch()
        cancel_row.addWidget(self.ai_cancel_btn)
        ai_group_layout.addLayout(cancel_row)

        self.ai_group.setEnabled(self.app_state.ai_colorization.enabled)
        ai_layout.addWidget(self.ai_group)

        layout.addWidget(self.ai_frame)
        self.ai_frame.collapse()

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
        self.ai_deoldify_model_combo.currentTextChanged.connect(self.on_ai_deoldify_model_changed)
        self.ai_render_factor_spin.valueChanged.connect(self.on_ai_render_factor_changed)
        self.ai_sat_slider['slider'].valueChanged.connect(
            lambda v: self.on_ai_slider_changed(v, self.ai_sat_slider, 'saturation')
        )
        self.ai_contrast_slider['slider'].valueChanged.connect(
            lambda v: self.on_ai_slider_changed(v, self.ai_contrast_slider, 'contrast')
        )
        self.ai_denoise_slider['slider'].valueChanged.connect(
            lambda v: self.on_ai_slider_changed(v, self.ai_denoise_slider, 'denoise')
        )
        self.ai_cc_slider['slider'].valueChanged.connect(
            lambda v: self.on_ai_slider_changed(v, self.ai_cc_slider, 'color_correct_strength')
        )
        self.ai_batch_spin.valueChanged.connect(self.on_ai_batch_changed)
        self.ai_fp16_check.toggled.connect(self.on_ai_fp16_changed)
        self.ai_load_btn.clicked.connect(self.on_ai_load)
        self.ai_load_folder_btn.clicked.connect(self.on_ai_load_folder)
        self.ai_extract_btn.clicked.connect(self.on_ai_extract)
        self.ai_remove_btn.clicked.connect(self.on_ai_remove)
        self.ai_colorize_btn.clicked.connect(self.on_ai_colorize)
        self.ai_recombine_btn.clicked.connect(self.on_ai_recombine)
        self.ai_item_list.itemDoubleClicked.connect(self.on_ai_colorize)
        self.ai_cancel_btn.clicked.connect(self.on_ai_cancel)
        self._ai_single_done.connect(self._on_colorize_single_done)
        self._batch_folder_done.connect(self._on_folder_done)
        self._extract_done.connect(self._on_extract_done)
        self._recombine_done.connect(self._on_recombine_done)

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
        self.ai_contrast_slider['slider'].setEnabled(ai_en)
        self.ai_denoise_slider['slider'].setEnabled(ai_en)
        self.ai_batch_spin.setEnabled(ai_en)
        self.ai_fp16_check.setEnabled(ai_en and "cuda" in self.app_state.ai_colorization.gpu_device)
        self.ai_load_btn.setEnabled(ai_en)
        self.ai_load_folder_btn.setEnabled(ai_en)
        self.ai_extract_btn.setEnabled(ai_en)
        self.ai_remove_btn.setEnabled(ai_en)
        self.ai_colorize_btn.setEnabled(ai_en)
        self.ai_recombine_btn.setEnabled(ai_en)

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
            "SIGGRAPH17 (Balanced)": "siggraph17",
            "DeOldify (Premium)": "deoldify",
        }
        self.app_state.ai_colorization.engine = engine_map.get(text, "eccv16")
        is_deoldify = self.app_state.ai_colorization.engine == "deoldify"
        for w in getattr(self, 'ai_deoldify_widgets', []):
            w.setVisible(is_deoldify)
        self.settings_changed.emit()

    def on_ai_deoldify_model_changed(self, text):
        mv_map = {"Video (ResNet101)": "video", "Artistic (ResNet34)": "artistic", "Stable (ResNet101)": "stable"}
        self.app_state.ai_colorization.deoldify_model = mv_map.get(text, "video")
        self.settings_changed.emit()

    def on_ai_render_factor_changed(self, value):
        self.app_state.ai_colorization.render_factor = value
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

    def _get_selected_path(self):
        item = self.ai_item_list.currentItem()
        return item.text() if item else None

    def _is_folder(self, path):
        return os.path.isdir(path)

    def on_ai_load(self):
        """Load images into the list."""
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Images to Colorize", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
        )
        for p in paths:
            self.ai_item_list.addItem(p)

    def on_ai_load_folder(self):
        """Load a folder into the list."""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder with PNG Frames")
        if folder:
            self.ai_item_list.addItem(folder)

    def on_ai_remove(self):
        """Remove selected item from the list."""
        item = self.ai_item_list.currentItem()
        if item:
            fp = item.text()
            self._folder_video_map.pop(fp, None)
            self.ai_item_list.takeItem(self.ai_item_list.row(item))

    def on_ai_colorize(self, *args):
        """Colorize the selected item (image file or folder of PNGs)."""
        import threading, os
        path = self._get_selected_path()
        if not path:
            return

        if self._is_folder(path):
            self._run_folder_colorize(path)
        else:
            self._run_single_colorize(path)

    def _run_single_colorize(self, path):
        """Colorize a single image file."""
        import threading
        from pathlib import Path
        stem = Path(path).stem
        parent = Path(path).parent
        out_dir = parent / "ai_colorized"
        out_dir.mkdir(exist_ok=True)
        n = 1
        while (out_dir / f"{stem}_{n:03d}.png").exists():
            n += 1
        out_path = out_dir / f"{stem}_{n:03d}.png"

        self.ai_colorize_btn.setEnabled(False)
        self.ai_colorize_btn.setText("Colorizing...")

        def run():
            try:
                from controller import VideoController
                if self._cached_colorizer is None:
                    ctrl = VideoController(self.app_state)
                    self._cached_colorizer = ctrl._get_colorizer()
                colorizer = self._cached_colorizer
                if colorizer is None:
                    self._ai_single_done.emit()
                    return
                import cv2, numpy as np
                gray = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                if gray is None:
                    self.app_state.log(f"Could not read image: {path}", "ERROR")
                    return
                luma = gray.astype(np.float32) / 255.0
                rgb = colorizer.colorize_frame(luma)
                ai = self.app_state.ai_colorization
                if ai.saturation != 1.0 or ai.contrast != 1.0 or ai.denoise > 0.0:
                    from colorizers.utils import apply_postprocessing
                    rgb = apply_postprocessing(rgb, ai.saturation, ai.contrast, ai.denoise)
                bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                cv2.imwrite(str(out_path), bgr)
                self.app_state.log(f"Colorized image saved: {out_path}", "SUCCESS")
            except Exception as e:
                self.app_state.log(f"Colorize failed: {e}", "ERROR")
                import traceback
                traceback.print_exc()
            finally:
                self._ai_single_done.emit()

        thread = threading.Thread(target=run)
        thread.start()

    def _on_colorize_single_done(self):
        self.ai_colorize_btn.setEnabled(True)
        self.ai_colorize_btn.setText("Colorize")

    def _run_folder_colorize(self, folder):
        """Colorize all PNG frames in a folder."""
        import threading
        from pathlib import Path
        out_dir = Path(folder) / "ai_colorized"
        if out_dir.exists() and any(out_dir.iterdir()):
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self,
                "Overwrite?",
                f"ai_colorized/ already exists with colorized frames.\n"
                f"Overwrite? Existing files with the same name will be replaced.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        out_dir.mkdir(exist_ok=True)

        self.ai_colorize_btn.setEnabled(False)
        self.ai_colorize_btn.setText("Colorizing...")
        self.ai_item_progress.setText("Running...")
        self.ai_item_progress.setStyleSheet("color: orange;")
        self._enable_cancel(True)

        cancel = self.app_state.ai_cancel_event
        cancel.clear()

        def run():
            import os, time
            t0 = time.time()
            last_pct = 0
            from controller import VideoController
            if self._cached_colorizer is None:
                ctrl = VideoController(self.app_state)
                self._cached_colorizer = ctrl._get_colorizer()
            colorizer = self._cached_colorizer
            if colorizer is None:
                self._batch_folder_done.emit()
                return
            import cv2, numpy as np
            frames = sorted([f for f in os.listdir(folder) if f.lower().endswith('.png')])
            total = len(frames)
            processed = 0
            batch_luma = []
            batch_names = []
            batch_sz = self.app_state.ai_colorization.batch_size
            ai = self.app_state.ai_colorization
            try:
                for fname in frames:
                    if cancel.is_set():
                        break
                    src = os.path.join(folder, fname)
                    gray = cv2.imread(src, cv2.IMREAD_GRAYSCALE)
                    if gray is None:
                        continue
                    luma = gray.astype(np.float32) / 255.0
                    batch_luma.append(luma)
                    batch_names.append(fname)
                    if len(batch_luma) >= batch_sz:
                        arr = np.stack(batch_luma, axis=0)
                        rgb_batch = colorizer.colorize_batch(arr)
                        if ai.saturation != 1.0 or ai.contrast != 1.0 or ai.denoise > 0.0:
                            from colorizers.utils import apply_postprocessing
                            for i in range(len(rgb_batch)):
                                rgb_batch[i] = apply_postprocessing(
                                    rgb_batch[i], ai.saturation, ai.contrast, ai.denoise
                                )
                        for fn, rgb in zip(batch_names, rgb_batch):
                            out_path = out_dir / fn
                            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                            cv2.imwrite(str(out_path), bgr)
                        processed += len(batch_luma)
                        batch_luma = []
                        batch_names = []
                        pct = int(processed / total * 100) if total > 0 else 0
                        if abs(pct - last_pct) >= 5:
                            self.app_state.log(f"Colorizing: {pct}% ({processed}/{total} frames)", "INFO")
                            last_pct = pct
                if batch_luma:
                    arr = np.stack(batch_luma, axis=0)
                    rgb_batch = colorizer.colorize_batch(arr)
                    if ai.saturation != 1.0 or ai.contrast != 1.0 or ai.denoise > 0.0:
                        from colorizers.utils import apply_postprocessing
                        for i in range(len(rgb_batch)):
                            rgb_batch[i] = apply_postprocessing(
                                rgb_batch[i], ai.saturation, ai.contrast, ai.denoise
                            )
                    for fn, rgb in zip(batch_names, rgb_batch):
                        out_path = out_dir / fn
                        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                        cv2.imwrite(str(out_path), bgr)
                    processed += len(batch_luma)
                elapsed = time.time() - t0
                if cancel.is_set():
                    self.app_state.log(f"⏹ Colour cancelled after {processed}/{total} frames ({elapsed:.1f}s)", "WARN")
                else:
                    self.app_state.log(f"Colour complete: {processed}/{total} frames in {elapsed:.1f}s", "SUCCESS")
            except Exception as e:
                self.app_state.log(f"Colour failed: {e}", "ERROR")
                import traceback
                traceback.print_exc()
            finally:
                cancel.clear()
                self._batch_folder_done.emit()

        thread = threading.Thread(target=run)
        thread.start()

    def _enable_cancel(self, enabled):
        self.ai_cancel_btn.setEnabled(enabled)
        self.ai_cancel_btn.setText("Cancel" if enabled else "Cancel")

    def on_ai_extract(self):
        """Extract PNG frames from a video, add the output folder to the list."""
        import threading, os
        from pathlib import Path
        from PySide6.QtWidgets import QFileDialog

        video_path, _ = QFileDialog.getOpenFileName(
            self, "Select Video to Extract Frames From", "",
            "Video (*.mp4 *.mkv *.avi *.mov *.webm)"
        )
        if not video_path:
            return

        stem = Path(video_path).stem
        parent = Path(video_path).parent
        out_dir = parent / f"{stem}_frames"
        out_dir.mkdir(exist_ok=True)

        from controller import VideoController
        ctrl = VideoController(self.app_state)
        fps = ctrl.backend.get_fps(video_path)
        if fps <= 0:
            fps = 24000 / 1001

        # Add to list immediately with video info
        self.ai_item_list.addItem(str(out_dir))
        self._folder_video_map[str(out_dir)] = (video_path, fps)

        self.ai_extract_btn.setEnabled(False)
        self.ai_extract_btn.setText("Extracting...")
        self.ai_item_progress.setText("Extracting...")
        self.ai_item_progress.setStyleSheet("color: orange;")
        self._enable_cancel(True)

        cancel = self.app_state.ai_cancel_event
        cancel.clear()

        def run():
            try:
                ffmpeg = self.app_state.ffmpeg_path
                import subprocess
                cmd = [
                    ffmpeg, "-y", "-i", video_path,
                    "-pix_fmt", "gray",
                    "-vf", f"fps={fps}",
                    os.path.join(str(out_dir), "frame_%08d.png")
                ]
                proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                while proc.poll() is None:
                    if cancel.is_set():
                        proc.terminate()
                        break
                    import time
                    time.sleep(0.1)
                proc.wait()
                frame_count = len([f for f in os.listdir(str(out_dir)) if f.endswith('.png')])
                if cancel.is_set():
                    self.app_state.log(f"⏹ Extraction cancelled: {frame_count} frames in {out_dir.name}", "WARN")
                else:
                    self.app_state.log(f"Extracted {frame_count} frames to {out_dir}", "SUCCESS")
            except Exception as e:
                self.app_state.log(f"Extraction failed: {e}", "ERROR")
                import traceback
                traceback.print_exc()
            finally:
                cancel.clear()
                self._extract_done.emit()

        thread = threading.Thread(target=run)
        thread.start()

    def _on_extract_done(self):
        self.ai_extract_btn.setEnabled(True)
        self.ai_extract_btn.setText("Extract")
        self.ai_item_progress.setText("")
        self.ai_item_progress.setStyleSheet("color: gray;")
        self._enable_cancel(False)

    def on_ai_recombine(self):
        """Recombine colorized frames into video with audio."""
        import threading, os, subprocess
        from pathlib import Path
        from PySide6.QtWidgets import QFileDialog

        path = self._get_selected_path()
        if not path or not self._is_folder(path):
            self.app_state.log("Select a folder (must be in the list) to recombine", "WARN")
            return
        folder = Path(path)
        colorized_dir = folder / "ai_colorized"
        if not colorized_dir.exists() or not any(colorized_dir.iterdir()):
            self.app_state.log(f"No colorized frames found in {colorized_dir}", "ERROR")
            return

        # Get original video info from stored map or prompt user
        info = self._folder_video_map.get(str(folder))
        if info and os.path.isfile(info[0]):
            video_path, fps = info
        else:
            video_path, _ = QFileDialog.getOpenFileName(
                self, "Select Original Video for Audio", "",
                "Video (*.mp4 *.mkv *.avi *.mov *.webm)"
            )
            if not video_path:
                return
            from controller import VideoController
            ctrl = VideoController(self.app_state)
            fps = ctrl.backend.get_fps(video_path)
            if fps <= 0:
                fps = 24000 / 1001

        stem = folder.stem
        output_path = folder.parent / f"{stem}_colorized.mp4"
        ffmpeg = self.app_state.ffmpeg_path

        self.ai_recombine_btn.setEnabled(False)
        self.ai_recombine_btn.setText("Recombining...")
        self.ai_item_progress.setText("Recombining...")
        self.ai_item_progress.setStyleSheet("color: orange;")
        self._enable_cancel(True)

        cancel = self.app_state.ai_cancel_event
        cancel.clear()

        def run():
            try:
                input_pattern = os.path.join(str(colorized_dir), "frame_%08d.png")
                cmd = [
                    ffmpeg, "-y",
                    "-framerate", str(fps),
                    "-i", input_pattern,
                    "-i", video_path,
                    "-map", "0:v",
                    "-map", "1:a?",
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-preset", "fast",
                    "-crf", "18",
                    "-c:a", "copy",
                    "-shortest",
                    str(output_path)
                ]
                proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                while proc.poll() is None:
                    if cancel.is_set():
                        proc.terminate()
                        break
                    import time
                    time.sleep(0.1)
                proc.wait()
                if cancel.is_set():
                    self.app_state.log("⏹ Recombination cancelled", "WARN")
                    if output_path.exists():
                        output_path.unlink()
                elif proc.returncode == 0:
                    self.app_state.log(f"Recombined video: {output_path}", "SUCCESS")
                else:
                    self.app_state.log("Recombination failed", "ERROR")
            except Exception as e:
                self.app_state.log(f"Recombination error: {e}", "ERROR")
                import traceback
                traceback.print_exc()
            finally:
                cancel.clear()
                self._recombine_done.emit()

        thread = threading.Thread(target=run)
        thread.start()

    def _on_recombine_done(self):
        self.ai_recombine_btn.setEnabled(True)
        self.ai_recombine_btn.setText("Recombine")
        self.ai_item_progress.setText("")
        self.ai_item_progress.setStyleSheet("color: gray;")
        self._enable_cancel(False)

    def _on_folder_done(self):
        self.ai_colorize_btn.setEnabled(True)
        self.ai_colorize_btn.setText("Colorize")
        self.ai_item_progress.setText("")
        self.ai_item_progress.setStyleSheet("color: gray;")
        self._enable_cancel(False)

    def on_ai_cancel(self):
        """Cancel the current AI colorization operation."""
        self.app_state.ai_cancel_event.set()
        self.ai_cancel_btn.setEnabled(False)
        self.ai_cancel_btn.setText("Cancelling...")
        self.app_state.log("⏹ Cancel requested — stopping AI colorization...", "WARN")

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
        ai.contrast = 1.0
        ai.denoise = 0.0
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
        # Contrast reset
        m_con = self.ai_contrast_slider['slider'].property("multiplier")
        self.ai_contrast_slider['slider'].blockSignals(True)
        self.ai_contrast_slider['slider'].setValue(int(1.0 * m_con))
        self.ai_contrast_slider['slider'].blockSignals(False)
        self.ai_contrast_slider['value_label'].setText("1.00")
        # Denoise reset
        m_den = self.ai_denoise_slider['slider'].property("multiplier")
        self.ai_denoise_slider['slider'].blockSignals(True)
        self.ai_denoise_slider['slider'].setValue(0)
        self.ai_denoise_slider['slider'].blockSignals(False)
        self.ai_denoise_slider['value_label'].setText("0.00")
        # Color correct reset
        ai.color_correct_strength = 0.5
        m_cc = self.ai_cc_slider['slider'].property("multiplier")
        self.ai_cc_slider['slider'].blockSignals(True)
        self.ai_cc_slider['slider'].setValue(int(0.5 * m_cc))
        self.ai_cc_slider['slider'].blockSignals(False)
        self.ai_cc_slider['value_label'].setText("0.50")
        # Reset pipeline status labels
        self.ai_item_progress.setText("")
        self.ai_item_progress.setStyleSheet("color: gray;")
