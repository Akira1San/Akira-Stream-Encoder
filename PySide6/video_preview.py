"""
Video Preview Component - Handles real-time preview functionality (PySide6)
Uses native Qt (QImage, QPixmap) instead of PIL/Pillow
"""
import io
import os
import re
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
        self.deleted_segments = []  # List of (start_time, end_time) tuples
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
    
    def set_deleted_segments(self, deleted_segments: list):
        """
        Set deleted segments to display (regions that will be removed in final output)
        Args:
            deleted_segments: List of (start_time, end_time) tuples
        """
        self.deleted_segments = deleted_segments
        self.update()
    
    def clear_deleted_segments(self):
        """Clear all deleted segment markers"""
        self.deleted_segments = []
        self.update()
    
    def clear_cut_points(self):
        """Clear all cut markers"""
        self.cut_points = []
        self.update()
    
    def paintEvent(self, event):
        """Override paintEvent to draw cut markers and deleted segments"""
        # Call parent paintEvent first (draws slider handle and groove)
        super().paintEvent(event)
        
        if self.duration <= 0:
            return
        
        # Create painter
        painter = QPainter(self)
        
        # Draw deleted segments first (as red background regions)
        if self.deleted_segments:
            for seg_start, seg_end in self.deleted_segments:
                if seg_start >= seg_end:
                    continue
                
                start_x = self._value_to_pixel(self.time_to_value(seg_start))
                end_x = self._value_to_pixel(self.time_to_value(seg_end))
                
                # Draw semi-transparent red overlay
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(200, 50, 50, 100))  # Red with alpha
                width = max(4, int(end_x - start_x))
                painter.drawRect(int(start_x), 0, width, self.height())
        
        # Draw cut point markers
        if self.cut_points:
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
        
    def load_frame(self, video_path: str, timestamp: float, backend, is_dvd_source: bool = False, first_vob_path: str = None, subtitle_filter: str = "", max_size: tuple = None, extra_video_filter: str = "", extra_image_paths: list = None):
        """Load a frame from video at specified timestamp using backend"""
        self._cancelled = False
        self._is_dvd_source = is_dvd_source

        data = backend.capture_frame(video_path, timestamp, subtitle_filter, is_dvd_source, first_vob_path, max_size, extra_video_filter, extra_image_paths)

        if self._cancelled:
            return

        if data:
            image = QImage()
            image.loadFromData(data, "PNG")
            if not image.isNull():
                self.frame_loaded.emit(image)
                return
            self.error_occurred.emit("Failed to decode image")
        else:
            self.error_occurred.emit("Frame extraction failed")
            
    def cancel(self):
        """Cancel the current operation"""
        self._cancelled = True


class FilterOverlay(QWidget):
    """
    Overlay widget that displays processed video frames with filters and subtitles.
    Supports GIMP-style split preview (original on left, processed on right).
    Sits on top of the video widget and displays filtered preview.
    """
    
    def __init__(self, app_state=None, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        
        # Current processed frame to display
        self._current_image: Optional[QImage] = None
        self._original_image: Optional[QImage] = None
        self._subtitle_text: str = ""
        self._frozen: bool = False
        self._split_enabled: bool = False
        
        # Video dimensions for font scaling
        self._video_width: int = 1920
        self._video_height: int = 1080
    
    def set_split_enabled(self, enabled: bool):
        """Enable or disable 50/50 split preview (original | processed)"""
        self._split_enabled = enabled
        self.update()
    
    def set_frozen(self, frozen: bool):
        """Set frozen state - shows message that preview is paused during playback"""
        self._frozen = frozen
        self.update()
    
    def set_video_size(self, width: int, height: int):
        """Set video dimensions for proper font scaling"""
        if width > 0 and height > 0:
            self._video_width = width
            self._video_height = height
    
    def set_image(self, image: QImage):
        """Set the processed frame to display"""
        if not image.isNull():
            self._current_image = image.copy()
            # Auto-detect video size from image if not set
            if self._video_width == 1920 and self._video_height == 1080:
                self._video_width = image.width()
                self._video_height = image.height()
            self.update()
    
    def set_original_image(self, image: QImage):
        """Set the original (unfiltered) frame for split preview"""
        if not image.isNull():
            self._original_image = image.copy()
            self.update()
    
    def set_subtitle(self, text: str):
        """Set subtitle text to display"""
        self._subtitle_text = text
        self.update()
    
    def clear(self):
        """Clear the overlay"""
        self._current_image = None
        self._original_image = None
        self._subtitle_text = ""
        self.update()
    
    def draw_subtitle_on_image(self, image: QImage, text: str) -> QImage:
        """Draw subtitle text on the image using QPainter"""
        # Create a copy of the image to draw on
        result = image.copy()
        painter = QPainter(result)
        
        # Get subtitle settings
        subs = self.app_state.subtitles
        
        # Calculate font scale - image is displayed at preview size (320x180)
        # so we need to scale font up proportionally
        img_width = result.width()
        img_height = result.height()
        
        # Reference preview size
        ref_preview_width = 320
        ref_preview_height = 180
        
        # Scale font so it appears proportional after widget scaling
        # If video is 1920x960 and preview is 320x180, scale by ~6x
        width_scale = img_width / ref_preview_width
        height_scale = img_height / ref_preview_height
        font_scale = min(width_scale, height_scale)
        
        # Set up font with scaled pixel size
        font = QFont(subs.font)
        scaled_size = max(int(subs.size * font_scale), 12)
        font.setPixelSize(scaled_size)
        painter.setFont(font)
        
        # Calculate text rect
        metrics = painter.fontMetrics()
        lines = text.split('\n')
        max_width = max(metrics.horizontalAdvance(line) for line in lines)
        total_height = metrics.height() * len(lines)
        
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
            painter.save()
            painter.setOpacity(subs.bg_opacity)
            bg_color = QColor(subs.bg_color)
            painter.fillRect(x - 10, y - metrics.height() + 5,
                           max_width + 20, total_height + 10, bg_color)
            painter.restore()
        
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
    
    def paintEvent(self, event):
        """Draw the processed frame and subtitle on the overlay.
        When split mode is on, shows original on left half and processed on right half
        with a vertical divider line in the middle."""
        super().paintEvent(event)
        
        if self._current_image is None or self._current_image.isNull():
            return
        
        painter = QPainter(self)
        w = self.width()
        h = self.height()
        mid_x = w // 2
        
        # Get processed image (with subtitles if present)
        processed = self._current_image
        if self._subtitle_text:
            processed = self.draw_subtitle_on_image(self._current_image.copy(), self._subtitle_text)
        
        if self._split_enabled and self._original_image is not None:
            # ---- Split mode: original left, processed right ----
            
            # Scale original to left half
            orig_pixmap = QPixmap.fromImage(self._original_image)
            orig_left = orig_pixmap.scaled(
                mid_x, h,
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation
            )
            painter.drawPixmap(0, 0, mid_x, h, orig_left)
            
            # Scale processed to right half
            proc_pixmap = QPixmap.fromImage(processed)
            proc_right = proc_pixmap.scaled(
                w - mid_x, h,
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation
            )
            painter.drawPixmap(mid_x, 0, w - mid_x, h, proc_right)
            
            # Draw vertical divider line
            painter.setPen(QPen(QColor(200, 200, 200), 2))
            painter.drawLine(mid_x, 0, mid_x, h)
            
            # Draw "Original" / "Processed" labels
            label_font = QFont("Arial", 9)
            painter.setFont(label_font)
            painter.setPen(QColor(220, 220, 220))
            painter.drawText(4, 4, mid_x - 4, 16,
                             Qt.AlignLeft | Qt.AlignVCenter, "Original")
            painter.drawText(mid_x + 4, 4, w - mid_x - 4, 16,
                             Qt.AlignRight | Qt.AlignVCenter, "Processed")
        else:
            # ---- Normal mode: full processed image ----
            pixmap = QPixmap.fromImage(processed)
            scaled = pixmap.scaled(
                self.size(),
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation
            )
            painter.drawPixmap(0, 0, scaled)
        
        if self._frozen:
            painter.setPen(QColor(128, 128, 128, 180))
            painter.setFont(QFont("Arial", 10))
            painter.drawText(self.rect(), Qt.AlignCenter,
                "Preview frozen during playback\nChanges apply on pause")
        
        painter.end()
    

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
        self._playable_duration: float = 0.0  # QMediaPlayer's actual seekable range (first VOB for DVD)
        self.current_frame: Optional[QImage] = None
        self.is_playing: bool = False
        self.playback_speed: float = 1.0  # 1.0 = normal speed
        self._playback_time: float = 0.0  # Current playback position in seconds
        
        # Deleted segments (will be removed in final output)
        self._deleted_segments: list = []
        
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
        
        # Refresh preview when media engine changes
        self.app_state.media_engine_changed.connect(self.refresh_preview)
        
        # Filter overlay timer for processed preview
        self._overlay_timer = QTimer(self)
        self._overlay_timer.setInterval(500)  # Update every 500ms (2 fps) - slower for FFmpeg fallback
        self._overlay_timer.timeout.connect(self._update_filter_overlay)
        
        # Current subtitle text for overlay
        self._current_subtitle: str = ""
        
        # Split preview toggle (GIMP-style 50/50 original|processed)
        self._split_preview: bool = False
        
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
        self.filter_overlay = FilterOverlay(self.app_state)
        self.filter_overlay.setMinimumSize(self.preview_width, self.preview_height)
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
        
        # Split preview toggle (GIMP-style 50/50)
        self.split_btn = QPushButton("⊞ Split")
        self.split_btn.setMaximumWidth(80)
        self.split_btn.setCheckable(True)
        self.split_btn.setChecked(False)
        self.split_btn.setToolTip("Toggle 50/50 split preview: original | processed")
        self.split_btn.toggled.connect(self.on_split_toggled)
        playback_layout.addWidget(self.split_btn)
        
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
        # For DVD sources, use the first VOB file (QMediaPlayer can't parse concat .txt)
        playback_path = video_path
        if self.app_state.dvd.is_dvd_source and video_path.endswith('.txt'):
            for title in self.app_state.dvd.available_titles:
                if title.title_number == self.app_state.dvd.selected_title_number:
                    if title.vob_files:
                        first_vob = title.vob_files[0]
                        if os.path.exists(first_vob):
                            playback_path = first_vob
                    break
        self._video_player.load_file(playback_path)
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
        self._deleted_segments = []
        
        # Reset timeline
        self.timeline_slider.set_duration(0)
        self.timeline_slider.setValue(0)
        self.time_label.setText("00:00")
        
        # Clear deleted segments display
        self.timeline_slider.deleted_segments = []
        
        # Reset view: show placeholder labels (index 0) using stacked layout
        self.original_container.layout().setCurrentIndex(0)
        self.processed_container.layout().setCurrentIndex(0)
        self.filter_overlay.clear()
        
        # Clear any pending frame loader
        self._cleanup_thread()
    
    def update_deleted_segments(self, deleted_segments: list):
        """Update the deleted segments for preview playback"""
        self._deleted_segments = deleted_segments
        self.timeline_slider.deleted_segments = deleted_segments
        self.timeline_slider.update()
    
    def clear_deleted_segments(self):
        """Clear deleted segments"""
        self._deleted_segments = []
        self.timeline_slider.deleted_segments = []
        self.timeline_slider.update()
    
    def _is_position_in_deleted_segment(self, position: float) -> bool:
        """Check if a position falls within any deleted segment"""
        for seg_start, seg_end in self._deleted_segments:
            if seg_start <= position < seg_end:
                return True
        return False
    
    def _get_next_valid_position(self, position: float) -> float:
        """Get the next position after any deleted segment"""
        for seg_start, seg_end in self._deleted_segments:
            if seg_start <= position < seg_end:
                return seg_end
        return position
        
    def _on_video_position_changed(self, position_sec: float):
        """Handle video player position change - update timeline and processed preview"""
        # Skip if user is manually seeking (prevents feedback loop)
        if self._is_user_seeking:
            return
        
        self._playback_time = position_sec
        
        # Skip deleted segments during playback
        if self._deleted_segments and self.is_playing:
            if self._is_position_in_deleted_segment(position_sec):
                # Jump past the deleted segment
                next_pos = self._get_next_valid_position(position_sec)
                self._video_player.seek(self._cap_seek(next_pos))
                self._playback_time = next_pos
                position_sec = next_pos
        
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
        # For DVD sources, QMediaPlayer only sees the first VOB file (~10 min),
        # so we store its actual seekable range separately but keep the full
        # title duration (from load_video_metadata) for the timeline display.
        if self.app_state.dvd.is_dvd_source:
            if duration_sec > 0:
                self._playable_duration = duration_sec
                self.app_state.log(f"Video player duration (first VOB): {duration_sec:.2f}s", "INFO")
            return
        if duration_sec > 0 and duration_sec != self.duration:
            self.duration = duration_sec
            self._playable_duration = duration_sec
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
        if frame.isNull() or self.is_playing:
            return

        # Downscale to preview size for performance
        original = frame.scaled(
            self.preview_width, self.preview_height,
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        # Apply filters to the captured frame
        processed = self.apply_filters(original)
        
        # Get current subtitle text
        sub_text = self._get_current_subtitle()
        
        # Update filter overlay with both original and processed frames
        self.filter_overlay.set_original_image(original)
        self.filter_overlay.set_image(processed)
        self.filter_overlay.set_subtitle(sub_text)
    
    def _update_filter_overlay(self):
        """
        Timer callback to update the filter overlay.
        Uses FFmpeg as fallback if QVideoSink doesn't work.
        During playback the overlay is frozen — skip FFmpeg fallback entirely.
        """
        if self.is_playing:
            return

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
        
        # Check user-selected subtitle file first
        sub_path = None
        selected = self.app_state.subtitles.selected_subtitle
        if selected and os.path.exists(selected):
            sub_path = selected
        
        # Fall back to auto-detect by basename
        if not sub_path:
            base = os.path.splitext(self.current_video_path)[0]
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
    
    def _find_subtitle_file(self) -> Optional[str]:
        """Find the subtitle file to use for preview burning"""
        if not self.app_state.subtitles.burn_subs:
            return None
        
        # Check user-selected subtitle file
        selected = self.app_state.subtitles.selected_subtitle
        if selected and os.path.exists(selected):
            return selected
        
        if not self.current_video_path:
            return None
        
        # Auto-detect by basename
        base = os.path.splitext(self.current_video_path)[0]
        for ext in [".srt", ".ass", ".ssa", ".sub"]:
            test_path = base + ext
            if os.path.exists(test_path):
                return test_path
        return None
    
    def _hex_to_ass(self, hex_color: str, opacity: float = 1.0) -> str:
        """Convert hex color to ASS format (&HAABBGGRR)"""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        alpha = 255 - int(opacity * 255)
        return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"
    
    def _build_subtitle_filter_string(self, sub_path: str) -> str:
        """Build FFmpeg subtitle filter string for preview with user styling"""
        subs = self.app_state.subtitles
        
        # Escape path for FFmpeg filter syntax
        escaped_path = sub_path.replace("\\", "/").replace("'", "'\\''")
        escaped_path = escaped_path.replace("[", "\\[").replace("]", "\\]")
        escaped_path = re.sub(r'^([A-Z]):/', r'\1\:/', escaped_path, flags=re.IGNORECASE)
        
        # For VobSub files - bitmap-based, no force_style supported
        if sub_path.lower().endswith('.sub'):
            return f"subtitles='{escaped_path}':original_size=720x576"
        
        # Build force_style options for text-based subtitles (SRT/ASS)
        style = []
        
        if subs.font != "Arial":
            style.append(f"Fontname={subs.font}")
        style.append(f"Fontsize={subs.size}")
        if subs.color != "#FFFFFF":
            style.append(f"PrimaryColour={self._hex_to_ass(subs.color)}")
        if subs.outline_color != "#000000":
            style.append(f"OutlineColour={self._hex_to_ass(subs.outline_color)}")
        if subs.outline_width != 2:
            style.append(f"Outline={subs.outline_width}")
        
        # Shadow and background settings
        if subs.shadow_enabled and subs.bg_opacity > 0.0:
            shadow_ass = self._hex_to_ass(subs.shadow_color, subs.shadow_opacity)
            style.append(f"BackColour={shadow_ass}")
            style.append("BorderStyle=3")
            shadow_distance = max(subs.shadow_offset_x, subs.shadow_offset_y, 2)
            style.append(f"Shadow={shadow_distance}")
        elif subs.shadow_enabled:
            style.append("BorderStyle=2")
            outline_ass = self._hex_to_ass(subs.shadow_color, subs.shadow_opacity)
            style.append(f"OutlineColour={outline_ass}")
            shadow_distance = max(subs.shadow_offset_x, subs.shadow_offset_y, 2)
            style.append(f"Shadow={shadow_distance}")
        elif subs.bg_opacity > 0.0:
            ass_bg = self._hex_to_ass(subs.bg_color, subs.bg_opacity)
            style.append(f"BackColour={ass_bg}")
            style.append("BorderStyle=4")
        else:
            style.append("BorderStyle=1")
        
        if subs.shadow_enabled and subs.outline_width == 0:
            style.append("Outline=1")
        
        pos_map = {"bottom": 2, "top": 8, "center": 10}
        if subs.position != "bottom":
            style.append(f"Alignment={pos_map.get(subs.position, 2)}")
        
        if subs.vertical_offset > 0:
            if subs.position == "bottom":
                margin_v = max(0, 20 - subs.vertical_offset)
                style.append(f"MarginV={margin_v}")
            else:
                style.append(f"MarginV={subs.vertical_offset}")
        
        force_style = f":force_style='{','.join(style)}'" if style else ""
        return f"subtitles='{escaped_path}'{force_style}"
    
    def _build_dvd_subtitle_filter(self, vob_path: str, sub_idx: int) -> str:
        return ""
    
    def load_video_metadata(self, video_path: str):
        """Load video metadata using backend"""
        is_dvd_source = self.app_state.dvd.is_dvd_source and video_path.endswith('.txt')
        try:
            duration = self.app_state.backend.get_duration(video_path)
            if duration and duration > 0:
                self.duration = duration
                if not is_dvd_source:
                    self._playable_duration = duration
                self.app_state.log(f"Video duration: {self.duration:.2f}s", "INFO")
                self.timeline_slider.set_duration(self.duration)
                return
        except Exception as e:
            self.app_state.log(f"Backend duration failed: {e}", "WARN")
        if is_dvd_source and self.app_state.dvd.available_titles:
            for title in self.app_state.dvd.available_titles:
                if title.title_number == self.app_state.dvd.selected_title_number:
                    self.duration = title.duration
                    self.app_state.log(f"Using DVD title duration: {self.duration:.2f}s", "INFO")
                    self.timeline_slider.set_duration(self.duration)
                    return
        self.app_state.log("Could not determine video duration", "WARN")
        self.duration = 0.0
        self._playable_duration = 0.0
            
    def on_timeline_changed(self, value):
        """Handle timeline slider change while dragging"""
        if self.duration > 0:
            timestamp = self.timeline_slider.value_to_time(value)
            
            # Skip deleted segments when user drags into them
            if self._deleted_segments and self._is_position_in_deleted_segment(timestamp):
                timestamp = self._get_next_valid_position(timestamp)
                # Update slider to match the adjusted position
                adjusted_value = self.timeline_slider.time_to_value(timestamp)
                self.timeline_slider.blockSignals(True)
                self.timeline_slider.setValue(adjusted_value)
                self.timeline_slider.blockSignals(False)
            
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
            
            # Seek original video during drag (QMediaPlayer is fast)
            # For DVD sources, cap to the first VOB's actual duration
            # Processed preview updates on slider release only
            if self._is_user_seeking:
                seek_pos = timestamp
                if self._playable_duration > 0 and timestamp >= self._playable_duration:
                    seek_pos = max(0.0, self._playable_duration - 1.0)
                self._video_player.seek(seek_pos)
                self._playback_time = timestamp
    
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
    
    def _cap_seek(self, timestamp: float) -> float:
        """Cap seek position to the playable range (first VOB for DVD sources)."""
        if self._playable_duration > 0 and timestamp >= self._playable_duration:
            return max(0.0, self._playable_duration - 1.0)
        return timestamp

    def on_timeline_released(self):
        """Handle timeline slider release - finalize seek and resume playback"""
        # Clear the seeking flag
        self._is_user_seeking = False
        
        if self.current_video_path and self.duration > 0:
            value = self.timeline_slider.value()
            timestamp = self.timeline_slider.value_to_time(value)
            
            # Use QMediaPlayer for smooth seeking
            # For DVD sources, cap to the first VOB's actual duration
            self._video_player.seek(self._cap_seek(timestamp))
            
            # Sync playback time (keep actual slider position, not capped seek)
            self._playback_time = timestamp
            
            # Update processed preview only when paused (during playback the
            # overlay is intentionally frozen to prevent FFmpeg blocking the UI)
            if not self.is_playing:
                self._update_filter_overlay()
            
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
        if not self.current_video_path and not self.app_state.extra.generate_video:
            return
            
        # Cancel any pending load and clean up previous thread
        self._cleanup_thread()
        
        # Check if this is a DVD source
        is_dvd_source = self.app_state.dvd.is_dvd_source and self.current_video_path and self.current_video_path.endswith('.txt')
        
        # Get first VOB path for DVD preview fallback
        first_vob_path = None
        if is_dvd_source and self.app_state.dvd.available_titles:
            for title in self.app_state.dvd.available_titles:
                if title.title_number == self.app_state.dvd.selected_title_number:
                    if title.vob_files:
                        first_vob_path = title.vob_files[0]
                    break
        
        # Build subtitle filter string if burning is enabled
        subtitle_filter = ""
        if self.app_state.subtitles.burn_subs:
            if is_dvd_source and self.app_state.dvd.selected_subtitle_index >= 0 and first_vob_path:
                sub_idx = self.app_state.dvd.selected_subtitle_index
                subtitle_filter = self._build_dvd_subtitle_filter(first_vob_path, sub_idx)
            else:
                sub_path = self._find_subtitle_file()
                if sub_path:
                    subtitle_filter = self._build_subtitle_filter_string(sub_path)
        
        # Build Extra overlay filters for preview (drawtext + images)
        extra_video_filter = ""
        extra_image_paths = []
        backend = self.app_state.backend
        if hasattr(backend, 'build_extra_preview_filter'):
            extra_video_filter = backend.build_extra_preview_filter(self.app_state)
        if hasattr(backend, 'has_preview_image_overlays') and backend.has_preview_image_overlays(self.app_state):
            for item in self.app_state.extra.image_overlays:
                if item.enabled and item.image_path and os.path.exists(item.image_path):
                    extra_image_paths.append(item.image_path)
        
        # Create new loader thread
        self._loader_thread = QThread()
        self._frame_loader = FrameLoader()
        self._frame_loader.moveToThread(self._loader_thread)
        
        # Connect signals
        self._frame_loader.frame_loaded.connect(self.on_frame_loaded)
        self._frame_loader.error_occurred.connect(self.on_frame_error)
        self._loader_thread.started.connect(
            lambda: self._frame_loader.load_frame(
                self.current_video_path, timestamp, self.app_state.backend,
                is_dvd_source, first_vob_path, subtitle_filter,
                (self.preview_width, self.preview_height),
                extra_video_filter, extra_image_paths
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
        # Downscale to preview size for performance
        image = image.scaled(
            self.preview_width, self.preview_height,
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.current_frame = image
        
        # Display original
        self.display_image(self.original_label, image)
        
        # Apply filters and update the filter overlay (not the hidden label)
        processed = self.apply_filters(image)
        self.filter_overlay.set_original_image(image)
        self.filter_overlay.set_image(processed)
        
        # Use QPainter overlay for subtitle display (text-based subs).
        # FFmpeg may also burn subtitles into the frame but the overlay is
        # the reliable fallback for external SRT/ASS files.
        # For DVD sources, skip the overlay unless the user loaded an external text subtitle.
        is_dvd_source = (self.app_state.dvd.is_dvd_source
                         and self.current_video_path
                         and self.current_video_path.endswith('.txt'))
        has_external_sub = bool(self.app_state.subtitles.selected_subtitle)
        if not is_dvd_source or has_external_sub:
            sub_text = self._get_current_subtitle()
            self.filter_overlay.set_subtitle(sub_text)
        else:
            self.filter_overlay.set_subtitle("")
        
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
        
        # Denoise (HQDN3D)
        if getattr(self.app_state.filters, 'denoise', False):
            filters.append("hqdn3d")
        
        # Sharpen (Unsharp)
        if getattr(self.app_state.filters, 'sharpen', False):
            amount = getattr(self.app_state.filters, 'sharpen_amount', 1.0)
            filters.append(f"unsharp=5:5:{amount}")
        
        # CAS (Contrast Adaptive Sharpen)
        if getattr(self.app_state.filters, 'cas_enabled', False):
            strength = getattr(self.app_state.filters, 'cas_strength', 0.0)
            filters.append(f"cas={strength}")
        
        # Deblock
        if getattr(self.app_state.filters, 'deblock', False):
            strength = getattr(self.app_state.filters, 'deblock_strength', 0.5)
            filters.append(f"deblock=filter=strong:alpha={strength}:beta={strength}")
        
        # Deinterlace (Yadif)
        if getattr(self.app_state.filters, 'deinterlace', False):
            filters.append("yadif")
        
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

        # Colorization (B&W → Color)
        colorization = self.app_state.colorization
        if colorization.enabled:
            if colorization.method == "tint":
                h = colorization.tint_hue / 360.0
                s = min(colorization.tint_saturation, 1.0)
                tr, tg, tb = self._hsl_to_rgb(h, s, 0.5)
                strength = colorization.tint_strength
                rc = (1.0 - strength + strength * tg) / 3.0
                gc = (1.0 - strength + strength * tb) / 3.0
                bc = (1.0 - strength + strength * tr) / 3.0
                filters.append("format=gbrp")
                filters.append(
                    f"colorchannelmixer="
                    f"rr={rc:.6f}:rg={rc:.6f}:rb={rc:.6f}:"
                    f"gr={gc:.6f}:gg={gc:.6f}:gb={gc:.6f}:"
                    f"br={bc:.6f}:bg={bc:.6f}:bb={bc:.6f}"
                )
            elif colorization.method == "pseudocolor":
                preset = colorization.pseudocolor_preset
                opacity = colorization.pseudocolor_opacity
                filters.append(f"pseudocolor=colorpreset={preset}:opacity={opacity}")
            elif colorization.method == "lut":
                lut_path = colorization.lut_path
                if lut_path and os.path.exists(lut_path):
                    lut_type = colorization.lut_type
                    escaped = lut_path.replace("'", "'\\''")
                    if lut_type == "lut3d":
                        filters.append(f"lut3d=file='{escaped}'")
                    elif lut_type == "lutrgb":
                        filters.append(f"lutrgb=file='{escaped}'")
                    elif lut_type == "lutyuv":
                        filters.append(f"lutyuv=file='{escaped}'")

        if not filters:
            return image.copy()

        filter_str = ",".join(filters)
        backend = self.app_state.backend
        if not hasattr(backend, 'apply_video_filter'):
            return image.copy()

        try:
            buffer = QBuffer()
            buffer.open(QBuffer.ReadWrite)
            image.save(buffer, "PNG")
            image_bytes = bytes(buffer.data())
            buffer.close()

            self.app_state.log(f"Preview filter: {filter_str}", "DEBUG")

            result = backend.apply_video_filter(image_bytes, filter_str)
            if result:
                processed = QImage()
                processed.loadFromData(result, "PNG")
                if not processed.isNull():
                    image = processed
            else:
                self.app_state.log("Filter failed, returning original image", "WARN")
        except Exception as e:
            self.app_state.log(f"Filter preview error: {e}", "WARN")

        return image

    @staticmethod
    def _hsl_to_rgb(h: float, s: float, l: float) -> tuple:
        """Convert HSL (all 0.0-1.0) to RGB (0.0-1.0)"""
        if s == 0.0:
            return l, l, l
        def hue_to_rgb(p, q, t):
            if t < 0.0: t += 1.0
            if t > 1.0: t -= 1.0
            if t < 1.0 / 6.0: return p + (q - p) * 6.0 * t
            if t < 1.0 / 2.0: return q
            if t < 2.0 / 3.0: return p + (q - p) * (2.0 / 3.0 - t) * 6.0
            return p
        q = l * (1.0 + s) if l < 0.5 else l + s - l * s
        p = 2.0 * l - q
        return hue_to_rgb(p, q, h + 1.0 / 3.0), hue_to_rgb(p, q, h), hue_to_rgb(p, q, h - 1.0 / 3.0)

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
            painter.save()
            painter.setOpacity(subs.bg_opacity)
            bg_color = QColor(subs.bg_color)
            painter.fillRect(x - 10, y - metrics.height() + 5,
                           max_width + 20, total_height + 10, bg_color)
            painter.restore()
        
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
        elif self.app_state.extra.generate_video:
            self.seek_preview(0)
            
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
            self.filter_overlay.set_original_image(self.current_frame)
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
        self._video_player.seek(self._cap_seek(position))
        
        # Start playback
        self._video_player.play()
        
        # Stop overlay timer during playback to prevent FFmpeg blocking the UI
        self._overlay_timer.stop()
        self.filter_overlay.set_frozen(True)
        
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
        
    def on_split_toggled(self, checked: bool):
        """Handle split preview toggle"""
        self._split_preview = checked
        self.filter_overlay.set_split_enabled(checked)
        mode = "ON" if checked else "OFF"
        self.app_state.log(f"Split preview {mode}", "INFO")
    
    def on_pause_clicked(self):
        """Handle pause button click"""
        self.is_playing = False
        
        # Clear seeking flag
        self._is_user_seeking = False
        
        # Stop overlay timer
        self._overlay_timer.stop()
        self.filter_overlay.set_frozen(False)
        
        # Use QMediaPlayer for smooth playback
        self._video_player.pause()
        
        # Refresh processed preview at paused position
        current_pos = self._video_player.get_position()
        self.seek_preview(current_pos)
        
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
