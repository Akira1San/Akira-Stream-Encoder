"""
Video Player Component - Handles video playback using QMediaPlayer (PySide6)
Provides smooth video playback with timeline seeking and playback controls.
Also supports frame capture via QVideoSink for filter overlay preview.
"""
from typing import Optional, Callable

from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QObject, Signal, QUrl, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoFrame
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtGui import QImage, QPixmap


class VideoPlayer(QObject):
    """
    Video player using QMediaPlayer for smooth video playback.
    Combines video and audio playback in a single component.
    Supports frame capture via QVideoSink for filter overlay preview.
    """
    
    # Signals for playback state changes
    position_changed = Signal(float)  # Current position in seconds
    duration_changed = Signal(float)  # Total duration in seconds
    state_changed = Signal(str)  # "playing", "paused", "stopped"
    error_occurred = Signal(str)  # Error message
    playback_rate_changed = Signal(float)  # Playback speed changed
    frame_captured = Signal(object)  # QImage frame captured
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Create QMediaPlayer instance
        self._media_player = QMediaPlayer()
        
        # Create audio output
        self._audio_output = QAudioOutput()
        self._media_player.setAudioOutput(self._audio_output)
        
        # Create video widget (can be None initially, set later)
        self._video_widget: Optional[QVideoWidget] = None
        
        # Frame capture support
        self._video_sink = None
        self._frame_callback: Optional[Callable] = None
        self._last_captured_frame: Optional[QImage] = None
        
        # State tracking
        self._current_source: Optional[str] = None
        self._is_ready: bool = False
        self._playback_rate: float = 1.0
        
        # Connect internal signals
        self._connect_signals()
    
    def _connect_signals(self):
        """Connect QMediaPlayer signals to our handlers"""
        self._media_player.positionChanged.connect(self._on_position_changed)
        self._media_player.durationChanged.connect(self._on_duration_changed)
        self._media_player.playbackStateChanged.connect(self._on_state_changed)
        self._media_player.errorOccurred.connect(self._on_error)
        self._media_player.playbackRateChanged.connect(self._on_playback_rate_changed)
        self._media_player.activeTracksChanged.connect(self._on_subtitle_tracks_changed)
    
    def _on_position_changed(self, position_ms: int):
        """Handle position change from QMediaPlayer"""
        position_sec = position_ms / 1000.0
        self.position_changed.emit(position_sec)
    
    def _on_duration_changed(self, duration_ms: int):
        """Handle duration change from QMediaPlayer"""
        duration_sec = duration_ms / 1000.0
        self._is_ready = duration_sec > 0
        self.duration_changed.emit(duration_sec)
    
    def _on_state_changed(self, state):
        """Handle playback state change"""
        state_map = {
            QMediaPlayer.PlayingState: "playing",
            QMediaPlayer.PausedState: "paused",
            QMediaPlayer.StoppedState: "stopped"
        }
        self.state_changed.emit(state_map.get(state, "stopped"))
    
    def _on_error(self, error, error_string):
        """Handle playback errors"""
        self.error_occurred.emit(f"Video error: {error_string}")
    
    def _on_playback_rate_changed(self, rate: float):
        """Handle playback rate change"""
        self._playback_rate = rate
        self.playback_rate_changed.emit(rate)
    
    def _on_subtitle_tracks_changed(self):
        """Disable subtitle rendering whenever subtitle tracks change"""
        self._media_player.setActiveSubtitleTrack(-1)

    def set_video_output(self, video_widget: QVideoWidget):
        """
        Set the video output widget with frame capture enabled.
        
        Args:
            video_widget: QVideoWidget to display video
        """
        self.set_video_output_with_sink(video_widget, enable_sink=True)
    
    def load_file(self, file_path: str) -> bool:
        """
        Load a video file for playback.
        
        Args:
            file_path: Path to the video file
            
        Returns:
            True if file loaded successfully
        """
        if not file_path:
            return False
        
        self._current_source = file_path
        self._is_ready = False
        
        url = QUrl.fromLocalFile(file_path)
        self._media_player.setSource(url)
        self._media_player.setActiveSubtitleTrack(-1)
        
        return True
    
    def play(self):
        """Start or resume playback"""
        if self._current_source:
            self._media_player.play()
    
    def pause(self):
        """Pause playback"""
        self._media_player.pause()
    
    def stop(self):
        """Stop playback and reset position"""
        self._media_player.stop()
    
    def toggle_play_pause(self):
        """Toggle between play and pause states"""
        if self._media_player.playbackState() == QMediaPlayer.PlayingState:
            self.pause()
        else:
            self.play()
    
    def seek(self, position_sec: float):
        """
        Seek to a specific position.
        
        Args:
            position_sec: Position in seconds
        """
        position_ms = int(position_sec * 1000)
        self._media_player.setPosition(position_ms)
    
    def seek_relative(self, offset_sec: float):
        """
        Seek relative to current position.
        
        Args:
            offset_sec: Offset in seconds (can be negative)
        """
        current_pos = self.get_position()
        new_pos = max(0, current_pos + offset_sec)
        duration = self.get_duration()
        if new_pos > duration:
            new_pos = duration
        self.seek(new_pos)
    
    def set_volume(self, volume: float):
        """
        Set playback volume.
        
        Args:
            volume: Volume level from 0.0 to 1.0
        """
        self._audio_output.setVolume(max(0.0, min(1.0, volume)))
    
    def get_volume(self) -> float:
        """Get current volume level (0.0 to 1.0)"""
        return self._audio_output.volume()
    
    def set_muted(self, muted: bool):
        """Mute or unmute audio"""
        self._audio_output.setMuted(muted)
    
    def is_muted(self) -> bool:
        """Check if audio is muted"""
        return self._audio_output.isMuted()
    
    def set_playback_rate(self, rate: float):
        """
        Set playback speed.
        
        Args:
            rate: Playback rate (e.g., 1.0 = normal, 1.5 = 1.5x speed)
        """
        # Clamp to valid range (0.25x to 4x)
        self._media_player.setPlaybackRate(max(0.25, min(4.0, rate)))
    
    def get_playback_rate(self) -> float:
        """Get current playback speed"""
        return self._playback_rate
    
    def get_position(self) -> float:
        """Get current position in seconds"""
        return self._media_player.position() / 1000.0
    
    def get_duration(self) -> float:
        """Get total duration in seconds"""
        return self._media_player.duration() / 1000.0
    
    def is_playing(self) -> bool:
        """Check if currently playing"""
        return self._media_player.playbackState() == QMediaPlayer.PlayingState
    
    def is_paused(self) -> bool:
        """Check if currently paused"""
        return self._media_player.playbackState() == QMediaPlayer.PausedState
    
    def is_stopped(self) -> bool:
        """Check if currently stopped"""
        return self._media_player.playbackState() == QMediaPlayer.StoppedState
    
    def is_ready(self) -> bool:
        """Check if media is ready for playback"""
        return self._is_ready
    
    def get_current_source(self) -> Optional[str]:
        """Get the current media source path"""
        return self._current_source
    
    def cleanup(self):
        """Release resources"""
        self._media_player.stop()
        self._media_player.setSource(QUrl())
        self._current_source = None
        self._is_ready = False
    
    # ============== Frame Capture Methods ==============
    
    def set_video_output_with_sink(self, video_widget: QVideoWidget, enable_sink: bool = True):
        """
        Set the video output widget with optional frame capture.
        
        Args:
            video_widget: QVideoWidget to display video
            enable_sink: If True, enables QVideoSink for frame capture
        """
        self._video_widget = video_widget
        
        if enable_sink:
            # Try to use QVideoSink for frame capture
            try:
                from PySide6.QtMultimedia import QVideoSink
                self._video_sink = QVideoSink()
                self._video_sink.videoFrameChanged.connect(self._on_video_frame_changed)
                self._media_player.setVideoSink(self._video_sink)
                self._media_player.setVideoOutput(video_widget)
            except (ImportError, AttributeError):
                # Fallback for older PySide6 versions - use video widget only
                self._media_player.setVideoOutput(video_widget)
                self._video_sink = None
        else:
            self._media_player.setVideoOutput(video_widget)
            self._video_sink = None
    
    def _on_video_frame_changed(self, frame: QVideoFrame):
        """Handle incoming video frame from QVideoSink"""
        if not frame.isValid():
            return
        
        # Convert QVideoFrame to QImage
        image = self._video_frame_to_image(frame)
        if not image.isNull():
            self._last_captured_frame = image
            self.frame_captured.emit(image)
            
            # Call callback if registered
            if self._frame_callback:
                self._frame_callback(image)
    
    def _video_frame_to_image(self, frame: QVideoFrame) -> QImage:
        """Convert QVideoFrame to QImage"""
        # Make a copy of the frame to ensure we can read it
        copied_frame = QVideoFrame(frame)
        
        if not copied_frame.map(QVideoFrame.ReadOnly):
            return QImage()
        
        try:
            # Get frame properties
            width = copied_frame.width()
            height = copied_frame.height()
            
            # Determine pixel format and create image accordingly
            if copied_frame.pixelFormat() == QVideoFrame.Format_RGB32:
                img = QImage(
                    copied_frame.bits(),
                    width,
                    height,
                    width * 4,
                    QImage.Format_RGB32
                ).copy()
            elif copied_frame.pixelFormat() == QVideoFrame.Format_BGR32:
                img = QImage(
                    copied_frame.bits(),
                    width,
                    height,
                    width * 4,
                    QImage.Format_BGR32
                ).copy()
            elif copied_frame.pixelFormat() == QVideoFrame.Format_ARGB32:
                img = QImage(
                    copied_frame.bits(),
                    width,
                    height,
                    width * 4,
                    QImage.Format_ARGB32
                ).copy()
            elif copied_frame.pixelFormat() == QVideoFrame.Format_RGB565:
                # Handle RGB565 format
                img = QImage(
                    copied_frame.bits(),
                    width,
                    height,
                    width * 2,
                    QImage.Format_RGB16
                ).copy()
            else:
                # Try generic approach
                img = QImage(
                    copied_frame.bits(),
                    width,
                    height,
                    width * 4,
                    QImage.Format_RGB32
                ).copy()
            
            return img
        finally:
            copied_frame.unmap()
    
    def set_frame_callback(self, callback: Callable[[QImage], None]):
        """
        Set a callback function to receive captured frames.
        
        Args:
            callback: Function that takes a QImage as parameter
        """
        self._frame_callback = callback
    
    def get_last_frame(self) -> Optional[QImage]:
        """Get the last captured frame"""
        return self._last_captured_frame
    
    def capture_current_frame(self) -> Optional[QImage]:
        """
        Request capture of current frame.
        Note: Frame will be delivered via frame_captured signal or callback.
        Returns the last captured frame immediately if available.
        """
        return self._last_captured_frame


class VideoPlayerWidget(QVideoWidget):
    """
    Enhanced QVideoWidget with additional functionality.
    Provides a video display widget that can be used standalone or embedded.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 180)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        )
    
    def set_aspect_ratio_mode(self, mode: Qt.AspectRatioMode):
        """
        Set the aspect ratio mode.
        
        Args:
            mode: Qt.AspectRatioMode (KeepAspectRatio, KeepAspectRatioByExpanding, IgnoreAspectRatio)
        """
        # QVideoWidget uses native aspect ratio handling
        # This is a placeholder for additional customization if needed
        pass


# Import QtWidgets for QSizePolicy
from PySide6 import QtWidgets
from PySide6.QtCore import Qt
