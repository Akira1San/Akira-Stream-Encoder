"""
Timeline Widget - Visual timeline for composition layers

This widget displays a simplified timeline showing layer duration bars
with a draggable playhead and zoom controls.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSlider, QToolButton, QSizePolicy,
    QMenu
)
from PySide6.QtCore import Qt, Signal, QTimer, QRect, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QMouseEvent, QPolygon

from composition.models import Layer, Composition


# Layer colors for timeline bars
LAYER_COLORS = {
    'color': QColor(76, 175, 80),    # Green
    'video': QColor(33, 150, 243),   # Blue
    'image': QColor(156, 39, 176),   # Purple
    'text': QColor(255, 152, 0),     # Orange
    'shape': QColor(0, 188, 212),    # Cyan
    'audio': QColor(233, 30, 99),    # Pink
}


class TimeRuler(QWidget):
    """
    Time ruler widget showing time markers.
    """
    
    def __init__(self, duration: float = 30.0, pixels_per_second: float = 50.0, parent=None):
        super().__init__(parent)
        self.duration = duration
        self.pixels_per_second = pixels_per_second
        
        self.setFixedHeight(25)
        self.setMinimumWidth(int(duration * pixels_per_second))
        
    def set_duration(self, duration: float):
        """Set the total duration"""
        self.duration = duration
        self.setMinimumWidth(int(duration * self.pixels_per_second))
        self.update()
        
    def set_zoom(self, pixels_per_second: float):
        """Set zoom level"""
        self.pixels_per_second = pixels_per_second
        self.setMinimumWidth(int(self.duration * pixels_per_second))
        self.update()
        
    def paintEvent(self, event):
        """Draw time ruler"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), QColor(45, 45, 45))
        
        # Calculate time step based on zoom
        if self.pixels_per_second < 20:
            major_step = 10.0  # Every 10 seconds
            minor_step = 2.0   # Every 2 seconds
        elif self.pixels_per_second < 50:
            major_step = 5.0   # Every 5 seconds
            minor_step = 1.0   # Every 1 second
        elif self.pixels_per_second < 100:
            major_step = 2.0   # Every 2 seconds
            minor_step = 0.5   # Every 0.5 seconds
        else:
            major_step = 1.0   # Every 1 second
            minor_step = 0.25  # Every 0.25 seconds
        
        # Draw minor ticks
        painter.setPen(QPen(QColor(80, 80, 80), 1))
        t = 0
        while t <= self.duration:
            x = int(t * self.pixels_per_second)
            painter.drawLine(x, self.height() - 8, x, self.height())
            t += minor_step
        
        # Draw major ticks and labels
        painter.setPen(QPen(QColor(150, 150, 150), 1))
        painter.setFont(QFont("Arial", 8))
        
        t = 0
        while t <= self.duration:
            x = int(t * self.pixels_per_second)
            painter.drawLine(x, 0, x, self.height())
            
            # Time label
            minutes = int(t // 60)
            seconds = int(t % 60)
            frames = int((t % 1) * 30)  # Assuming 30 fps
            if minutes > 0:
                time_str = f"{minutes}:{seconds:02d}"
            else:
                time_str = f"{seconds}s"
            painter.drawText(x + 3, 12, time_str)
            
            t += major_step


class LayerBar(QFrame):
    """
    Visual representation of a layer's duration in the timeline.
    """
    
    # Signals
    timing_changed = Signal(str, float, float)  # layer_id, start_time, end_time
    selected = Signal(str)  # layer_id
    
    def __init__(self, layer: Layer, pixels_per_second: float = 50.0, parent=None):
        super().__init__(parent)
        self.layer = layer
        self.pixels_per_second = pixels_per_second
        self._dragging = None  # 'move', 'start', 'end'
        self._drag_start_pos = None
        self._original_start = None
        self._original_end = None
        
        self.setFixedHeight(30)
        self._update_geometry()
        self.setCursor(Qt.PointingHandCursor)
        
    def _update_geometry(self):
        """Update position and size based on layer timing"""
        x = int(self.layer.start_time * self.pixels_per_second)
        width = int(self.layer.duration * self.pixels_per_second)
        self.move(x, 0)
        self.setFixedWidth(max(width, 10))  # Minimum width of 10 pixels
        self._update_style()
        
    def _update_style(self):
        """Update visual style"""
        color = LAYER_COLORS.get(self.layer.layer_type, QColor(128, 128, 128))
        
        if self.layer.enabled:
            self.setStyleSheet(f"""
                LayerBar {{
                    background-color: {color.name()};
                    border: 1px solid {color.darker(120).name()};
                    border-radius: 3px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                LayerBar {{
                    background-color: {color.darker(150).name()};
                    border: 1px solid {color.darker(180).name()};
                    border-radius: 3px;
                }}
            """)
            
    def set_zoom(self, pixels_per_second: float):
        """Set zoom level"""
        self.pixels_per_second = pixels_per_second
        self._update_geometry()
        
    def update_from_layer(self):
        """Update from layer data"""
        self._update_geometry()
        
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press"""
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
            self._original_start = self.layer.start_time
            self._original_end = self.layer.end_time
            
            # Determine drag mode based on position
            width = self.width()
            if event.pos().x() < 10:
                self._dragging = 'start'
                self.setCursor(Qt.SizeHorCursor)
            elif event.pos().x() > width - 10:
                self._dragging = 'end'
                self.setCursor(Qt.SizeHorCursor)
            else:
                self._dragging = 'move'
                self.setCursor(Qt.SizeAllCursor)
                
            self.selected.emit(self.layer.id)
            
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for dragging"""
        if self._dragging is None or self._drag_start_pos is None:
            return
            
        # Calculate time delta
        dx = event.pos().x() - self._drag_start_pos.x()
        dt = dx / self.pixels_per_second
        
        if self._dragging == 'move':
            # Move entire layer
            new_start = max(0, self._original_start + dt)
            new_end = new_start + self.layer.duration
            self.layer.start_time = new_start
            self.layer.end_time = new_end
        elif self._dragging == 'start':
            # Adjust start time
            new_start = max(0, min(self._original_start + dt, self.layer.end_time - 0.1))
            self.layer.start_time = new_start
        elif self._dragging == 'end':
            # Adjust end time
            new_end = max(self.layer.start_time + 0.1, self._original_end + dt)
            self.layer.end_time = new_end
            
        self._update_geometry()
        
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release"""
        if self._dragging:
            self.timing_changed.emit(self.layer.id, self.layer.start_time, self.layer.end_time)
            self._dragging = None
            self._drag_start_pos = None
            self.setCursor(Qt.PointingHandCursor)


class Playhead(QWidget):
    """
    Draggable playhead indicator for the timeline.
    """
    
    position_changed = Signal(float)  # time in seconds
    
    def __init__(self, duration: float = 30.0, pixels_per_second: float = 50.0, parent=None):
        super().__init__(parent)
        self.duration = duration
        self.pixels_per_second = pixels_per_second
        self._position = 0.0  # Current time in seconds
        self._dragging = False
        
        self.setFixedHeight(200)  # Will be adjusted by parent
        self.setFixedWidth(12)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setCursor(Qt.SizeHorCursor)
        
    def set_position(self, time: float):
        """Set playhead position"""
        self._position = max(0, min(time, self.duration))
        self._update_position()
        
    def _update_position(self):
        """Update widget position"""
        x = int(self._position * self.pixels_per_second) - self.width() // 2
        self.move(x, 0)
        
    def set_duration(self, duration: float):
        """Set total duration"""
        self.duration = duration
        self._update_position()
        
    def set_zoom(self, pixels_per_second: float):
        """Set zoom level"""
        self.pixels_per_second = pixels_per_second
        self._update_position()
        
    def paintEvent(self, event):
        """Draw playhead"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw triangle at top
        painter.setBrush(QBrush(QColor(255, 87, 34)))  # Orange
        painter.setPen(Qt.NoPen)
        
        # Triangle pointing down
        polygon = QPolygon([
            QPoint(6, 0),    # Top center
            QPoint(0, 10),   # Left
            QPoint(12, 10),  # Right
        ])
        painter.drawPolygon(polygon)
        
        # Vertical line
        painter.setPen(QPen(QColor(255, 87, 34), 2))
        painter.drawLine(6, 10, 6, self.height())
        
        painter.end()
        
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press"""
        if event.button() == Qt.LeftButton:
            self._dragging = True
            
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move"""
        if self._dragging:
            # Calculate new position from global position
            parent = self.parentWidget()
            if parent:
                local_pos = parent.mapFromGlobal(self.mapToGlobal(event.pos()))
                new_time = local_pos.x() / self.pixels_per_second
                self.set_position(new_time)
                self.position_changed.emit(self._position)
                
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release"""
        self._dragging = False


class TimelineTrack(QWidget):
    """
    Single track row in the timeline containing a layer bar.
    """
    
    timing_changed = Signal(str, float, float)  # layer_id, start, end
    layer_selected = Signal(str)  # layer_id
    
    def __init__(self, layer: Layer, pixels_per_second: float = 50.0, parent=None):
        super().__init__(parent)
        self.layer = layer
        self.pixels_per_second = pixels_per_second
        
        self.setFixedHeight(35)
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup UI"""
        self.layer_bar = LayerBar(self.layer, self.pixels_per_second, self)
        self.layer_bar.timing_changed.connect(self.timing_changed.emit)
        self.layer_bar.selected.connect(self.layer_selected.emit)
        
    def set_zoom(self, pixels_per_second: float):
        """Set zoom level"""
        self.pixels_per_second = pixels_per_second
        self.layer_bar.set_zoom(pixels_per_second)
        
    def update_from_layer(self):
        """Update from layer data"""
        self.layer_bar.update_from_layer()


class CompositionTimeline(QWidget):
    """
    Main timeline widget for composition editing.
    
    Features:
    - Time ruler with markers
    - Layer duration bars (draggable)
    - Playhead (draggable)
    - Zoom controls
    """
    
    # Signals
    time_changed = Signal(float)  # Current time in seconds
    layer_timing_changed = Signal(str, float, float)  # layer_id, start, end
    layer_selected = Signal(str)  # layer_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._composition = None
        self._pixels_per_second = 50.0
        self._current_time = 0.0
        self._tracks = {}  # layer_id -> TimelineTrack
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup timeline UI"""
        self.setMinimumHeight(150)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(0)
        
        # === Header with controls ===
        header = QFrame()
        header.setStyleSheet("QFrame { background-color: #2d2d2d; border-radius: 3px; }")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(5, 5, 5, 5)
        
        # Time display
        self.time_label = QLabel("00:00:00")
        self.time_label.setStyleSheet("color: #ddd; font-family: monospace; font-size: 12px;")
        header_layout.addWidget(self.time_label)
        
        header_layout.addStretch()
        
        # Zoom controls
        zoom_out = QToolButton()
        zoom_out.setText("➖")
        zoom_out.setFixedSize(24, 24)
        zoom_out.clicked.connect(self._zoom_out)
        header_layout.addWidget(zoom_out)
        
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(10, 200)
        self.zoom_slider.setValue(50)
        self.zoom_slider.setFixedWidth(100)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        header_layout.addWidget(self.zoom_slider)
        
        zoom_in = QToolButton()
        zoom_in.setText("➕")
        zoom_in.setFixedSize(24, 24)
        zoom_in.clicked.connect(self._zoom_in)
        header_layout.addWidget(zoom_in)
        
        main_layout.addWidget(header)
        
        # === Timeline area ===
        timeline_container = QFrame()
        timeline_container.setStyleSheet("QFrame { background-color: #1e1e1e; border: 1px solid #3d3d3d; border-radius: 3px; }")
        timeline_layout = QVBoxLayout(timeline_container)
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        timeline_layout.setSpacing(0)
        
        # Scroll area for timeline
        scroll = QScrollArea()
        scroll.setWidgetResizable(False)  # Allow horizontal scroll
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        # Timeline content widget
        self.timeline_content = QWidget()
        self.timeline_layout = QVBoxLayout(self.timeline_content)
        self.timeline_layout.setContentsMargins(0, 0, 0, 0)
        self.timeline_layout.setSpacing(2)
        
        # Time ruler
        self.time_ruler = TimeRuler(30.0, self._pixels_per_second)
        self.timeline_layout.addWidget(self.time_ruler)
        
        # Tracks container
        self.tracks_container = QWidget()
        self.tracks_layout = QVBoxLayout(self.tracks_container)
        self.tracks_layout.setContentsMargins(0, 0, 0, 0)
        self.tracks_layout.setSpacing(2)
        self.tracks_layout.addStretch()
        self.timeline_layout.addWidget(self.tracks_container)
        
        scroll.setWidget(self.timeline_content)
        timeline_layout.addWidget(scroll)
        
        self._scroll = scroll
        main_layout.addWidget(timeline_container, 1)
        
        # Playhead (overlay)
        self.playhead = Playhead(30.0, self._pixels_per_second, self.timeline_content)
        self.playhead.position_changed.connect(self._on_playhead_moved)
        
    def set_composition(self, composition: Composition):
        """Set the composition to display"""
        self._composition = composition
        self._clear_tracks()
        
        if composition:
            # Update duration
            self.time_ruler.set_duration(composition.duration)
            self.playhead.set_duration(composition.duration)
            
            # Update minimum width
            min_width = int(composition.duration * self._pixels_per_second)
            self.timeline_content.setMinimumWidth(min_width)
            
            # Add tracks for each layer (in reverse order to match layer stack)
            for layer in reversed(composition.layers):
                self._add_track(layer)
                
            # Update playhead height
            self._update_playhead_height()
            
    def _clear_tracks(self):
        """Clear all tracks"""
        for track in self._tracks.values():
            track.deleteLater()
        self._tracks.clear()
        
    def _add_track(self, layer: Layer):
        """Add a track for a layer"""
        track = TimelineTrack(layer, self._pixels_per_second)
        track.timing_changed.connect(self._on_layer_timing_changed)
        track.layer_selected.connect(self.layer_selected.emit)
        
        # Insert before stretch
        self.tracks_layout.insertWidget(self.tracks_layout.count() - 1, track)
        self._tracks[layer.id] = track
        
    def _update_playhead_height(self):
        """Update playhead height to match content"""
        ruler_height = 25
        track_height = 35
        track_count = len(self._tracks)
        total_height = ruler_height + (track_count * (track_height + 2))
        self.playhead.setFixedHeight(total_height)
        
    def _on_zoom_changed(self, value: int):
        """Handle zoom slider change"""
        self._pixels_per_second = value
        self._update_zoom()
        
    def _zoom_in(self):
        """Zoom in"""
        new_value = min(200, self.zoom_slider.value() + 10)
        self.zoom_slider.setValue(new_value)
        
    def _zoom_out(self):
        """Zoom out"""
        new_value = max(10, self.zoom_slider.value() - 10)
        self.zoom_slider.setValue(new_value)
        
    def _update_zoom(self):
        """Update zoom level"""
        self.time_ruler.set_zoom(self._pixels_per_second)
        
        for track in self._tracks.values():
            track.set_zoom(self._pixels_per_second)
            
        self.playhead.set_zoom(self._pixels_per_second)
        
        if self._composition:
            min_width = int(self._composition.duration * self._pixels_per_second)
            self.timeline_content.setMinimumWidth(min_width)
            
    def _on_playhead_moved(self, time: float):
        """Handle playhead position change"""
        self._current_time = time
        self._update_time_label()
        self.time_changed.emit(time)
        
    def _on_layer_timing_changed(self, layer_id: str, start: float, end: float):
        """Handle layer timing change"""
        self.layer_timing_changed.emit(layer_id, start, end)
        
    def _update_time_label(self):
        """Update time display"""
        hours = int(self._current_time // 3600)
        minutes = int((self._current_time % 3600) // 60)
        seconds = int(self._current_time % 60)
        frames = int((self._current_time % 1) * 30)
        self.time_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}")
        
    def set_time(self, time: float):
        """Set current time"""
        self._current_time = time
        self.playhead.set_position(time)
        self._update_time_label()
        
    def get_time(self) -> float:
        """Get current time"""
        return self._current_time
        
    def update_layer(self, layer: Layer):
        """Update a specific layer track"""
        if layer.id in self._tracks:
            self._tracks[layer.id].update_from_layer()
            
    def add_layer(self, layer: Layer):
        """Add a new layer track"""
        self._add_track(layer)
        self._update_playhead_height()
        
    def remove_layer(self, layer_id: str):
        """Remove a layer track"""
        if layer_id in self._tracks:
            track = self._tracks.pop(layer_id)
            self.tracks_layout.removeWidget(track)
            track.deleteLater()
            self._update_playhead_height()
