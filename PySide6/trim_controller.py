"""
Trim Controller - Business logic for trimming operations (PySide6)
"""
import os
import subprocess
import re
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
        Find nearest keyframe to target time
        
        Args:
            video_path: Path to video file
            target_time: Desired cut position in seconds
            
        Returns:
            adjusted_time: float (aligned to nearest keyframe)
        """
        ffprobe_path = self.app_state.ffprobe_path
        
        # Try to find ffprobe
        if not ffprobe_path or ffprobe_path == "ffprobe":
            ffmpeg_path = self.app_state.ffmpeg_path
            if ffmpeg_path != "ffmpeg" and os.path.exists(ffmpeg_path):
                base_dir = os.path.dirname(ffmpeg_path)
                candidate = os.path.join(base_dir, "ffprobe.exe" if os.name == 'nt' else "ffprobe")
                if os.path.exists(candidate):
                    ffprobe_path = candidate
                    
        try:
            # Get keyframe information
            cmd = [
                ffprobe_path,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "frame=pts_time",
                "-of", "csv=p=0",
                "-skip_frame", "nokey",
                video_path
            ]
            
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=10
            )
            
            if result.returncode == 0 and result.stdout:
                # Parse keyframe times
                keyframe_times = []
                for line in result.stdout.split('\n'):
                    try:
                        pts_time = float(line.strip())
                        keyframe_times.append(pts_time)
                    except ValueError:
                        continue
                
                if keyframe_times:
                    # Find nearest keyframe
                    nearest_kf = min(keyframe_times, key=lambda t: abs(t - target_time))
                    self.app_state.log(f"Aligned cut from {target_time:.3f}s to keyframe at {nearest_kf:.3f}s", "INFO")
                    return nearest_kf
            
            self.app_state.log("Could not align to keyframe, using exact position", "WARN")
            return target_time
            
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
