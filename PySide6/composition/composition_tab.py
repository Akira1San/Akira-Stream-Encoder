"""
Composition Tab - Main tab for the composition-based video editor

This tab provides a complete interface for creating video compositions
with layers, effects, and timeline.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QFrame, QFileDialog, QSizePolicy,
    QProgressDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal

from models import AppState
from composition.models import (
    Composition, Layer, ColorLayer, VideoLayer, ImageLayer, 
    TextLayer, ShapeLayer, create_layer
)
from composition.layer_stack import LayerStackWidget
from composition.properties_panel import PropertiesPanel
from composition.timeline import CompositionTimeline
from composition.preview import CompositionPreview
from composition.renderer import CompositionRenderer, RenderSettings, RenderDialog


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
        
        # Renderer
        self._renderer = CompositionRenderer(self)
        self._progress_dialog = None
        
        self._setup_ui()
        self._connect_signals()
        self._connect_renderer_signals()
        
        # Initialize preview and timeline with the default composition
        self.preview.set_composition(self.composition)
        self.timeline.set_composition(self.composition)
        
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
        self.preview = CompositionPreview()
        top_splitter.addWidget(self.preview)
        
        # Properties Panel
        self.properties = PropertiesPanel()
        top_splitter.addWidget(self.properties)
        
        # Set initial sizes
        top_splitter.setSizes([200, 400, 200])
        
        main_splitter.addWidget(top_splitter)
        
        # === Timeline Section ===
        self.timeline = CompositionTimeline()
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
        
        # Properties panel signals
        self.properties.layer_changed.connect(self._on_layer_changed)
        self.properties.effect_added.connect(self._on_effect_added)
        self.properties.effect_removed.connect(self._on_effect_removed)
        
        # Timeline signals
        self.timeline.layer_selected.connect(self._on_layer_selected)
        self.timeline.layer_timing_changed.connect(self._on_layer_timing_changed)
        self.timeline.time_changed.connect(self._on_time_changed)
        
        # Preview signals
        self.preview.time_changed.connect(self._on_preview_time_changed)
        
    def _connect_renderer_signals(self):
        """Connect renderer signals"""
        self._renderer.render_started.connect(self._on_render_started)
        self._renderer.render_progress.connect(self._on_render_progress)
        self._renderer.render_completed.connect(self._on_render_completed)
        self._renderer.render_error.connect(self._on_render_error)
        
    def _on_new_composition(self):
        """Create new composition"""
        self.composition = Composition()
        self.layer_stack.set_layers(self.composition.layers)
        self.timeline.set_composition(self.composition)
        self.preview.set_composition(self.composition)
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
                self.timeline.set_composition(self.composition)
                self.preview.set_composition(self.composition)
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
        if self._renderer.is_rendering():
            QMessageBox.warning(
                self,
                "Rendering in Progress",
                "A render is already in progress. Please wait or cancel it."
            )
            return
        
        # Check if composition has any layers
        if not self.composition.layers:
            QMessageBox.warning(
                self,
                "Empty Composition",
                "Cannot render an empty composition. Please add some layers first."
            )
            return
        
        # Show render settings dialog
        settings = RenderDialog.get_render_settings(self.composition, self)
        if settings:
            self._renderer.render(self.composition, settings)
            
    def _on_render_started(self):
        """Handle render started"""
        self.app_state.log("Rendering started...", "INFO")
        
        # Create progress dialog
        self._progress_dialog = QProgressDialog(
            "Rendering composition...",
            "Cancel",
            0, 100,
            self
        )
        self._progress_dialog.setWindowTitle("Rendering")
        self._progress_dialog.setWindowModality(Qt.WindowModal)
        self._progress_dialog.setAutoClose(False)
        self._progress_dialog.setAutoReset(False)
        self._progress_dialog.canceled.connect(self._on_render_cancelled)
        self._progress_dialog.show()
        
    def _on_render_progress(self, frame: int, total_frames: int, time: float):
        """Handle render progress update"""
        if self._progress_dialog:
            progress = int((frame / total_frames) * 100) if total_frames > 0 else 0
            self._progress_dialog.setValue(progress)
            self._progress_dialog.setLabelText(
                f"Rendering frame {frame}/{total_frames}\n"
                f"Time: {time:.2f}s"
            )
            
    def _on_render_completed(self, success: bool, message: str):
        """Handle render completion"""
        if self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None
            
        if success:
            self.app_state.log(f"Render completed: {message}", "INFO")
            QMessageBox.information(
                self,
                "Render Complete",
                message
            )
        else:
            self.app_state.log(f"Render failed: {message}", "ERROR")
            QMessageBox.warning(
                self,
                "Render Failed",
                message
            )
            
    def _on_render_error(self, error_message: str):
        """Handle render error"""
        self.app_state.log(f"Render error: {error_message}", "ERROR")
        if self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None
        QMessageBox.critical(
            self,
            "Render Error",
            f"An error occurred during rendering:\n{error_message}"
        )
        
    def _on_render_cancelled(self):
        """Handle render cancellation by user"""
        if self._renderer.is_rendering():
            self._renderer.cancel()
            self.app_state.log("Render cancelled by user", "WARN")
        
    def _on_layer_selected(self, layer_id: str):
        """Handle layer selection"""
        layer = self.composition.get_layer(layer_id)
        if layer:
            self.app_state.log(f"Selected layer: {layer.name}", "INFO")
            # Update properties panel
            self.properties.set_layer(layer)
        else:
            self.properties.set_layer(None)
            
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
        self.timeline.add_layer(layer)
        
        # Select the new layer
        self.layer_stack.select_layer(layer.id)
        
        # Update preview
        self.preview.request_update()
        
        self.composition_changed.emit()
        self.app_state.log(f"Added {layer_type} layer: {layer.name}", "INFO")
        
    def _on_remove_layer(self, layer_id: str):
        """Remove a layer"""
        layer = self.composition.get_layer(layer_id)
        if layer:
            self.composition.remove_layer(layer_id)
            self.layer_stack.remove_layer(layer_id)
            self.timeline.remove_layer(layer_id)
            # Update preview
            self.preview.request_update()
            self.composition_changed.emit()
            self.app_state.log(f"Removed layer: {layer.name}", "INFO")
            
    def _on_move_layer(self, layer_id: str, new_index: int):
        """Move a layer to a new position"""
        self.composition.move_layer(layer_id, new_index)
        # Refresh the layer stack to show new order
        self.layer_stack.set_layers(self.composition.layers)
        # Refresh timeline
        self.timeline.set_composition(self.composition)
        # Re-select the moved layer
        self.layer_stack.select_layer(layer_id)
        self.composition_changed.emit()
        self.app_state.log(f"Moved layer to position {new_index}", "INFO")
        
    def _on_layer_visibility_changed(self, layer_id: str, visible: bool):
        """Handle layer visibility change"""
        layer = self.composition.get_layer(layer_id)
        if layer:
            layer.enabled = visible
            # Update preview
            self.preview.request_update()
            self.composition_changed.emit()
            
    def _on_layer_changed(self, layer_id: str):
        """Handle layer property change from properties panel"""
        layer = self.composition.get_layer(layer_id)
        if layer:
            # Update layer stack to reflect name changes
            self.layer_stack.update_layer(layer)
            # Update timeline to reflect timing changes
            self.timeline.update_layer(layer)
            # Update preview
            self.preview.request_update()
            self.composition_changed.emit()
            
    def _on_layer_timing_changed(self, layer_id: str, start: float, end: float):
        """Handle layer timing change from timeline"""
        layer = self.composition.get_layer(layer_id)
        if layer:
            # Update properties panel to show new timing
            self.properties.set_layer(layer)
            self.composition_changed.emit()
            self.app_state.log(f"Updated layer timing: {layer.name}", "INFO")
            
    def _on_time_changed(self, time: float):
        """Handle playhead time change from timeline"""
        # Update preview to match timeline playhead
        self.preview.set_time(time)
        
    def _on_preview_time_changed(self, time: float):
        """Handle time change from preview playback"""
        # Update timeline playhead to match preview
        self.timeline.set_time(time)
            
    def _on_effect_added(self, layer_id: str, effect_type: str):
        """Handle effect added"""
        self.app_state.log(f"Added {effect_type} effect to layer", "INFO")
        self.composition_changed.emit()
        
    def _on_effect_removed(self, layer_id: str, effect_id: str):
        """Handle effect removed"""
        self.app_state.log("Removed effect from layer", "INFO")
        self.composition_changed.emit()
