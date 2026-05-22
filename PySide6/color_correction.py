"""
Color Correction (EQ) Panel (PySide6)
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QSlider, QPushButton, QFrame, QComboBox
)
from PySide6.QtCore import Qt, Signal

from models import AppState


class ColorCorrectionPanel(QWidget):
    """Panel for color correction (EQ) settings"""
    
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
        
    def on_enable_changed(self, checked):
        """Handle enable checkbox change"""
        self.app_state.eq.enabled = checked
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
            
        self.settings_changed.emit()
        self.app_state.log("EQ settings reset to defaults", "INFO")
