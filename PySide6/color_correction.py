"""
Color Correction (EQ) Panel (PySide6)
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QSlider, QPushButton, QFrame
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
                
    def reset_defaults(self):
        """Reset all EQ settings to defaults"""
        self.app_state.eq.brightness = 0.0
        self.app_state.eq.contrast = 1.0
        self.app_state.eq.saturation = 1.0
        self.app_state.eq.gamma = 1.0
        self.app_state.eq.gamma_r = 1.0
        self.app_state.eq.gamma_g = 1.0
        self.app_state.eq.gamma_b = 1.0
        
        # Update sliders
        for slider_dict in [self.brightness_slider, self.contrast_slider, 
                           self.saturation_slider, self.gamma_slider]:
            default = slider_dict['slider'].property("default_value")
            multiplier = slider_dict['slider'].property("multiplier")
            slider_dict['slider'].setValue(int(default * multiplier))
            
        for slider_dict in [self.gamma_r_slider, self.gamma_g_slider, self.gamma_b_slider]:
            multiplier = slider_dict['slider'].property("multiplier")
            slider_dict['slider'].setValue(int(1.0 * multiplier))
            
        self.settings_changed.emit()
        self.app_state.log("EQ settings reset to defaults", "INFO")
