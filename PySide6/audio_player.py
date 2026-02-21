"""
Audio Player Component - Handles audio playback using Qt Multimedia (PySide6)
"""
from typing import Optional

from PySide6.QtCore import QObject, Signal, QUrl, Slot
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput


class AudioPlayer(QObject):
    """
    Audio player using QMediaPlayer for synchronized playback with video preview.
    """
    
    position_changed = Signal(float)  # Current position in seconds
    duration_changed = Signal(float)  # Total duration in seconds
    state_changed = Signal(str)  # "playing", "paused", "stopped"
    error_occurred = Signal(str)  # Error message
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._media_player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._media_player.setAudioOutput(self._audio_output)
        
        self._current_source: Optional[str] = None
        self._is_ready: bool = False
        
        self._connect_signals()
        
    def _connect_signals(self):
        self._media_player.positionChanged.connect(self._on_position_changed)
        self._media_player.durationChanged.connect(self._on_duration_changed)
        self._media_player.playbackStateChanged.connect(self._on_state_changed)
        self._media_player.errorOccurred.connect(self._on_error)
        
    def _on_position_changed(self, position_ms: int):
        position_sec = position_ms / 1000.0
        self.position_changed.emit(position_sec)
        
    def _on_duration_changed(self, duration_ms: int):
        duration_sec = duration_ms / 1000.0
        self._is_ready = duration_sec > 0
        self.duration_changed.emit(duration_sec)
        
    def _on_state_changed(self, state):
        state_map = {
            QMediaPlayer.PlayingState: "playing",
            QMediaPlayer.PausedState: "paused",
            QMediaPlayer.StoppedState: "stopped"
        }
        self.state_changed.emit(state_map.get(state, "stopped"))
        
    def _on_error(self, error, error_string):
        self.error_occurred.emit(f"Audio error: {error_string}")
        
    def load_file(self, file_path: str) -> bool:
        """
        Load an audio/video file for playback.
        
        Args:
            file_path: Path to the media file
            
        Returns:
            True if file loaded successfully
        """
        if not file_path:
            return False
            
        self._current_source = file_path
        self._is_ready = False
        
        url = QUrl.fromLocalFile(file_path)
        self._media_player.setSource(url)
        
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
        
    def seek(self, position_sec: float):
        """
        Seek to a specific position.
        
        Args:
            position_sec: Position in seconds
        """
        position_ms = int(position_sec * 1000)
        self._media_player.setPosition(position_ms)
        
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
        
    def get_position(self) -> float:
        """Get current position in seconds"""
        return self._media_player.position() / 1000.0
        
    def get_duration(self) -> float:
        """Get total duration in seconds"""
        return self._media_player.duration() / 1000.0
        
    def is_playing(self) -> bool:
        """Check if currently playing"""
        return self._media_player.playbackState() == QMediaPlayer.PlayingState
        
    def is_ready(self) -> bool:
        """Check if media is ready for playback"""
        return self._is_ready
        
    def set_muted(self, muted: bool):
        """Mute or unmute audio"""
        self._audio_output.setMuted(muted)
        
    def is_muted(self) -> bool:
        """Check if audio is muted"""
        return self._audio_output.isMuted()
        
    def cleanup(self):
        """Release resources"""
        self._media_player.stop()
        self._media_player.setSource(QUrl())
        self._current_source = None
        self._is_ready = False
