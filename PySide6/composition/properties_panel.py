"""
Properties Panel - Layer property editor for composition

This widget displays and edits properties of the selected layer,
including transform, timing, type-specific properties, and effects.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSpinBox, QDoubleSpinBox, QComboBox,
    QLineEdit, QCheckBox, QSlider, QColorDialog, QMenu,
    QGroupBox, QFormLayout, QSizePolicy, QToolButton, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor

from composition.models import (
    Layer, ColorLayer, VideoLayer, ImageLayer, TextLayer, ShapeLayer,
    Effect, BlendMode, LayerType, ShapeType, EffectType
)


# Blend mode options for combo box
BLEND_MODES = [
    ("Normal", "normal"),
    ("Multiply", "multiply"),
    ("Screen", "screen"),
    ("Overlay", "overlay"),
    ("Darken", "darken"),
    ("Lighten", "lighten"),
    ("Color Dodge", "color_dodge"),
    ("Color Burn", "color_burn"),
    ("Hard Light", "hard_light"),
    ("Soft Light", "soft_light"),
    ("Difference", "difference"),
    ("Exclusion", "exclusion"),
]


class PropertySection(QFrame):
    """
    Collapsible section for grouping properties.
    """
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._expanded = True
        self._setup_ui(title)
        
    def _setup_ui(self, title: str):
        """Setup section UI"""
        self.setStyleSheet("""
            PropertySection {
                background-color: #2a2a2a;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                margin-top: 5px;
            }
        """)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(5)
        
        # Header with toggle
        self.header = QPushButton(f"▼ {title}")
        self.header.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ddd;
                font-weight: bold;
                text-align: left;
                border: none;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #333;
            }
        """)
        self.header.clicked.connect(self._toggle)
        self.main_layout.addWidget(self.header)
        
        # Content container
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(10, 0, 0, 0)
        self.content_layout.setSpacing(5)
        self.main_layout.addWidget(self.content)
        
        self._title = title
        
    def _toggle(self):
        """Toggle section visibility"""
        self._expanded = not self._expanded
        self.content.setVisible(self._expanded)
        arrow = "▼" if self._expanded else "▶"
        self.header.setText(f"{arrow} {self._title}")
        
    def add_widget(self, widget: QWidget):
        """Add a widget to the section content"""
        self.content_layout.addWidget(widget)
        
    def add_layout(self, layout):
        """Add a layout to the section content"""
        self.content_layout.addLayout(layout)


class ColorButton(QPushButton):
    """
    Button that shows a color and opens color picker on click.
    """
    
    color_changed = Signal(str)  # hex color
    
    def __init__(self, color: str = "#FFFFFF", parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(60, 24)
        self._update_style()
        self.clicked.connect(self._on_click)
        
    def _update_style(self):
        """Update button appearance"""
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._color};
                border: 1px solid #555;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                border: 2px solid #888;
            }}
        """)
        
    def _on_click(self):
        """Open color picker"""
        color = QColorDialog.getColor(QColor(self._color), self, "Select Color")
        if color.isValid():
            self._color = color.name()
            self._update_style()
            self.color_changed.emit(self._color)
            
    def set_color(self, color: str):
        """Set the color"""
        self._color = color
        self._update_style()
        
    def get_color(self) -> str:
        """Get the current color"""
        return self._color


class PropertiesPanel(QWidget):
    """
    Main properties panel for editing layer properties.
    
    Displays:
    - Layer name and type
    - Transform (position, scale, rotation)
    - Timing (start/end time)
    - Type-specific properties
    - Effects list
    """
    
    # Signals
    layer_changed = Signal(str)  # layer_id
    effect_added = Signal(str, str)  # layer_id, effect_type
    effect_removed = Signal(str, str)  # layer_id, effect_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._layer = None
        self._updating = False  # Flag to prevent feedback loops
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the properties panel UI"""
        self.setMinimumWidth(250)
        self.setMaximumWidth(350)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Header
        header = QLabel("Properties")
        header.setStyleSheet("font-weight: bold; font-size: 14px; color: #ddd; padding: 5px;")
        main_layout.addWidget(header)
        
        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                background-color: #1e1e1e;
            }
        """)
        
        # Content container
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        self.content_layout.setSpacing(10)
        self.content_layout.addStretch()
        
        scroll.setWidget(self.content)
        main_layout.addWidget(scroll, 1)
        
        # Create property sections
        self._create_common_section()
        self._create_transform_section()
        self._create_timing_section()
        self._create_type_specific_section()
        self._create_effects_section()
        
        # Initially show placeholder
        self._show_placeholder()
        
    def _create_common_section(self):
        """Create common properties section"""
        self.common_section = PropertySection("Layer")
        
        # Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._on_name_changed)
        name_layout.addWidget(self.name_edit)
        self.common_section.add_layout(name_layout)
        
        # Opacity
        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(QLabel("Opacity:"))
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_layout.addWidget(self.opacity_slider)
        self.opacity_label = QLabel("100%")
        self.opacity_label.setFixedWidth(40)
        opacity_layout.addWidget(self.opacity_label)
        self.common_section.add_layout(opacity_layout)
        
        # Blend mode
        blend_layout = QHBoxLayout()
        blend_layout.addWidget(QLabel("Blend:"))
        self.blend_combo = QComboBox()
        for name, value in BLEND_MODES:
            self.blend_combo.addItem(name, value)
        self.blend_combo.currentIndexChanged.connect(self._on_blend_changed)
        blend_layout.addWidget(self.blend_combo)
        self.common_section.add_layout(blend_layout)
        
        self.content_layout.insertWidget(0, self.common_section)
        
    def _create_transform_section(self):
        """Create transform properties section"""
        self.transform_section = PropertySection("Transform")
        
        # Position
        pos_layout = QFormLayout()
        self.pos_x_spin = QDoubleSpinBox()
        self.pos_x_spin.setRange(-9999, 9999)
        self.pos_x_spin.valueChanged.connect(self._on_transform_changed)
        pos_layout.addRow("X:", self.pos_x_spin)
        
        self.pos_y_spin = QDoubleSpinBox()
        self.pos_y_spin.setRange(-9999, 9999)
        self.pos_y_spin.valueChanged.connect(self._on_transform_changed)
        pos_layout.addRow("Y:", self.pos_y_spin)
        self.transform_section.add_layout(pos_layout)
        
        # Scale
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("Scale:"))
        self.scale_x_spin = QDoubleSpinBox()
        self.scale_x_spin.setRange(0.01, 10.0)
        self.scale_x_spin.setSingleStep(0.1)
        self.scale_x_spin.valueChanged.connect(self._on_transform_changed)
        scale_layout.addWidget(self.scale_x_spin)
        
        self.scale_y_spin = QDoubleSpinBox()
        self.scale_y_spin.setRange(0.01, 10.0)
        self.scale_y_spin.setSingleStep(0.1)
        self.scale_y_spin.valueChanged.connect(self._on_transform_changed)
        scale_layout.addWidget(self.scale_y_spin)
        
        self.link_scale_btn = QToolButton()
        self.link_scale_btn.setText("🔗")
        self.link_scale_btn.setCheckable(True)
        self.link_scale_btn.setChecked(True)
        self.link_scale_btn.setToolTip("Link X and Y scale")
        scale_layout.addWidget(self.link_scale_btn)
        self.transform_section.add_layout(scale_layout)
        
        # Rotation
        rot_layout = QHBoxLayout()
        rot_layout.addWidget(QLabel("Rotation:"))
        self.rotation_spin = QDoubleSpinBox()
        self.rotation_spin.setRange(-360, 360)
        self.rotation_spin.setSingleStep(1.0)
        self.rotation_spin.valueChanged.connect(self._on_transform_changed)
        rot_layout.addWidget(self.rotation_spin)
        rot_layout.addWidget(QLabel("°"))
        rot_layout.addStretch()
        self.transform_section.add_layout(rot_layout)
        
        self.content_layout.insertWidget(1, self.transform_section)
        
    def _create_timing_section(self):
        """Create timing properties section"""
        self.timing_section = PropertySection("Timing")
        
        # Start time
        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("Start:"))
        self.start_spin = QDoubleSpinBox()
        self.start_spin.setRange(0, 9999)
        self.start_spin.setSingleStep(0.1)
        self.start_spin.setSuffix(" s")
        self.start_spin.valueChanged.connect(self._on_timing_changed)
        start_layout.addWidget(self.start_spin)
        self.timing_section.add_layout(start_layout)
        
        # End time
        end_layout = QHBoxLayout()
        end_layout.addWidget(QLabel("End:"))
        self.end_spin = QDoubleSpinBox()
        self.end_spin.setRange(0, 9999)
        self.end_spin.setSingleStep(0.1)
        self.end_spin.setSuffix(" s")
        self.end_spin.valueChanged.connect(self._on_timing_changed)
        end_layout.addWidget(self.end_spin)
        self.timing_section.add_layout(end_layout)
        
        # Duration (read-only)
        dur_layout = QHBoxLayout()
        dur_layout.addWidget(QLabel("Duration:"))
        self.duration_label = QLabel("30.0 s")
        self.duration_label.setStyleSheet("color: #888;")
        dur_layout.addWidget(self.duration_label)
        dur_layout.addStretch()
        self.timing_section.add_layout(dur_layout)
        
        self.content_layout.insertWidget(2, self.timing_section)
        
    def _create_type_specific_section(self):
        """Create type-specific properties section"""
        self.type_section = PropertySection("Layer Properties")
        self.type_content = QWidget()
        self.type_content_layout = QVBoxLayout(self.type_content)
        self.type_content_layout.setContentsMargins(0, 0, 0, 0)
        self.type_section.add_widget(self.type_content)
        self.content_layout.insertWidget(3, self.type_section)
        
    def _create_effects_section(self):
        """Create effects section"""
        self.effects_section = PropertySection("Effects")
        
        # Effects list container
        self.effects_list = QWidget()
        self.effects_list_layout = QVBoxLayout(self.effects_list)
        self.effects_list_layout.setContentsMargins(0, 0, 0, 0)
        self.effects_list_layout.setSpacing(5)
        self.effects_section.add_widget(self.effects_list)
        
        # Add effect button
        add_effect_layout = QHBoxLayout()
        self.add_effect_btn = QPushButton("➕ Add Effect")
        self.add_effect_btn.clicked.connect(self._show_add_effect_menu)
        add_effect_layout.addWidget(self.add_effect_btn)
        self.effects_section.add_layout(add_effect_layout)
        
        self.content_layout.insertWidget(4, self.effects_section)
        
    def _show_placeholder(self):
        """Show placeholder when no layer is selected"""
        self.common_section.setVisible(False)
        self.transform_section.setVisible(False)
        self.timing_section.setVisible(False)
        self.type_section.setVisible(False)
        self.effects_section.setVisible(False)
        
        # Show placeholder label
        if not hasattr(self, '_placeholder'):
            self._placeholder = QLabel("Select a layer to edit\nits properties")
            self._placeholder.setAlignment(Qt.AlignCenter)
            self._placeholder.setStyleSheet("color: #666; padding: 20px;")
            self.content_layout.insertWidget(0, self._placeholder)
        self._placeholder.setVisible(True)
        
    def _hide_placeholder(self):
        """Hide placeholder when a layer is selected"""
        if hasattr(self, '_placeholder'):
            self._placeholder.setVisible(False)
            
        self.common_section.setVisible(True)
        self.transform_section.setVisible(True)
        self.timing_section.setVisible(True)
        self.type_section.setVisible(True)
        self.effects_section.setVisible(True)
        
    def set_layer(self, layer: Layer):
        """Set the layer to edit"""
        self._layer = layer
        self._updating = True
        
        if layer is None:
            self._show_placeholder()
            self._updating = False
            return
            
        self._hide_placeholder()
        
        # Update common properties
        self.name_edit.setText(layer.name)
        self.opacity_slider.setValue(int(layer.opacity * 100))
        
        # Set blend mode
        for i, (name, value) in enumerate(BLEND_MODES):
            if value == layer.blend_mode:
                self.blend_combo.setCurrentIndex(i)
                break
                
        # Update transform
        self.pos_x_spin.setValue(layer.transform.position_x)
        self.pos_y_spin.setValue(layer.transform.position_y)
        self.scale_x_spin.setValue(layer.transform.scale_x)
        self.scale_y_spin.setValue(layer.transform.scale_y)
        self.rotation_spin.setValue(layer.transform.rotation)
        
        # Update timing
        self.start_spin.setValue(layer.start_time)
        self.end_spin.setValue(layer.end_time)
        self._update_duration_label()
        
        # Update type-specific properties
        self._update_type_specific(layer)
        
        # Update effects list
        self._update_effects_list()
        
        self._updating = False
        
    def _update_duration_label(self):
        """Update the duration label"""
        if self._layer:
            duration = self._layer.duration
            self.duration_label.setText(f"{duration:.1f} s")
            
    def _update_type_specific(self, layer: Layer):
        """Update type-specific property editors"""
        # Clear existing widgets
        while self.type_content_layout.count():
            item = self.type_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        # Add type-specific editors
        if isinstance(layer, ColorLayer):
            self._create_color_properties(layer)
        elif isinstance(layer, VideoLayer):
            self._create_video_properties(layer)
        elif isinstance(layer, ImageLayer):
            self._create_image_properties(layer)
        elif isinstance(layer, TextLayer):
            self._create_text_properties(layer)
        elif isinstance(layer, ShapeLayer):
            self._create_shape_properties(layer)
        else:
            # Generic layer - no type-specific properties
            label = QLabel("No additional properties")
            label.setStyleSheet("color: #666;")
            self.type_content_layout.addWidget(label)
            
    def _create_color_properties(self, layer: ColorLayer):
        """Create color layer properties"""
        # Color picker
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Color:"))
        self.color_btn = ColorButton(layer.color)
        self.color_btn.color_changed.connect(self._on_color_changed)
        color_layout.addWidget(self.color_btn)
        color_layout.addStretch()
        self.type_content_layout.addLayout(color_layout)
        
        # Gradient toggle
        gradient_layout = QHBoxLayout()
        self.gradient_check = QCheckBox("Gradient")
        self.gradient_check.setChecked(layer.gradient_enabled)
        self.gradient_check.stateChanged.connect(self._on_gradient_toggled)
        gradient_layout.addWidget(self.gradient_check)
        self.type_content_layout.addLayout(gradient_layout)
        
        # Gradient color (if enabled)
        if layer.gradient_enabled:
            grad_color_layout = QHBoxLayout()
            grad_color_layout.addWidget(QLabel("Gradient Color:"))
            self.gradient_color_btn = ColorButton(layer.gradient_color)
            self.gradient_color_btn.color_changed.connect(self._on_gradient_color_changed)
            grad_color_layout.addWidget(self.gradient_color_btn)
            grad_color_layout.addStretch()
            self.type_content_layout.addLayout(grad_color_layout)
            
            # Gradient direction
            dir_layout = QHBoxLayout()
            dir_layout.addWidget(QLabel("Direction:"))
            self.gradient_dir_spin = QDoubleSpinBox()
            self.gradient_dir_spin.setRange(0, 360)
            self.gradient_dir_spin.setValue(layer.gradient_direction)
            self.gradient_dir_spin.setSuffix("°")
            self.gradient_dir_spin.valueChanged.connect(self._on_gradient_direction_changed)
            dir_layout.addWidget(self.gradient_dir_spin)
            dir_layout.addStretch()
            self.type_content_layout.addLayout(dir_layout)
            
    def _create_video_properties(self, layer: VideoLayer):
        """Create video layer properties"""
        # Source path
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Source:"))
        self.video_path_edit = QLineEdit(layer.source_path)
        self.video_path_edit.setReadOnly(True)
        path_layout.addWidget(self.video_path_edit)
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(30)
        browse_btn.clicked.connect(self._on_browse_video)
        path_layout.addWidget(browse_btn)
        self.type_content_layout.addLayout(path_layout)
        
        # Loop
        loop_layout = QHBoxLayout()
        self.loop_check = QCheckBox("Loop")
        self.loop_check.setChecked(layer.loop)
        self.loop_check.stateChanged.connect(self._on_loop_toggled)
        loop_layout.addWidget(self.loop_check)
        self.type_content_layout.addLayout(loop_layout)
        
        # Mute
        mute_layout = QHBoxLayout()
        self.mute_check = QCheckBox("Mute Audio")
        self.mute_check.setChecked(layer.mute)
        self.mute_check.stateChanged.connect(self._on_mute_toggled)
        mute_layout.addWidget(self.mute_check)
        self.type_content_layout.addLayout(mute_layout)
        
        # Volume
        vol_layout = QHBoxLayout()
        vol_layout.addWidget(QLabel("Volume:"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 200)
        self.volume_slider.setValue(int(layer.volume * 100))
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        vol_layout.addWidget(self.volume_slider)
        self.volume_label = QLabel(f"{int(layer.volume * 100)}%")
        self.volume_label.setFixedWidth(40)
        vol_layout.addWidget(self.volume_label)
        self.type_content_layout.addLayout(vol_layout)
        
    def _create_image_properties(self, layer: ImageLayer):
        """Create image layer properties"""
        # Source path
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Source:"))
        self.image_path_edit = QLineEdit(layer.source_path)
        self.image_path_edit.setReadOnly(True)
        path_layout.addWidget(self.image_path_edit)
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(30)
        browse_btn.clicked.connect(self._on_browse_image)
        path_layout.addWidget(browse_btn)
        self.type_content_layout.addLayout(path_layout)
        
        # Fit mode
        fit_layout = QHBoxLayout()
        fit_layout.addWidget(QLabel("Fit Mode:"))
        self.fit_combo = QComboBox()
        self.fit_combo.addItems(["Fill", "Fit", "Stretch", "None"])
        self.fit_combo.setCurrentText(layer.fit_mode.capitalize())
        self.fit_combo.currentTextChanged.connect(self._on_fit_mode_changed)
        fit_layout.addWidget(self.fit_combo)
        self.type_content_layout.addLayout(fit_layout)
        
    def _create_text_properties(self, layer: TextLayer):
        """Create text layer properties"""
        # Text content
        text_layout = QVBoxLayout()
        text_layout.addWidget(QLabel("Text:"))
        self.text_edit = QLineEdit(layer.text)
        self.text_edit.textChanged.connect(self._on_text_changed)
        text_layout.addWidget(self.text_edit)
        self.type_content_layout.addLayout(text_layout)
        
        # Font family
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("Font:"))
        self.font_combo = QComboBox()
        self.font_combo.addItems(["Arial", "Helvetica", "Times New Roman", "Georgia", "Verdana", "Courier New"])
        self.font_combo.setCurrentText(layer.font_family)
        self.font_combo.currentTextChanged.connect(self._on_font_changed)
        font_layout.addWidget(self.font_combo)
        self.type_content_layout.addLayout(font_layout)
        
        # Font size
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Size:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 200)
        self.font_size_spin.setValue(layer.font_size)
        self.font_size_spin.valueChanged.connect(self._on_font_size_changed)
        size_layout.addWidget(self.font_size_spin)
        size_layout.addWidget(QLabel("pt"))
        size_layout.addStretch()
        self.type_content_layout.addLayout(size_layout)
        
        # Font weight
        weight_layout = QHBoxLayout()
        self.bold_check = QCheckBox("Bold")
        self.bold_check.setChecked(layer.font_weight == "bold")
        self.bold_check.stateChanged.connect(self._on_bold_toggled)
        weight_layout.addWidget(self.bold_check)
        
        self.italic_check = QCheckBox("Italic")
        self.italic_check.setChecked(layer.font_style == "italic")
        self.italic_check.stateChanged.connect(self._on_italic_toggled)
        weight_layout.addWidget(self.italic_check)
        self.type_content_layout.addLayout(weight_layout)
        
        # Text color
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Color:"))
        self.text_color_btn = ColorButton(layer.color)
        self.text_color_btn.color_changed.connect(self._on_text_color_changed)
        color_layout.addWidget(self.text_color_btn)
        color_layout.addStretch()
        self.type_content_layout.addLayout(color_layout)
        
        # Alignment
        align_layout = QHBoxLayout()
        align_layout.addWidget(QLabel("Align:"))
        self.align_combo = QComboBox()
        self.align_combo.addItems(["Left", "Center", "Right"])
        self.align_combo.setCurrentText(layer.alignment.capitalize())
        self.align_combo.currentTextChanged.connect(self._on_alignment_changed)
        align_layout.addWidget(self.align_combo)
        self.type_content_layout.addLayout(align_layout)
        
    def _create_shape_properties(self, layer: ShapeLayer):
        """Create shape layer properties"""
        # Shape type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Shape:"))
        self.shape_combo = QComboBox()
        self.shape_combo.addItems(["Rectangle", "Ellipse", "Line", "Polygon", "Star"])
        self.shape_combo.setCurrentText(layer.shape_type.capitalize())
        self.shape_combo.currentTextChanged.connect(self._on_shape_type_changed)
        type_layout.addWidget(self.shape_combo)
        self.type_content_layout.addLayout(type_layout)
        
        # Size
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Size:"))
        self.shape_width_spin = QDoubleSpinBox()
        self.shape_width_spin.setRange(1, 9999)
        self.shape_width_spin.setValue(layer.width)
        self.shape_width_spin.valueChanged.connect(self._on_shape_size_changed)
        size_layout.addWidget(self.shape_width_spin)
        size_layout.addWidget(QLabel("×"))
        self.shape_height_spin = QDoubleSpinBox()
        self.shape_height_spin.setRange(1, 9999)
        self.shape_height_spin.setValue(layer.height)
        self.shape_height_spin.valueChanged.connect(self._on_shape_size_changed)
        size_layout.addWidget(self.shape_height_spin)
        self.type_content_layout.addLayout(size_layout)
        
        # Fill color
        fill_layout = QHBoxLayout()
        self.fill_check = QCheckBox("Fill")
        self.fill_check.setChecked(layer.fill_enabled)
        self.fill_check.stateChanged.connect(self._on_fill_toggled)
        fill_layout.addWidget(self.fill_check)
        self.fill_color_btn = ColorButton(layer.fill_color)
        self.fill_color_btn.color_changed.connect(self._on_fill_color_changed)
        fill_layout.addWidget(self.fill_color_btn)
        fill_layout.addStretch()
        self.type_content_layout.addLayout(fill_layout)
        
        # Stroke
        stroke_layout = QHBoxLayout()
        self.stroke_check = QCheckBox("Stroke")
        self.stroke_check.setChecked(layer.stroke_enabled)
        self.stroke_check.stateChanged.connect(self._on_stroke_toggled)
        stroke_layout.addWidget(self.stroke_check)
        self.stroke_color_btn = ColorButton(layer.stroke_color)
        self.stroke_color_btn.color_changed.connect(self._on_stroke_color_changed)
        stroke_layout.addWidget(self.stroke_color_btn)
        self.type_content_layout.addLayout(stroke_layout)
        
        # Stroke width
        stroke_width_layout = QHBoxLayout()
        stroke_width_layout.addWidget(QLabel("Stroke Width:"))
        self.stroke_width_spin = QDoubleSpinBox()
        self.stroke_width_spin.setRange(0.5, 50)
        self.stroke_width_spin.setValue(layer.stroke_width)
        self.stroke_width_spin.valueChanged.connect(self._on_stroke_width_changed)
        stroke_width_layout.addWidget(self.stroke_width_spin)
        stroke_width_layout.addStretch()
        self.type_content_layout.addLayout(stroke_width_layout)
        
        # Corner radius (for rectangles)
        if layer.shape_type == "rectangle":
            corner_layout = QHBoxLayout()
            corner_layout.addWidget(QLabel("Corner Radius:"))
            self.corner_spin = QDoubleSpinBox()
            self.corner_spin.setRange(0, 500)
            self.corner_spin.setValue(layer.corner_radius)
            self.corner_spin.valueChanged.connect(self._on_corner_radius_changed)
            corner_layout.addWidget(self.corner_spin)
            corner_layout.addStretch()
            self.type_content_layout.addLayout(corner_layout)
            
    def _update_effects_list(self):
        """Update the effects list"""
        # Clear existing widgets
        while self.effects_list_layout.count():
            item = self.effects_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        if not self._layer:
            return
            
        # Add effect items
        for effect in self._layer.effects:
            item = self._create_effect_item(effect)
            self.effects_list_layout.addWidget(item)
            
        # Show "No effects" message if empty
        if not self._layer.effects:
            no_effects = QLabel("No effects applied")
            no_effects.setStyleSheet("color: #666;")
            self.effects_list_layout.addWidget(no_effects)
            
    def _create_effect_item(self, effect: Effect) -> QWidget:
        """Create a widget for an effect item"""
        item = QFrame()
        item.setStyleSheet("""
            QFrame {
                background-color: #333;
                border: 1px solid #444;
                border-radius: 3px;
            }
        """)
        
        layout = QVBoxLayout(item)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Header row
        header = QHBoxLayout()
        
        # Enable checkbox
        enable_check = QCheckBox()
        enable_check.setChecked(effect.enabled)
        enable_check.stateChanged.connect(lambda state, e=effect: self._on_effect_enabled(e, state))
        header.addWidget(enable_check)
        
        # Effect name
        name_label = QLabel(effect.name)
        name_label.setStyleSheet("font-weight: bold;")
        header.addWidget(name_label, 1)
        
        # Remove button
        remove_btn = QToolButton()
        remove_btn.setText("×")
        remove_btn.setFixedSize(20, 20)
        remove_btn.clicked.connect(lambda checked, e=effect: self._on_remove_effect(e))
        header.addWidget(remove_btn)
        
        layout.addLayout(header)
        
        # Parameter controls (simplified for now)
        params_widget = self._create_effect_params(effect)
        if params_widget:
            layout.addWidget(params_widget)
            
        return item
        
    def _create_effect_params(self, effect: Effect) -> QWidget:
        """Create parameter controls for an effect"""
        if not effect.parameters:
            return None
            
        params_widget = QWidget()
        params_layout = QFormLayout(params_widget)
        params_layout.setContentsMargins(20, 0, 0, 0)
        params_layout.setSpacing(3)
        
        for param_name, value in effect.parameters.items():
            # Skip complex parameters like keyframes
            if isinstance(value, (list, dict)):
                continue
                
            # Create appropriate control
            if isinstance(value, bool):
                check = QCheckBox()
                check.setChecked(value)
                check.stateChanged.connect(lambda state, e=effect, p=param_name: self._on_effect_param_changed(e, p, bool(state)))
                params_layout.addRow(param_name.replace("_", " ").title() + ":", check)
            elif isinstance(value, float):
                spin = QDoubleSpinBox()
                spin.setRange(-9999, 9999)
                spin.setValue(value)
                spin.valueChanged.connect(lambda val, e=effect, p=param_name: self._on_effect_param_changed(e, p, val))
                params_layout.addRow(param_name.replace("_", " ").title() + ":", spin)
            elif isinstance(value, int):
                spin = QSpinBox()
                spin.setRange(-9999, 9999)
                spin.setValue(value)
                spin.valueChanged.connect(lambda val, e=effect, p=param_name: self._on_effect_param_changed(e, p, val))
                params_layout.addRow(param_name.replace("_", " ").title() + ":", spin)
            elif isinstance(value, str) and value.startswith("#"):
                # Color parameter
                color_btn = ColorButton(value)
                color_btn.color_changed.connect(lambda color, e=effect, p=param_name: self._on_effect_param_changed(e, p, color))
                params_layout.addRow(param_name.replace("_", " ").title() + ":", color_btn)
            else:
                # String parameter
                line_edit = QLineEdit(str(value))
                line_edit.textChanged.connect(lambda text, e=effect, p=param_name: self._on_effect_param_changed(e, p, text))
                params_layout.addRow(param_name.replace("_", " ").title() + ":", line_edit)
                
        return params_widget
        
    def _show_add_effect_menu(self):
        """Show menu to add a new effect"""
        menu = QMenu(self)
        
        effects = [
            ("🎨 Color Correction", "color_correction"),
            ("🌫️ Blur", "blur"),
            ("🌑 Shadow", "shadow"),
            ("✨ Glow", "glow"),
            ("⬆️ Fade", "fade"),
            ("✂️ Crop", "crop"),
            ("🎭 Mask", "mask"),
        ]
        
        for name, effect_type in effects:
            action = menu.addAction(name)
            action.triggered.connect(lambda checked, t=effect_type: self._on_add_effect(t))
            
        menu.exec_(self.add_effect_btn.mapToGlobal(self.add_effect_btn.rect().bottomLeft()))
        
    # === Event handlers ===
    
    def _on_name_changed(self, name: str):
        if self._updating or not self._layer:
            return
        self._layer.name = name
        self.layer_changed.emit(self._layer.id)
        
    def _on_opacity_changed(self, value: int):
        if self._updating or not self._layer:
            return
        self._layer.opacity = value / 100.0
        self.opacity_label.setText(f"{value}%")
        self.layer_changed.emit(self._layer.id)
        
    def _on_blend_changed(self, index: int):
        if self._updating or not self._layer:
            return
        self._layer.blend_mode = self.blend_combo.currentData()
        self.layer_changed.emit(self._layer.id)
        
    def _on_transform_changed(self):
        if self._updating or not self._layer:
            return
            
        # Check if scale should be linked
        sender = self.sender()
        if sender in (self.scale_x_spin, self.scale_y_spin) and self.link_scale_btn.isChecked():
            if sender == self.scale_x_spin:
                self._updating = True
                self.scale_y_spin.setValue(self.scale_x_spin.value())
                self._updating = False
            else:
                self._updating = True
                self.scale_x_spin.setValue(self.scale_y_spin.value())
                self._updating = False
                
        self._layer.transform.position_x = self.pos_x_spin.value()
        self._layer.transform.position_y = self.pos_y_spin.value()
        self._layer.transform.scale_x = self.scale_x_spin.value()
        self._layer.transform.scale_y = self.scale_y_spin.value()
        self._layer.transform.rotation = self.rotation_spin.value()
        self.layer_changed.emit(self._layer.id)
        
    def _on_timing_changed(self):
        if self._updating or not self._layer:
            return
            
        start = self.start_spin.value()
        end = self.end_spin.value()
        
        # Ensure end > start
        if end <= start:
            self._updating = True
            self.end_spin.setValue(start + 0.1)
            end = start + 0.1
            self._updating = False
            
        self._layer.start_time = start
        self._layer.end_time = end
        self._update_duration_label()
        self.layer_changed.emit(self._layer.id)
        
    # Color layer handlers
    def _on_color_changed(self, color: str):
        if self._updating or not self._layer or not isinstance(self._layer, ColorLayer):
            return
        self._layer.color = color
        self.layer_changed.emit(self._layer.id)
        
    def _on_gradient_toggled(self, state: int):
        if self._updating or not self._layer or not isinstance(self._layer, ColorLayer):
            return
        self._layer.gradient_enabled = bool(state)
        self._update_type_specific(self._layer)  # Rebuild to show/hide gradient options
        self.layer_changed.emit(self._layer.id)
        
    def _on_gradient_color_changed(self, color: str):
        if self._updating or not self._layer or not isinstance(self._layer, ColorLayer):
            return
        self._layer.gradient_color = color
        self.layer_changed.emit(self._layer.id)
        
    def _on_gradient_direction_changed(self, value: float):
        if self._updating or not self._layer or not isinstance(self._layer, ColorLayer):
            return
        self._layer.gradient_direction = value
        self.layer_changed.emit(self._layer.id)
        
    # Video layer handlers
    def _on_browse_video(self):
        if not self._layer or not isinstance(self._layer, VideoLayer):
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Video", "",
            "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)"
        )
        if path:
            self._layer.source_path = path
            self.video_path_edit.setText(path)
            self.layer_changed.emit(self._layer.id)
            
    def _on_loop_toggled(self, state: int):
        if self._updating or not self._layer or not isinstance(self._layer, VideoLayer):
            return
        self._layer.loop = bool(state)
        self.layer_changed.emit(self._layer.id)
        
    def _on_mute_toggled(self, state: int):
        if self._updating or not self._layer or not isinstance(self._layer, VideoLayer):
            return
        self._layer.mute = bool(state)
        self.layer_changed.emit(self._layer.id)
        
    def _on_volume_changed(self, value: int):
        if self._updating or not self._layer or not isinstance(self._layer, VideoLayer):
            return
        self._layer.volume = value / 100.0
        self.volume_label.setText(f"{value}%")
        self.layer_changed.emit(self._layer.id)
        
    # Image layer handlers
    def _on_browse_image(self):
        if not self._layer or not isinstance(self._layer, ImageLayer):
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)"
        )
        if path:
            self._layer.source_path = path
            self.image_path_edit.setText(path)
            self.layer_changed.emit(self._layer.id)
            
    def _on_fit_mode_changed(self, text: str):
        if self._updating or not self._layer or not isinstance(self._layer, ImageLayer):
            return
        self._layer.fit_mode = text.lower()
        self.layer_changed.emit(self._layer.id)
        
    # Text layer handlers
    def _on_text_changed(self, text: str):
        if self._updating or not self._layer or not isinstance(self._layer, TextLayer):
            return
        self._layer.text = text
        self.layer_changed.emit(self._layer.id)
        
    def _on_font_changed(self, font: str):
        if self._updating or not self._layer or not isinstance(self._layer, TextLayer):
            return
        self._layer.font_family = font
        self.layer_changed.emit(self._layer.id)
        
    def _on_font_size_changed(self, size: int):
        if self._updating or not self._layer or not isinstance(self._layer, TextLayer):
            return
        self._layer.font_size = size
        self.layer_changed.emit(self._layer.id)
        
    def _on_bold_toggled(self, state: int):
        if self._updating or not self._layer or not isinstance(self._layer, TextLayer):
            return
        self._layer.font_weight = "bold" if state else "normal"
        self.layer_changed.emit(self._layer.id)
        
    def _on_italic_toggled(self, state: int):
        if self._updating or not self._layer or not isinstance(self._layer, TextLayer):
            return
        self._layer.font_style = "italic" if state else "normal"
        self.layer_changed.emit(self._layer.id)
        
    def _on_text_color_changed(self, color: str):
        if self._updating or not self._layer or not isinstance(self._layer, TextLayer):
            return
        self._layer.color = color
        self.layer_changed.emit(self._layer.id)
        
    def _on_alignment_changed(self, text: str):
        if self._updating or not self._layer or not isinstance(self._layer, TextLayer):
            return
        self._layer.alignment = text.lower()
        self.layer_changed.emit(self._layer.id)
        
    # Shape layer handlers
    def _on_shape_type_changed(self, text: str):
        if self._updating or not self._layer or not isinstance(self._layer, ShapeLayer):
            return
        self._layer.shape_type = text.lower()
        self._update_type_specific(self._layer)  # Rebuild for corner radius option
        self.layer_changed.emit(self._layer.id)
        
    def _on_shape_size_changed(self):
        if self._updating or not self._layer or not isinstance(self._layer, ShapeLayer):
            return
        self._layer.width = self.shape_width_spin.value()
        self._layer.height = self.shape_height_spin.value()
        self.layer_changed.emit(self._layer.id)
        
    def _on_fill_toggled(self, state: int):
        if self._updating or not self._layer or not isinstance(self._layer, ShapeLayer):
            return
        self._layer.fill_enabled = bool(state)
        self.layer_changed.emit(self._layer.id)
        
    def _on_fill_color_changed(self, color: str):
        if self._updating or not self._layer or not isinstance(self._layer, ShapeLayer):
            return
        self._layer.fill_color = color
        self.layer_changed.emit(self._layer.id)
        
    def _on_stroke_toggled(self, state: int):
        if self._updating or not self._layer or not isinstance(self._layer, ShapeLayer):
            return
        self._layer.stroke_enabled = bool(state)
        self.layer_changed.emit(self._layer.id)
        
    def _on_stroke_color_changed(self, color: str):
        if self._updating or not self._layer or not isinstance(self._layer, ShapeLayer):
            return
        self._layer.stroke_color = color
        self.layer_changed.emit(self._layer.id)
        
    def _on_stroke_width_changed(self, value: float):
        if self._updating or not self._layer or not isinstance(self._layer, ShapeLayer):
            return
        self._layer.stroke_width = value
        self.layer_changed.emit(self._layer.id)
        
    def _on_corner_radius_changed(self, value: float):
        if self._updating or not self._layer or not isinstance(self._layer, ShapeLayer):
            return
        self._layer.corner_radius = value
        self.layer_changed.emit(self._layer.id)
        
    # Effect handlers
    def _on_add_effect(self, effect_type: str):
        if not self._layer:
            return
        self._layer.add_effect(effect_type)
        self._update_effects_list()
        self.effect_added.emit(self._layer.id, effect_type)
        self.layer_changed.emit(self._layer.id)
        
    def _on_remove_effect(self, effect: Effect):
        if not self._layer:
            return
        self._layer.remove_effect(effect.id)
        self._update_effects_list()
        self.effect_removed.emit(self._layer.id, effect.id)
        self.layer_changed.emit(self._layer.id)
        
    def _on_effect_enabled(self, effect: Effect, state: int):
        effect.enabled = bool(state)
        self.layer_changed.emit(self._layer.id)
        
    def _on_effect_param_changed(self, effect: Effect, param_name: str, value):
        effect.parameters[param_name] = value
        self.layer_changed.emit(self._layer.id)
