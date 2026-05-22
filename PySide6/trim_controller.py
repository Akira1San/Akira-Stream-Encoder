"""
Trim Controller - Business logic for trimming operations (PySide6)
"""
from typing import Tuple, Optional

from models import AppState


class TrimController:
    """Business logic for single-cut trimming operations"""
    
    def __init__(self, app_state: AppState):
        self.app_state = app_state
        self.MINIMUM_SEGMENT_DURATION = 5.0  # 5 seconds minimum per segment
        
    def validate_cut_position(self, cut_time: float, total_duration: float) -> Tuple[bool, str]:
        """
        Validate if cut position is valid
        
        Args:
            cut_time: Desired cut position in seconds
            total_duration: Total video duration in seconds
            
        Returns:
            (valid: bool, message: str)
        """
        # Check if cut is at beginning
        if cut_time < self.MINIMUM_SEGMENT_DURATION:
            return False, f"Cut must be at least {self.MINIMUM_SEGMENT_DURATION} seconds from start."
        
        # Check if cut is at end
        if cut_time >= total_duration - self.MINIMUM_SEGMENT_DURATION:
            return False, f"Cut must be at least {self.MINIMUM_SEGMENT_DURATION} seconds from end."
        
        # Check if cut exceeds total duration
        if cut_time > total_duration:
            return False, "Cut position exceeds video duration."
        
        return True, ""
        
    def align_to_keyframe(self, video_path: str, target_time: float) -> float:
        """
        Find nearest keyframe to target time using backend
        """
        try:
            backend = self.app_state.backend
            aligned = backend.align_to_keyframe(video_path, target_time)
            if aligned != target_time:
                self.app_state.log(f"Aligned cut from {target_time:.3f}s to keyframe at {aligned:.3f}s", "INFO")
            else:
                self.app_state.log("Could not align to keyframe, using exact position", "WARN")
            return aligned
        except Exception as e:
            self.app_state.log(f"Keyframe alignment failed: {e}. Using exact position.", "WARN")
            return target_time
            
    def get_selected_tracks(self) -> list:
        """Get list of selected track types"""
        tracks = []
        if self.app_state.tracks.video_selected:
            tracks.append("video")
        if self.app_state.tracks.audio_selected:
            tracks.append("audio")
        if self.app_state.tracks.subtitle_selected and self.app_state.tracks.subtitle_available:
            tracks.append("subtitle")
        return tracks
        
    def format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS.ms"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"
