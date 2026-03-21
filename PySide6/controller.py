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
        Handles both regular video files and DVD concat files.
        """
        duration = 0.0
        ffprobe_path = self.app_state.ffprobe_path
        ffmpeg_path = self.app_state.ffmpeg_path
        
        # Check if this is a DVD concat file
        is_dvd_concat = input_path.endswith('.txt') and self.app_state.dvd.is_dvd_source
        
        # Try to find ffprobe
        if ffmpeg_path != "ffmpeg" and os.path.exists(ffmpeg_path):
            base_dir = os.path.dirname(ffmpeg_path)
            candidate = os.path.join(base_dir, "ffprobe.exe" if os.name == 'nt' else "ffprobe")
            if os.path.exists(candidate):
                ffprobe_path = candidate
                
        # Attempt 1: Use FFprobe
        if ffprobe_path:
            try:
                # Build command - add concat demuxer for DVD sources
                cmd = [ffprobe_path, "-v", "error"]
                if is_dvd_concat:
                    cmd.extend(["-f", "concat", "-safe", "0"])
                cmd.extend(["-i", input_path])
                cmd.extend([
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1"
                ])
                result = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, timeout=60
                )
                
                if result.returncode == 0 and result.stdout.strip() and result.stdout.strip() != 'N/A':
                    duration = float(result.stdout.strip())
                    self.app_state.log(f"Duration detected via ffprobe: {duration} sec", "INFO")
                    return duration
            except subprocess.TimeoutExpired:
                self.app_state.log(f"ffprobe timed out for {os.path.basename(input_path)}. Trying ffmpeg...", "WARN")
            except Exception as e:
                self.app_state.log(f"ffprobe failed: {e}", "WARN")
        
        # Attempt 1.5: For DVD sources, use pre-calculated duration from title scan
        if is_dvd_concat and self.app_state.dvd.available_titles:
            for title in self.app_state.dvd.available_titles:
                if title.title_number == self.app_state.dvd.selected_title_number:
                    duration = title.duration
                    self.app_state.log(f"Using pre-scanned DVD duration: {duration} sec", "INFO")
                    return duration
                
        # Attempt 2: Fallback to ffmpeg
        try:
            cmd = [ffmpeg_path]
            if is_dvd_concat:
                cmd.extend(["-f", "concat", "-safe", "0"])
            cmd.extend(["-i", input_path])
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
    
    def get_audio_tracks(self, input_path: str) -> List[dict]:
        """
        Detects audio tracks in the input video using ffprobe.
        Returns list of dicts with: index, codec, channels, sample_rate, language, title
        """
        audio_tracks = []
        ffprobe_path = self.app_state.ffprobe_path
        ffmpeg_path = self.app_state.ffmpeg_path
        
        # Try to find ffprobe
        if ffmpeg_path != "ffmpeg" and os.path.exists(ffmpeg_path):
            base_dir = os.path.dirname(ffmpeg_path)
            candidate = os.path.join(base_dir, "ffprobe.exe" if os.name == 'nt' else "ffprobe")
            if os.path.exists(candidate):
                ffprobe_path = candidate
        
        if not ffprobe_path:
            ffprobe_path = "ffprobe"
        
        try:
            cmd = [
                ffprobe_path,
                "-v", "error",
                "-show_entries", "stream=index,codec_type,codec_name,channels,sample_rate:stream_tags=language,title",
                "-of", "json",
                input_path
            ]
            
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=30
            )
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                
                for stream in data.get('streams', []):
                    if stream.get('codec_type') == 'audio':
                        tags = stream.get('tags', {})
                        track_info = {
                            'index': stream.get('index', 0),
                            'codec': stream.get('codec_name', 'unknown'),
                            'channels': stream.get('channels', 2),
                            'sample_rate': stream.get('sample_rate', ''),
                            'language': tags.get('language', ''),
                            'title': tags.get('title', '')
                        }
                        audio_tracks.append(track_info)
                        
        except Exception as e:
            self.app_state.log(f"Audio track detection failed: {e}", "WARN")
            
        return audio_tracks
        
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
        
        # Check if this is a DVD concat source
        is_dvd_source = self.app_state.dvd.is_dvd_source and input_path.endswith('.txt')
        
        # Check extract clip mode
        if self.app_state.split.extract_clip_enabled:
            self.app_state.log("Extracting clip segment", "INFO")
            start_min = self.app_state.split.extract_start_min
            duration_min = self.app_state.split.extract_duration_min
            # Convert minutes to seconds for FFmpeg (avoids HH:MM vs MM:SS confusion)
            start_time = str(int(start_min * 60))
            duration = str(int(duration_min * 60))
            
            burn_subs = self.app_state.subtitles.burn_subs
            sub_path = self.find_subtitle_file(input_path) if burn_subs else None
            
            # Check for DVD subtitle burning - NOT SUPPORTED (dvd_subtitle is bitmap format)
            # FFmpeg cannot convert dvd_subtitle to text format or overlay bitmap subtitles
            burning_dvd_subs = is_dvd_source and self.app_state.dvd.selected_subtitle_index >= 0
            if burning_dvd_subs:
                self.app_state.log("DVD subtitle burning is not supported (bitmap format). Skipping subtitle burn.", "WARN")
                self.app_state.log("Tip: Use HandBrake or mencoder for DVD subtitle burning.", "INFO")
            
            # Add concat demuxer flags for DVD sources
            if is_dvd_source:
                cmd.extend(["-f", "concat", "-safe", "0"])
            
            # External subtitle burning (non-DVD sources)
            if burn_subs and sub_path and not is_dvd_source:
                cmd.extend(["-i", input_path])
                
                # Handle external audio file for subtitle burning mode
                external_audio_enabled = getattr(self.app_state.tracks, 'external_audio_enabled', False)
                external_audio_path = getattr(self.app_state.tracks, 'external_audio_path', '')
                
                if external_audio_enabled and external_audio_path and os.path.exists(external_audio_path):
                    cmd.extend(["-i", external_audio_path])
                    self.app_state.log(f"External Audio: Using {os.path.basename(external_audio_path)}", "INFO")
                    self._external_audio_enabled = True
                else:
                    self._external_audio_enabled = False
                
                cmd.extend(["-ss", start_time])
                cmd.extend(["-t", duration])
                
                # Build full filter chain including AR conversion and all video filters
                video_filters, audio_filters = self.build_filter_complex(input_path)
                
                subs_filter = self.build_subtitle_filter(sub_path)
                if subs_filter:
                    # Build filter chain with subtitle burn + all video filters
                    filter_parts = []
                    
                    # Add video filters first (AR conversion, scale, etc.)
                    if video_filters:
                        filter_parts.append(video_filters)
                    
                    # Add subtitle burn
                    filter_parts.append(subs_filter)
                    
                    filter_parts.append("setpts=PTS-STARTPTS")
                    vf_chain = ",".join(filter_parts)
                    
                    cmd.extend(["-vf", vf_chain])
                    cmd.extend(["-af", "asetpts=PTS-STARTPTS"])
                    self.app_state.log(f"Burning subtitles with video filters (including AR conversion)", "INFO")
            else:
                cmd.extend(["-ss", start_time])
                cmd.extend(["-i", input_path])
                
                # Handle external audio file for extract clip mode
                external_audio_enabled = getattr(self.app_state.tracks, 'external_audio_enabled', False)
                external_audio_path = getattr(self.app_state.tracks, 'external_audio_path', '')
                
                if external_audio_enabled and external_audio_path and os.path.exists(external_audio_path):
                    cmd.extend(["-i", external_audio_path])
                    self.app_state.log(f"External Audio: Using {os.path.basename(external_audio_path)}", "INFO")
                    self._external_audio_enabled = True
                else:
                    self._external_audio_enabled = False
                
                cmd.extend(["-t", duration])
                
                # Build video filters (includes AR conversion, scale, deinterlace, etc.)
                video_filters, audio_filters = self.build_filter_complex(input_path)
                
                # Apply video filters if any
                if video_filters:
                    cmd.extend(["-vf", video_filters])
                    self.app_state.log(f"Applying video filters (including AR conversion)", "INFO")
                elif self.app_state.encoding.resolution != "none" and self.app_state.encoding.scale_mode == "off":
                    # Fallback: use -s for resolution if no complex filters
                    cmd.extend(["-s", self.app_state.encoding.resolution])
                    self.app_state.log(f"Scale output to {self.app_state.encoding.resolution}", "INFO")
                
                if burn_subs and not is_dvd_source:
                    self.app_state.log("No external subtitle file found (.srt, .ass, .ssa, .sub)", "WARN")
            
            # Video codec handling for extract clip mode
            video_mode = getattr(self.app_state.encoding, 'video_mode', 'encode')
            if video_mode == "copy":
                cmd.extend(["-c:v", "copy"])
                self.app_state.log("Video: Copy original stream (no re-encode)", "INFO")
            else:
                encoder = self.app_state.encoding.encoder
                cmd.extend(["-c:v", encoder])
                self.app_state.log(f"Video: Encoding with {encoder}", "INFO")
                
                # GPU settings
                if self.app_state.encoding.use_gpu and "nvenc" in encoder:
                    cmd.extend(["-preset", self.app_state.encoding.gpu_preset])
                    cmd.extend(["-cq", str(self.app_state.encoding.cq)])
                else:
                    cmd.extend(["-crf", str(self.app_state.encoding.cq)])
                    cmd.extend(["-preset", self.app_state.encoding.cpu_preset])
                    if self.app_state.encoding.cpu_tune != "none":
                        cmd.extend(["-tune", self.app_state.encoding.cpu_tune])
                
                # Resolution - ONLY add -s if video filters are NOT applied (they handle scaling)
                # If video_filters were applied via -vf, don't override with -s
                if self.app_state.encoding.resolution != "none" and self.app_state.encoding.scale_mode == "off":
                    if video_filters:
                        # Video filters already applied - they include scale, don't add -s
                        self.app_state.log(f"Resolution handled by video filters (not adding -s)", "INFO")
                    else:
                        cmd.extend(["-s", self.app_state.encoding.resolution])
                
                # Pixel format for compatibility
                cmd.extend(["-pix_fmt", "yuv420p"])
                
                # --- STRICT STREAMER FLAGS for extract clip ---
                # H.265 (libx265) requires x265-params for keyframe and level control
                if encoder == "libx265":
                    cmd.extend(["-x265-params", "keyint=144:min-keyint=144:bframes=0:level=4.0"])
                else:
                    # H.264 and NVENC use standard flags
                    cmd.extend(["-g", "144"])  # GOP size
                    cmd.extend(["-bf", "0"])  # No B-frames
                
                # Profile and level
                cmd.extend(["-profile:v", "main"])  # Profile: main
                if encoder != "libx265":
                    cmd.extend(["-level:v", "4.0"])  # Level for H.264/NVENC
                
                # Force keyframe at start for clean cut
                cmd.extend(["-force_key_frames:v", "0"])
            
            # Map video from first input (external audio would be second input if present)
            if self.app_state.tracks.video_selected:
                if self._external_audio_enabled:
                    cmd.extend(["-map", "0:v"])
                else:
                    cmd.extend(["-map", "0:v"])
            
            # Map audio - either from external or from input file
            if self.app_state.tracks.audio_selected:
                if self._external_audio_enabled:
                    cmd.extend(["-map", "1:a"])
                else:
                    cmd.extend(["-map", "0:a"])  # Map audio from input file
            
            # Build audio filters for extract clip mode
            _, audio_filters = self.build_filter_complex(input_path)
            
            # Handle external audio in extract clip mode
            if self._external_audio_enabled:
                cmd.extend(["-map", "1:a"])
                
                # Use copy mode by default for external audio
                if self.app_state.tracks.audio_copy_mode:
                    ext_audio_path = self.app_state.tracks.external_audio_path
                    ext = os.path.splitext(ext_audio_path)[1].lower()
                    if ext in ['.mp3', '.aac', '.ac3', '.m4a', '.flac', '.ogg', '.wav']:
                        cmd.extend(["-c:a", "copy"])
                        self.app_state.log("Audio: Copy external file", "INFO")
                    else:
                        cmd.extend(["-c:a", "aac", "-b:a", "128k", "-ac", "2"])
                        self.app_state.log("Audio: Re-encode external to AAC", "INFO")
                else:
                    cmd.extend(["-c:a", "aac", "-b:a", "128k", "-ac", "2", "-channel_layout", "stereo"])
                    self.app_state.log("Audio: Re-encode external to AAC stereo", "INFO")
                
                # Use shortest to handle duration mismatch
                cmd.extend(["-shortest"])
                
            elif self.app_state.tracks.audio_copy_mode:
                # Cannot apply audio filters in copy mode - warn user
                if audio_filters:
                    self.app_state.log("Audio: Copy mode - audio filters (volume, denoise, etc.) will not be applied", "WARN")
                cmd.extend(["-c:a", "copy"])
                self.app_state.log("Audio: Copy original stream", "INFO")
            else:
                cmd.extend(["-c:a", "aac", "-b:a", "128k", "-ac", "2", "-channel_layout", "stereo"])
                self.app_state.log("Audio: Re-encode to AAC stereo", "INFO")
                # Apply audio filters when re-encoding
                if audio_filters:
                    cmd.extend(["-af", audio_filters])
                    self.app_state.log(f"Audio filters: {audio_filters}", "INFO")
            cmd.extend(["-y", output_path])
            return cmd
        else:
            # Normal encoding mode
            self.app_state.log("Normal Re-Encoding Mode", "INFO")
            
            # Check for DVD subtitle burning - NOT SUPPORTED (dvd_subtitle is bitmap format)
            burning_dvd_subs = is_dvd_source and self.app_state.dvd.selected_subtitle_index >= 0
            if burning_dvd_subs:
                self.app_state.log("DVD subtitle burning is not supported (bitmap format). Skipping subtitle burn.", "WARN")
                self.app_state.log("Tip: Use HandBrake or mencoder for DVD subtitle burning.", "INFO")
            
            # Add hardware decoding for GPU encoders
            encoder = self.app_state.encoding.encoder
            if self.app_state.encoding.use_gpu and "nvenc" in encoder:
                cmd.extend(["-hwaccel", "cuda"])
            
            # Handle DVD concat source
            if is_dvd_source:
                self.app_state.log("DVD Source: Using concat demuxer", "INFO")
                cmd.extend(["-f", "concat", "-safe", "0"])
            
            cmd.extend(["-i", input_path])
            
            # Handle external audio file
            external_audio_enabled = getattr(self.app_state.tracks, 'external_audio_enabled', False)
            external_audio_path = getattr(self.app_state.tracks, 'external_audio_path', '')
            
            if external_audio_enabled and external_audio_path and os.path.exists(external_audio_path):
                cmd.extend(["-i", external_audio_path])
                self.app_state.log(f"External Audio: Using {os.path.basename(external_audio_path)}", "INFO")
            else:
                external_audio_enabled = False  # Reset if file doesn't exist
            
            # Store for later use in audio mapping
            self._external_audio_enabled = external_audio_enabled
            
            # Seek AFTER input for accurate frame-precise seeking (avoids green frames)
            if start_time:
                cmd.extend(["-ss", start_time])
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
                cmd.extend(["-preset", self.app_state.encoding.gpu_preset])
                cmd.extend(["-cq", str(self.app_state.encoding.cq)])
            else:
                cmd.extend(["-crf", str(self.app_state.encoding.cq)])
                cmd.extend(["-preset", self.app_state.encoding.cpu_preset])
                if self.app_state.encoding.cpu_tune != "none":
                    cmd.extend(["-tune", self.app_state.encoding.cpu_tune])
            
            # Resolution - only use -s if scale_mode is off
            # Note: When AR conversion is used, the filter chain handles dimensions - don't use -s
            if self.app_state.encoding.resolution != "none" and self.app_state.encoding.scale_mode == "off":
                # Only add -s if AR conversion is NOT enabled (filter handles it)
                ar_enabled = getattr(self.app_state.filters, 'ar_convert_enabled', False)
                if ar_enabled:
                    self.app_state.log(f"AR conversion enabled - using filter dimensions (not adding -s)", "INFO")
                else:
                    cmd.extend(["-s", self.app_state.encoding.resolution])
                
            # Framerate
            cmd.extend(["-r", self.app_state.encoding.framerate])
            
            # --- STRICT STREAMER FLAGS ---
            
            # H.265 (libx265) requires x265-params for keyframe and level control
            if encoder == "libx265":
                # Use x265-params for H.265 specific settings (keyint, bframes, level)
                cmd.extend(["-x265-params", "keyint=144:min-keyint=144:bframes=0:level=4.0"])
            else:
                # H.264 and NVENC use standard flags
                cmd.extend(["-g", "144"])  # GOP size
                cmd.extend(["-bf", "0"])  # No B-frames
            
            cmd.extend(["-pix_fmt", "yuv420p"])  # Pixel format
            
            # Profile and level - handle differently for H.265
            if encoder == "libx265":
                cmd.extend(["-profile:v", "main"])  # Profile: main for H.265
                # Level is set in x265-params above
            else:
                cmd.extend(["-profile:v", "main"])  # Profile: main
                cmd.extend(["-level:v", "4.0"])  # Level 4.0 for H.264/NVENC
            
            # Force keyframe at start to avoid green frames after seeking/cutting
            cmd.extend(["-force_key_frames:v", "0"])
            
            # Bitrate
            if self.app_state.encoding.use_original_bitrate:
                orig_br = self.get_video_bitrate(input_path)
                if orig_br:
                    cmd.extend(["-b:v", f"{orig_br}k"])
                    cmd.extend(["-maxrate", f"{orig_br}k"])
                    cmd.extend(["-bufsize", f"{orig_br * 2}k"])
            else:
                target_br = self.app_state.encoding.target_bitrate
                if target_br and target_br.isdigit():
                    target_br_int = int(target_br)
                    cmd.extend(["-b:v", f"{target_br_int}k"])
                    cmd.extend(["-maxrate", f"{target_br_int}k"])
                    cmd.extend(["-bufsize", f"{target_br_int * 2}k"])
        
        # Map video stream
        if self.app_state.tracks.video_selected:
            cmd.extend(["-map", "0:v:0"])
        
        # Audio handling - check external audio first
        external_audio_enabled = getattr(self, '_external_audio_enabled', False)
        
        # Use encoding panel audio mode by default, or track panel if set
        audio_mode = getattr(self.app_state.encoding, 'audio_mode', 'encode')
        if audio_mode == "copy" or self.app_state.tracks.audio_copy_mode:
            audio_copy = True
        else:
            audio_copy = False
        
        # Check if we should use external audio
        use_external_audio = (
            external_audio_enabled and 
            self.app_state.tracks.audio_selected and
            getattr(self.app_state.tracks, 'external_audio_path', '')
        )
        
        if use_external_audio:
            # Use external audio (input index 1)
            cmd.extend(["-map", "1:a"])
            
            # For external audio, use copy mode by default (faster and maintains quality)
            # or encode mode based on user preference
            if audio_copy:
                # Determine codec from file extension
                ext_audio_path = self.app_state.tracks.external_audio_path
                ext = os.path.splitext(ext_audio_path)[1].lower()
                
                # Most formats support stream copy
                if ext in ['.mp3', '.aac', '.ac3', '.m4a', '.flac', '.ogg', '.wav']:
                    cmd.extend(["-c:a", "copy"])
                    self.app_state.log(f"Audio: Copy external file ({os.path.basename(ext_audio_path)})", "INFO")
                else:
                    # Re-encode if format doesn't support copy
                    cmd.extend(["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"])
                    self.app_state.log(f"Audio: Re-encode external file to AAC", "INFO")
            else:
                # Re-encode external audio to AAC
                cmd.extend(["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", "-channel_layout", "stereo"])
                self.app_state.log("Audio: Re-encode external audio to AAC stereo", "INFO")
            
            # Use -shortest to ensure output doesn't exceed shorter of video/audio
            cmd.extend(["-shortest"])
            
        elif self.app_state.tracks.audio_selected:
            # Use embedded audio from video file
            audio_stream_idx = self.app_state.tracks.audio_stream_index
            # Default to first audio stream (0) if index is invalid
            if audio_stream_idx is None or audio_stream_idx < 0:
                audio_stream_idx = 0
            # Map the specific audio stream
            cmd.extend(["-map", f"0:a:{audio_stream_idx}"])
            
            if audio_copy:
                # Copy original audio without re-encoding
                cmd.extend(["-c:a", "copy"])
                self.app_state.log(f"Audio: Copy original stream (track {audio_stream_idx})", "INFO")
            else:
                # Re-encode to AAC with standard settings - force 2 channels (stereo)
                cmd.extend(["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", "-channel_layout", "stereo"])
                self.app_state.log(f"Audio: Re-encode to AAC stereo (track {audio_stream_idx})", "INFO")
        else:
            # No audio
            cmd.extend(["-an"])
            self.app_state.log("Audio: Disabled", "INFO")
        
        # Filters (video and audio separated)
        video_filters, audio_filters = self.build_filter_complex(input_path)
        
        # Apply video filters
        if video_filters:
            cmd.extend(["-vf", video_filters])
        if audio_filters:
            cmd.extend(["-af", audio_filters])
            
        # Output
        cmd.extend(["-y", output_path])
        
        return cmd
        
    def build_filter_complex(self, input_path: str = "") -> tuple:
        """Build FFmpeg filter strings - returns (video_filters, audio_filters)"""
        video_filters = []
        audio_filters = []
        
        # Scale filter with algorithm (when scale_mode is "on")
        if self.app_state.encoding.scale_mode == "on" and self.app_state.encoding.resolution != "none":
            res = self.app_state.encoding.resolution
            algorithm = self.app_state.encoding.scale_algorithm
            quality = self.app_state.encoding.scale_quality
            
            interl = "1" if quality == "quality" else "0"
            
            if algorithm == "bilinear":
                if quality == "quality":
                    scale_filter = f"scale={res}:flags=lanczos:interl={interl}"
                else:
                    scale_filter = f"scale={res}"
            elif algorithm == "bicubic":
                scale_filter = f"scale={res}:flags=bicubic:interl={interl}"
            elif algorithm == "lanczos":
                scale_filter = f"scale={res}:flags=lanczos:interl={interl}"
            elif algorithm == "spline":
                scale_filter = f"scale={res}:flags=spline:interl={interl}"
            elif algorithm == "area":
                scale_filter = f"scale={res}:flags=area:interl={interl}"
            else:
                scale_filter = f"scale={res}"
            
            video_filters.append(scale_filter)
            self.app_state.log(f"Scale: {res} with {algorithm} ({quality})", "INFO")
        
        # Deinterlace
        if self.app_state.filters.deinterlace:
            video_filters.append("yadif")
            
        # Denoise
        if self.app_state.filters.denoise:
            video_filters.append("hqdn3d")

        # Smart Crop (Black Bar Removal)
        if getattr(self.app_state.filters, 'smart_crop_enabled', False):
            crop_mode = getattr(self.app_state.filters, 'smart_crop_mode', 'manual')
            min_dimension = 16  # Minimum dimension for codec compatibility

            if crop_mode == 'manual':
                # Manual crop values - ensure even dimensions for codec compatibility
                w = max(self.app_state.filters.smart_crop_w, min_dimension)
                h = max(self.app_state.filters.smart_crop_h, min_dimension)
                x = self.app_state.filters.smart_crop_x
                y = self.app_state.filters.smart_crop_y

                # Make dimensions even (required by most codecs)
                w = w // 2 * 2
                h = h // 2 * 2

                video_filters.append(f"crop={w}:{h}:{x}:{y}")
                self.app_state.log(f"Smart Crop: Manual {w}x{h} at ({x},{y})", "INFO")

                # Show crop preview if enabled
                if getattr(self.app_state.filters, 'smart_crop_show_preview', False):
                    video_filters.append(f"drawbox=x={x}:y={y}:w={w}:h={h}:color=green:thickness=3")
                    self.app_state.log("Smart Crop Preview: Green border shown", "INFO")
            else:
                # Auto mode: Use preset values
                w = max(self.app_state.filters.smart_crop_w, min_dimension)
                h = max(self.app_state.filters.smart_crop_h, min_dimension)

                # Make dimensions even
                w = w // 2 * 2
                h = h // 2 * 2

                self.app_state.log("Smart Crop: Auto mode (using preset dimensions)", "INFO")
                self.app_state.log(f"Smart Crop: Crop to {w}x{h} - adjust in Manual mode if needed", "INFO")
                # Auto-center the crop
                video_filters.append(f"crop={w}:{h}:(iw-{w})/2:(ih-{h})/2")

                # Show preview in auto mode
                if getattr(self.app_state.filters, 'smart_crop_show_preview', False):
                    video_filters.append(f"drawbox=x=(iw-{w})/2:y=(ih-{h})/2:w={w}:h={h}:color=green:thickness=3")
                    self.app_state.log("Smart Crop Preview: Green border shown", "INFO")

        # Aspect Ratio Conversion
        if getattr(self.app_state.filters, 'ar_convert_enabled', False):
            ar_targets = {
                "16:9": 16.0/9.0,
                "4:3": 4.0/3.0,
                "1:1": 1.0,
                "2.35:1": 2.35
            }
            target_ar = ar_targets.get(getattr(self.app_state.filters, 'ar_target', '16:9'), 16.0/9.0)
            ar_method = getattr(self.app_state.filters, 'ar_method', 'crop')

            self.app_state.log(f"AR Conversion: {ar_method} to {target_ar:.2f}:1", "INFO")

            if ar_method == "crop":
                # Crop to target aspect ratio (centered)
                # Output width = ih * target_ar, centered horizontally
                video_filters.append(f"crop=ih*{target_ar:.4f}:ih:(ih*{target_ar:.4f}-iw)/2:0")
            elif ar_method == "pad":
                # Add black bars to reach target AR (centered)
                video_filters.append(f"pad=ih*{target_ar:.4f}:ih:(ih*{target_ar:.4f}-iw)/2:0:black")
            elif ar_method == "scale_2step":
                # Two-step scaling to preserve all content without distortion
                video_filters.append(f"scale=iw*min({target_ar:.4f}*(ih/iw),1):ih*min(1,({target_ar:.4f})/(ih/iw)),setsar=1")
            else:  # stretch
                # Stretch to fill target AR (may distort)
                video_filters.append(f"scale=iw*{target_ar:.4f}:ih")
            
            # Force SAR to 1:1 after AR conversion for clean output
            video_filters.append("setsar=1:1")

        # Delogo (Logo/Watermark Removal)
        if getattr(self.app_state.filters, 'delogo_enabled', False):
            x = self.app_state.filters.delogo_x
            y = self.app_state.filters.delogo_y
            w = self.app_state.filters.delogo_w
            h = self.app_state.filters.delogo_h
            video_filters.append(f"delogo=x={x}:y={y}:w={w}:h={h}")
            self.app_state.log(f"Delogo: x={x}, y={y}, w={w}, h={h}", "INFO")
            
            # Show preview rectangle if enabled
            if getattr(self.app_state.filters, 'delogo_show', False):
                video_filters.append(f"drawbox=x={x}:y={y}:w={w}:h={h}:color=red:thickness=2")
                self.app_state.log("Delogo Preview: Red rectangle shown", "INFO")
            
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
                video_filters.append(f"eq={':'.join(eq_params)}")
        
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
                video_filters.append(f"colorbalance={':'.join(wb_params)}")
        
        # Subtitles burn-in - look for external subtitle files
        # DVD subtitles are handled separately in build_ffmpeg_command after extraction
        if self.app_state.subtitles.burn_subs:
            # Look for external subtitle file
            sub_path = self.find_subtitle_file(input_path)
            if sub_path:
                subs_filter = self.build_subtitle_filter(sub_path)
                if subs_filter:
                    video_filters.append(subs_filter)
                    self.app_state.log(f"Burning subtitles from: {os.path.basename(sub_path)}", "INFO")
            else:
                # Don't warn here for DVD sources - they're handled separately
                if not self.app_state.dvd.is_dvd_source:
                    self.app_state.log("No external subtitle file found (.srt or .ass)", "WARN")
                
        # Volume (audio filter)
        if self.app_state.filters.volume_enabled:
            audio_filters.append(f"volume={self.app_state.filters.volume_db}dB")
        
        # Audio Denoise (afftdn - FFT-based denoiser)
        if getattr(self.app_state.filters, 'audio_denoise', False):
            audio_filters.append("afftdn=nf=-25")
            self.app_state.log("Audio: Applying noise reduction filter", "INFO")
        
        # Dynamic Audio Normalizer
        if getattr(self.app_state.filters, 'audio_dynnorm', False):
            audio_filters.append("dynaudnorm=f=150:g=15:r=0.95")
            self.app_state.log("Audio: Applying dynamic normalizer", "INFO")
        
        # Audio Compressor
        if getattr(self.app_state.filters, 'audio_compressor', False):
            audio_filters.append("acompressor=threshold=0.15:ratio=3:attack=20:release=250")
            self.app_state.log("Audio: Applying audio compressor", "INFO")
        
        return (
            ",".join(video_filters) if video_filters else "",
            ",".join(audio_filters) if audio_filters else ""
        )
        
    def find_subtitle_file(self, video_path: str) -> Optional[str]:
        """Find external subtitle file (.srt, .ass, .ssa, .sub) for the video"""
        if not video_path:
            return None
        
        # Check if user selected a specific subtitle file
        selected = self.app_state.subtitles.selected_subtitle
        if selected and os.path.exists(selected):
            return selected
        
        # Auto-detect: look for subtitle with same base name
        base = os.path.splitext(video_path)[0]
        for ext in [".srt", ".ass", ".ssa", ".sub"]:
            sub_path = base + ext
            if os.path.exists(sub_path):
                return sub_path
        return None
    
    def build_subtitle_filter(self, sub_path: str) -> str:
        """Build FFmpeg subtitle filter with styling options"""
        subs = self.app_state.subtitles
        
        # Check if this is a VobSub (.sub) file - these are bitmap-based
        is_vobsub = sub_path.lower().endswith('.sub')
        
        # Escape path for FFmpeg filter
        # Convert backslashes to forward slashes and escape special characters
        escaped_path = sub_path.replace("\\", "/").replace("'", "'\\''")
        # Escape brackets which are special in FFmpeg filter syntax
        escaped_path = escaped_path.replace("[", "\\[").replace("]", "\\]")
        # Escape the colon after the drive letter (Windows paths)
        # Replace C:/ with C\:/ to escape the colon
        import re
        escaped_path = re.sub(r'^([A-Z]):/', r'\1\:/', escaped_path, flags=re.IGNORECASE)
        
        # For VobSub files, use simpler filter (no force_style supported for bitmap subs)
        if is_vobsub:
            # VobSub subtitles are bitmap-based, so no styling options apply
            # Just overlay them as-is
            return f"subtitles='{escaped_path}'"
        
        # Build force_style options for text-based subtitles
        style = []
        
        if subs.font != "Arial":
            style.append(f"Fontname={subs.font}")
        # Always set Fontsize to ensure consistent behavior (FFmpeg default is not 24)
        style.append(f"Fontsize={subs.size}")
        if subs.color != "#FFFFFF":
            style.append(f"PrimaryColour={self.hex_to_ass(subs.color)}")
        if subs.outline_color != "#000000":
            style.append(f"OutlineColour={self.hex_to_ass(subs.outline_color)}")
        if subs.outline_width != 2:
            style.append(f"Outline={subs.outline_width}")
        
        # Shadow and background settings
        # BorderStyle: 1=outline only, 2=outline+shadow, 3=opaque box+shadow, 4=opaque box
        if subs.shadow_enabled and subs.bg_opacity > 0.0:
            # Shadow + background (both enabled) - use BorderStyle=3 with BackColour
            shadow_ass = self.hex_to_ass(subs.shadow_color, subs.shadow_opacity)
            style.append(f"BackColour={shadow_ass}")
            style.append("BorderStyle=3")  # 3 = opaque box with drop shadow
            
            # Shadow is the offset distance (not a color)
            shadow_distance = max(subs.shadow_offset_x, subs.shadow_offset_y, 2)
            style.append(f"Shadow={shadow_distance}")
        elif subs.shadow_enabled:
            # Shadow only (no background) - use BorderStyle=2
            # Shadow color is controlled by OutlineColour in BorderStyle=2
            style.append("BorderStyle=2")  # 2 = outline + drop shadow
            
            # Set outline colour to shadow colour (for BorderStyle=2, shadow uses outline colour)
            outline_ass = self.hex_to_ass(subs.shadow_color, subs.shadow_opacity)
            style.append(f"OutlineColour={outline_ass}")
            
            # Shadow is the offset distance (not a color)
            shadow_distance = max(subs.shadow_offset_x, subs.shadow_offset_y, 2)
            style.append(f"Shadow={shadow_distance}")
        elif subs.bg_opacity > 0.0:
            # Background only (no shadow)
            ass_bg = self.hex_to_ass(subs.bg_color, subs.bg_opacity)
            style.append(f"BackColour={ass_bg}")
            style.append("BorderStyle=4")  # 4 = opaque box
        else:
            style.append("BorderStyle=1")  # 1 = outline only (default)

        # Ensure there's an outline width (required for shadow to be visible)
        if subs.shadow_enabled and subs.outline_width == 0:
            style.append("Outline=1")
        
        # Position mapping
        pos_map = {"bottom": 2, "top": 8, "center": 10}
        if subs.position != "bottom":
            style.append(f"Alignment={pos_map.get(subs.position, 2)}")
        
        # Vertical offset (for letterboxed videos - move subtitles into black bars)
        # For bottom alignment: MarginV is distance FROM bottom, so higher value = higher subtitle
        # To move DOWN, we decrease the margin (base 20px from preview logic)
        if subs.vertical_offset > 0:
            if subs.position == "bottom":
                margin_v = max(0, 20 - subs.vertical_offset)
                style.append(f"MarginV={margin_v}")
            else:
                style.append(f"MarginV={subs.vertical_offset}")
        
        # Build the filter string
        force_style = f":force_style='{','.join(style)}'" if style else ""
        
        return f"subtitles='{escaped_path}'{force_style}"
    
    def hex_to_ass(self, hex_color: str, opacity: float = 1.0) -> str:
        """Convert hex color to ASS format (&HAABBGGRR)
        
        Note: In ASS format:
        - Alpha: &H00 = fully transparent, &HFF = fully opaque
        - Colors are in BGR order (not RGB)
        """
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        # ASS alpha: 00 = transparent, FF = opaque (inverted from typical)
        alpha = int(opacity * 255)
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
        # Check for DVD subtitle burning - NOT SUPPORTED (dvd_subtitle is bitmap format)
        is_dvd_source = self.app_state.dvd.is_dvd_source and input_path.endswith('.txt')
        if is_dvd_source and self.app_state.dvd.selected_subtitle_index >= 0:
            self.app_state.log("DVD subtitle burning is not supported (bitmap format). Skipping subtitle burn.", "WARN")
            self.app_state.log("Tip: Use HandBrake or mencoder for DVD subtitle burning.", "INFO")
            # Disable subtitle selection to prevent confusion
            self.app_state.dvd.selected_subtitle_index = -1
        
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
        
        # Generate PTS if missing (fixes "pts has no value" warnings)
        cmd.extend(["-fflags", "+genpts+igndts"])
        
        # Use -copyts to preserve original timestamps (helps with playback issues)
        cmd.extend(["-copyts"])
        
        # Duration
        if duration:
            cmd.extend(["-t", duration])
        
        # Copy video and audio streams without re-encoding
        cmd.extend(["-c:v", "copy"])
        
        # Check for external audio file
        external_audio_enabled = getattr(self.app_state.tracks, 'external_audio_enabled', False)
        external_audio_path = getattr(self.app_state.tracks, 'external_audio_path', '')
        has_external_audio = external_audio_enabled and external_audio_path and os.path.exists(external_audio_path)
        
        # Add external audio as second input if available
        if has_external_audio:
            cmd.extend(["-i", external_audio_path])
            self.app_state.log(f"Fast cut: Using external audio {os.path.basename(external_audio_path)}", "INFO")
        
        # Map video stream
        if self.app_state.tracks.video_selected:
            cmd.extend(["-map", "0:v:0"])
        
        # Audio handling - map specific stream
        if self.app_state.tracks.audio_selected:
            if has_external_audio:
                # Use external audio (input index 1)
                cmd.extend(["-map", "1:a"])
                # Use copy codec for external audio
                ext_audio_path = self.app_state.tracks.external_audio_path
                ext = os.path.splitext(ext_audio_path)[1].lower()
                if ext in ['.mp3', '.mp2']:
                    cmd.extend(["-c:a", "copy"])
                elif ext == '.wav':
                    cmd.extend(["-c:a", "pcm_s16le"])
                elif ext == '.flac':
                    cmd.extend(["-c:a", "copy"])
                else:
                    # For aac, ogg, m4a, etc - re-encode to aac for compatibility
                    cmd.extend(["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"])
            else:
                # Use embedded audio from video
                audio_stream_idx = self.app_state.tracks.audio_stream_index
                cmd.extend(["-map", f"0:a:{audio_stream_idx}"])
                
                # Check audio mode from Encoding Settings first, then fallback to Track Selection setting
                audio_mode = getattr(self.app_state.encoding, 'audio_mode', 'encode')
                audio_copy = (audio_mode == 'copy') or self.app_state.tracks.audio_copy_mode
                
                if audio_copy:
                    cmd.extend(["-c:a", "copy"])
                else:
                    # Re-encode audio but keep video copy
                    cmd.extend(["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", "-channel_layout", "stereo"])
        else:
            cmd.extend(["-an"])
        
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
        
        output_path = os.path.join(output_folder, f"{base_name}.{container}")
        
        # Handle duplicates
        counter = 1
        original_path = output_path
        while os.path.exists(output_path):
            name = f"{Path(original_path).stem}_{counter}"
            output_path = os.path.join(output_folder, f"{name}.{container}")
            counter += 1
            
        return output_path
