"""
Video Preview Component - Handles real-time preview functionality (PySide6)
Uses native Qt (QImage, QPixmap) instead of PIL/Pillow
"""
import io
import os
import subprocess
import threading
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QGroupBox, QSplitter, QSizePolicy, QPushButton, QComboBox
)
from PySide6.QtCore import Qt, Signal, QThread, QObject, QBuffer
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QFont, QPen


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
    """Custom slider with cut point markers"""
    
    cut_marker_clicked = Signal(float, str)  # position, cut_id
    
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.cut_points = []  # List of (position_seconds, cut_id)
        self.duration = 0.0
        self.hovered_cut = None  # Currently hovered cut for visual feedback
        
    def set_cut_points(self, cut_points: list, duration: float):
        """
        Set cut points to display
        Args:
            cut_points: List of (position_seconds, cut_id) tuples
            duration: Video duration in seconds
        """
        self.cut_points = cut_points
        self.duration = duration
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
            # Convert seconds to slider position (0-1000)
            if self.duration > 0:
                slider_val = int((cut_pos / self.duration) * 1000)
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
        """Convert slider value (0-1000) to pixel position"""
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
            slider_val = int((cut_pos / self.duration) * 1000)
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
            slider_val = int((cut_pos / self.duration) * 1000)
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


class FrameLoader(QObject):
    """Worker object for loading frames in background thread"""
    
    frame_loaded = Signal(object)  # QImage
    error_occurred = Signal(str)
    
    def __init__(self):
        super().__init__()
        self._cancelled = False
        
    def load_frame(self, video_path: str, timestamp: float, ffmpeg_path: str):
        """Load a frame from video at specified timestamp"""
        self._cancelled = False
        
        cmd = [
            ffmpeg_path, "-ss", str(timestamp),
            "-i", video_path, "-vframes", "1", "-q:v", "2",
            "-f", "image2pipe", "-vcodec", "png", "-"
        ]
        
        try:
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=10
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
                self.error_occurred.emit("FFmpeg failed to extract frame")
                
        except subprocess.TimeoutExpired:
            self.error_occurred.emit("Frame extraction timed out")
        except Exception as e:
            self.error_occurred.emit(f"Error: {str(e)}")
            
    def cancel(self):
        """Cancel the current operation"""
        self._cancelled = True


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
        
        # Frame loader thread
        self._loader_thread: Optional[QThread] = None
        self._frame_loader: Optional[FrameLoader] = None
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Split view: Original | Processed
        split = QSplitter(Qt.Horizontal)
        
        # Original frame
        original_group = QGroupBox("Original")
        original_layout = QVBoxLayout(original_group)
        
        self.original_label = QLabel("No Video")
        self.original_label.setAlignment(Qt.AlignCenter)
        self.original_label.setMinimumSize(320, 180)
        self.original_label.setStyleSheet("background-color: #1a1a1a; color: #888;")
        self.original_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        original_layout.addWidget(self.original_label)
        
        split.addWidget(original_group)
        
        # Processed frame
        processed_group = QGroupBox("Processed Preview")
        processed_layout = QVBoxLayout(processed_group)
        
        self.processed_label = QLabel("No Video")
        self.processed_label.setAlignment(Qt.AlignCenter)
        self.processed_label.setMinimumSize(320, 180)
        self.processed_label.setStyleSheet("background-color: #1a1a1a; color: #888;")
        self.processed_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        processed_layout.addWidget(self.processed_label)
        
        split.addWidget(processed_group)
        split.setSizes([400, 400])
        
        layout.addWidget(split)
        
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
        self.speed_combo.addItems(["0.5x", "1.0x", "1.5x", "2.0x"])
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.currentTextChanged.connect(self.on_speed_changed)
        self.speed_combo.setMaximumWidth(70)
        playback_layout.addWidget(self.speed_combo)
        
        playback_layout.addStretch()
        layout.addLayout(playback_layout)
        
        # Timeline controls
        timeline_layout = QHBoxLayout()
        
        timeline_layout.addWidget(QLabel("Timeline:"))
        
        self.timeline_slider = TimelineSlider(Qt.Horizontal)
        self.timeline_slider.setRange(0, 1000)
        self.timeline_slider.valueChanged.connect(self.on_timeline_changed)
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
        self.current_video_path = video_path
        
        # Get video duration
        self.load_video_metadata(video_path)
        
        # Load initial frame
        self.seek_preview(0)
        
    def load_video_metadata(self, video_path: str):
        """Load video metadata using ffprobe"""
        ffprobe_path = self.app_state.ffprobe_path
        
        cmd = [
            ffprobe_path, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        
        try:
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=5
            )
            if result.returncode == 0:
                self.duration = float(result.stdout.strip())
                self.app_state.log(f"Video duration: {self.duration:.2f}s", "INFO")
        except Exception as e:
            self.app_state.log(f"Failed to get video duration: {e}", "WARN")
            self.duration = 0.0
            
    def on_timeline_changed(self, value):
        """Handle timeline slider change"""
        if self.duration > 0:
            timestamp = (value / 1000.0) * self.duration
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
            
            # Update slider position
            slider_value = int((seconds / self.duration) * 1000)
            self.timeline_slider.setValue(slider_value)
            
            # Seek to that position
            self.seek_preview(seconds)
            
        except ValueError:
            self.app_state.log(f"Invalid time format: {text}. Use MM:SS or seconds", "WARN")
            
    def on_timeline_released(self):
        """Handle timeline slider release - load frame"""
        if self.current_video_path and self.duration > 0:
            value = self.timeline_slider.value()
            timestamp = (value / 1000.0) * self.duration
            self.seek_preview(timestamp)
            
    def get_current_timestamp(self):
        """Get the current timeline position in seconds"""
        if self.duration > 0:
            value = self.timeline_slider.value()
            return (value / 1000.0) * self.duration
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
            
        # Create new loader thread
        self._loader_thread = QThread()
        self._frame_loader = FrameLoader()
        self._frame_loader.moveToThread(self._loader_thread)
        
        # Connect signals
        self._frame_loader.frame_loaded.connect(self.on_frame_loaded)
        self._frame_loader.error_occurred.connect(self.on_frame_error)
        self._loader_thread.started.connect(
            lambda: self._frame_loader.load_frame(
                self.current_video_path, timestamp, self.app_state.ffmpeg_path
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
        
        # Apply filters and display processed
        processed = self.apply_filters(image)
        self.display_image(self.processed_label, processed)
        
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
                timestamp = (value / 1000.0) * self.duration
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
            timestamp = (value / 1000.0) * self.duration
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
        
        # Scale offset for preview (preview might be smaller than actual video)
        # Use a reasonable scaling factor
        scale_factor = img_height / 480.0  # Assume 480p as reference
        scaled_offset = int(subs.vertical_offset * scale_factor)
        
        if subs.position == "bottom":
            y = img_height - 20 - total_height + scaled_offset
        elif subs.position == "top":
            y = 20 + metrics.height() - scaled_offset  # Negative offset moves down
        else:  # center
            y = (img_height - total_height) // 2
        
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
            timestamp = (value / 1000.0) * self.duration
            self.seek_preview(timestamp)
            
    def resizeEvent(self, event):
        """Handle resize - rescale images"""
        super().resizeEvent(event)
        if self.current_frame and not self.current_frame.isNull():
            self.display_image(self.original_label, self.current_frame)
            processed = self.apply_filters(self.current_frame)
            self.display_image(self.processed_label, processed)
            
    def on_play_clicked(self):
        """Handle play button click - start auto-advancing frames"""
        if not self.current_video_path or self.duration <= 0:
            return
        
        self.is_playing = True
        self.play_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        
        # Calculate timer interval based on playback speed
        # Base: 30 fps, adjust by speed
        base_fps = 30
        actual_fps = base_fps * self.playback_speed
        interval = int(1000 / actual_fps)
        
        # Start playback timer
        self.playback_timer = self.startTimer(interval)
        self.app_state.log(f"Playback started at {self.playback_speed}x speed", "INFO")
        
    def on_speed_changed(self, speed_text):
        """Handle playback speed change"""
        # Parse speed from text like "1.0x"
        speed = float(speed_text.replace('x', ''))
        self.playback_speed = speed
        
        # If currently playing, restart timer with new speed
        if self.is_playing:
            self.killTimer(self.playback_timer)
            base_fps = 30
            actual_fps = base_fps * self.playback_speed
            interval = int(1000 / actual_fps)
            self.playback_timer = self.startTimer(interval)
            self.app_state.log(f"Playback speed changed to {self.playback_speed}x", "INFO")
        
    def on_pause_clicked(self):
        """Handle pause button click"""
        self.is_playing = False
        if hasattr(self, 'playback_timer'):
            self.killTimer(self.playback_timer)
        self.play_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.app_state.log("Playback paused", "INFO")
        
    def on_stop_clicked(self):
        """Handle stop button click - reset to beginning"""
        self.is_playing = False
        if hasattr(self, 'playback_timer'):
            self.killTimer(self.playback_timer)
        
        # Reset to beginning
        self.timeline_slider.setValue(0)
        self.seek_preview(0)
        
        self.play_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.app_state.log("Playback stopped", "INFO")
        
    def timerEvent(self, event):
        """Handle timer events for playback"""
        if not self.is_playing or self.duration <= 0:
            return
            
        # Advance timeline based on playback speed
        current_value = self.timeline_slider.value()
        # Advance by speed factor (1.0 = 1 step, 2.0 = 2 steps, etc.)
        new_value = current_value + max(1, int(self.playback_speed))
        
        if new_value > 1000:
            # Reached end
            self.on_stop_clicked()
            return
            
        self.timeline_slider.setValue(new_value)
        
        # Load frame at new position
        timestamp = (new_value / 1000.0) * self.duration
        self.seek_preview(timestamp)
