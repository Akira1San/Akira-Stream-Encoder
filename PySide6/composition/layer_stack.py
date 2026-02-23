"""
Layer Stack Widget - Displays layers in a stack with drag-to-reorder

This widget shows all layers in a composition, from bottom to top,
with controls for visibility, locking, and reordering.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QMenu, QToolButton, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QMimeData, QPoint
from PySide6.QtGui import QDrag, QDropEvent, QDragEnterEvent, QPainter, QColor, QPen

from composition.models import Layer, ColorLayer, VideoLayer, ImageLayer, TextLayer, ShapeLayer


# Layer type icons (using Unicode symbols for simplicity)
LAYER_ICONS = {
    'color': '🎨',
    'video': '🎬',
    'image': '🖼️',
    'text': '📝',
    'shape': '⬛',
    'audio': '🔊',
    'base': '📄',
}


class LayerItemWidget(QFrame):
    """
    Widget representing a single layer in the stack.
    
    Displays: [Icon] [Name] [Visibility] [Lock] [Effects count]
    """
    
    # Signals
    selected = Signal(str)  # layer_id
    visibility_toggled = Signal(str, bool)  # layer_id, visible
    lock_toggled = Signal(str, bool)  # layer_id, locked
    delete_requested = Signal(str)  # layer_id
    duplicate_requested = Signal(str)  # layer_id
    
    def __init__(self, layer: Layer, parent=None):
        super().__init__(parent)
        self.layer = layer
        self._selected = False
        self._drag_start_pos = None
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the layer item UI"""
        self.setFixedHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)
        
        # Drag handle
        self.drag_handle = QLabel("☰")
        self.drag_handle.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.drag_handle)
        
        # Layer icon
        icon = LAYER_ICONS.get(self.layer.layer_type, '📄')
        self.icon_label = QLabel(icon)
        self.icon_label.setFixedWidth(20)
        layout.addWidget(self.icon_label)
        
        # Layer name
        self.name_label = QLabel(self.layer.name)
        self.name_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.name_label, 1)
        
        # Effects indicator
        effects_count = len(self.layer.effects)
        if effects_count > 0:
            self.effects_label = QLabel(f"✨{effects_count}")
            self.effects_label.setStyleSheet("color: #888; font-size: 10px;")
            layout.addWidget(self.effects_label)
        
        # Visibility button
        self.visible_btn = QToolButton()
        self.visible_btn.setFixedSize(24, 24)
        self.visible_btn.setText("👁" if self.layer.enabled else "👁‍🗨")
        self.visible_btn.setToolTip("Toggle visibility")
        self.visible_btn.clicked.connect(self._on_visibility_toggle)
        layout.addWidget(self.visible_btn)
        
        # Lock button
        self.lock_btn = QToolButton()
        self.lock_btn.setFixedSize(24, 24)
        self.lock_btn.setText("🔒" if self.layer.locked else "🔓")
        self.lock_btn.setToolTip("Toggle lock")
        self.lock_btn.clicked.connect(self._on_lock_toggle)
        layout.addWidget(self.lock_btn)
        
        self._update_style()
        
    def _update_style(self):
        """Update widget style based on selection state"""
        if self._selected:
            self.setStyleSheet("""
                LayerItemWidget {
                    background-color: #3498db;
                    border: 1px solid #2980b9;
                    border-radius: 3px;
                }
                QLabel { color: white; }
            """)
        else:
            self.setStyleSheet("""
                LayerItemWidget {
                    background-color: #2a2a2a;
                    border: 1px solid #3d3d3d;
                    border-radius: 3px;
                }
                LayerItemWidget:hover {
                    background-color: #333;
                }
                QLabel { color: #ddd; }
            """)
            
    def set_selected(self, selected: bool):
        """Set selection state"""
        self._selected = selected
        self._update_style()
        
    def is_selected(self) -> bool:
        """Check if selected"""
        return self._selected
        
    def _on_visibility_toggle(self):
        """Handle visibility toggle"""
        self.layer.enabled = not self.layer.enabled
        self.visible_btn.setText("👁" if self.layer.enabled else "👁‍🗨")
        self.visibility_toggled.emit(self.layer.id, self.layer.enabled)
        
    def _on_lock_toggle(self):
        """Handle lock toggle"""
        self.layer.locked = not self.layer.locked
        self.lock_btn.setText("🔒" if self.layer.locked else "🔓")
        self.lock_toggled.emit(self.layer.id, self.layer.locked)
        
    def mousePressEvent(self, event):
        """Handle mouse press for selection and drag"""
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
            self.selected.emit(self.layer.id)
        elif event.button() == Qt.RightButton:
            self._show_context_menu(event.pos())
            
    def mouseReleaseEvent(self, event):
        """Handle mouse release - reset drag state"""
        self._drag_start_pos = None
            
    def mouseMoveEvent(self, event):
        """Handle drag start"""
        if self._drag_start_pos is None:
            return
            
        distance = (event.pos() - self._drag_start_pos).manhattanLength()
        if distance < 10:
            return
            
        # Start drag
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setData("application/x-layer-id", self.layer.id.encode())
        mime_data.setText(self.layer.id)
        drag.setMimeData(mime_data)
        
        # Reset drag start position
        self._drag_start_pos = None
        
        # Execute drag
        result = drag.exec_(Qt.MoveAction)
        
    def _show_context_menu(self, pos):
        """Show context menu"""
        menu = QMenu(self)
        
        duplicate_action = menu.addAction("Duplicate Layer")
        duplicate_action.triggered.connect(lambda: self.duplicate_requested.emit(self.layer.id))
        
        delete_action = menu.addAction("Delete Layer")
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self.layer.id))
        
        menu.addSeparator()
        
        # Layer-specific actions
        if isinstance(self.layer, (VideoLayer, ImageLayer)):
            fit_menu = menu.addMenu("Fit Mode")
            for mode in ["fill", "fit", "stretch", "none"]:
                action = fit_menu.addAction(mode.capitalize())
                action.triggered.connect(lambda checked, m=mode: self._set_fit_mode(m))
        
        menu.exec_(self.mapToGlobal(pos))
        
    def _set_fit_mode(self, mode: str):
        """Set fit mode for image/video layers"""
        if isinstance(self.layer, (VideoLayer, ImageLayer)):
            self.layer.fit_mode = mode
            
    def update_from_layer(self):
        """Update UI from layer state"""
        self.name_label.setText(self.layer.name)
        self.visible_btn.setText("👁" if self.layer.enabled else "👁‍🗨")
        self.lock_btn.setText("🔒" if self.layer.locked else "🔓")


class LayerStackWidget(QWidget):
    """
    Widget displaying the stack of layers in a composition.
    
    Layers are displayed bottom-to-top (first layer at bottom).
    Supports drag-to-reorder, selection, and context menus.
    """
    
    # Signals
    layer_selected = Signal(str)  # layer_id
    layer_added = Signal(str)  # layer_type
    layer_removed = Signal(str)  # layer_id
    layer_moved = Signal(str, int)  # layer_id, new_index
    layer_visibility_changed = Signal(str, bool)  # layer_id, visible
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._layer_widgets = {}  # layer_id -> LayerItemWidget
        self._selected_layer_id = None
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the layer stack UI"""
        self.setMinimumWidth(200)
        self.setMaximumWidth(300)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Header
        header_layout = QHBoxLayout()
        
        header = QLabel("Layers")
        header.setStyleSheet("font-weight: bold; font-size: 14px; color: #ddd;")
        header_layout.addWidget(header)
        
        header_layout.addStretch()
        
        # Add layer button with menu
        self.add_btn = QPushButton("➕")
        self.add_btn.setFixedSize(28, 28)
        self.add_btn.setToolTip("Add Layer")
        self.add_btn.clicked.connect(self._show_add_menu)
        header_layout.addWidget(self.add_btn)
        
        main_layout.addLayout(header_layout)
        
        # Scrollable layer list
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
        
        # Layer container
        self.layer_container = QWidget()
        self.layer_layout = QVBoxLayout(self.layer_container)
        self.layer_layout.setContentsMargins(0, 0, 0, 0)
        self.layer_layout.setSpacing(2)
        self.layer_layout.addStretch()
        
        scroll.setWidget(self.layer_container)
        main_layout.addWidget(scroll, 1)
        
        # Store scroll reference for coordinate mapping
        self._scroll = scroll
        
        # Enable drop for reordering on both the container and this widget
        self.setAcceptDrops(True)
        self.layer_container.setAcceptDrops(True)
        
    def _show_add_menu(self):
        """Show menu to add new layer"""
        menu = QMenu(self)
        
        color_action = menu.addAction(f"{LAYER_ICONS['color']} Color Layer")
        color_action.triggered.connect(lambda: self.layer_added.emit('color'))
        
        video_action = menu.addAction(f"{LAYER_ICONS['video']} Video Layer")
        video_action.triggered.connect(lambda: self.layer_added.emit('video'))
        
        image_action = menu.addAction(f"{LAYER_ICONS['image']} Image Layer")
        image_action.triggered.connect(lambda: self.layer_added.emit('image'))
        
        text_action = menu.addAction(f"{LAYER_ICONS['text']} Text Layer")
        text_action.triggered.connect(lambda: self.layer_added.emit('text'))
        
        shape_action = menu.addAction(f"{LAYER_ICONS['shape']} Shape Layer")
        shape_action.triggered.connect(lambda: self.layer_added.emit('shape'))
        
        menu.exec_(self.add_btn.mapToGlobal(QPoint(0, self.add_btn.height())))
        
    def set_layers(self, layers: list):
        """Set the layers to display (bottom to top order)"""
        # Clear existing widgets
        self._clear_layers()
        
        # Add widgets for each layer (in reverse order so top layer is at top of list)
        for layer in reversed(layers):
            self._add_layer_widget(layer)
            
    def _clear_layers(self):
        """Clear all layer widgets"""
        for widget in self._layer_widgets.values():
            widget.deleteLater()
        self._layer_widgets.clear()
        self._selected_layer_id = None
        
    def _add_layer_widget(self, layer: Layer):
        """Add a widget for a layer"""
        widget = LayerItemWidget(layer, self)
        widget.selected.connect(self._on_layer_selected)
        widget.visibility_toggled.connect(self._on_visibility_toggled)
        widget.lock_toggled.connect(self._on_lock_toggled)
        widget.delete_requested.connect(self._on_delete_requested)
        widget.duplicate_requested.connect(self._on_duplicate_requested)
        
        # Insert before stretch
        self.layer_layout.insertWidget(0, widget)
        self._layer_widgets[layer.id] = widget
        
    def add_layer(self, layer: Layer):
        """Add a new layer to the top of the stack"""
        self._add_layer_widget(layer)
        
    def remove_layer(self, layer_id: str):
        """Remove a layer widget"""
        if layer_id in self._layer_widgets:
            widget = self._layer_widgets.pop(layer_id)
            self.layer_layout.removeWidget(widget)
            widget.deleteLater()
            
            if self._selected_layer_id == layer_id:
                self._selected_layer_id = None
                
    def move_layer(self, layer_id: str, new_index: int):
        """Move a layer to a new position"""
        if layer_id not in self._layer_widgets:
            return
            
        widget = self._layer_widgets[layer_id]
        
        # Remove and re-insert at new position
        self.layer_layout.removeWidget(widget)
        self.layer_layout.insertWidget(new_index, widget)
        
    def select_layer(self, layer_id: str):
        """Select a layer by ID"""
        # Deselect previous
        if self._selected_layer_id and self._selected_layer_id in self._layer_widgets:
            self._layer_widgets[self._selected_layer_id].set_selected(False)
            
        # Select new
        self._selected_layer_id = layer_id
        if layer_id and layer_id in self._layer_widgets:
            self._layer_widgets[layer_id].set_selected(True)
            
    def get_selected_layer_id(self) -> str:
        """Get the currently selected layer ID"""
        return self._selected_layer_id
        
    def _on_layer_selected(self, layer_id: str):
        """Handle layer selection"""
        self.select_layer(layer_id)
        self.layer_selected.emit(layer_id)
        
    def _on_visibility_toggled(self, layer_id: str, visible: bool):
        """Handle visibility toggle"""
        self.layer_visibility_changed.emit(layer_id, visible)
        
    def _on_lock_toggled(self, layer_id: str, locked: bool):
        """Handle lock toggle"""
        pass  # Just update the layer model
        
    def _on_delete_requested(self, layer_id: str):
        """Handle delete request"""
        self.layer_removed.emit(layer_id)
        
    def _on_duplicate_requested(self, layer_id: str):
        """Handle duplicate request"""
        # This will be handled by the parent tab
        pass
        
    # Drag and drop for reordering
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter"""
        if event.mimeData().hasFormat("application/x-layer-id"):
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dragMoveEvent(self, event):
        """Handle drag move - provide visual feedback"""
        if event.mimeData().hasFormat("application/x-layer-id"):
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dropEvent(self, event: QDropEvent):
        """Handle drop for layer reordering"""
        if not event.mimeData().hasFormat("application/x-layer-id"):
            event.ignore()
            return
            
        layer_id = bytes(event.mimeData().data("application/x-layer-id")).decode('utf-8')
        
        # Get drop position in layer container coordinates
        drop_pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
        
        # Map to layer container coordinates
        drop_pos_in_container = self.layer_container.mapFromGlobal(self.mapToGlobal(drop_pos))
        
        # Count actual layer widgets (excluding stretch)
        layer_count = sum(1 for i in range(self.layer_layout.count()) 
                         if self.layer_layout.itemAt(i) and self.layer_layout.itemAt(i).widget())
        
        # Find the widget under the drop position
        ui_index = 0
        found = False
        
        for i in range(self.layer_layout.count()):
            item = self.layer_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                widget_rect = widget.geometry()
                
                if widget_rect.contains(drop_pos_in_container):
                    # Calculate if dropping above or below
                    if drop_pos_in_container.y() < widget_rect.center().y():
                        ui_index = i
                    else:
                        ui_index = i + 1
                    found = True
                    break
        
        # If not found over a widget, determine position based on Y coordinate
        if not found:
            # Find closest position
            for i in range(self.layer_layout.count()):
                item = self.layer_layout.itemAt(i)
                if item and item.widget():
                    widget = item.widget()
                    if drop_pos_in_container.y() < widget.geometry().top():
                        ui_index = i
                        found = True
                        break
            
            if not found:
                # Drop at the end
                ui_index = layer_count
        
        # Clamp index to valid range
        ui_index = max(0, min(ui_index, layer_count))
        
        # Convert UI index to composition index
        # UI displays layers reversed (top layer at index 0)
        # Composition stores layers bottom-to-top (bottom layer at index 0)
        # So: composition_index = layer_count - ui_index
        composition_index = layer_count - ui_index
        
        self.layer_moved.emit(layer_id, composition_index)
        event.acceptProposedAction()
        
    def update_layer(self, layer: Layer):
        """Update a layer widget"""
        if layer.id in self._layer_widgets:
            self._layer_widgets[layer.id].update_from_layer()
