"""
NLE Preview Widget - Video preview panel with playback controls
"""
import os
import subprocess
import tempfile
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QSlider
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor

from nle.nle_models import NLEProject, NLEClip


class FrameExtractor(QThread):
    """Worker thread to extract a frame from video using FFmpeg"""
    
    frame_ready = Signal(QImage)  # Emitted when frame is ready
    error = Signal(str)  # Emitted on error
    
    def __init__(self, source_path: str, timestamp: float, width: int = 320, height: int = 180):
        super().__init__()
        self.source_path = source_path
        self.timestamp = timestamp
        self.width = width
        self.height = height
        self._cancelled = False
        
    def run(self):
        """Extract frame using FFmpeg"""
        if self._cancelled:
            return
            
        try:
            # Create temp file for output
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                output_path = tmp.name
            
            # FFmpeg command to extract single frame
            cmd = [
                'ffmpeg',
                '-y',  # Overwrite output
                '-ss', str(self.timestamp),  # Seek to timestamp
                '-i', self.source_path,
                '-vframes', '1',  # Extract 1 frame
                '-vf', f'scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2:black',
                output_path
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10
            )
            
            if self._cancelled:
                return
                
            if result.returncode == 0 and os.path.exists(output_path):
                # Load image
                image = QImage(output_path)
                if not image.isNull():
                    self.frame_ready.emit(image)
                else:
                    self.error.emit("Failed to load extracted frame")
            else:
                error_msg = result.stderr.decode('utf-8', errors='ignore')[:200]
                self.error.emit(f"FFmpeg error: {error_msg}")
                
            # Cleanup temp file
            try:
                os.unlink(output_path)
            except:
                pass
                
        except subprocess.TimeoutExpired:
            self.error.emit("Frame extraction timed out")
        except Exception as e:
            self.error.emit(str(e))
            
    def cancel(self):
        """Cancel the extraction"""
        self._cancelled = True


class NLEPreviewWidget(QFrame):
    """
    Preview widget for NLE timeline.
    
    Displays video frames at playhead position with playback controls.
    """
    
    # Signals
    playhead_move_requested = Signal(float)  # Request playhead move
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._project: Optional[NLEProject] = None
        self._current_clip: Optional[NLEClip] = None
        self._current_time: float = 0.0
        self._is_playing: bool = False
        self._playback_speed: float = 1.0
        self._ffmpeg_path: str = "ffmpeg"
        
        # Frame extractor worker
        self._extractor: Optional[FrameExtractor] = None
        
        # Playback timer
        self._playback_timer = QTimer(self)
        self._playback_timer.timeout.connect(self._on_playback_tick)
        self._playback_interval = 33  # ~30 fps
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the preview UI"""
        self.setStyleSheet("""
            NLEPreviewWidget {
                background-color: #1a1a1a;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
            }
            QLabel {
                color: #ddd;
            }
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border: none;
                padding: 8px 12px;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Header
        header = QLabel("Preview")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)
        
        # Preview display area
        self.preview_label = QLabel()
        self.preview_label.setMinimumSize(320, 180)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #000;
                border: 1px solid #2a2a2a;
                border-radius: 2px;
            }
        """)
        self.preview_label.setText("No preview")
        self.preview_label.setScaledContents(False)
        layout.addWidget(self.preview_label, 1)
        
        # Time display
        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet("font-family: monospace; font-size: 12px;")
        layout.addWidget(self.time_label)
        
        # Playback controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(5)
        
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setEnabled(False)
        controls_layout.addWidget(self.stop_btn)
        
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.clicked.connect(self._on_play_pause)
        controls_layout.addWidget(self.play_btn)
        
        self.step_back_btn = QPushButton("⏮ -1s")
        self.step_back_btn.clicked.connect(self._on_step_back)
        controls_layout.addWidget(self.step_back_btn)
        
        self.step_fwd_btn = QPushButton("+1s ⏭")
        self.step_fwd_btn.clicked.connect(self._on_step_forward)
        controls_layout.addWidget(self.step_fwd_btn)
        
        layout.addLayout(controls_layout)
        
        # Clip info
        self.clip_info_label = QLabel("No clip selected")
        self.clip_info_label.setStyleSheet("color: #888; font-size: 11px;")
        self.clip_info_label.setWordWrap(True)
        layout.addWidget(self.clip_info_label)
        
    def set_project(self, project: NLEProject):
        """Set the NLE project"""
        self._project = project
        
    def set_ffmpeg_path(self, path: str):
        """Set FFmpeg executable path"""
        self._ffmpeg_path = path
        
    def update_preview(self, time: float):
        """Update preview for given timeline time"""
        self._current_time = time
        
        if not self._project:
            self._show_no_preview()
            return
            
        # Find clip at current time
        clip = self._find_clip_at_time(time)
        
        if clip != self._current_clip:
            self._current_clip = clip
            
        if clip:
            self._extract_frame(clip, time)
            self._update_clip_info(clip, time)
        else:
            self._show_no_preview()
            
    def _find_clip_at_time(self, time: float) -> Optional[NLEClip]:
        """Find clip at given timeline time"""
        if not self._project:
            return None
            
        # Search video tracks first
        for track in self._project.get_video_tracks():
            if track.muted:
                continue
            clip = track.get_clip_at_time(time)
            if clip:
                return clip
                
        # Then audio tracks
        for track in self._project.get_audio_tracks():
            if track.muted:
                continue
            clip = track.get_clip_at_time(time)
            if clip:
                return clip
                
        return None
        
    def _extract_frame(self, clip: NLEClip, timeline_time: float):
        """Extract frame from clip at timeline position"""
        # Cancel previous extraction
        if self._extractor and self._extractor.isRunning():
            self._extractor.cancel()
            self._extractor.wait()
            
        # Calculate source time
        source_time = clip.source_start + (timeline_time - clip.timeline_start)
        source_time = max(0, source_time)
        
        # Get preview size
        preview_size = self.preview_label.size()
        width = min(640, preview_size.width())
        height = min(360, preview_size.height())
        
        # Create and start extractor
        self._extractor = FrameExtractor(
            clip.source_path,
            source_time,
            width,
            height
        )
        self._extractor.frame_ready.connect(self._on_frame_ready)
        self._extractor.error.connect(self._on_extraction_error)
        self._extractor.start()
        
    def _on_frame_ready(self, image: QImage):
        """Handle extracted frame"""
        pixmap = QPixmap.fromImage(image)
        self.preview_label.setPixmap(pixmap.scaled(
            self.preview_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        ))
        
    def _on_extraction_error(self, error: str):
        """Handle extraction error"""
        self._show_error(error)
        
    def _show_no_preview(self):
        """Show no preview placeholder"""
        self.preview_label.clear()
        self.preview_label.setText("No clip at playhead")
        self.clip_info_label.setText("No clip selected")
        
    def _show_error(self, message: str):
        """Show error message"""
        self.preview_label.clear()
        self.preview_label.setText(f"Preview error")
        self.clip_info_label.setText(f"Error: {message[:50]}")
        
    def _update_clip_info(self, clip: NLEClip, time: float):
        """Update clip info display"""
        source_time = clip.source_start + (time - clip.timeline_start)
        info = f"📹 {clip.name}\n"
        info += f"Source: {self._format_time(source_time)} / {self._format_time(clip.source_end - clip.source_start)}\n"
        info += f"Timeline: {self._format_time(time)}"
        self.clip_info_label.setText(info)
        
    def _format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS"""
        total_secs = int(seconds)
        hours = total_secs // 3600
        minutes = (total_secs % 3600) // 60
        secs = total_secs % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        
    def _update_time_display(self):
        """Update time display label"""
        current = self._format_time(self._current_time)
        total = self._format_time(self._project.duration if self._project else 0)
        self.time_label.setText(f"{current} / {total}")
        
    # === Playback Controls ===
    
    def _on_play_pause(self):
        """Toggle play/pause"""
        if self._is_playing:
            self._pause()
        else:
            self._play()
            
    def _play(self):
        """Start playback"""
        self._is_playing = True
        self.play_btn.setText("⏸ Pause")
        self.stop_btn.setEnabled(True)
        self._playback_timer.start(int(self._playback_interval / self._playback_speed))
        
    def _pause(self):
        """Pause playback"""
        self._is_playing = False
        self.play_btn.setText("▶ Play")
        self._playback_timer.stop()
        
    def _on_stop(self):
        """Stop playback and return to start"""
        self._pause()
        self._current_time = 0.0
        self.playhead_move_requested.emit(0.0)
        self.update_preview(0.0)
        self.stop_btn.setEnabled(False)
        
    def _on_playback_tick(self):
        """Handle playback timer tick"""
        if not self._project:
            self._pause()
            return
            
        # Advance time
        self._current_time += self._playback_interval / 1000.0 * self._playback_speed
        
        # Check if past end
        if self._current_time >= self._project.duration:
            self._on_stop()
            return
            
        # Update playhead and preview
        self.playhead_move_requested.emit(self._current_time)
        self.update_preview(self._current_time)
        self._update_time_display()
        
    def _on_step_back(self):
        """Step back 1 second"""
        self._current_time = max(0, self._current_time - 1.0)
        self.playhead_move_requested.emit(self._current_time)
        self.update_preview(self._current_time)
        self._update_time_display()
        
    def _on_step_forward(self):
        """Step forward 1 second"""
        if self._project:
            self._current_time = min(self._project.duration, self._current_time + 1.0)
        self.playhead_move_requested.emit(self._current_time)
        self.update_preview(self._current_time)
        self._update_time_display()
        
    def is_playing(self) -> bool:
        """Check if currently playing"""
        return self._is_playing
        
    def stop_playback(self):
        """Stop playback"""
        self._on_stop()
        
    def cleanup(self):
        """Cleanup resources"""
        self._pause()
        if self._extractor and self._extractor.isRunning():
            self._extractor.cancel()
            self._extractor.wait()
