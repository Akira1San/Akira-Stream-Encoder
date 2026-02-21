"""
NLE Clip Widget - Clip block widget for timeline
"""
from PySide6.QtWidgets import QWidget, QSizePolicy, QMenu
from PySide6.QtCore import Qt, Signal, QPoint, QRect
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QCursor

from nle.nle_models import NLEClip


class NLEClipWidget(QWidget):
    """
    Clip widget for the NLE timeline.
    
    Displays as a colored rectangle with:
    - Source filename
    - Time range
    - Resize handles on edges
    - Selection highlight
    """
    
    clicked = Signal(str)  # clip_id
    moved = Signal(str, float)  # clip_id, new_start
    trimmed = Signal(str, float, float)  # clip_id, new_start, new_end
    delete_requested = Signal(str)  # clip_id
    split_requested = Signal(str, float)  # clip_id, position
    
    # Color schemes for different track types
    VIDEO_COLORS = {
        'background': QColor(41, 128, 185),  # Blue
        'border': QColor(52, 152, 219),
        'selected': QColor(46, 204, 113),  # Green
        'text': QColor(255, 255, 255),
    }
    AUDIO_COLORS = {
        'background': QColor(142, 68, 173),  # Purple
        'border': QColor(155, 89, 182),
        'selected': QColor(46, 204, 113),  # Green
        'text': QColor(255, 255, 255),
    }
    
    # Handle width for resize
    HANDLE_WIDTH = 8
    
    def __init__(self, clip: NLEClip, parent=None):
        super().__init__(parent)
        self.clip = clip
        self._selected = False
        self._dragging = False
        self._trimming_left = False
        self._trimming_right = False
        self._drag_start_pos = 0
        self._drag_start_time = 0.0
        self._pixels_per_second = 20.0
        self._scroll_offset = 0.0
        
        self._setup_ui()
        self.update_position()
        
    def _setup_ui(self):
        """Setup the clip widget"""
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setMouseTracking(True)
        self.setCursor(Qt.ArrowCursor)
        
    def set_zoom(self, pixels_per_second: float):
        """Set zoom level"""
        self._pixels_per_second = pixels_per_second
        self.update_position()
        
    def set_scroll_offset(self, offset: float):
        """Set scroll offset"""
        self._scroll_offset = offset
        self.update_position()
        
    def update_position(self):
        """Update widget position and size based on timeline position"""
        # Calculate x position from timeline start
        x = int(self.clip.timeline_start * self._pixels_per_second - self._scroll_offset)
        
        # Calculate width from duration
        width = int(self.clip.duration * self._pixels_per_second)
        width = max(width, 20)  # Minimum width
        
        self.move(x, 5)
        self.setFixedWidth(width)
        self.update()
        
    def set_selected(self, selected: bool):
        """Set selection state"""
        self._selected = selected
        self.update()
        
    def is_selected(self) -> bool:
        """Check if selected"""
        return self._selected
        
    def _get_colors(self):
        """Get color scheme based on track type"""
        # This will be determined by the parent track
        # For now, default to video colors
        return self.VIDEO_COLORS
        
    def paintEvent(self, event):
        """Paint the clip widget"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        colors = self._get_colors()
        
        # Background
        if self._selected:
            painter.setPen(QPen(colors['selected'], 2))
        else:
            painter.setPen(QPen(colors['border'], 1))
            
        painter.setBrush(QBrush(colors['background']))
        painter.drawRoundedRect(1, 1, self.width() - 2, self.height() - 2, 4, 4)
        
        # Clip name
        painter.setPen(QPen(colors['text']))
        font = QFont("Segoe UI", 9)
        painter.setFont(font)
        
        # Truncate name if needed
        name = self.clip.name
        if len(name) > 20:
            name = name[:17] + "..."
            
        painter.drawText(10, 15, name)
        
        # Time range
        font.setPointSize(8)
        painter.setFont(font)
        time_text = f"{self._format_time(self.clip.source_start)} - {self._format_time(self.clip.source_end)}"
        painter.drawText(10, 28, time_text)
        
        # Draw resize handles
        handle_color = colors['border'].lighter(120)
        painter.setPen(QPen(handle_color, 1))
        painter.setBrush(QBrush(handle_color))
        
        # Left handle
        painter.drawRect(0, 0, 3, self.height())
        
        # Right handle
        painter.drawRect(self.width() - 3, 0, 3, self.height())
        
    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
        
    def mousePressEvent(self, event):
        """Handle mouse press"""
        if event.button() == Qt.LeftButton:
            self._handle_left_press(event.pos())
        elif event.button() == Qt.RightButton:
            self._show_context_menu(event.pos())
            
    def _handle_left_press(self, pos):
        """Handle left mouse button press"""
        # Check if clicking on resize handles
        if pos.x() < self.HANDLE_WIDTH:
            self._trimming_left = True
            self._drag_start_pos = pos.x()
        elif pos.x() > self.width() - self.HANDLE_WIDTH:
            self._trimming_right = True
            self._drag_start_pos = pos.x()
        else:
            # Start drag
            self._dragging = True
            self._drag_start_pos = pos.x()
            self._drag_start_time = self.clip.timeline_start
            
        self.clicked.emit(self.clip.id)
        
    def mouseMoveEvent(self, event):
        """Handle mouse move"""
        pos = event.pos()
        
        # Update cursor based on position
        if pos.x() < self.HANDLE_WIDTH or pos.x() > self.width() - self.HANDLE_WIDTH:
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.setCursor(Qt.SizeAllCursor)
            
        if self._dragging:
            # Calculate new position
            delta_x = pos.x() - self._drag_start_pos
            delta_time = delta_x / self._pixels_per_second
            new_start = max(0, self._drag_start_time + delta_time)
            
            # Snap to 0.1 second
            new_start = round(new_start * 10) / 10
            
            self.clip.timeline_start = new_start
            self.update_position()
            
        elif self._trimming_left:
            # Trim from left (adjust source_start and timeline_start)
            delta_x = pos.x() - self._drag_start_pos
            delta_time = delta_x / self._pixels_per_second
            
            new_timeline_start = max(0, self._drag_start_time + delta_time)
            new_source_start = self.clip.source_start + delta_time
            
            # Minimum duration check
            if self.clip.source_end - new_source_start >= 0.1:
                self.clip.timeline_start = new_timeline_start
                self.clip.source_start = new_source_start
                self.update_position()
                
        elif self._trimming_right:
            # Trim from right (adjust source_end)
            delta_x = pos.x() - self._drag_start_pos
            delta_time = delta_x / self._pixels_per_second
            
            new_source_end = self.clip.source_end + delta_time
            
            # Minimum duration check
            if new_source_end - self.clip.source_start >= 0.1:
                self.clip.source_end = new_source_end
                self.update_position()
                
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        if self._dragging:
            self.moved.emit(self.clip.id, self.clip.timeline_start)
        elif self._trimming_left or self._trimming_right:
            self.trimmed.emit(self.clip.id, self.clip.source_start, self.clip.source_end)
            
        self._dragging = False
        self._trimming_left = False
        self._trimming_right = False
        
    def _show_context_menu(self, pos):
        """Show context menu"""
        menu = QMenu(self)
        
        delete_action = menu.addAction("Delete Clip")
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self.clip.id))
        
        menu.addSeparator()
        
        split_action = menu.addAction("Split at Position")
        split_action.triggered.connect(lambda: self._on_split(pos))
        
        menu.exec_(self.mapToGlobal(pos))
        
    def _on_split(self, pos):
        """Handle split action"""
        # Calculate split position in source time
        clip_x = pos.x()
        clip_time_ratio = clip_x / self.width()
        split_time = self.clip.source_start + (self.clip.duration * clip_time_ratio)
        
        self.split_requested.emit(self.clip.id, split_time)
