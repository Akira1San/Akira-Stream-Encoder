"""
Composition Tab - Main tab for the composition-based video editor

This tab provides a complete interface for creating video compositions
with layers, effects, and timeline.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QFrame, QFileDialog, QSizePolicy
)
from PySide6.QtCore import Qt, Signal

from models import AppState
from composition.models import (
    Composition, Layer, ColorLayer, VideoLayer, ImageLayer, 
    TextLayer, ShapeLayer, create_layer
)
from composition.layer_stack import LayerStackWidget


class PreviewPlaceholder(QFrame):
    """Placeholder for composition preview"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 180)
        self.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        label = QLabel("Preview\n\nAdd layers to see preview")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #666;")
        layout.addWidget(label)


class PropertiesPlaceholder(QFrame):
    """Placeholder for properties panel"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
        
        header = QLabel("Properties")
        header.setStyleSheet("font-weight: bold; font-size: 14px; color: #ddd; padding: 10px;")
        layout.addWidget(header)
        
        self.content = QLabel("Select a layer to edit")
        self.content.setAlignment(Qt.AlignCenter)
        self.content.setStyleSheet("color: #666; padding: 20px;")
        layout.addWidget(self.content, 1)


class TimelinePlaceholder(QFrame):
    """Placeholder for timeline"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(100)
        self.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        label = QLabel("Timeline\n\nLayer duration bars will appear here")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #666;")
        layout.addWidget(label)


class CompositionTab(QWidget):
    """
    Main Composition Editor Tab
    
    Layout:
    ┌──────────────┬──────────────────────┬───────────────┐
    │ Layer Stack  │      Preview         │  Properties   │
    │ (left)       │    (center)          │   (right)     │
    ├──────────────┴──────────────────────┴───────────────┤
    │                    Timeline                          │
    └─────────────────────────────────────────────────────┘
    """
    
    # Signals
    composition_changed = Signal()
    
    def __init__(self, app_state: AppState, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.composition = Composition()
        
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """Setup the main UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # === Toolbar ===
        toolbar = self._create_toolbar()
        main_layout.addWidget(toolbar)
        
        # === Main Content Area ===
        main_splitter = QSplitter(Qt.Vertical)
        
        # Top section: Layer Stack | Preview | Properties
        top_splitter = QSplitter(Qt.Horizontal)
        
        # Layer Stack
        self.layer_stack = LayerStackWidget()
        top_splitter.addWidget(self.layer_stack)
        
        # Preview
        self.preview = PreviewPlaceholder()
        top_splitter.addWidget(self.preview)
        
        # Properties
        self.properties = PropertiesPlaceholder()
        top_splitter.addWidget(self.properties)
        
        # Set initial sizes
        top_splitter.setSizes([200, 400, 200])
        
        main_splitter.addWidget(top_splitter)
        
        # === Timeline Section ===
        self.timeline = TimelinePlaceholder()
        main_splitter.addWidget(self.timeline)
        
        main_splitter.setSizes([400, 150])
        
        main_layout.addWidget(main_splitter)
        
    def _create_toolbar(self) -> QWidget:
        """Create the toolbar"""
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
        """)
        
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Composition actions
        new_btn = QPushButton("📄 New")
        new_btn.setToolTip("New Composition")
        new_btn.clicked.connect(self._on_new_composition)
        layout.addWidget(new_btn)
        
        open_btn = QPushButton("📂 Open")
        open_btn.setToolTip("Open Composition")
        open_btn.clicked.connect(self._on_open_composition)
        layout.addWidget(open_btn)
        
        save_btn = QPushButton("💾 Save")
        save_btn.setToolTip("Save Composition")
        save_btn.clicked.connect(self._on_save_composition)
        layout.addWidget(save_btn)
        
        layout.addSpacing(20)
        
        # Composition settings
        settings_btn = QPushButton("⚙️ Settings")
        settings_btn.setToolTip("Composition settings (resolution, fps, duration)")
        settings_btn.clicked.connect(self._on_settings)
        layout.addWidget(settings_btn)
        
        layout.addStretch()
        
        # Render action
        render_btn = QPushButton("▶️ Render")
        render_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        render_btn.setToolTip("Render composition to video")
        render_btn.clicked.connect(self._on_render)
        layout.addWidget(render_btn)
        
        return toolbar
        
    def _connect_signals(self):
        """Connect internal signals"""
        # Layer stack signals
        self.layer_stack.layer_selected.connect(self._on_layer_selected)
        self.layer_stack.layer_added.connect(self._on_add_layer)
        self.layer_stack.layer_removed.connect(self._on_remove_layer)
        self.layer_stack.layer_moved.connect(self._on_move_layer)
        self.layer_stack.layer_visibility_changed.connect(self._on_layer_visibility_changed)
        
    def _on_new_composition(self):
        """Create new composition"""
        self.composition = Composition()
        self.layer_stack.set_layers(self.composition.layers)
        self.composition_changed.emit()
        self.app_state.log("Created new composition", "INFO")
        
    def _on_open_composition(self):
        """Open composition from file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Composition",
            "",
            "Composition (*.comp.json);;All Files (*)"
        )
        if file_path:
            import json
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                self.composition = Composition.from_dict(data)
                self.layer_stack.set_layers(self.composition.layers)
                self.composition_changed.emit()
                self.app_state.log(f"Opened composition: {file_path}", "INFO")
            except Exception as e:
                self.app_state.log(f"Failed to open: {e}", "ERROR")
                
    def _on_save_composition(self):
        """Save composition to file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Composition",
            f"{self.composition.name}.comp.json",
            "Composition (*.comp.json);;All Files (*)"
        )
        if file_path:
            import json
            try:
                with open(file_path, 'w') as f:
                    json.dump(self.composition.to_dict(), f, indent=2)
                self.app_state.log(f"Saved composition: {file_path}", "INFO")
            except Exception as e:
                self.app_state.log(f"Failed to save: {e}", "ERROR")
                
    def _on_settings(self):
        """Show composition settings dialog"""
        # TODO: Implement settings dialog
        self.app_state.log("Settings dialog not yet implemented", "INFO")
        
    def _on_render(self):
        """Render composition to video"""
        self.app_state.log("Rendering not yet implemented", "WARN")
        
    def _on_layer_selected(self, layer_id: str):
        """Handle layer selection"""
        layer = self.composition.get_layer(layer_id)
        if layer:
            self.app_state.log(f"Selected layer: {layer.name}", "INFO")
            # Update properties panel (future implementation)
            
    def _on_add_layer(self, layer_type: str):
        """Add a new layer"""
        # Create layer with default settings
        layer = create_layer(layer_type)
        
        # Set default timing
        layer.start_time = 0.0
        layer.end_time = self.composition.duration
        
        # Add to composition
        self.composition.add_layer(layer)
        
        # Add to UI
        self.layer_stack.add_layer(layer)
        
        # Select the new layer
        self.layer_stack.select_layer(layer.id)
        
        self.composition_changed.emit()
        self.app_state.log(f"Added {layer_type} layer: {layer.name}", "INFO")
        
    def _on_remove_layer(self, layer_id: str):
        """Remove a layer"""
        layer = self.composition.get_layer(layer_id)
        if layer:
            self.composition.remove_layer(layer_id)
            self.layer_stack.remove_layer(layer_id)
            self.composition_changed.emit()
            self.app_state.log(f"Removed layer: {layer.name}", "INFO")
            
    def _on_move_layer(self, layer_id: str, new_index: int):
        """Move a layer to a new position"""
        self.composition.move_layer(layer_id, new_index)
        self.composition_changed.emit()
        
    def _on_layer_visibility_changed(self, layer_id: str, visible: bool):
        """Handle layer visibility change"""
        layer = self.composition.get_layer(layer_id)
        if layer:
            layer.enabled = visible
            self.composition_changed.emit()
