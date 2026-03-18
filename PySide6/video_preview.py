"""
Video Preview Component - Handles real-time preview functionality (PySide6)
Uses native Qt (QImage, QPixmap) instead of PIL/Pillow
"""
import io
import os
import subprocess
from typing import Optional

from PySide6 import QtWidgets
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QGroupBox, QSplitter, QSizePolicy, QPushButton, QComboBox,
    QStackedLayout
)
from PySide6.QtCore import Qt, Signal, QThread, QObject, QBuffer, QTimer
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QFont, QPen

from video_player import VideoPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget


def parse_srt_file(srt_path: str) -> list:
    """Parse SRT file and return list of subtitle entries"""
    entries = []
    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        try:
            with open(srt_path, 'r', encoding='latin-1') as f:
                content = f.read()
        except:
            return entries
    
    # Split by double newline to get subtitle blocks
    blocks = content.strip().split('\n\n')
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        
        # Parse time line (format: 00:00:00,000 --> 00:00:00,000)
        time_line = lines[1]
        if '-->' not in time_line:
            continue
        
        times = time_line.split('-->')
        if len(times) != 2:
            continue
        
        start_time = srt_time_to_seconds(times[0].strip())
        end_time = srt_time_to_seconds(times[1].strip())
        
        # Get subtitle text (remaining lines)
        text = '\n'.join(lines[2:])
        
        entries.append({
            'start': start_time,
            'end': end_time,
            'text': text
        })
    
    return entries


def srt_time_to_seconds(time_str: str) -> float:
    """Convert SRT timestamp to seconds"""
    # Format: 00:00:00,000 or 00:00:00.000
    time_str = time_str.replace(',', '.')
    parts = time_str.split(':')
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    return 0.0


def get_subtitle_text(srt_path: str, timestamp: float) -> str:
    """Get subtitle text at a specific timestamp"""
    entries = parse_srt_file(srt_path)
    for entry in entries:
        if entry['start'] <= timestamp < entry['end']:
            return entry['text']
    return ""

from models import AppState


class TimelineSlider(QSlider):
    """Custom slider with cut point markers and dynamic range for precise positioning"""
    
    cut_marker_clicked = Signal(float, str)  # position, cut_id
    
    # Constants for dynamic range
    STEPS_PER_SECOND = 30  # ~frame-accurate at 30fps
    MAX_STEPS = 100000     # Cap to prevent performance issues
    
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.cut_points = []  # List of (position_seconds, cut_id)
        self.duration = 0.0
        self.hovered_cut = None  # Currently hovered cut for visual feedback
        self._slider_max = 1000  # Current slider maximum
        
        # Enable keyboard focus for navigation shortcuts
        self.setFocusPolicy(Qt.StrongFocus)
        
    def set_duration(self, duration: float):
        """
        Set duration and update slider range dynamically.
        Provides ~frame-accurate precision (30 steps per second).
        """
        self.duration = max(0.0, duration)
        if self.duration > 0:
            # Calculate steps: 30 per second, capped at MAX_STEPS
            steps = min(int(self.duration * self.STEPS_PER_SECOND), self.MAX_STEPS)
            self._slider_max = max(steps, 1000)  # Minimum 1000 for short videos
        else:
            self._slider_max = 1000
        self.setRange(0, self._slider_max)
        
    def time_to_value(self, time_seconds: float) -> int:
        """Convert time in seconds to slider value"""
        if self.duration <= 0:
            return 0
        return int((time_seconds / self.duration) * self._slider_max)
    
    def value_to_time(self, value: int) -> float:
        """Convert slider value to time in seconds"""
        if self._slider_max <= 0:
            return 0.0
        return (value / self._slider_max) * self.duration
        
    def set_cut_points(self, cut_points: list, duration: float):
        """
        Set cut points to display
        Args:
            cut_points: List of (position_seconds, cut_id) tuples
            duration: Video duration in seconds
        """
        self.cut_points = cut_points
        if duration != self.duration:
            self.set_duration(duration)
        self.update()
    
    def clear_cut_points(self):
        """Clear all cut markers"""
        self.cut_points = []
        self.update()
    
    def paintEvent(self, event):
        """Override paintEvent to draw cut markers"""
        # Call parent paintEvent first (draws slider handle and groove)
        super().paintEvent(event)
        
        if not self.cut_points or self.duration <= 0:
            return
        
        # Create painter
        painter = QPainter(self)
        
        for cut_pos, cut_id in self.cut_points:
            # Convert seconds to slider position using dynamic range
            if self.duration > 0:
                slider_val = self.time_to_value(cut_pos)
                x = self._value_to_pixel(slider_val)
                
                # Check if this cut is hovered
                is_hovered = (self.hovered_cut == cut_id)
                
                # Draw wider marker with border for better visibility
                if is_hovered:
                    # Highlighted marker when hovered
                    painter.setPen(QPen(QColor(255, 255, 255), 3))  # White border
                    painter.setBrush(QColor(0, 255, 0))  # Bright green
                    marker_width = 14
                else:
                    # Normal marker
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(0, 200, 0))  # Green
                    marker_width = 10
                
                # Draw vertical line/marker - full height of slider with slight margin
                painter.drawRect(int(x) - marker_width//2, 0, marker_width, self.height())
        
        painter.end()
    
    def _value_to_pixel(self, value: int) -> float:
        """Convert slider value to pixel position"""
        # Get slider dimensions
        slider_width = self.width()
        handle_width = 20  # Approximate handle width
        
        # Calculate available width (excluding handle)
        available_width = slider_width - handle_width
        
        min_val = self.minimum()
        max_val = self.maximum()
        
        if max_val == min_val:
            return handle_width / 2
        
        # Calculate position
        position = (handle_width / 2) + (value - min_val) * available_width / (max_val - min_val)
        
        return position
    
    def mousePressEvent(self, event):
        """Handle mouse press to detect clicks on cut markers"""
        if not self.cut_points or self.duration <= 0:
            super().mousePressEvent(event)
            return
        
        # Check if click is near a cut marker
        click_x = event.position().x()
        tolerance = 25  # Large tolerance for easy clicking
        
        # Find the closest marker
        closest_cut = None
        closest_distance = float('inf')
        
        for cut_pos, cut_id in self.cut_points:
            slider_val = self.time_to_value(cut_pos)
            marker_x = self._value_to_pixel(slider_val)
            distance = abs(click_x - marker_x)
            
            if distance <= tolerance and distance < closest_distance:
                closest_distance = distance
                closest_cut = (cut_pos, cut_id, slider_val)
        
        if closest_cut:
            cut_pos, cut_id, slider_val = closest_cut
            # Jump to this cut position
            self.setValue(slider_val)
            self.sliderReleased.emit()
            # Emit signal that this cut marker was clicked
            self.cut_marker_clicked.emit(cut_pos, cut_id)
            return
        
        # If not near a marker, handle as normal slider click
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for hover effects"""
        if not self.cut_points or self.duration <= 0:
            super().mouseMoveEvent(event)
            return
        
        # Check if hovering over a cut marker
        mouse_x = event.position().x()
        tolerance = 25  # Large tolerance to match click area
        
        hovered_cut = None
        for cut_pos, cut_id in self.cut_points:
            slider_val = self.time_to_value(cut_pos)
            marker_x = self._value_to_pixel(slider_val)
            
            if abs(mouse_x - marker_x) <= tolerance:
                hovered_cut = cut_id
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                break
        
        if hovered_cut != self.hovered_cut:
            self.hovered_cut = hovered_cut
            self.update()  # Repaint to show hover effect
        
        if not hovered_cut:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        
        super().mouseMoveEvent(event)
    
    def leaveEvent(self, event):
        """Handle mouse leave"""
        if self.hovered_cut:
            self.hovered_cut = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.update()
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts for precise navigation"""
        if self.duration <= 0:
            super().keyPressEvent(event)
            return
        
        key = event.key()
        modifiers = event.modifiers()
        
        # Calculate step sizes based on current range
        frame_step = max(1, self._slider_max // (int(self.duration * 30)))  # 1 frame at 30fps
        second_step = max(1, self._slider_max // int(self.duration))  # 1 second
        five_second_step = max(1, self._slider_max * 5 // int(self.duration))  # 5 seconds
        
        handled = False
        
        if key == Qt.Key_Left:
            if modifiers & Qt.ShiftModifier:
                # Shift+Left: Jump back 1 second
                new_value = max(0, self.value() - second_step)
            elif modifiers & Qt.ControlModifier:
                # Ctrl+Left: Jump back 5 seconds
                new_value = max(0, self.value() - five_second_step)
            else:
                # Left: Step back 1 frame
                new_value = max(0, self.value() - frame_step)
            handled = True
            
        elif key == Qt.Key_Right:
            if modifiers & Qt.ShiftModifier:
                # Shift+Right: Jump forward 1 second
                new_value = min(self._slider_max, self.value() + second_step)
            elif modifiers & Qt.ControlModifier:
                # Ctrl+Right: Jump forward 5 seconds
                new_value = min(self._slider_max, self.value() + five_second_step)
            else:
                # Right: Step forward 1 frame
                new_value = min(self._slider_max, self.value() + frame_step)
            handled = True
            
        elif key == Qt.Key_J:
            # J: Jump back 5 seconds
            new_value = max(0, self.value() - five_second_step)
            handled = True
            
        elif key == Qt.Key_L:
            # L: Jump forward 5 seconds
            new_value = min(self._slider_max, self.value() + five_second_step)
            handled = True
            
        elif key == Qt.Key_Home:
            # Home: Go to start
            new_value = 0
            handled = True
            
        elif key == Qt.Key_End:
            # End: Go to end
            new_value = self._slider_max
            handled = True
        
        if handled:
            self.setValue(new_value)
            self.sliderReleased.emit()
        else:
            super().keyPressEvent(event)
    
    def stepBy(self, steps: int):
        """Override stepBy for finer stepping with mouse wheel/page keys"""
        if self.duration <= 0:
            super().stepBy(steps)
            return
        
        # Use frame-sized steps instead of default large steps
        frame_step = max(1, self._slider_max // (int(self.duration * 30)))
        new_value = self.value() + steps * frame_step
        new_value = max(0, min(self._slider_max, new_value))
        self.setValue(new_value)


class FrameLoader(QObject):
    """Worker object for loading frames in background thread"""
    
    frame_loaded = Signal(object)  # QImage
    error_occurred = Signal(str)
    
    def __init__(self):
        super().__init__()
        self._cancelled = False
        self._is_dvd_source = False
        
    def load_frame(self, video_path: str, timestamp: float, ffmpeg_path: str, is_dvd_source: bool = False, first_vob_path: str = None):
        """Load a frame from video at specified timestamp
        
        Args:
            video_path: Path to video file or concat file
            timestamp: Seek position in seconds
            ffmpeg_path: Path to ffmpeg executable
            is_dvd_source: True if this is a DVD concat source
            first_vob_path: Path to first VOB file for DVD preview fallback
        """
        self._cancelled = False
        self._is_dvd_source = is_dvd_source
        
        # For DVD sources, try the first VOB file directly for preview
        # This is more reliable than concat demuxer for frame extraction
        if is_dvd_source and first_vob_path and os.path.exists(first_vob_path):
            # Use first VOB for preview (limited to first ~1GB but much faster)
            # Limit timestamp to reasonable range for first VOB
            preview_timestamp = min(timestamp, 600.0)  # Cap at 10 minutes
            cmd = [ffmpeg_path, "-ss", str(preview_timestamp)]
            cmd.extend(["-i", first_vob_path])
            cmd.extend(["-vframes", "1", "-q:v", "2", "-f", "image2pipe", "-vcodec", "png", "-"])
        elif is_dvd_source:
            # Fallback to concat demuxer
            cmd = [ffmpeg_path, "-ss", str(timestamp)]
            cmd.extend(["-f", "concat", "-safe", "0"])
            cmd.extend(["-i", video_path])
            cmd.extend(["-vframes", "1", "-q:v", "2", "-f", "image2pipe", "-vcodec", "png", "-"])
        else:
            # Standard seeking for regular video files
            cmd = [ffmpeg_path, "-ss", str(timestamp)]
            cmd.extend(["-i", video_path, "-vframes", "1", "-q:v", "2", "-f", "image2pipe", "-vcodec", "png", "-"])
        
        try:
            # Use longer timeout for DVD sources (VOB files can be slow)
            timeout = 30 if is_dvd_source else 10
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=timeout
            )
            
            if self._cancelled:
                return
                
            if result.returncode == 0 and result.stdout:
                # Load image from bytes using QImage
                image = QImage()
                image.loadFromData(result.stdout, "PNG")
                
                if not image.isNull():
                    self.frame_loaded.emit(image)
                else:
                    self.error_occurred.emit("Failed to decode image")
            else:
                # Log the error for debugging
                error_msg = result.stderr.decode('utf-8', errors='ignore') if result.stderr else "Unknown error"
                self.error_occurred.emit(f"FFmpeg failed: {error_msg[:200]}")
                
        except subprocess.TimeoutExpired:
            self.error_occurred.emit("Frame extraction timed out")
        except Exception as e:
            self.error_occurred.emit(f"Error: {str(e)}")
            
    def cancel(self):
        """Cancel the current operation"""
        self._cancelled = True


class FilterOverlay(QWidget):
    """
    Overlay widget that displays processed video frames with filters and subtitles.
    Sits on top of the video widget and displays filtered preview.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        
        # Current processed frame to display
        self._current_image: Optional[QImage] = None
        self._subtitle_text: str = ""
    
    def set_image(self, image: QImage):
        """Set the processed frame to display"""
        if not image.isNull():
            self._current_image = image.copy()
            self.update()
    
    def set_subtitle(self, text: str):
        """Set subtitle text to display"""
        self._subtitle_text = text
        self.update()
    
    def clear(self):
        """Clear the overlay"""
        self._current_image = None
        self._subtitle_text = ""
        self.update()
    
    def paintEvent(self, event):
        """Draw the processed frame and subtitle on the overlay"""
        super().paintEvent(event)
        
        if self._current_image is None or self._current_image.isNull():
            return
        
        painter = QPainter(self)
        
        # Scale the image to fill the widget (ignore aspect ratio to fill the panel)
        pixmap = QPixmap.fromImage(self._current_image)
        scaled = pixmap.scaled(
            self.size(),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation
        )
        
        # Draw the image
        painter.drawPixmap(0, 0, scaled)
        
        # Draw subtitle if present
        if self._subtitle_text:
            self._draw_subtitle(painter, scaled.width(), scaled.height(), 0, 0)
        
        painter.end()
    
    def _draw_subtitle(self, painter: QPainter, img_width: int, img_height: int, img_x: int, img_y: int):
        """Draw subtitle text on the image"""
        from models import AppState
        
        # Get default settings if AppState not available
        font_family = "Arial"
        font_size = 24
        text_color = "white"
        bg_color = "black"
        bg_opacity = 0.5
        position = "bottom"
        outline_width = 2
        outline_color = "black"
        vertical_offset = 0
        
        # Try to get settings from AppState if available
        if hasattr(self, 'app_state') and self.app_state:
            subs = self.app_state.subtitles
            font_family = subs.font
            font_size = subs.size
            text_color = subs.color
            bg_color = subs.bg_color
            bg_opacity = subs.bg_opacity
            position = subs.position
            outline_width = subs.outline_width
            outline_color = subs.outline_color
            vertical_offset = subs.vertical_offset
        
        # Set up font
        font = QFont(font_family)
        font.setPixelSize(font_size)
        painter.setFont(font)
        
        # Calculate text position
        metrics = painter.fontMetrics()
        lines = self._subtitle_text.split('\n')
        max_width = max(metrics.horizontalAdvance(line) for line in lines)
        total_height = metrics.height() * len(lines)
        
        # Position based on settings (relative to video image)
        if position == "bottom":
            x = img_x + (img_width - max_width) // 2
            y = img_y + img_height - 20 - total_height + vertical_offset
        elif position == "top":
            x = img_x + (img_width - max_width) // 2
            y = img_y + 20 + metrics.height() - vertical_offset
        else:  # center
            x = img_x + (img_width - max_width) // 2
            y = img_y + (img_height - total_height) // 2
        
        # Draw background if opacity > 0
        if bg_opacity > 0:
            bg = QColor(bg_color)
            bg.setAlpha(int(bg_opacity * 255))
            painter.fillRect(x - 10, y - metrics.height() + 5,
                           max_width + 20, total_height + 10, bg)
        
        # Draw outline
        outline = QColor(outline_color)
        text_col = QColor(text_color)
        
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx != 0 or dy != 0:
                    painter.setPen(outline)
                    painter.drawText(x + dx, y + dy, max_width, total_height,
                                   Qt.AlignLeft | Qt.AlignTop, self._subtitle_text)
        
        # Draw main text
        painter.setPen(text_col)
        painter.drawText(x, y, max_width, total_height,
                        Qt.AlignLeft | Qt.AlignTop, self._subtitle_text)


class VideoPreview(QWidget):
    """
    Video preview widget with before/after comparison.
    Uses native Qt image handling instead of PIL.
    """
    
    frame_changed = Signal(float)  # Emitted when frame changes
    
    def __init__(self, app_state: AppState, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        
        self.current_video_path: Optional[str] = None
        self.duration: float = 0.0
        self.current_frame: Optional[QImage] = None
        self.is_playing: bool = False
        self.playback_speed: float = 1.0  # 1.0 = normal speed
        self._playback_time: float = 0.0  # Current playback position in seconds
        
        # Frame loader thread
        self._loader_thread: Optional[QThread] = None
        self._frame_loader: Optional[FrameLoader] = None
        
        # Flag to prevent feedback loop between slider and video position
        self._is_user_seeking: bool = False  # True when user is dragging timeline
        
        # Video player (QMediaPlayer for smooth playback)
        self._video_player = VideoPlayer(self)
        self._video_player_widget: Optional[QVideoWidget] = None
        self._video_player.position_changed.connect(self._on_video_position_changed)
        self._video_player.duration_changed.connect(self._video_duration_changed)
        self._video_player.state_changed.connect(self._video_state_changed)
        self._video_player.error_occurred.connect(self._on_video_error)
        
        # Volume tracking (stored for persistence)
        self._audio_volume: float = 0.8  # Default volume 80%
        
        # Connect frame capture for filter overlay preview
        self._video_player.frame_captured.connect(self._on_frame_captured)
        
        # Filter overlay timer for processed preview
        self._overlay_timer = QTimer(self)
        self._overlay_timer.setInterval(500)  # Update every 500ms (2 fps) - slower for FFmpeg fallback
        self._overlay_timer.timeout.connect(self._update_filter_overlay)
        
        # Current subtitle text for overlay
        self._current_subtitle: str = ""
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Split view: Original | Processed
        self.split = QSplitter(Qt.Horizontal)
        
        # Default preview size
        self.preview_width = 320
        self.preview_height = 180
        
        # Original frame
        self.original_group = QGroupBox("Original")
        original_layout = QVBoxLayout(self.original_group)
        original_layout.setContentsMargins(5, 5, 5, 5)
        
        # Create container for original video (label + QVideoWidget stacked)
        self.original_container = QWidget()
        self.original_container.setMinimumSize(self.preview_width, self.preview_height)
        self.original_container.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        )
        self.original_container.setStyleSheet("background-color: #1a1a1a;")
        original_stacked_layout = QStackedLayout(self.original_container)
        original_stacked_layout.setContentsMargins(0, 0, 0, 0)
        original_stacked_layout.setSpacing(0)
        
        # Placeholder label (shown when no video) - index 0
        self.original_label = QLabel("No Video")
        self.original_label.setAlignment(Qt.AlignCenter)
        self.original_label.setMinimumSize(self.preview_width, self.preview_height)
        self.original_label.setStyleSheet("background-color: #1a1a1a; color: #888;")
        self.original_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        original_stacked_layout.addWidget(self.original_label)
        
        # Create video widget for smooth playback (QVideoWidget) - index 1
        self._video_widget = QVideoWidget()
        self._video_widget.setMinimumSize(self.preview_width, self.preview_height)
        self._video_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        )
        self._video_player.set_video_output(self._video_widget)
        original_stacked_layout.addWidget(self._video_widget)
        
        self.original_group.layout().addWidget(self.original_container)
        
        self.split.addWidget(self.original_group)
        
        # Processed frame
        self.processed_group = QGroupBox("Processed Preview")
        processed_layout = QVBoxLayout(self.processed_group)
        processed_layout.setContentsMargins(5, 5, 5, 5)
        
        # Container for processed preview (label + overlay stacked)
        self.processed_container = QWidget()
        self.processed_container.setMinimumSize(self.preview_width, self.preview_height)
        self.processed_container.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        )
        self.processed_container.setStyleSheet("background-color: #1a1a1a;")
        processed_stacked_layout = QStackedLayout(self.processed_container)
        processed_stacked_layout.setContentsMargins(0, 0, 0, 0)
        processed_stacked_layout.setSpacing(0)
        
        # Placeholder label (shown when no video) - index 0
        self.processed_label = QLabel("No Video")
        self.processed_label.setAlignment(Qt.AlignCenter)
        self.processed_label.setMinimumSize(self.preview_width, self.preview_height)
        self.processed_label.setStyleSheet("background-color: #1a1a1a; color: #888;")
        self.processed_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        processed_stacked_layout.addWidget(self.processed_label)
        
        # Filter overlay widget (for displaying QMediaPlayer frames with filters applied) - index 1
        self.filter_overlay = FilterOverlay()
        self.filter_overlay.setMinimumSize(self.preview_width, self.preview_height)
        self.filter_overlay.app_state = self.app_state  # Pass app_state for subtitle settings
        processed_stacked_layout.addWidget(self.filter_overlay)
        
        processed_layout.addWidget(self.processed_container)
        
        self.split.addWidget(self.processed_group)
        self.split.setSizes([400, 400])
        
        self.original_group.setMinimumHeight(self.preview_height + 30)
        self.processed_group.setMinimumHeight(self.preview_height + 30)
        self.split.setMinimumHeight(self.preview_height + 40)
        
        self.setMinimumHeight(self.preview_height + 180)
        
        layout.addWidget(self.split)
        
        # Playback controls
        playback_layout = QHBoxLayout()
        
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setMaximumWidth(80)
        self.play_btn.clicked.connect(self.on_play_clicked)
        playback_layout.addWidget(self.play_btn)
        
        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.setMaximumWidth(80)
        self.pause_btn.clicked.connect(self.on_pause_clicked)
        self.pause_btn.setEnabled(False)
        playback_layout.addWidget(self.pause_btn)
        
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setMaximumWidth(80)
        self.stop_btn.clicked.connect(self.on_stop_clicked)
        playback_layout.addWidget(self.stop_btn)
        
        playback_layout.addSpacing(20)
        
        # Playback speed dropdown
        playback_layout.addWidget(QLabel("Speed:"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.25x", "0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "1.75x", "2.0x"])
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.currentTextChanged.connect(self.on_speed_changed)
        self.speed_combo.setMaximumWidth(80)
        playback_layout.addWidget(self.speed_combo)
        
        playback_layout.addSpacing(15)
        
        # Preview size dropdown
        playback_layout.addWidget(QLabel("Preview:"))
        self.size_combo = QComboBox()
        self.size_combo.addItems(["Small", "Medium"])
        self.size_combo.setCurrentText("Small")
        self.size_combo.currentTextChanged.connect(self.on_size_changed)
        self.size_combo.setMaximumWidth(80)
        playback_layout.addWidget(self.size_combo)
        
        playback_layout.addSpacing(15)
        
        # Volume control
        playback_layout.addWidget(QLabel("Vol:"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(int(self._audio_volume * 100))
        self.volume_slider.setMaximumWidth(80)
        self.volume_slider.setToolTip("Audio volume")
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        playback_layout.addWidget(self.volume_slider)
        
        self.mute_btn = QPushButton("🔊")
        self.mute_btn.setMaximumWidth(40)
        self.mute_btn.setToolTip("Mute/Unmute audio")
        self.mute_btn.clicked.connect(self.on_mute_clicked)
        playback_layout.addWidget(self.mute_btn)
        
        playback_layout.addStretch()
        layout.addLayout(playback_layout)
        
        # Timeline controls
        timeline_layout = QHBoxLayout()
        
        timeline_layout.addWidget(QLabel("Timeline:"))
        
        self.timeline_slider = TimelineSlider(Qt.Horizontal)
        self.timeline_slider.setRange(0, 1000)  # Will be updated dynamically when duration is set
        # Connect timeline slider signals
        self.timeline_slider.valueChanged.connect(self.on_timeline_changed)
        self.timeline_slider.sliderPressed.connect(self.on_timeline_pressed)
        self.timeline_slider.sliderReleased.connect(self.on_timeline_released)
        timeline_layout.addWidget(self.timeline_slider)
        
        self.time_label = QLabel("00:00")
        self.time_label.setMinimumWidth(50)
        timeline_layout.addWidget(self.time_label)
        
        # Time input field for direct time entry
        from PySide6.QtWidgets import QLineEdit
        self.time_input = QLineEdit()
        self.time_input.setMaximumWidth(80)
        self.time_input.setPlaceholderText("MM:SS")
        self.time_input.setToolTip("Enter time in MM:SS format or seconds")
        self.time_input.returnPressed.connect(self.on_time_input_entered)
        timeline_layout.addWidget(self.time_input)
        
        layout.addLayout(timeline_layout)
        
    def set_video(self, video_path: str):
        """Set the current video for preview"""
        # Edge case: empty or invalid path
        if not video_path:
            self.app_state.log("No video file specified", "WARN")
            return
        
        # Edge case: file doesn't exist
        if not os.path.exists(video_path):
            self.app_state.log(f"Video file not found: {video_path}", "ERROR")
            return
        
        # Stop any current playback
        if self.is_playing:
            self.on_stop_clicked()
        
        self.current_video_path = video_path
        
        # Set up dual-view layout using stacked layouts
        # Original panel: show QVideoWidget (index 1), hide placeholder label (index 0)
        self.original_container.layout().setCurrentIndex(1)
        self._video_widget.update()
        
        # Processed panel: show FilterOverlay (index 1), hide placeholder label (index 0)
        self.processed_container.layout().setCurrentIndex(1)
        self.filter_overlay.update()
        
        # Load video into QMediaPlayer for smooth playback
        self._video_player.load_file(video_path)
        self._video_player.set_volume(self._audio_volume)
        
        # Seek to beginning to show first frame
        self._video_player.seek(0)
        
        # Log for debugging
        self.app_state.log(f"Video loaded: {video_path}", "INFO")
        
        # Get video duration from QMediaPlayer (faster than ffprobe)
        # Duration will be available via duration_changed signal
        # Also try ffprobe as fallback
        self.load_video_metadata(video_path)
        
        # Load initial frame for processed preview (FFmpeg frame capture)
        self.seek_preview(0)
        
    def clear_video(self):
        """Clear the current video and reset the preview"""
        # Stop any current playback
        if self.is_playing:
            self.on_stop_clicked()
        
        # Stop and cleanup video player
        self._video_player.cleanup()
        
        # Reset state
        self.current_video_path = None
        self.duration = 0.0
        self.current_frame = None
        self._playback_time = 0.0
        
        # Reset timeline
        self.timeline_slider.set_duration(0)
        self.timeline_slider.setValue(0)
        self.time_label.setText("00:00")
        
        # Reset view: show placeholder labels (index 0) using stacked layout
        self.original_container.layout().setCurrentIndex(0)
        self.processed_container.layout().setCurrentIndex(0)
        self.filter_overlay.clear()
        
        # Clear any pending frame loader
        self._cleanup_thread()
        
    def _on_video_position_changed(self, position_sec: float):
        """Handle video player position change - update timeline and processed preview"""
        # Skip if user is manually seeking (prevents feedback loop)
        if self._is_user_seeking:
            return
        
        self._playback_time = position_sec
        
        # Update timeline slider
        if self.duration > 0:
            slider_value = self.timeline_slider.time_to_value(position_sec)
            self.timeline_slider.setValue(slider_value)
            
            # Update time label
            mins, secs = divmod(int(position_sec), 60)
            hours = mins // 60
            mins = mins % 60
            if hours > 0:
                time_str = f"{hours}:{mins:02d}:{secs:02d}"
            else:
                time_str = f"{mins:02d}:{secs:02d}"
            self.time_label.setText(time_str)
    
    def _video_duration_changed(self, duration_sec: float):
        """Handle video player duration change"""
        if duration_sec > 0 and duration_sec != self.duration:
            self.duration = duration_sec
            self.timeline_slider.set_duration(self.duration)
            self.app_state.log(f"Video duration (QMediaPlayer): {self.duration:.2f}s", "INFO")
            
            # Check if this might be an audio-only file (very short duration with certain extensions)
            # Audio files might show as having duration but no video track
            if self.current_video_path:
                ext = os.path.splitext(self.current_video_path)[1].lower()
                audio_exts = ['.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.wma']
                if ext in audio_exts:
                    self.app_state.log("Audio-only file detected - video preview may not work", "WARN")
    
    def _video_state_changed(self, state: str):
        """Handle video player state change"""
        if state == "stopped" and self.is_playing:
            # Video finished playing
            self.on_pause_clicked()
            self.app_state.log("Playback finished", "INFO")
    
    def _on_video_error(self, error_msg: str):
        """Handle video player errors"""
        # Check for specific error types and handle gracefully
        if "Unsupported" in error_msg or "Format" in error_msg:
            self.app_state.log(f"Unsupported video format: {error_msg}", "WARN")
            # Show user-friendly message
            self.app_state.log("Try using a different video format (MP4, MKV, AVI)", "INFO")
        elif "Not Found" in error_msg or "404" in error_msg:
            self.app_state.log(f"Video file not found: {error_msg}", "ERROR")
        elif "Access" in error_msg or "Denied" in error_msg:
            self.app_state.log(f"Cannot access video file: {error_msg}", "ERROR")
        else:
            self.app_state.log(f"Video error: {error_msg}", "WARN")
    
    def _on_frame_captured(self, frame: QImage):
        """
        Handle captured frame from QMediaPlayer.
        Apply filters and update the overlay display.
        """
        if frame.isNull():
            return
        
        # Apply filters to the captured frame
        processed = self.apply_filters(frame)
        
        # Get current subtitle text
        sub_text = self._get_current_subtitle()
        
        # Update filter overlay with processed frame and subtitle
        self.filter_overlay.set_image(processed)
        self.filter_overlay.set_subtitle(sub_text)
    
    def _update_filter_overlay(self):
        """
        Timer callback to update the filter overlay.
        This is called periodically during playback to refresh the preview.
        Uses FFmpeg as fallback if QVideoSink doesn't work.
        """
        # First try to get frame from QVideoSink
        last_frame = self._video_player.get_last_frame()
        
        if last_frame is not None and not last_frame.isNull():
            # QVideoSink is working - use captured frame
            self._on_frame_captured(last_frame)
        else:
            # QVideoSink not working - use FFmpeg fallback
            current_pos = self._video_player.get_position()
            # Use seek_preview to get frame via FFmpeg
            self.seek_preview(current_pos)
    
    def _get_current_subtitle(self) -> str:
        """Get subtitle text for current playback position"""
        if not self.app_state.subtitles.burn_subs or not self.current_video_path:
            return ""
        
        # Look for external subtitle file
        base = os.path.splitext(self.current_video_path)[0]
        sub_path = None
        for ext in [".srt", ".ass", ".ssa", ".sub"]:
            test_path = base + ext
            if os.path.exists(test_path):
                sub_path = test_path
                break
        
        if not sub_path:
            return ""
        
        # Get subtitle for current timestamp
        timestamp = self._playback_time
        return get_subtitle_text(sub_path, timestamp)
        
    def load_video_metadata(self, video_path: str):
        """Load video metadata using ffprobe"""
        ffprobe_path = self.app_state.ffprobe_path
        
        # Check if this is a DVD concat source
        is_dvd_source = self.app_state.dvd.is_dvd_source and video_path.endswith('.txt')
        
        cmd = [ffprobe_path, "-v", "error"]
        
        # Add concat demuxer for DVD sources (must come before -i)
        if is_dvd_source:
            cmd.extend(["-f", "concat", "-safe", "0"])
        
        # Add input file
        cmd.extend(["-i", video_path])
        
        cmd.extend([
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1"
        ])
        
        try:
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=30  # Increased timeout for DVD
            )
            if result.returncode == 0 and result.stdout.strip() and result.stdout.strip() != 'N/A':
                self.duration = float(result.stdout.strip())
                self.app_state.log(f"Video duration: {self.duration:.2f}s", "INFO")
                # Update slider range for precise positioning
                self.timeline_slider.set_duration(self.duration)
            else:
                # Fallback: try to get duration from DVD state if available
                if is_dvd_source and self.app_state.dvd.available_titles:
                    for title in self.app_state.dvd.available_titles:
                        if title.title_number == self.app_state.dvd.selected_title_number:
                            self.duration = title.duration
                            self.app_state.log(f"Using DVD title duration: {self.duration:.2f}s", "INFO")
                            # Update slider range for precise positioning
                            self.timeline_slider.set_duration(self.duration)
                            return
                self.app_state.log(f"Could not determine video duration", "WARN")
        except Exception as e:
            self.app_state.log(f"Failed to get video duration: {e}", "WARN")
            self.duration = 0.0
            
    def on_timeline_changed(self, value):
        """Handle timeline slider change while dragging"""
        if self.duration > 0:
            timestamp = self.timeline_slider.value_to_time(value)
            mins, secs = divmod(int(timestamp), 60)
            hours = mins // 60
            mins = mins % 60
            if hours > 0:
                time_str = f"{hours}:{mins:02d}:{secs:02d}"
            else:
                time_str = f"{mins:02d}:{secs:02d}"
            self.time_label.setText(time_str)
            # Update input field to match
            self.time_input.setText(time_str)
            
            # Seek video in real-time while dragging (if user is seeking)
            if self._is_user_seeking:
                self._video_player.seek(timestamp)
                self._playback_time = timestamp
                # Also update the processed preview via FFmpeg
                self.seek_preview(timestamp)
    
    def on_time_input_entered(self):
        """Handle time input field entry"""
        if self.duration <= 0:
            return
            
        text = self.time_input.text().strip()
        if not text:
            return
            
        try:
            # Try parsing as MM:SS or HH:MM:SS
            parts = text.split(':')
            if len(parts) == 1:
                # Just seconds
                seconds = float(parts[0])
            elif len(parts) == 2:
                # MM:SS
                mins = int(parts[0])
                secs = int(parts[1])
                seconds = mins * 60 + secs
            elif len(parts) == 3:
                # HH:MM:SS
                hours = int(parts[0])
                mins = int(parts[1])
                secs = int(parts[2])
                seconds = hours * 3600 + mins * 60 + secs
            else:
                raise ValueError("Invalid time format")
            
            # Clamp to valid range
            seconds = max(0, min(seconds, self.duration))
            
            # Update slider position using dynamic range
            slider_value = self.timeline_slider.time_to_value(seconds)
            self.timeline_slider.setValue(slider_value)
            
            # Seek to that position
            self.seek_preview(seconds)
            
        except ValueError:
            self.app_state.log(f"Invalid time format: {text}. Use MM:SS or seconds", "WARN")
            
    def on_timeline_pressed(self):
        """Handle timeline slider press - start real-time seeking"""
        self._is_user_seeking = True
        
        # Pause overlay updates during seeking to prevent flicker
        self._overlay_timer.stop()
    
    def on_timeline_released(self):
        """Handle timeline slider release - finalize seek and resume playback"""
        # Clear the seeking flag
        self._is_user_seeking = False
        
        if self.current_video_path and self.duration > 0:
            value = self.timeline_slider.value()
            timestamp = self.timeline_slider.value_to_time(value)
            
            # Use QMediaPlayer for smooth seeking
            self._video_player.seek(timestamp)
            # Update filter overlay immediately after seeking (for dual-view)
            self._update_filter_overlay()
            
            # Sync playback time
            self._playback_time = timestamp
            
            # Resume overlay timer if playing
            if self.is_playing:
                self._overlay_timer.start()
            
    def get_current_timestamp(self):
        """Get the current timeline position in seconds"""
        if self.duration > 0:
            value = self.timeline_slider.value()
            return self.timeline_slider.value_to_time(value)
        return 0.0
    
    def update_cut_markers(self, cut_points: list):
        """
        Update the cut point markers on the timeline
        Args:
            cut_points: List of (position_seconds, cut_id) tuples
        """
        self.timeline_slider.set_cut_points(cut_points, self.duration)
            
    def seek_preview(self, timestamp: float):
        """Seek to specific timestamp and update preview"""
        if not self.current_video_path:
            return
            
        # Cancel any pending load and clean up previous thread
        self._cleanup_thread()
        
        # Check if this is a DVD source
        is_dvd_source = self.app_state.dvd.is_dvd_source and self.current_video_path.endswith('.txt')
        
        # Get first VOB path for DVD preview fallback
        first_vob_path = None
        if is_dvd_source and self.app_state.dvd.available_titles:
            for title in self.app_state.dvd.available_titles:
                if title.title_number == self.app_state.dvd.selected_title_number:
                    if title.vob_files:
                        first_vob_path = title.vob_files[0]
                    break
            
        # Create new loader thread
        self._loader_thread = QThread()
        self._frame_loader = FrameLoader()
        self._frame_loader.moveToThread(self._loader_thread)
        
        # Connect signals
        self._frame_loader.frame_loaded.connect(self.on_frame_loaded)
        self._frame_loader.error_occurred.connect(self.on_frame_error)
        self._loader_thread.started.connect(
            lambda: self._frame_loader.load_frame(
                self.current_video_path, timestamp, self.app_state.ffmpeg_path, is_dvd_source, first_vob_path
            )
        )
        
        # Start loading
        self._loader_thread.start()
        
    def _cleanup_thread(self):
        """Clean up the loader thread safely"""
        if self._frame_loader:
            self._frame_loader.cancel()
            
        if self._loader_thread:
            if self._loader_thread.isRunning():
                self._loader_thread.quit()
                self._loader_thread.wait(1000)  # Wait up to 1 second
            self._loader_thread = None
            self._frame_loader = None
        
    def on_frame_loaded(self, image: QImage):
        """Handle loaded frame"""
        self.current_frame = image
        
        # Display original
        self.display_image(self.original_label, image)
        
        # Apply filters and update the filter overlay (not the hidden label)
        processed = self.apply_filters(image)
        sub_text = self._get_current_subtitle()
        self.filter_overlay.set_image(processed)
        self.filter_overlay.set_subtitle(sub_text)
        
        # Debug log to trace processed preview
        self.app_state.log(f"Preview updated: original={image.width()}x{image.height()}, processed={processed.width()}x{processed.height()}", "DEBUG")
        
        # Clean up thread
        self._cleanup_thread()
            
    def on_frame_error(self, error_msg: str):
        """Handle frame loading error"""
        self.app_state.log(f"Preview error: {error_msg}", "WARN")
        
        # Clean up thread
        self._cleanup_thread()
            
    def display_image(self, label: QLabel, image: QImage):
        """Display QImage in QLabel, scaled to fit"""
        if image.isNull():
            return
            
        # Scale to fit label while maintaining aspect ratio
        pixmap = QPixmap.fromImage(image)
        scaled = pixmap.scaled(
            label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        label.setPixmap(scaled)
        
    def apply_filters(self, image: QImage) -> QImage:
        """
        Apply preview filters to image.
        Uses FFmpeg eq filter for color correction preview.
        """
        # Build filter chain
        filters = []
        
        # EQ (Color Correction)
        if self.app_state.eq.enabled:
            eq_params = []
            if self.app_state.eq.brightness != 0:
                eq_params.append(f"brightness={self.app_state.eq.brightness}")
            if self.app_state.eq.contrast != 1.0:
                eq_params.append(f"contrast={self.app_state.eq.contrast}")
            if self.app_state.eq.saturation != 1.0:
                eq_params.append(f"saturation={self.app_state.eq.saturation}")
            if self.app_state.eq.gamma != 1.0:
                eq_params.append(f"gamma={self.app_state.eq.gamma}")
            if self.app_state.eq.gamma_r != 1.0:
                eq_params.append(f"gamma_r={self.app_state.eq.gamma_r}")
            if self.app_state.eq.gamma_g != 1.0:
                eq_params.append(f"gamma_g={self.app_state.eq.gamma_g}")
            if self.app_state.eq.gamma_b != 1.0:
                eq_params.append(f"gamma_b={self.app_state.eq.gamma_b}")
                
            if eq_params:
                filters.append(f"eq={':'.join(eq_params)}")
        
        # White Balance (colorbalance filter)
        if self.app_state.eq.white_balance_enabled:
            wb_params = []
            
            # Shadows
            if self.app_state.eq.wb_shadows_r != 0:
                wb_params.append(f"rs={self.app_state.eq.wb_shadows_r}")
            if self.app_state.eq.wb_shadows_g != 0:
                wb_params.append(f"gs={self.app_state.eq.wb_shadows_g}")
            if self.app_state.eq.wb_shadows_b != 0:
                wb_params.append(f"bs={self.app_state.eq.wb_shadows_b}")
            
            # Midtones
            if self.app_state.eq.wb_midtones_r != 0:
                wb_params.append(f"rm={self.app_state.eq.wb_midtones_r}")
            if self.app_state.eq.wb_midtones_g != 0:
                wb_params.append(f"gm={self.app_state.eq.wb_midtones_g}")
            if self.app_state.eq.wb_midtones_b != 0:
                wb_params.append(f"bm={self.app_state.eq.wb_midtones_b}")
            
            # Highlights
            if self.app_state.eq.wb_highlights_r != 0:
                wb_params.append(f"rh={self.app_state.eq.wb_highlights_r}")
            if self.app_state.eq.wb_highlights_g != 0:
                wb_params.append(f"gh={self.app_state.eq.wb_highlights_g}")
            if self.app_state.eq.wb_highlights_b != 0:
                wb_params.append(f"bh={self.app_state.eq.wb_highlights_b}")
            
            if wb_params:
                filters.append(f"colorbalance={':'.join(wb_params)}")
        
        # Get subtitle text BEFORE processing with FFmpeg (we need the timestamp)
        sub_text = ""
        sub_path = None
        if self.app_state.subtitles.burn_subs and self.current_video_path:
            # Look for external subtitle file
            base = os.path.splitext(self.current_video_path)[0]
            for ext in [".srt", ".ass", ".ssa", ".sub"]:
                test_path = base + ext
                if os.path.exists(test_path):
                    sub_path = test_path
                    break
            
        if not filters:
            # No FFmpeg filters to apply, just draw subtitles if needed
            if sub_path and self.app_state.subtitles.burn_subs and self.duration > 0:
                value = self.timeline_slider.value()
                timestamp = self.timeline_slider.value_to_time(value)
                sub_text = get_subtitle_text(sub_path, timestamp)
                if sub_text:
                    self.app_state.log(f"Preview: Drawing subtitle at {timestamp:.1f}s: {sub_text[:50]}...", "DEBUG")
                    return self.draw_subtitle_on_image(image.copy(), sub_text)
            return image.copy()
            
        # Use FFmpeg to apply filters
        filter_str = ",".join(filters)
        
        try:
            # Convert QImage to bytes using QBuffer
            buffer = QBuffer()
            buffer.open(QBuffer.ReadWrite)
            image.save(buffer, "PNG")
            image_bytes = bytes(buffer.data())
            buffer.close()
            
            # Apply filter using FFmpeg
            cmd = [
                self.app_state.ffmpeg_path,
                "-i", "-",  # Read from stdin
                "-vf", filter_str,
                "-f", "image2pipe",
                "-vcodec", "png",
                "-"
            ]
            
            self.app_state.log(f"Preview filter: {filter_str}", "DEBUG")
            
            result = subprocess.run(
                cmd, input=image_bytes,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=5
            )
            
            if result.returncode != 0:
                stderr = result.stderr.decode('utf-8', errors='ignore') if result.stderr else "Unknown error"
                self.app_state.log(f"FFmpeg filter error: {stderr[:200]}", "WARN")
            
            if result.returncode == 0 and result.stdout:
                processed = QImage()
                processed.loadFromData(result.stdout, "PNG")
                if not processed.isNull():
                    image = processed
            else:
                self.app_state.log(f"Filter failed, returning original image", "WARN")
                    
        except Exception as e:
            self.app_state.log(f"Filter preview error: {e}", "WARN")
        
        # Get subtitle text for current timestamp and draw it
        if sub_path and self.app_state.subtitles.burn_subs and self.duration > 0:
            value = self.timeline_slider.value()
            timestamp = self.timeline_slider.value_to_time(value)
            sub_text = get_subtitle_text(sub_path, timestamp)
            if sub_text:
                self.app_state.log(f"Preview: Drawing subtitle at {timestamp:.1f}s: {sub_text[:50]}...", "DEBUG")
                image = self.draw_subtitle_on_image(image, sub_text)
        
        return image
    
    def draw_subtitle_on_image(self, image: QImage, text: str) -> QImage:
        """Draw subtitle text on the image using QPainter"""
        # Create a copy of the image to draw on
        result = image.copy()
        painter = QPainter(result)
        
        # Get subtitle settings
        subs = self.app_state.subtitles
        
        # Set up font (use pixel size to match FFmpeg)
        font = QFont(subs.font)
        font.setPixelSize(subs.size)
        painter.setFont(font)
        
        # Calculate text rect
        metrics = painter.fontMetrics()
        lines = text.split('\n')
        max_width = max(metrics.horizontalAdvance(line) for line in lines)
        total_height = metrics.height() * len(lines)
        
        # Position based on settings
        img_width = result.width()
        img_height = result.height()
        
        x = (img_width - max_width) // 2  # Center horizontally
        
        if subs.position == "bottom":
            y = img_height - 20 - total_height + subs.vertical_offset
        elif subs.position == "top":
            y = 20 + metrics.height() - subs.vertical_offset
        else:  # center
            y = (img_height - total_height) // 2
        
        # Draw shadow if enabled (drawn first, behind everything)
        if subs.shadow_enabled and subs.shadow_opacity > 0:
            shadow_color = QColor(subs.shadow_color)
            shadow_color.setAlpha(int(subs.shadow_opacity * 255))
            shadow_x = x + subs.shadow_offset_x
            shadow_y = y + subs.shadow_offset_y
            painter.setPen(shadow_color)
            painter.drawText(shadow_x, shadow_y, max_width, total_height,
                           Qt.AlignLeft | Qt.AlignTop, text)
        
        # Draw background if opacity > 0
        if subs.bg_opacity > 0:
            bg_color = QColor(subs.bg_color)
            bg_color.setAlpha(int(subs.bg_opacity * 255))
            painter.fillRect(x - 10, y - metrics.height() + 5,
                           max_width + 20, total_height + 10, bg_color)
        
        # Draw outline
        outline_color = QColor(subs.outline_color)
        text_color = QColor(subs.color)
        
        # Draw text with simple outline effect
        for dx in range(-subs.outline_width, subs.outline_width + 1):
            for dy in range(-subs.outline_width, subs.outline_width + 1):
                if dx != 0 or dy != 0:
                    painter.setPen(outline_color)
                    painter.drawText(x + dx, y + dy, max_width, total_height,
                                   Qt.AlignLeft | Qt.AlignTop, text)
        
        # Draw main text
        painter.setPen(text_color)
        painter.drawText(x, y, max_width, total_height,
                        Qt.AlignLeft | Qt.AlignTop, text)
        
        painter.end()
        return result
        
    def refresh_preview(self):
        """Refresh preview with current settings"""
        if self.current_video_path and self.duration > 0:
            value = self.timeline_slider.value()
            timestamp = self.timeline_slider.value_to_time(value)
            self.seek_preview(timestamp)
            
    def resizeEvent(self, event):
        """Handle resize - rescale images"""
        super().resizeEvent(event)
        # Update container sizes to match new dimensions
        if self.original_container:
            self.original_container.setMinimumSize(self.preview_width, self.preview_height)
        if self.processed_container:
            self.processed_container.setMinimumSize(self.preview_width, self.preview_height)
        
        if self.current_frame and not self.current_frame.isNull():
            self.display_image(self.original_label, self.current_frame)
            processed = self.apply_filters(self.current_frame)
            sub_text = self._get_current_subtitle()
            self.filter_overlay.set_image(processed)
            self.filter_overlay.set_subtitle(sub_text)
            
    def on_play_clicked(self):
        """Handle play button click - use QMediaPlayer for smooth playback"""
        if not self.current_video_path or self.duration <= 0:
            return
        
        # Use QMediaPlayer for smooth playback
        # Dual-view: both panels already showing correct widgets via stacked layout
        # Just ensure they are set to video/overlay (index 1)
        self.original_container.layout().setCurrentIndex(1)
        self.processed_container.layout().setCurrentIndex(1)
        
        # Seek to current position first
        value = self.timeline_slider.value()
        position = self.timeline_slider.value_to_time(value)
        self._video_player.seek(position)
        
        # Start playback
        self._video_player.play()
        
        # Start overlay update timer (for filter preview updates)
        self._overlay_timer.start()
        
        self.is_playing = True
        self.play_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.app_state.log(f"Smooth playback started at {self.playback_speed}x speed", "INFO")
        
    def on_speed_changed(self, speed_text):
        """Handle playback speed change"""
        # Parse speed from text like "1.0x"
        speed = float(speed_text.replace('x', ''))
        self.playback_speed = speed
        
        # Use QMediaPlayer's playback rate for smooth playback
        self._video_player.set_playback_rate(speed)
        self.app_state.log(f"Playback speed changed to {self.playback_speed}x", "INFO")
    
    def on_size_changed(self, size_text):
        """Handle preview size change"""
        sizes = {
            "Small": (320, 180),
            "Medium": (480, 270)
        }
        w, h = sizes.get(size_text, (320, 180))
        self.preview_width = w
        self.preview_height = h
        
        # Update container sizes
        self.original_container.setMinimumSize(w, h)
        self.processed_container.setMinimumSize(w, h)
        
        # Update widget sizes
        self.original_label.setMinimumSize(w, h)
        self.processed_label.setMinimumSize(w, h)
        self.filter_overlay.setMinimumSize(w, h)
        self._video_widget.setMinimumSize(w, h)
        
        self.original_group.setMinimumHeight(h + 30)
        self.processed_group.setMinimumHeight(h + 30)
        self.split.setMinimumHeight(h + 40)
        
        self.setMinimumHeight(h + 180)
        
    def on_pause_clicked(self):
        """Handle pause button click"""
        self.is_playing = False
        
        # Clear seeking flag
        self._is_user_seeking = False
        
        # Stop overlay timer
        self._overlay_timer.stop()
        
        # Use QMediaPlayer for smooth playback
        self._video_player.pause()
        
        self.play_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.app_state.log("Playback paused", "INFO")
        
    def on_stop_clicked(self):
        """Handle stop button click - reset to beginning"""
        self.is_playing = False
        
        # Clear seeking flag
        self._is_user_seeking = False
        
        # Stop overlay timer
        self._overlay_timer.stop()
        
        # Use QMediaPlayer for smooth playback
        self._video_player.stop()
        # Dual-view: Keep both panels showing video/overlay (index 1)
        # This shows the last frame
        self.original_container.layout().setCurrentIndex(1)
        self.processed_container.layout().setCurrentIndex(1)
        
        # Reset to beginning
        self._playback_time = 0.0
        self.timeline_slider.setValue(0)
        self.seek_preview(0)
        
        self.play_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.app_state.log("Playback stopped", "INFO")
        
    def on_volume_changed(self, value: int):
        """Handle volume slider change"""
        self._audio_volume = value / 100.0
        
        # Update video player volume
        self._video_player.set_volume(self._audio_volume)
        
        # Update mute button icon
        if value == 0:
            self.mute_btn.setText("🔇")
        else:
            self.mute_btn.setText("🔊")
            
    def on_mute_clicked(self):
        """Handle mute button click"""
        # Toggle mute on video player
        is_muted = self._video_player.is_muted()
        self._video_player.set_muted(not is_muted)
        
        if not is_muted:
            self.mute_btn.setText("🔇")
        else:
            self.mute_btn.setText("🔊")
