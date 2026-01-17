import os
import subprocess
import re


class TrimController:
    """Business logic for single-cut trimming operations"""
    
    def __init__(self, app_state, log_callback):
        self.state = app_state
        self.log = log_callback
        self.MINIMUM_SEGMENT_DURATION = 5.0  # 5 seconds minimum per segment
    
    def validate_cut_position(self, cut_time, total_duration):
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
    
    def align_to_keyframe(self, video_path, target_time):
        """
        Find nearest keyframe to target time
        
        Args:
            video_path: Path to video file
            target_time: Desired cut position in seconds
            
        Returns:
            adjusted_time: float (aligned to nearest keyframe)
        """
        # Try to find keyframes using ffprobe
        ffprobe_path = "ffprobe"
        ffmpeg_path = getattr(self.state, 'ffmpeg_path').get()
        
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
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            
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
                    self.log(f"Aligned cut from {target_time:.3f}s to keyframe at {nearest_kf:.3f}s")
                    return nearest_kf
            
            self.log("Could not align to keyframe, using exact position")
            return target_time
            
        except Exception as e:
            self.log(f"Keyframe alignment failed: {e}. Using exact position.")
            return target_time
    
    def get_selected_tracks(self):
        """
        Get list of selected track types
        
        Returns:
            list of track types: ["video", "audio", "subtitle"]
        """
        selected = []
        
        if getattr(self.state, 'track_video_selected').get():
            selected.append("video")
        
        if getattr(self.state, 'track_audio_selected').get():
            selected.append("audio")
        
        if getattr(self.state, 'track_subtitle_available').get() and \
           getattr(self.state, 'track_subtitle_selected').get():
            selected.append("subtitle")
        
        return selected
    
    def execute_single_cut(self, input_path, cut_time, tracks_to_cut):
        """
        Execute single cut operation
        
        Args:
            input_path: Path to input video file
            cut_time: Cut position in seconds (keyframe aligned)
            tracks_to_cut: List of track types to cut ("video", "audio", "subtitle")
            
        Returns:
            (success: bool, message: str)
        """
        try:
            total_duration = self.get_video_duration(input_path)
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_folder = getattr(self.state, 'output_folder').get()
            container = getattr(self.state, 'container').get()
            
            # Cut position already aligned to keyframe
            aligned_cut_time = cut_time
            
            # Create segment 1 (before cut)
            output_path_1 = os.path.join(output_folder, f"{base_name}_part1.{container}")
            success_1, msg_1 = self._create_segment(
                input_path, output_path_1, 
                0.0, aligned_cut_time, 
                tracks_to_cut,
                container
            )
            
            if not success_1:
                return False, msg_1
            
            # Create segment 2 (after cut)
            output_path_2 = os.path.join(output_folder, f"{base_name}_part2.{container}")
            success_2, msg_2 = self._create_segment(
                input_path, output_path_2,
                aligned_cut_time, total_duration,
                tracks_to_cut,
                container
            )
            
            if not success_2:
                return False, msg_2
            
            return True, f"Successfully cut video into 2 segments: {base_name}_part1.{container} and {base_name}_part2.{container}"
            
        except Exception as e:
            return False, f"Cut operation failed: {str(e)}"
    
    def _create_segment(self, input_path, output_path, start_time, end_time, tracks_to_cut, container):
        """
        Create a single video segment
        
        Args:
            input_path: Input video path
            output_path: Output video path
            start_time: Start time in seconds
            end_time: End time in seconds
            tracks_to_cut: List of track types to include
            container: Container format (mp4, mkv, avi)
            
        Returns:
            (success: bool, message: str)
        """
        # Format times for FFmpeg
        sh, sm, ss = self._seconds_to_hms(start_time)
        start_str = f"{sh:02d}:{sm:02d}:{ss:02d}"
        
        eh, em, es = self._seconds_to_hms(end_time)
        end_str = f"{eh:02d}:{em:02d}:{es:02d}"
        
        # Build FFmpeg command
        ffmpeg_path = getattr(self.state, 'ffmpeg_path').get()
        cmd = [ffmpeg_path]
        
        # Start time (fast seeking at keyframe)
        cmd.extend(["-ss", start_str])
        
        # Input file
        cmd.extend(["-i", input_path])
        
        # End time
        duration = end_time - start_time
        dh, dm, ds = self._seconds_to_hms(duration)
        duration_str = f"{dh:02d}:{dm:02d}:{ds:02d}"
        cmd.extend(["-t", duration_str])
        
        # Stream copy flags based on selected tracks
        if "video" not in tracks_to_cut:
            cmd.append("-an")  # No audio
        
        if "audio" not in tracks_to_cut:
            cmd.append("-vn")  # No video
        
        # Stream copy (fast)
        cmd.extend(["-c", "copy"])
        
        # Output file with container format (no problematic flags needed for stream copy)
        cmd.extend(["-f", container])
        cmd.extend(["-y", output_path])
        
        try:
            self.log(f"Creating segment: {' '.join(cmd)}")
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
            
            if result.returncode != 0:
                return False, f"FFmpeg failed with code {result.returncode}"
            
            return True, ""
            
        except subprocess.TimeoutExpired:
            return False, "Segment creation timed out (5 minutes). Try reducing complexity."
        except Exception as e:
            return False, f"Segment creation error: {str(e)}"
    
    def get_video_duration(self, input_path):
        """
        Get video duration using ffprobe
        
        Args:
            input_path: Path to video file
            
        Returns:
            duration in seconds (float)
        """
        ffprobe_path = "ffprobe"
        ffmpeg_path = getattr(self.state, 'ffmpeg_path').get()
        
        if ffmpeg_path != "ffmpeg" and os.path.exists(ffmpeg_path):
            base_dir = os.path.dirname(ffmpeg_path)
            candidate = os.path.join(base_dir, "ffprobe.exe" if os.name == 'nt' else "ffprobe")
            if os.path.exists(candidate):
                ffprobe_path = candidate
        
        try:
            cmd = [
                ffprobe_path,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                input_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
            
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
            
        except Exception as e:
            self.log(f"Could not get video duration: {e}")
        
        return 0.0
    
    def _seconds_to_hms(self, seconds):
        """Convert seconds to hours:minutes:seconds"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return h, m, s