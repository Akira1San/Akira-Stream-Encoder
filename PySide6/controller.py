"""
Video Controller - Business logic for video encoding (PySide6)
"""
import os
import subprocess
import threading
import re
from typing import Optional, List, Dict, Any
from pathlib import Path

from models import AppState


class VideoController:
    """Handles all business logic for video encoding and file processing"""
    
    def __init__(self, app_state: AppState):
        self.app_state = app_state
        self.current_process: Optional[subprocess.Popen] = None
        self.is_encoding = False
        
    def get_video_duration(self, input_path: str) -> float:
        """
        Detects video duration using ffprobe or ffmpeg.
        """
        duration = 0.0
        ffprobe_path = self.app_state.ffprobe_path
        ffmpeg_path = self.app_state.ffmpeg_path
        
        # Try to find ffprobe
        if ffmpeg_path != "ffmpeg" and os.path.exists(ffmpeg_path):
            base_dir = os.path.dirname(ffmpeg_path)
            candidate = os.path.join(base_dir, "ffprobe.exe" if os.name == 'nt' else "ffprobe")
            if os.path.exists(candidate):
                ffprobe_path = candidate
                
        # Attempt 1: Use FFprobe
        if ffprobe_path:
            try:
                cmd = [
                    ffprobe_path,
                    "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    input_path
                ]
                result = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, timeout=60
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    duration = float(result.stdout.strip())
                    self.app_state.log(f"Duration detected via ffprobe: {duration} sec", "INFO")
                    return duration
            except subprocess.TimeoutExpired:
                self.app_state.log(f"ffprobe timed out for {os.path.basename(input_path)}. Trying ffmpeg...", "WARN")
            except Exception as e:
                self.app_state.log(f"ffprobe failed: {e}", "WARN")
                
        # Attempt 2: Fallback to ffmpeg
        try:
            cmd = [ffmpeg_path, "-i", input_path]
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=60
            )
            stderr_output = result.stderr
            
            # Regex for Duration
            match = re.search(r"Duration:\s*(\d{2}:\d{2}:\d{2})", stderr_output)
            if match:
                h, m, s = map(int, match.group(1).split(':'))
                duration = h * 3600 + m * 60 + s
                return duration
        except subprocess.TimeoutExpired:
            self.app_state.log(f"ffmpeg timed out for {os.path.basename(input_path)}.", "WARN")
        except Exception as e:
            self.app_state.log(f"ffmpeg detection failed: {e}", "WARN")
            
        return duration
        
    def get_video_bitrate(self, input_path: str) -> Optional[int]:
        """
        Detect the video bitrate of the input file.
        Returns bitrate in kbps (int) or None if failed.
        """
        ffprobe_path = self.app_state.ffprobe_path
        ffmpeg_path = self.app_state.ffmpeg_path
        
        # Try to find ffprobe
        if ffmpeg_path != "ffmpeg" and os.path.exists(ffmpeg_path):
            base_dir = os.path.dirname(ffmpeg_path)
            candidate = os.path.join(base_dir, "ffprobe.exe" if os.name == 'nt' else "ffprobe")
            if os.path.exists(candidate):
                ffprobe_path = candidate
                
        self.app_state.log(f"Detecting bitrate for {os.path.basename(input_path)}...", "INFO")
        
        try:
            # Method 1: ffprobe
            cmd = [
                ffprobe_path,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=bit_rate",
                "-of", "default=noprint_wrappers=1:nokey=1",
                input_path
            ]
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                br_bps = int(result.stdout.strip())
                br_kbps = br_bps // 1000
                self.app_state.log(f"Detected bitrate: {br_kbps} kbps", "INFO")
                return br_kbps
        except Exception as e:
            self.app_state.log(f"ffprobe detection failed: {e}", "WARN")
            
        try:
            # Method 2: Fallback to parsing ffmpeg -i
            cmd = [ffmpeg_path, "-i", input_path]
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=10
            )
            stderr_output = result.stderr
            
            match = re.search(r"bitrate:\s*(\d+)\s*kb/s", stderr_output)
            if match:
                br_kbps = int(match.group(1))
                self.app_state.log(f"Detected bitrate via ffmpeg: {br_kbps} kbps", "INFO")
                return br_kbps
        except Exception as e:
            self.app_state.log(f"ffmpeg bitrate parsing failed: {e}", "WARN")
            
        self.app_state.log("Could not detect original bitrate.", "WARN")
        return None
        
    def build_ffmpeg_command(self, input_path: str, output_path: str,
                            start_time: Optional[str] = None,
                            duration: Optional[str] = None) -> List[str]:
        """Build the complete FFmpeg command based on current settings"""
        # Store input path for subtitle filter
        self.current_input_path = input_path
        
        cmd = [self.app_state.ffmpeg_path]
        
        # Check fast split mode
        if self.app_state.split.enabled:
            self.app_state.log("Using Fast Split (Stream Copy)", "INFO")
            if start_time:
                cmd.extend(["-ss", start_time])
            if duration:
                cmd.extend(["-t", duration])
            cmd.extend(["-i", input_path])
            cmd.extend(["-c", "copy"])
            cmd.extend(["-y", output_path])
            return cmd
            
        # Check extract clip mode
        if self.app_state.split.extract_clip_enabled:
            self.app_state.log("Extracting clip segment", "INFO")
            start_min = self.app_state.split.extract_start_min
            duration_min = self.app_state.split.extract_duration_min
            start_time = f"{start_min}:00"
            duration = f"{duration_min}:00"
            cmd.extend(["-ss", start_time])
            cmd.extend(["-i", input_path])
            cmd.extend(["-t", duration])
            
            # Burn subtitles for clip extraction if enabled
            if self.app_state.subtitles.burn_subs:
                sub_path = self.find_subtitle_file(input_path)
                if sub_path:
                    subs_filter = self.build_subtitle_filter(sub_path)
                    if subs_filter:
                        cmd.extend(["-vf", subs_filter])
                        self.app_state.log(f"Burning subtitles from: {os.path.basename(sub_path)}", "INFO")
                else:
                    self.app_state.log("No external subtitle file found (.srt or .ass)", "WARN")
            
            # Audio codec for clip extraction - use copy or encode based on settings
            if self.app_state.tracks.audio_copy_mode:
                cmd.extend(["-c:a", "copy"])
                self.app_state.log("Audio: Copy original stream", "INFO")
            else:
                # Re-encode to AAC with 2 channels (stereo)
                cmd.extend(["-c:a", "aac", "-b:a", "192k", "-ac", "2"])
                self.app_state.log("Audio: Re-encode to AAC stereo", "INFO")
            cmd.extend(["-y", output_path])
            return cmd
        else:
            # Normal encoding mode
            self.app_state.log("Normal Re-Encoding Mode", "INFO")
            
            # Input and trim
            if start_time:
                cmd.extend(["-ss", start_time])
            cmd.extend(["-i", input_path])
            if duration:
                cmd.extend(["-t", duration])
            
        # Video codec - check if video mode is copy or encode
        video_mode = getattr(self.app_state.encoding, 'video_mode', 'encode')
        
        if video_mode == "copy":
            # Video copy mode - copy stream without re-encoding
            cmd.extend(["-c:v", "copy"])
            self.app_state.log("Video: Copy original stream (no re-encode)", "INFO")
        else:
            # Encode mode - use selected encoder
            encoder = self.app_state.encoding.encoder
            cmd.extend(["-c:v", encoder])
            
            # GPU settings
            if self.app_state.encoding.use_gpu and "nvenc" in encoder:
                cmd.extend(["-preset", "p4"])
                cmd.extend(["-cq", str(self.app_state.encoding.cq)])
            else:
                cmd.extend(["-crf", str(self.app_state.encoding.cq)])
                cmd.extend(["-preset", "medium"])
                
            # Resolution
            if self.app_state.encoding.resolution != "none":
                cmd.extend(["-s", self.app_state.encoding.resolution])
                
            # Framerate
            cmd.extend(["-r", self.app_state.encoding.framerate])
            
            # --- STRICT STREAMER FLAGS ---
            cmd.extend(["-g", "144"])  # GOP size
            cmd.extend(["-bf", "0"])  # No B-frames
            cmd.extend(["-pix_fmt", "yuv420p"])  # Pixel format
            cmd.extend(["-profile:v", "main"])  # Profile: main
            cmd.extend(["-level:v", "4.0"])  # Level 4.0 (compatible with level 120)
            
            # Bitrate
            if self.app_state.encoding.use_original_bitrate:
                orig_br = self.get_video_bitrate(input_path)
                if orig_br:
                    cmd.extend(["-b:v", f"{orig_br}k"])
            else:
                target_br = self.app_state.encoding.target_bitrate
                if target_br and target_br.isdigit():
                    cmd.extend(["-b:v", f"{target_br}k"])
                    cmd.extend(["-maxrate", f"{self.app_state.encoding.max_bitrate}k"])
                    cmd.extend(["-bufsize", f"{self.app_state.encoding.max_bitrate * 2}k"])
        
        # Map video stream
        if self.app_state.tracks.video_selected:
            cmd.extend(["-map", "0:v:0"])
        
        # Audio handling - check both track panel setting and encoding panel setting
        audio_mode = getattr(self.app_state.encoding, 'audio_mode', 'encode')
        
        # Use encoding panel audio mode by default, or track panel if set
        if audio_mode == "copy" or self.app_state.tracks.audio_copy_mode:
            audio_copy = True
        else:
            audio_copy = False
        
        if self.app_state.tracks.audio_selected:
            audio_stream_idx = self.app_state.tracks.audio_stream_index
            # Map the specific audio stream
            cmd.extend(["-map", f"0:a:{audio_stream_idx}"])
            
            if audio_copy:
                # Copy original audio without re-encoding
                cmd.extend(["-c:a", "copy"])
                self.app_state.log(f"Audio: Copy original stream (track {audio_stream_idx})", "INFO")
            else:
                # Re-encode to AAC with standard settings - force 2 channels (stereo)
                cmd.extend(["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2"])
                self.app_state.log(f"Audio: Re-encode to AAC stereo (track {audio_stream_idx})", "INFO")
        else:
            # No audio
            cmd.extend(["-an"])
            self.app_state.log("Audio: Disabled", "INFO")
        
        # Filters
        filter_complex = self.build_filter_complex(input_path)
        if filter_complex:
            cmd.extend(["-vf", filter_complex])
            
        # Output
        cmd.extend(["-y", output_path])
        
        return cmd
        
    def build_filter_complex(self, input_path: str = "") -> str:
        """Build FFmpeg filter complex string from settings"""
        filters = []
        
        # Deinterlace
        if self.app_state.filters.deinterlace:
            filters.append("yadif")
            
        # Denoise
        if self.app_state.filters.denoise:
            filters.append("hqdn3d")
            
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
        
        # Subtitles burn-in - look for external subtitle files
        if self.app_state.subtitles.burn_subs:
            sub_path = self.find_subtitle_file(input_path)
            if sub_path:
                subs_filter = self.build_subtitle_filter(sub_path)
                if subs_filter:
                    filters.append(subs_filter)
                    self.app_state.log(f"Burning subtitles from: {os.path.basename(sub_path)}", "INFO")
            else:
                self.app_state.log("No external subtitle file found (.srt or .ass)", "WARN")
                
        # Volume
        if self.app_state.filters.volume_enabled:
            filters.append(f"volume={self.app_state.filters.volume_db}dB")
        
        # Audio Denoise (afftdn - FFT-based denoiser)
        if getattr(self.app_state.filters, 'audio_denoise', False):
            # afftdn with preset settings for general noise reduction
            # nf=-25 is a good default for typical background noise
            filters.append("afftdn=nf=-25")
            self.app_state.log("Audio: Applying noise reduction filter", "INFO")
            
        return ",".join(filters) if filters else ""
        
    def find_subtitle_file(self, video_path: str) -> Optional[str]:
        """Find external subtitle file (.srt or .ass) for the video"""
        if not video_path:
            return None
        base = os.path.splitext(video_path)[0]
        for ext in [".srt", ".ass"]:
            sub_path = base + ext
            if os.path.exists(sub_path):
                return sub_path
        return None
    
    def build_subtitle_filter(self, sub_path: str) -> str:
        """Build FFmpeg subtitle filter with styling options"""
        subs = self.app_state.subtitles
        
        # Escape path for FFmpeg filter (Windows paths need special handling)
        # Convert backslashes to forward slashes and escape colons
        escaped_path = sub_path.replace("\\", "/").replace(":", "\\:")
        
        # Build force_style options
        style = []
        
        if subs.font != "Arial":
            style.append(f"Fontname={subs.font}")
        if subs.size != 24:
            style.append(f"Fontsize={subs.size}")
        if subs.color != "#FFFFFF":
            style.append(f"PrimaryColour={self.hex_to_ass(subs.color)}")
        if subs.outline_color != "#000000":
            style.append(f"OutlineColour={self.hex_to_ass(subs.outline_color)}")
        if subs.outline_width != 2:
            style.append(f"Outline={subs.outline_width}")
        
        # Background color and opacity
        if subs.bg_opacity > 0.0:
            ass_bg = self.hex_to_ass(subs.bg_color, subs.bg_opacity)
            style.append(f"BackColour={ass_bg}")
            style.append("BorderStyle=4")  # Opaque box background
        
        # Position mapping
        pos_map = {"bottom": 2, "top": 8, "center": 10}
        if subs.position != "bottom":
            style.append(f"Alignment={pos_map.get(subs.position, 2)}")
        
        # Build the filter string
        force_style = f":force_style='{','.join(style)}'" if style else ""
        return f"subtitles='{escaped_path}'{force_style}"
    
    def hex_to_ass(self, hex_color: str, opacity: float = 1.0) -> str:
        """Convert hex color to ASS format (&HAABBGGRR)"""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        alpha = int((1.0 - opacity) * 255)
        return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"

    def encode_file(self, input_path: str, output_path: str,
                   progress_callback=None,
                   start_time: Optional[str] = None,
                   duration: Optional[str] = None) -> bool:
        """
        Encode a single video file.
        
        Args:
            input_path: Path to input video
            output_path: Path to output video
            progress_callback: Function to call with progress updates
            start_time: Start time for trim (optional)
            duration: Duration for trim (optional)
            
        Returns:
            True if successful, False otherwise
        """
        cmd = self.build_ffmpeg_command(input_path, output_path, start_time, duration)
        
        self.app_state.log(f"Starting encode: {os.path.basename(input_path)}", "INFO")
        self.app_state.log(f"Command: {' '.join(cmd)}", "INFO")
        
        try:
            self.is_encoding = True
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # Parse output for progress
            duration = self.get_video_duration(input_path)
            
            for line in self.current_process.stdout:
                line = line.strip()
                
                # Log progress lines (frame=, fps=, time=, etc.)
                if line.startswith('frame=') or 'fps=' in line or 'time=' in line:
                    self.app_state.log(f"Progress: {line}", "DEBUG")
                
                if progress_callback:
                    # Parse time from FFmpeg output
                    time_match = re.search(r"time=(\d{2}):(\d{2}):(\d{2})", line)
                    if time_match and duration > 0:
                        h, m, s = map(int, time_match.groups())
                        current_time = h * 3600 + m * 60 + s
                        progress = min(100, int((current_time / duration) * 100))
                        progress_callback(progress)
                        
            self.current_process.wait()
            
            if self.current_process.returncode == 0:
                self.app_state.log(f"✅ Encode complete: {os.path.basename(output_path)}", "SUCCESS")
                return True
            else:
                self.app_state.log(f"❌ Encode failed with code {self.current_process.returncode}", "ERROR")
                return False
                
        except Exception as e:
            self.app_state.log(f"❌ Encode error: {e}", "ERROR")
            return False
        finally:
            self.is_encoding = False
            self.current_process = None
            
    def cancel_encode(self):
        """Cancel the current encoding operation"""
        if self.current_process:
            self.current_process.terminate()
            self.app_state.log("Encoding cancelled by user", "INFO")
    
    def fast_cut_file(self, input_path: str, output_path: str,
                     start_time: Optional[str] = None,
                     duration: Optional[str] = None) -> bool:
        """
        Fast cut a video file without re-encoding (stream copy).
        Much faster than encoding but requires keyframe alignment.
        
        Args:
            input_path: Path to input video
            output_path: Path to output video
            start_time: Start time for trim (optional)
            duration: Duration for trim (optional)
            
        Returns:
            True if successful, False otherwise
        """
        cmd = [self.app_state.ffmpeg_path]
        
        # Seek to start position before input (faster)
        if start_time:
            cmd.extend(["-ss", start_time])
        
        cmd.extend(["-i", input_path])
        
        # Duration
        if duration:
            cmd.extend(["-t", duration])
        
        # Copy video and audio streams without re-encoding
        cmd.extend(["-c:v", "copy"])
        
        # Map video stream
        if self.app_state.tracks.video_selected:
            cmd.extend(["-map", "0:v:0"])
        
        # Audio handling - map specific stream
        if self.app_state.tracks.audio_selected:
            audio_stream_idx = self.app_state.tracks.audio_stream_index
            cmd.extend(["-map", f"0:a:{audio_stream_idx}"])
            
            if self.app_state.tracks.audio_copy_mode:
                cmd.extend(["-c:a", "copy"])
            else:
                # Re-encode audio but keep video copy
                cmd.extend(["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2"])
        else:
            cmd.extend(["-an"])
        
        # Avoid timestamp issues
        cmd.extend(["-avoid_negative_ts", "make_zero"])
        
        # Output
        cmd.extend(["-y", output_path])
        
        self.app_state.log(f"Fast cutting: {os.path.basename(input_path)}", "INFO")
        self.app_state.log(f"Command: {' '.join(cmd)}", "INFO")
        
        try:
            self.is_encoding = True
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            for line in self.current_process.stdout:
                line = line.strip()
                if line:
                    self.app_state.log(f"Fast cut: {line}", "DEBUG")
            
            self.current_process.wait()
            
            if self.current_process.returncode == 0:
                self.app_state.log(f"✅ Fast cut complete: {os.path.basename(output_path)}", "SUCCESS")
                return True
            else:
                self.app_state.log(f"❌ Fast cut failed with code {self.current_process.returncode}", "ERROR")
                return False
                
        except Exception as e:
            self.app_state.log(f"❌ Fast cut error: {e}", "ERROR")
            return False
        finally:
            self.is_encoding = False
            self.current_process = None
            
    def generate_output_path(self, input_path: str) -> str:
        """Generate output path based on settings"""
        if self.app_state.use_custom_filename and self.app_state.custom_filename:
            base_name = self.app_state.custom_filename
        else:
            base_name = Path(input_path).stem
            
        container = self.app_state.encoding.container
        output_folder = self.app_state.output_folder or os.path.dirname(input_path)
        
        # Add suffix if split mode
        if self.app_state.split.enabled:
            base_name += "_part1"
            
        output_path = os.path.join(output_folder, f"{base_name}.{container}")
        
        # Handle duplicates
        counter = 1
        original_path = output_path
        while os.path.exists(output_path):
            name = f"{Path(original_path).stem}_{counter}"
            output_path = os.path.join(output_folder, f"{name}.{container}")
            counter += 1
            
        return output_path
