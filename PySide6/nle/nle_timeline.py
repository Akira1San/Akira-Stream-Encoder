"""
NLE Timeline Widget - Timeline with ruler, playhead, and track container
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy, QStylePainter
)
from PySide6.QtCore import Qt, Signal, QTimer, QRect, QRectF, QPointF, QMimeData
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QDragEnterEvent, QDropEvent

from nle.nle_models import NLEProject, TrackType
from nle.nle_track import NLETrackWidget


class TimeRuler(QWidget):
    """
    Time ruler widget showing time scale.
    
    Displays time markers like: 00:00, 00:30, 01:00, etc.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(30)
        self.setMaximumHeight(30)
        
        # Time scale settings
        self._duration = 60.0  # Total duration in seconds
        self._pixels_per_second = 20.0  # Zoom level
        self._scroll_offset = 0.0  # Horizontal scroll offset in pixels
        
        # Appearance
        self.bg_color = QColor("#2a2a2a")
        self.text_color = QColor("#888888")
        self.tick_color = QColor("#555555")
        self.font = QFont("monospace", 9)
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    
    def set_duration(self, duration: float):
        """Set total duration in seconds"""
        self._duration = max(1.0, duration)
        self.update()
    
    def set_zoom(self, pixels_per_second: float):
        """Set zoom level (pixels per second)"""
        self._pixels_per_second = max(1.0, min(500.0, pixels_per_second))
        self.update()
    
    def set_scroll_offset(self, offset: float):
        """Set horizontal scroll offset in pixels"""
        self._scroll_offset = max(0, offset)
        self.update()
    
    def get_time_at_x(self, x: float) -> float:
        """Get time position at x coordinate"""
        return (x + self._scroll_offset) / self._pixels_per_second
    
    def get_x_at_time(self, time: float) -> float:
        """Get x coordinate at time position"""
        return time * self._pixels_per_second - self._scroll_offset
    
    def paintEvent(self, event):
        """Paint the time ruler"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), self.bg_color)
        
        # Calculate visible time range
        visible_width = self.width()
        start_time = self._scroll_offset / self._pixels_per_second
        end_time = start_time + visible_width / self._pixels_per_second
        
        # Determine tick interval based on zoom
        if self._pixels_per_second >= 100:
            # Major ticks every 1 second, minor every 0.5s
            major_interval = 1.0
            minor_interval = 0.5
        elif self._pixels_per_second >= 50:
            # Major ticks every 5 seconds, minor every 1s
            major_interval = 5.0
            minor_interval = 1.0
        elif self._pixels_per_second >= 20:
            # Major ticks every 10 seconds, minor every 5s
            major_interval = 10.0
            minor_interval = 5.0
        elif self._pixels_per_second >= 10:
            # Major ticks every 30 seconds, minor every 10s
            major_interval = 30.0
            minor_interval = 10.0
        else:
            # Major ticks every 60 seconds, minor every 30s
            major_interval = 60.0
            minor_interval = 30.0
        
        # Draw minor ticks
        painter.setPen(QPen(self.tick_color, 1))
        minor_time = (start_time // minor_interval) * minor_interval
        while minor_time <= end_time:
            x = self.get_x_at_time(minor_time)
            if x >= 0:
                painter.drawLine(int(x), self.height() - 8, int(x), self.height())
            minor_time += minor_interval
        
        # Draw major ticks and labels
        painter.setFont(self.font)
        painter.setPen(QPen(self.text_color))
        
        major_time = (start_time // major_interval) * major_interval
        while major_time <= end_time:
            x = self.get_x_at_time(major_time)
            if x >= 0:
                # Tick mark
                painter.setPen(QPen(self.tick_color, 1))
                painter.drawLine(int(x), self.height() - 15, int(x), self.height())
                
                # Time label
                painter.setPen(QPen(self.text_color))
                time_str = self._format_time_short(major_time)
                painter.drawText(int(x) + 3, self.height() - 17, time_str)
            major_time += major_interval
        
        painter.end()
    
    def _format_time_short(self, seconds: float) -> str:
        """Format time as MM:SS or HH:MM:SS"""
        total_secs = int(seconds)
        hours = total_secs // 3600
        minutes = (total_secs % 3600) // 60
        secs = total_secs % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    def minimumWidth(self) -> int:
        """Return minimum width based on duration and zoom"""
        return int(self._duration * self._pixels_per_second)


class Playhead(QWidget):
    """
    Draggable playhead indicator.
    
    A vertical line that can be dragged to seek through the timeline.
    """
    
    # Signals
    position_changed = Signal(float)  # New position in seconds
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._position = 0.0  # Current position in seconds
        self._pixels_per_second = 20.0
        self._scroll_offset = 0.0
        self._dragging = False
        
        # Appearance
        self.line_color = QColor("#ff4444")
        self.handle_color = QColor("#ff6666")
        self.handle_size = 12
        
        # Enable mouse tracking
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        
        # Set size policy
        self.setFixedWidth(self.handle_size)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
    
    def set_position(self, position: float):
        """Set playhead position in seconds"""
        self._position = max(0, position)
        self._update_geometry()
    
    def set_zoom(self, pixels_per_second: float):
        """Set zoom level"""
        self._pixels_per_second = max(1.0, pixels_per_second)
        self._update_geometry()
    
    def set_scroll_offset(self, offset: float):
        """Set scroll offset"""
        self._scroll_offset = max(0, offset)
        self._update_geometry()
    
    def _update_geometry(self):
        """Update widget position based on position and scroll"""
        x = self._position * self._pixels_per_second - self._scroll_offset - self.handle_size // 2
        self.move(int(x), 0)
        self.update()
    
    def paintEvent(self, event):
        """Paint the playhead"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw handle (triangle at top)
        painter.setBrush(QBrush(self.handle_color))
        painter.setPen(Qt.NoPen)
        
        handle_path = QPainterPath()
        handle_path.moveTo(self.width() // 2, 0)
        handle_path.lineTo(0, self.handle_size)
        handle_path.lineTo(self.width(), self.handle_size)
        handle_path.closeSubpath()
        painter.drawPath(handle_path)
        
        # Draw vertical line
        painter.setPen(QPen(self.line_color, 2))
        painter.drawLine(self.width() // 2, self.handle_size, 
                        self.width() // 2, self.height())
        
        painter.end()
    
    def mousePressEvent(self, event):
        """Start dragging"""
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self.setCursor(Qt.ClosedHandCursor)
    
    def mouseMoveEvent(self, event):
        """Handle dragging"""
        if self._dragging:
            # Calculate new position from global mouse position
            # We need parent widget for coordinate transformation
            parent = self.parent()
            if parent:
                global_pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
                parent_pos = parent.mapFromGlobal(global_pos)
                new_x = parent_pos.x() + self._scroll_offset
                new_position = new_x / self._pixels_per_second
                new_position = max(0, new_position)
                
                if new_position != self._position:
                    self._position = new_position
                    self._update_geometry()
                    self.position_changed.emit(self._position)
    
    def mouseReleaseEvent(self, event):
        """End dragging"""
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self.setCursor(Qt.PointingHandCursor)


class TrackContainer(QWidget):
    """
    Container widget for track rows.
    
    Manages the vertical layout of tracks.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.tracks = []  # List of track widgets
        
        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)
        self.layout.addStretch()
        
        # Appearance
        self.setStyleSheet("background-color: #1a1a1a;")
    
    def add_track_widget(self, track_widget: QWidget):
        """Add a track widget to the container"""
        self.tracks.append(track_widget)
        # Insert before the stretch
        self.layout.insertWidget(self.layout.count() - 1, track_widget)
    
    def remove_track_widget(self, track_widget: QWidget):
        """Remove a track widget from the container"""
        if track_widget in self.tracks:
            self.tracks.remove(track_widget)
            self.layout.removeWidget(track_widget)
            track_widget.deleteLater()
    
    def clear_tracks(self):
        """Remove all track widgets"""
        for track in self.tracks[:]:
            self.remove_track_widget(track)


class NLETimeline(QWidget):
    """
    Main NLE Timeline widget.
    
    Combines time ruler, playhead, and track container.
    """
    
    # Signals
    playhead_moved = Signal(float)  # Position in seconds
    zoom_changed = Signal(float)  # Pixels per second
    source_dropped = Signal(str, float)  # source_path, timeline_position
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._project = None
        self._pixels_per_second = 20.0  # Zoom level
        self._scroll_offset = 0.0
        
        # Enable drop for drag-and-drop from source bin
        self.setAcceptDrops(True)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup timeline UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Top section: Time ruler
        ruler_container = QWidget()
        ruler_layout = QHBoxLayout(ruler_container)
        ruler_layout.setContentsMargins(0, 0, 0, 0)
        ruler_layout.setSpacing(0)
        
        # Spacer for track headers
        header_spacer = QFrame()
        header_spacer.setFixedWidth(150)
        header_spacer.setStyleSheet("background-color: #2d2d2d;")
        ruler_layout.addWidget(header_spacer)
        
        # Time ruler
        self.time_ruler = TimeRuler()
        ruler_layout.addWidget(self.time_ruler)
        
        main_layout.addWidget(ruler_container)
        
        # Middle section: Playhead and tracks
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Track headers area (will be part of track container)
        self.track_container = TrackContainer()
        content_layout.addWidget(self.track_container)
        
        main_layout.addWidget(content_widget)
        
        # Playhead (overlay on content)
        self.playhead = Playhead()
        self.playhead.setParent(self)
        self.playhead.position_changed.connect(self._on_playhead_moved)
        
        # Connect zoom
        self.zoom_changed.connect(self._on_zoom_changed)
    
    def set_project(self, project: NLEProject):
        """Set the NLE project"""
        self._project = project
        self._refresh_tracks()
        self._update_duration()
    
    def _refresh_tracks(self):
        """Refresh track widgets from project"""
        self.track_container.clear_tracks()
        
        if self._project:
            for track in self._project.tracks:
                # Use NLETrackWidget instead of TrackRowWidget
                track_widget = NLETrackWidget(track, self)
                track_widget.clip_clicked.connect(self._on_clip_clicked)
                track_widget.set_zoom(self._pixels_per_second)
                self.track_container.add_track_widget(track_widget)
                
                # Add clip widgets for existing clips
                for clip in track.clips:
                    track_widget.add_clip(clip)
                    
    def _on_clip_clicked(self, clip_id: str):
        """Handle clip click - select the clip"""
        self.select_clip(clip_id)
    
    def _update_duration(self):
        """Update duration from project"""
        if self._project:
            self.time_ruler.set_duration(max(60.0, self._project.duration))
    
    def set_zoom(self, pixels_per_second: float):
        """Set zoom level"""
        self._pixels_per_second = max(1.0, min(500.0, pixels_per_second))
        self.zoom_changed.emit(self._pixels_per_second)
    
    def zoom_in(self):
        """Zoom in (increase pixels per second)"""
        self.set_zoom(self._pixels_per_second * 1.5)
    
    def zoom_out(self):
        """Zoom out (decrease pixels per second)"""
        self.set_zoom(self._pixels_per_second / 1.5)
    
    def _on_zoom_changed(self, pixels_per_second: float):
        """Handle zoom change"""
        self.time_ruler.set_zoom(pixels_per_second)
        self.playhead.set_zoom(pixels_per_second)
        
        # Update track clip positions
        for track_widget in self.track_container.tracks:
            track_widget.set_zoom(pixels_per_second)
    
    def _on_playhead_moved(self, position: float):
        """Handle playhead position change"""
        self.playhead_moved.emit(position)
    
    def resizeEvent(self, event):
        """Handle resize"""
        super().resizeEvent(event)
        # Update playhead position
        self.playhead.setFixedSize(self.playhead.width(), self.height())
        self.playhead._update_geometry()
    
    def get_zoom_percentage(self) -> int:
        """Get zoom level as percentage (100% = 20 pixels/second)"""
        return int((self._pixels_per_second / 20.0) * 100)
    
    def set_zoom_percentage(self, percentage: int):
        """Set zoom level as percentage"""
        self.set_zoom(20.0 * (percentage / 100.0))
    
    def get_playhead_position(self) -> float:
        """Get current playhead position in seconds"""
        return self.playhead._position
    
    def split_clip_at_playhead(self):
        """Split the clip under the playhead"""
        if not self._project:
            return False
            
        playhead_pos = self.get_playhead_position()
        
        # Find clip under playhead
        for track in self._project.tracks:
            clip = track.get_clip_at_time(playhead_pos)
            if clip:
                result = self._project.split_clip(clip.id, playhead_pos)
                if result:
                    self._refresh_tracks()
                    return True
        return False
    
    def delete_selected_clips(self):
        """Delete all selected clips"""
        if not self._project:
            return
            
        deleted = False
        for track in self._project.tracks:
            for clip in track.clips[:]:  # Copy list to avoid modification during iteration
                if clip.selected:
                    track.remove_clip(clip.id)
                    deleted = True
                    
        if deleted:
            self._refresh_tracks()
            
    def select_clip(self, clip_id: str, exclusive: bool = True):
        """Select a clip by ID"""
        if not self._project:
            return
            
        if exclusive:
            # Deselect all first
            for track in self._project.tracks:
                for clip in track.clips:
                    clip.selected = False
                    
        # Select the target clip
        for track in self._project.tracks:
            for clip in track.clips:
                if clip.id == clip_id:
                    clip.selected = True
                    break
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter - accept if it's a source file"""
        if event.mimeData().hasData("application/x-nle-source"):
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        """Handle drag move - show drop position"""
        if event.mimeData().hasData("application/x-nle-source"):
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dropEvent(self, event: QDropEvent):
        """Handle drop - create clip from source"""
        mime_data = event.mimeData()
        if not mime_data.hasData("application/x-nle-source"):
            event.ignore()
            return
            
        # Get source path
        source_path = bytes(mime_data.data("application/x-nle-source")).decode('utf-8')
        
        # Calculate timeline position from drop position
        drop_x = event.position().x() if hasattr(event, 'position') else event.pos().x()
        
        # Account for track header width (150px)
        header_width = 150
        timeline_x = drop_x - header_width
        
        # Convert to time
        timeline_position = max(0, timeline_x / self._pixels_per_second)
        
        # Snap to 0.1 second
        timeline_position = round(timeline_position * 10) / 10
        
        # Emit signal to create clip
        self.source_dropped.emit(source_path, timeline_position)
        event.acceptProposedAction()
