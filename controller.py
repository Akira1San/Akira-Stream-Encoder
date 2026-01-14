import os
import platform
import subprocess
import threading
import re


class VideoController:
    """Handles all business logic for video encoding and file processing"""
    
    def __init__(self, state, log_callback):
        self.state = state
        self.log = log_callback
        self.current_process = None
    
    def get_video_duration(self, input_path):
        """
        Detects video duration. Tries ffprobe first (fast), then ffmpeg.
        Increased timeout for large files.
        """
        duration = 0.0
        
        # Try to find ffprobe
        ffprobe_path = "ffprobe"
        ffmpeg_path = self.state.ffmpeg_path.get()
        
        if ffmpeg_path != "ffmpeg" and os.path.exists(ffmpeg_path):
            base_dir = os.path.dirname(ffmpeg_path)
            # Try to find ffprobe.exe in same folder
            candidate = os.path.join(base_dir, "ffprobe.exe" if os.name == 'nt' else "ffprobe")
            if os.path.exists(candidate):
                ffprobe_path = candidate

        # Attempt 1: Use FFprobe (Fastest & Most Reliable)
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
                # Increased timeout to 60 seconds for large MKV files
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
                
                if result.returncode == 0 and result.stdout.strip():
                    duration = float(result.stdout.strip())
                    self.log(f"Duration detected via ffprobe: {duration} sec")
                    return duration
            except subprocess.TimeoutExpired:
                self.log(f"ffprobe timed out for {os.path.basename(input_path)}. Trying ffmpeg...")
            except Exception as e:
                self.log(f"ffprobe failed: {e}")

        # Attempt 2: Fallback to ffmpeg (Parsing stderr)
        try:
            cmd = [ffmpeg_path, "-i", input_path]
            # Increased timeout
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
            stderr_output = result.stderr
            
            # Regex for Duration
            match = re.search(r"Duration:\s*(\d{2}:\d{2}:\d{2})", stderr_output)
            if match:
                h, m, s = map(int, match.group(1).split(':'))
                duration = h * 3600 + m * 60 + s
                return duration
        except subprocess.TimeoutExpired:
            self.log(f"ffmpeg timed out for {os.path.basename(input_path)}. Cannot determine duration.", "WARN")
        except Exception as e:
            self.log(f"ffmpeg detection failed: {e}", "WARN")
            
        return duration
    
    def get_video_bitrate(self, input_path):
        """
        Detect the video bitrate of the input file using ffprobe or ffmpeg.
        Returns bitrate in kbps (int) or None if failed.
        """
        # Try to find ffprobe based on ffmpeg path
        ffprobe_path = "ffprobe"
        if self.state.ffmpeg_path.get() != "ffmpeg":
            base_dir = os.path.dirname(self.state.ffmpeg_path.get())
            if base_dir:
                candidate = os.path.join(base_dir, "ffprobe.exe" if os.name == 'nt' else "ffprobe")
                if os.path.exists(candidate):
                    ffprobe_path = candidate
        
        self.log(f"Detecting bitrate for {os.path.basename(input_path)} using {ffprobe_path}...")
        
        try:
            # Method 1: ffprobe (cleaner)
            cmd = [
                ffprobe_path,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=bit_rate",
                "-of", "default=noprint_wrappers=1:nokey=1",
                input_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                br_bps = int(result.stdout.strip())
                br_kbps = br_bps // 1000
                self.log(f"Detected bitrate: {br_kbps} kbps")
                return br_kbps
        except Exception as e:
            self.log(f"ffprobe detection failed: {e}", "WARN")
        
        try:
            # Method 2: Fallback to parsing ffmpeg -i (messy but reliable if ffprobe missing)
            cmd = [self.state.ffmpeg_path.get(), "-i", input_path]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            stderr_output = result.stderr
            
            # Simple regex search for bitrate in the output line "bitrate: 5000 kb/s"
            match = re.search(r"bitrate:\s*(\d+)\s*kb/s", stderr_output)
            if match:
                br_kbps = int(match.group(1))
                self.log(f"Detected bitrate via ffmpeg output: {br_kbps} kbps")
                return br_kbps
        except Exception as e:
            self.log(f"ffmpeg bitrate parsing failed: {e}", "WARN")
            
        self.log("Could not detect original bitrate.", "WARN")
        return None
    
    def build_ffmpeg_command(self, input_path, output_path, target_bitrate=None, start_time_str=None, duration_str=None):
        """Build the complete FFmpeg command based on current settings"""
        # 1. Executable
        cmd = [self.state.ffmpeg_path.get()]

        # --- CHECK FAST SPLIT MODE ---
        if self.state.split_mode.get():
            self.log("Using Fast Split (Stream Copy)")
            cmd.extend(["-ss", start_time_str] if start_time_str else [])
            cmd.extend(["-t", duration_str] if duration_str else [])
            cmd.extend(["-i", input_path])
            cmd.extend(["-c", "copy"]) # Copy All streams
            cmd.extend(["-y", output_path])
            return cmd

        # --- NORMAL ENCODING MODE ---
        self.log("Normal Re-Encoding Mode")

        # 2. Trim Logic
        if start_time_str: cmd.extend(["-ss", start_time_str])
        if duration_str: cmd.extend(["-t", duration_str])

        # 3. Hardware Decoding Flags
        # REVERTED: Removed 'hwaccel_output_format' and 'device' to prevent crash.
        # We only use 'hwaccel cuda' which allows GPU decoding, 
        # and FFmpeg handles the transfer to encoder automatically.
        if self.state.use_gpu.get():
            cmd.extend(["-hwaccel", "cuda"])
            
        cmd.extend(["-i", input_path])
        cmd.extend(["-r", self.state.framerate_var.get()])
        cmd.extend(["-c:v", self.state.encoder_var.get()])
        
        if self.state.use_gpu.get():
            cmd.extend(["-preset", "p4"])
            if target_bitrate:
                cmd.extend(["-rc", "cbr"])
                cmd.extend(["-b:v", f"{target_bitrate}k", "-maxrate", f"{target_bitrate}k", "-bufsize", f"{target_bitrate * 2}k"])
            else:
                cmd.extend(["-rc", "vbr"])
                cmd.extend(["-cq", str(self.state.cq_var.get()), "-b:v", "0k"])
        else:
            cmd.extend(["-preset", "medium"])
            if target_bitrate:
                cmd.extend(["-b:v", f"{target_bitrate}k"])
            else:
                cmd.extend(["-crf", str(self.state.cq_var.get())])
        
        # --- STRICT STREAMER FLAGS ---
        cmd.extend(["-g", "144"]) 
        cmd.extend(["-bf", "0"])
        cmd.extend(["-pix_fmt", "yuv420p"])
        cmd.extend(["-profile:v", "main"])
        cmd.extend(["-level:v", "4.0"])
        
        # --- VIDEO FILTERS ---
        video_filters = []
        
        # 1. Resolution Handling (If "none", we detect source res to ensure compatibility)
        if self.state.resolution_var.get() != "none":
            target_res = self.state.resolution_var.get()
        else:
            # Detect Source Resolution to force "Copy" behavior
            # We check if we have stored source resolution, or detect on fly (heavy) or just don't scale.
            # For Normal Encoding, we usually leave it to auto, but to be safe:
            pass 
            # If we really want to force source res to ensure no scaling artifacts:
            # We could add logic here, but let's stick to explicit user selection for now.

        # 2. Geometry (Crop/Scale)
        if self.state.force_widescreen.get():
            target_res = self.state.resolution_var.get()
            if target_res == "none": target_res = "1920x1080" # Fallback or detect?

        # 3. Scale
        # FIX: Removed ":force_original_aspect_ratio=increase" to prevent EINVAL crash
        if self.state.resolution_var.get() != "none":
            target_res = self.state.resolution_var.get()
            
            if self.state.force_widescreen.get():
                # Simple scale (Crop handles aspect ratio)
                video_filters.append(f"scale={target_res}")
            else:
                # Normal mode (Fill frame)
                video_filters.append(f"scale={target_res}")

        # 4. Filters
        if self.state.deint.get(): video_filters.append("yadif")

        # --- COLOR CORRECTION (EQ) ---
        if self.state.eq_enable.get():
            eq_params = []
            
            brightness = self.state.eq_brightness.get()
            if abs(brightness) > 0.001:
                eq_params.append(f"brightness={brightness:.3f}")
            
            contrast = self.state.eq_contrast.get()
            if abs(contrast - 1.0) > 0.001:
                eq_params.append(f"contrast={contrast:.3f}")
            
            saturation = self.state.eq_saturation.get()
            if abs(saturation - 1.0) > 0.001:
                eq_params.append(f"saturation={saturation:.3f}")
            
            gamma = self.state.eq_gamma.get()
            if abs(gamma - 1.0) > 0.001:
                eq_params.append(f"gamma={gamma:.3f}")
            
            gamma_r = self.state.eq_gamma_r.get()
            gamma_g = self.state.eq_gamma_g.get()
            gamma_b = self.state.eq_gamma_b.get()
            
            if abs(gamma_r - 1.0) > 0.001 or abs(gamma_g - 1.0) > 0.001 or abs(gamma_b - 1.0) > 0.001:
                eq_params.append(f"gamma_r={gamma_r:.3f}")
                eq_params.append(f"gamma_g={gamma_g:.3f}")
                eq_params.append(f"gamma_b={gamma_b:.3f}")
            
            if eq_params:
                eq_filter = "eq=" + ":".join(eq_params)
                video_filters.append(eq_filter)
                self.log(f"Applying color correction: {eq_filter}")

        # --- SUBTITLE BURNING ---
        if self.state.burn_subs.get():
            subtitle_path = self.find_subtitle(input_path)
            if subtitle_path:
                subtitle_filter = self.build_subtitle_filter_complex(subtitle_path)
                video_filters.append(subtitle_filter)
                self.log(f"Burning subtitles from: {os.path.basename(subtitle_path)}")
            else:
                self.log(f"No subtitle file found for {os.path.basename(input_path)}")

        if video_filters:
            cmd.extend(["-vf", ",".join(video_filters)])

        # --- AUDIO ---
        cmd.extend(["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", "-channel_layout", "stereo"])
        
        cmd.extend(["-y", output_path])
        return cmd
    
    def encode_single_file(self, input_path, output_file, start_time_str=None, duration_str=None):
        """Encodes a single file with optional trimming/splitting"""
        try:
            # Build command
            cmd = self.build_ffmpeg_command(input_path, output_file, start_time_str=start_time_str, duration_str=duration_str)
            self.log(f"Running: {' '.join(cmd)}")
            
            # Run FFmpeg using Popen
            # FIX: Changed from STDOUT to PIPE to avoid AttributeError issues on Windows
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, # Read from standard error pipe
                universal_newlines=True,
                encoding='utf-8', errors='replace'
            )
            
            # --- SAFETY CHECK ---
            if self.current_process is None or not hasattr(self.current_process, 'stderr'):
                raise Exception("FFmpeg process failed to start")
            
            # Read logs in real-time
            while self.current_process and self.current_process.poll() is None:
                try:
                    if self.current_process.stderr:
                        line = self.current_process.stderr.readline() # Read from stderr pipe
                    else:
                        break
                    
                    if not line:
                        break
                    
                    # Log specific lines (Progress)
                    # 'elapsed' and 'speed' are the lines we wanted to see.
                    if "elapsed=" in line or "speed=" in line:
                        self.log(f"Progress: {line.strip()}")
                    
                    # Log errors
                    elif "[Error" in line or "Error reinitializing" in line:
                        self.log(f"FFmpeg: {line.strip()}")
                except:
                    break

            # Wait for process to finish
            return_code = self.current_process.wait() if self.current_process else -1
            
            if return_code != 0:
                self.log(f"Encoding FAILED for {os.path.basename(output_file)}. Return code: {return_code}")
                import tkinter.messagebox as messagebox
                messagebox.showerror("Encoding Error", f"Encoding failed.\nReturn code: {return_code}")
            else:
                self.log(f"Successfully encoded {os.path.basename(output_file)}")
                
        except subprocess.TimeoutExpired:
            err_msg = "Encoding timed out."
            self.log(err_msg)
            import tkinter.messagebox as messagebox
            messagebox.showerror("Error", err_msg)
        except Exception as e:
            err_msg = f"Exception during encoding:\n{e}"
            self.log(err_msg)
            import tkinter.messagebox as messagebox
            messagebox.showerror("Critical Error", err_msg)
    
    def process_batch(self, status_var):
        """Process the batch of files with optional splitting"""
        files = self.state.input_files
        
        # --- 1. PROCESS FILES ---
        for input_file in files:
            if not self.state.is_encoding: break
            
            # Check Split Mode
            parts_count = int(self.state.cut_parts.get())
            
            if parts_count == 1:
                # --- NORMAL ENCODING (Existing Logic) ---
                container = self.state.container.get()
                base_name = os.path.splitext(os.path.basename(input_file))[0]
                output_file = os.path.join(self.state.output_folder.get(), f"encoded_{base_name}.{container}")
                self.encode_single_file(input_file, output_file)
            else:
                # --- SPLIT ENCODING (New Logic) ---
                self.log(f"Splitting {os.path.basename(input_file)} by duration...")
                
                total_duration = self.get_video_duration(input_file)
                
                if total_duration == 0.0:
                    self.log(f"Error: Could not determine duration for {os.path.basename(input_file)}")
                    continue

                # Get user setting (Minutes)
                split_min = self.state.split_duration_min.get()
                split_seconds = split_min * 60
                
                # Calculate parts
                num_parts = int(total_duration / split_seconds)
                if num_parts < 1:
                    num_parts = 1 # At least 1 part
                
                self.log(f"Total Duration: {total_duration}s. Splitting into {num_parts} parts ({split_min} mins each).")
                
                # Loop for each part
                for i in range(num_parts):
                    if not self.state.is_encoding: break
                    
                    # Calculate Start Time and End Time
                    start_time = i * split_seconds
                    end_time = start_time + split_seconds
                    
                    # Clamp End Time to Total Duration (for last part)
                    if end_time > total_duration:
                        end_time = total_duration
                    
                    # Format time string (HH:MM:SS)
                    sh, remainder = divmod(int(start_time), 3600)
                    sm, ss = divmod(remainder, 60)
                    time_str = f"{sh:02d}:{sm:02d}:{ss:02d}"
                    
                    # Calculate Duration for this part
                    part_dur_sec = end_time - start_time
                    ph, remainder = divmod(int(part_dur_sec), 3600)
                    pm, ps = divmod(remainder, 60)
                    dur_str = f"{ph:02d}:{pm:02d}:{ps:02d}"
                    
                    # Create Output Filename
                    base_name = os.path.splitext(os.path.basename(input_file))[0]
                    container = self.state.container.get()
                    output_file = os.path.join(self.state.output_folder.get(), f"{base_name}_Part{i+1}.{container}")
                    
                    status_var.set(f"Part {i+1}/{num_parts}: {os.path.basename(input_file)}")
                    
                    # Encode this part
                    self.encode_single_file(input_file, output_file, start_time_str=time_str, duration_str=dur_str)

        # --- END OF BATCH ---
        status_var.set("Batch Complete")
        self.log("All tasks finished.")
        self.state.is_encoding = False
    
    def find_subtitle(self, video_path):
        """Find subtitle file for the given video path"""
        base = os.path.splitext(video_path)[0]
        for ext in [".srt", ".ass"]:
            if os.path.exists(base + ext):
                return base + ext
        return None
    
    def build_subtitle_filter_complex(self, sub_path):
        """Build FFmpeg subtitle filter complex"""
        p = sub_path.replace("\\", "/").replace(":", "\\:")
        style = []
        
        if self.state.sub_font.get() != "Arial": style.append(f"Fontname={self.state.sub_font.get()}")
        if self.state.sub_size.get() != 24: style.append(f"Fontsize={self.state.sub_size.get()}")
        if self.state.sub_color.get() != "#FFFFFF": style.append(f"PrimaryColour={self.hex_to_ass(self.state.sub_color.get())}")
        if self.state.sub_outline_color.get() != "#000000": style.append(f"OutlineColour={self.hex_to_ass(self.state.sub_outline_color.get())}")
        if self.state.sub_outline_width.get() != 2: style.append(f"Outline={self.state.sub_outline_width.get()}")
        
        bg_opacity = self.state.sub_bg_opacity.get()
        if bg_opacity > 0.0:
            bg_color_hex = self.state.sub_bg_color.get()
            ass_bg = self.hex_to_ass(bg_color_hex, bg_opacity)
            style.append(f"BackColour={ass_bg}")
            style.append("BorderStyle=4")
        
        pos_map = {"bottom": 2, "top": 8, "center": 10}
        if self.state.sub_position.get() != "bottom": style.append(f"Alignment={pos_map[self.state.sub_position.get()]}")
        
        force_style = f":force_style='{','.join(style)}'" if style else ""
        return f"subtitles='{p}'{force_style}"
    
    def hex_to_ass(self, hex_color, opacity=1.0):
        """Convert hex color to ASS color format"""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        alpha = int((1.0 - opacity) * 255)
        return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"
    
    def detect_video_tracks(self, video_path):
        """
        Analyze video file and return track information
        
        Args:
            video_path: Path to video file
            
        Returns:
            dict with track information
        """
        track_info = {
            'video': None,
            'audio': None,
            'subtitle': None
        }
        
        # Detect video stream
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name,width,height,r_frame_rate',
                '-of', 'default=noprint_wrappers=1',
                video_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split('|')
                codec = parts[0].strip()
                if len(parts) >= 4:
                    width = parts[1].strip()
                    height = parts[2].strip()
                    fps = parts[3].strip()
                    track_info['video'] = f"{codec}, {width}x{height}, {fps}fps"
        except Exception as e:
            self.log(f"Video track detection failed: {e}")
        
        # Detect audio stream
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'a:0',
                '-show_entries', 'stream=codec_name,channels,sample_rate',
                '-of', 'default=noprint_wrappers=1',
                video_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split('|')
                codec = parts[0].strip()
                if len(parts) >= 3:
                    channels = parts[2].strip()
                    track_info['audio'] = f"{codec}, {channels}ch"
        except Exception as e:
            self.log(f"Audio track detection failed: {e}")
        
        # Detect subtitle stream
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 's:0',
                '-show_entries', 'stream=codec_name',
                '-of', 'default=noprint_wrappers=1',
                video_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                codec = result.stdout.strip()
                track_info['subtitle'] = f"{codec}"
        except Exception as e:
            self.log(f"Subtitle track detection failed: {e}")
        
        self.log(f"Tracks detected: Video={bool(track_info['video'])}, Audio={bool(track_info['audio'])}, Subs={bool(track_info['subtitle'])}")
        return track_info
    
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
        ffmpeg_path = self.state.ffmpeg_path.get()
        
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