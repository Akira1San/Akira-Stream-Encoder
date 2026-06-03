"""
Video Controller - Business logic for video encoding (PySide6)
"""
import os
import subprocess
import threading
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from models import AppState
from handbrake_handler import HandBrakeHandler, ISO639_1_TO_639_2


class VideoController:
    """Handles all business logic for video encoding and file processing"""

    def __init__(self, app_state: AppState):
        self.app_state = app_state
        self.current_process: Optional[subprocess.Popen] = None
        self.is_encoding = False

    @property
    def backend(self):
        return self.app_state.backend

    def get_video_duration(self, input_path: str) -> float:
        duration = self.backend.get_duration(input_path)
        if duration > 0:
            self.app_state.log(f"Duration detected: {duration} sec", "INFO")
        return duration

    def get_audio_tracks(self, input_path: str) -> List[dict]:
        return self.backend.get_audio_tracks(input_path)

    def get_video_tracks(self, input_path: str) -> List[dict]:
        return self.backend.get_video_tracks(input_path)

    def get_video_bitrate(self, input_path: str) -> Optional[int]:
        br = self.backend.get_video_bitrate(input_path)
        if br:
            self.app_state.log(f"Detected bitrate: {br} kbps", "INFO")
        else:
            self.app_state.log("Could not detect original bitrate.", "WARN")
        return br
        
    def build_ffmpeg_command(self, input_path: str, output_path: str,
                            start_time: Optional[str] = None,
                            duration: Optional[str] = None) -> List[str]:
        return self.backend.build_command(input_path, output_path, start_time, duration)
        
    def build_filter_complex(self, input_path: str = "") -> tuple:
        video_filters, audio_filters = self.backend.build_filter_string(self.app_state)

        if self.app_state.subtitles.burn_subs:
            sub_path = self.backend.find_subtitle_file(input_path)
            if sub_path:
                subs_filter = self.backend.build_subtitle_filter(sub_path)
                if subs_filter:
                    if video_filters:
                        video_filters = f"{video_filters},{subs_filter}"
                    else:
                        video_filters = subs_filter
                    self.app_state.log(f"Burning subtitles from: {os.path.basename(sub_path)}", "INFO")
            else:
                if not self.app_state.dvd.is_dvd_source:
                    self.app_state.log("No external subtitle file found (.srt or .ass)", "WARN")

        return (video_filters, audio_filters)
        
    def find_subtitle_file(self, video_path: str) -> Optional[str]:
        return self.backend.find_subtitle_file(video_path)

    def build_subtitle_filter(self, sub_path: str) -> str:
        return self.backend.build_subtitle_filter(sub_path)

    def hex_to_ass(self, hex_color: str, opacity: float = 1.0) -> str:
        return self.backend.hex_to_ass(hex_color, opacity)

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
        # ── Extra: Standalone generated video ──
        if self.app_state.extra.generate_video:
            return self._encode_generated_video(output_path, progress_callback)

        # Handle extract clip mode (applies to both HandBrake and FFmpeg paths)
        if start_time is None and duration is None and self.app_state.split.extract_clip_enabled:
            start_min = self.app_state.split.extract_start_min
            duration_min = self.app_state.split.extract_duration_min
            start_time = str(int(start_min * 60))
            duration = str(int(duration_min * 60))
            self.app_state.log(f"Extract clip: start={start_time}s, duration={duration}s", "INFO")

        # Check for DVD subtitle burning via HandBrake
        is_dvd_source = self.app_state.dvd.is_dvd_source and input_path.endswith('.txt')
        burning_dvd_subs = is_dvd_source and self.app_state.dvd.selected_subtitle_index >= 0
        video_mode = getattr(self.app_state.encoding, 'video_mode', 'encode')
        
        use_handbrake = (
            burning_dvd_subs
            and self.app_state.handbrake_available
            and video_mode != "copy"
        )
        
        if use_handbrake:
            return self._encode_with_handbrake(
                input_path, output_path, progress_callback,
                start_time=start_time, duration=duration
            )
        
        if burning_dvd_subs:
            if self.app_state.media_engine == "gstreamer":
                self.app_state.log("GStreamer: burning DVD subtitles via dvdspu", "INFO")
            else:
                self.app_state.log("DVD subtitle burning is not supported (bitmap format). Skipping subtitle burn.", "WARN")
                if not self.app_state.handbrake_available:
                    self.app_state.log("Tip: Install HandBrakeCLI for DVD subtitle burning.", "INFO")
                elif video_mode == "copy":
                    self.app_state.log("Tip: HandBrake does not support stream copy. Switch to encode mode.", "INFO")
                self.app_state.dvd.selected_subtitle_index = -1
        
        # Validate custom resolution format
        if self.app_state.encoding.resolution == "Custom":
            custom_res = self.app_state.encoding.custom_resolution
            if not custom_res or not re.match(r'^\d+x\d+$', custom_res):
                self.app_state.log(f"Invalid custom resolution: '{custom_res}'. Expected format: WxH (e.g. 1920x1080)", "ERROR")
                return False

        self.app_state.log(f"Starting encode: {os.path.basename(input_path)} output={os.path.basename(output_path)}", "INFO")

        try:
            self.is_encoding = True
            self.current_process = self.backend.encode(
                input_path, output_path, self.app_state,
                start_time=start_time, duration=duration
            )

            # Parse output for progress
            vid_duration = self.get_video_duration(input_path)
            line_count = 0

            for line in self.current_process.stdout:
                line = line.strip()
                line_count += 1

                if line.startswith('frame=') or 'fps=' in line or 'time=' in line:
                    self.app_state.log(f"Progress: {line}", "DEBUG")

                if progress_callback:
                    time_match = re.search(r"time=(\d{2}):(\d{2}):(\d{2})", line)
                    if time_match and vid_duration > 0:
                        h, m, s = map(int, time_match.groups())
                        current_time = h * 3600 + m * 60 + s
                        progress = min(100, int((current_time / vid_duration) * 100))
                        progress_callback(progress)

            if line_count > 0:
                self.app_state.log(f"Read {line_count} output lines for {os.path.basename(output_path)}", "DEBUG")
            self.current_process.wait()

            if self.current_process.returncode == 0:
                self.app_state.log(f"✅ Encode complete: {os.path.basename(output_path)}", "SUCCESS")
                self._append_command_log(output_path, f"Result: Success (code 0)")
                return True
            else:
                self.app_state.log(f"❌ Encode failed with code {self.current_process.returncode}", "ERROR")
                self._append_command_log(output_path, f"Result: Failed (code {self.current_process.returncode})")
                return False

        except Exception as e:
            self.app_state.log(f"❌ Encode error: {e}", "ERROR")
            self._append_command_log(output_path, f"Result: Error - {e}")
            return False
        finally:
            self.is_encoding = False
            self.current_process = None

    def _encode_with_handbrake(self, input_path: str, output_path: str,
                               progress_callback=None,
                               start_time: Optional[str] = None,
                               duration: Optional[str] = None) -> bool:
        """Encode a DVD source with subtitle burn-in using HandBrakeCLI"""
        handler = HandBrakeHandler(
            self.app_state.handbrake_path,
            self.app_state.log
        )
        
        dvd_folder = self.app_state.dvd.dvd_folder_path
        title_number = self.app_state.dvd.selected_title_number
        subtitle_track = self.app_state.dvd.selected_subtitle_index
        
        encoder = self.app_state.encoding.encoder
        quality = self.app_state.encoding.cq
        
        # Parse resolution for HandBrake
        width, height = 0, 0
        res = self.app_state.encoding.custom_resolution if self.app_state.encoding.resolution == "Custom" else self.app_state.encoding.resolution
        if res and res != "none" and 'x' in res:
            parts = res.split('x')
            width = int(parts[0])
            height = int(parts[1])
        
        container = self.app_state.encoding.container
        if container == "avi":
            container = "av_avi"
        
        self.app_state.log(f"Using HandBrakeCLI for DVD subtitle burn-in", "INFO")

        # Scan titles with HandBrake and match by duration to find correct title number
        expected_duration = self.get_video_duration(input_path)
        hb_titles = handler.scan_titles(dvd_folder)
        if hb_titles:
            valid = [t for t in hb_titles if t.get('duration_seconds', 0) > 0]
            if valid:
                best = min(valid, key=lambda t: abs(t['duration_seconds'] - expected_duration))
                if best['title_number'] != title_number:
                    self.app_state.log(
                        f"Remapping title: app title {title_number} → HandBrake title {best['title_number']} "
                        f"(duration match: {best['duration_seconds']:.0f}s vs expected {expected_duration:.0f}s)",
                        "INFO"
                    )
                    title_number = best['title_number']

        # Map subtitle track by ISO language code using HandBrake's own scan
        # HandBrake uses 1-based track numbers, app uses 0-based indices.
        # The app has ISO 639-1 (2-letter) codes from IFO, HandBrake JSON gives
        # ISO 639-2 (3-letter) codes. Map app code to 3-letter and find matching track.
        mapped_by_language = False
        if subtitle_track >= 0 and hasattr(self.app_state.dvd, 'subtitle_tracks'):
            tracks = self.app_state.dvd.subtitle_tracks
            if subtitle_track < len(tracks):
                selected_lang = tracks[subtitle_track].get('language', '')
                if selected_lang:
                    hb_code = ISO639_1_TO_639_2.get(selected_lang, '')
                    if hb_code:
                        self.app_state.log(
                            f"Looking up subtitle: app code '{selected_lang}' → ISO 639-2 '{hb_code}'",
                            "INFO"
                        )
                        hb_subtitles = handler.scan_subtitles(dvd_folder, title_number)
                        if hb_subtitles:
                            matched_track = None
                            for hb_sub in hb_subtitles:
                                if hb_sub.get('language_code', '') == hb_code:
                                    matched_track = hb_sub['track']
                                    break
                            if matched_track is not None:
                                self.app_state.log(
                                    f"Mapped subtitle by ISO code: app '{selected_lang}' → "
                                    f"HandBrake track {matched_track} (code '{hb_code}')",
                                    "INFO"
                                )
                                subtitle_track = matched_track
                                mapped_by_language = True
                            else:
                                self.app_state.log(
                                    f"Could not find HandBrake track with code '{hb_code}' "
                                    f"(app lang '{selected_lang}'), falling back to index mapping",
                                    "WARN"
                                )
                    else:
                        self.app_state.log(
                            f"Unknown language code '{selected_lang}', falling back to index mapping",
                            "WARN"
                        )

        # Fall back to index-based mapping (0-based → 1-based)
        if subtitle_track >= 0 and not mapped_by_language:
            self.app_state.log(
                f"Falling back to index mapping: app index {subtitle_track} → HB track {subtitle_track + 1}",
                "WARN"
            )
            subtitle_track = subtitle_track + 1

        self.app_state.log(f"DVD folder: {dvd_folder}, Title: {title_number}, Subtitle track: {subtitle_track}", "INFO")
        
        try:
            self.is_encoding = True
            self.current_process = handler.encode_with_subs(
                input_path=dvd_folder,
                output_path=output_path,
                title_number=title_number,
                subtitle_track=subtitle_track,
                burn=True,
                video_encoder=encoder,
                quality=quality,
                audio_track=1,
                framerate=self.app_state.encoding.framerate,
                width=width,
                height=height,
                target_bitrate=self.app_state.encoding.target_bitrate,
                container=container,
                audio_mode=self.app_state.encoding.audio_mode,
                start_time=start_time,
                duration=duration,
            )
            
            # Parse HandBrake progress from stderr
            hb_duration = self.get_video_duration(input_path)
            
            for line in self.current_process.stderr:
                line = line.strip()
                if not line:
                    continue
                
                self.app_state.log(f"HandBrake: {line}", "DEBUG")
                
                if 'Encoding:' in line and progress_callback and hb_duration > 0:
                    pct_match = re.search(r"(\d+\.?\d*)\s*%", line)
                    if pct_match:
                        progress = min(100, int(float(pct_match.group(1))))
                        progress_callback(progress)
            
            self.current_process.wait()
            
            if self.current_process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                self.app_state.log(f"✅ HandBrake encode complete: {os.path.basename(output_path)}", "SUCCESS")
                self._append_command_log(output_path, f"Result: Success (code 0)")
                return True
            else:
                # Read any remaining stderr for error details
                remaining = self.current_process.stderr.read() if self.current_process.stderr else ""
                self.app_state.log(f"❌ HandBrake encode failed with code {self.current_process.returncode}", "ERROR")
                self._append_command_log(output_path, f"Result: Failed (code {self.current_process.returncode})")
                if remaining:
                    self.app_state.log(f"HandBrake error: {remaining.strip()[:500]}", "ERROR")
                return False
                
        except Exception as e:
            self.app_state.log(f"❌ HandBrake encode error: {e}", "ERROR")
            self._append_command_log(output_path, f"Result: Error - {e}")
            return False
        finally:
            self.is_encoding = False
            self.current_process = None
            
    def _append_command_log(self, output_path: str, message: str):
        log_path = output_path + ".log"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a") as f:
            f.write(f"[{timestamp}] {message}\n")

    def _encode_generated_video(self, output_path: str, progress_callback=None) -> bool:
        """Encode a standalone generated video (color background + optional silent audio)"""
        extra = self.app_state.extra
        self.app_state.log(f"Generating standby video: {os.path.basename(output_path)}", "INFO")

        try:
            self.is_encoding = True
            cmd = self.backend.build_generate_video_command(output_path)
            self.app_state.log(f"Command: {' '.join(cmd)}", "INFO")
            self._append_command_log(output_path, f"Command: {' '.join(cmd)}")

            self.current_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True, bufsize=1
            )

            for line in self.current_process.stdout:
                line = line.strip()
                if line:
                    self.app_state.log(f"Generate: {line}", "DEBUG")

            self.current_process.wait()

            if self.current_process.returncode == 0 and os.path.exists(output_path):
                self.app_state.log(f"✅ Generated video: {os.path.basename(output_path)}", "SUCCESS")
                self._append_command_log(output_path, f"Result: Success (code 0)")
                return True
            else:
                self.app_state.log(f"❌ Generate failed with code {self.current_process.returncode}", "ERROR")
                self._append_command_log(output_path, f"Result: Failed (code {self.current_process.returncode})")
                return False

        except Exception as e:
            self.app_state.log(f"❌ Generate error: {e}", "ERROR")
            self._append_command_log(output_path, f"Result: Error - {e}")
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
        self.app_state.log(f"Fast cutting: {os.path.basename(input_path)} output={os.path.basename(output_path)}", "INFO")

        try:
            self.is_encoding = True
            self.current_process = self.backend.fast_cut(
                input_path, output_path, start_time=start_time, duration=duration
            )

            line_count = 0
            for line in self.current_process.stdout:
                line = line.strip()
                line_count += 1
                if line:
                    self.app_state.log(f"Fast cut: {line}", "DEBUG")

            if line_count > 0:
                self.app_state.log(f"Read {line_count} output lines for {os.path.basename(output_path)}", "DEBUG")
            self.current_process.wait()

            if self.current_process.returncode == 0:
                self.app_state.log(f"✅ Fast cut complete: {os.path.basename(output_path)}", "SUCCESS")
                self._append_command_log(output_path, f"Result: Success (code 0)")
                return True
            else:
                self.app_state.log(f"❌ Fast cut failed with code {self.current_process.returncode}", "ERROR")
                self._append_command_log(output_path, f"Result: Failed (code {self.current_process.returncode})")
                return False

        except Exception as e:
            self.app_state.log(f"❌ Fast cut error: {e}", "ERROR")
            self._append_command_log(output_path, f"Result: Error - {e}")
            return False
        finally:
            self.is_encoding = False
            self.current_process = None
            
    def generate_output_path(self, input_path: str) -> str:
        """Generate output path based on settings"""
        is_dvd_concat = input_path.endswith('.txt') and self.app_state.dvd.is_dvd_source

        if self.app_state.use_custom_filename and self.app_state.custom_filename:
            base_name = self.app_state.custom_filename
        elif is_dvd_concat:
            base_name = f"dvd_title_{self.app_state.dvd.selected_title_number}"
        else:
            base_name = Path(input_path).stem

        container = self.app_state.encoding.container

        if self.app_state.output_folder:
            output_folder = self.app_state.output_folder
        elif is_dvd_concat and self.app_state.dvd.dvd_folder_path:
            output_folder = os.path.dirname(self.app_state.dvd.dvd_folder_path)
        else:
            output_folder = os.path.dirname(input_path)

        output_path = os.path.join(output_folder, f"{base_name}.{container}")
        
        # Handle duplicates
        counter = 1
        original_path = output_path
        while os.path.exists(output_path):
            name = f"{Path(original_path).stem}_{counter}"
            output_path = os.path.join(output_folder, f"{name}.{container}")
            counter += 1
            
        return output_path
    
    def join_segments(self, input_path: str, output_path: str,
                      segments: List[tuple], video_settings: dict, audio_settings: dict) -> bool:
        if not segments or len(segments) < 1:
            self.app_state.log("No segments to join", "ERROR")
            return False

        if len(segments) == 1:
            self.app_state.log("Single segment - using encode instead of join", "INFO")
            seg_start, seg_end = segments[0]
            dur = seg_end - seg_start
            return self.encode_file(input_path, output_path, start_time=str(seg_start), duration=str(dur))

        self.app_state.log(f"Joining {len(segments)} segments into one file", "INFO")

        try:
            self.is_encoding = True
            self.current_process = self.backend.join_segments(
                input_path, output_path, segments, video_settings, audio_settings
            )

            for line in self.current_process.stdout:
                line = line.strip()
                if line:
                    self.app_state.log(f"Join: {line}", "DEBUG")

            self.current_process.wait()

            if self.current_process.returncode == 0:
                self.app_state.log(f"✅ Join complete: {os.path.basename(output_path)}", "SUCCESS")
                self._append_command_log(output_path, f"Result: Success (code 0)")
                return True
            else:
                self.app_state.log(f"❌ Join failed with code {self.current_process.returncode}", "ERROR")
                self._append_command_log(output_path, f"Result: Failed (code {self.current_process.returncode})")
                return False

        except Exception as e:
            self.app_state.log(f"❌ Join error: {e}", "ERROR")
            self._append_command_log(output_path, f"Result: Error - {e}")
            return False
        finally:
            self.is_encoding = False
            self.current_process = None

    # ── AI Upscaling Pipeline Orchestration ────────────────────────

    def _get_frames_dir(self, input_path: str) -> str:
        import os
        from pathlib import Path
        ai = self.app_state.ai_upscaling
        if ai.frames_dir:
            return ai.frames_dir
        stem = Path(input_path).stem
        base = os.path.join(os.path.dirname(input_path), f".{stem}_frames")
        return base

    def extract_frames(self, input_path: str, progress_callback=None) -> bool:
        ai = self.app_state.ai_upscaling
        frames_dir = self._get_frames_dir(input_path)
        ai.frames_dir = frames_dir

        fps = self.backend.get_fps(input_path)
        part_min = ai.part_duration_minutes

        self.app_state.log(f"Extracting frames to {frames_dir} ({part_min}min parts @ {fps:.2f}fps)...", "INFO")
        result = self.backend.extract_frames(input_path, frames_dir, part_min, fps, progress_callback)

        if result:
            ai.frames_extracted = True
            part_dirs = self.backend.get_part_dirs(frames_dir)
            ai.total_parts = len(part_dirs)
            self.app_state.log(f"Extraction complete: {ai.total_parts} parts", "SUCCESS")
        else:
            ai.frames_extracted = False
            self.app_state.log("Frame extraction failed", "ERROR")

        return result

    def upscale_frames(self, progress_callback=None) -> bool:
        ai = self.app_state.ai_upscaling
        if not ai.frames_dir or not ai.frames_extracted:
            self.app_state.log("No frames to upscale. Extract frames first.", "ERROR")
            return False

        self.app_state.log(f"Upscaling with {ai.upscaler}/{ai.model} ({ai.scale}x)...", "INFO")
        result = self.backend.upscale_frames(
            ai.frames_dir, ai.upscaler, ai.model,
            ai.scale, ai.tile_size, progress_callback
        )

        if result:
            ai.frames_upscaled = True
            self.app_state.log("Upscaling complete", "SUCCESS")
        else:
            ai.frames_upscaled = False
            self.app_state.log("Upscaling failed", "ERROR")

        return result

    def upscale_part(self, part_name: str, progress_callback=None) -> bool:
        import os
        ai = self.app_state.ai_upscaling
        if not ai.frames_dir:
            self.app_state.log("No frames directory set.", "ERROR")
            return False

        src_dir = os.path.join(ai.frames_dir, part_name)
        out_dir = os.path.join(ai.frames_dir, f"{part_name}_{ai.upscaler}.png")
        if os.path.isdir(out_dir) and os.listdir(out_dir):
            self.app_state.log(f"Part {part_name} already upscaled", "INFO")
            return True
        os.makedirs(out_dir, exist_ok=True)

        from config import REALESRGAN_NCNN, ANIME4K_NCNN
        if ai.upscaler == "realesrgan":
            binary = self.app_state.realesrgan_path or REALESRGAN_NCNN
        elif ai.upscaler == "anime4k":
            binary = self.app_state.anime4k_path or ANIME4K_NCNN
        else:
            self.app_state.log(f"Unknown upscaler: {ai.upscaler}", "ERROR")
            return False

        if not os.path.isfile(binary):
            self.app_state.log(f"Upscaler binary not found: {binary}", "ERROR")
            return False
        if not os.access(binary, os.X_OK):
            self.app_state.log(f"Upscaler binary is not executable: {binary}. Run 'chmod +x \"{binary}\"' to fix.", "ERROR")
            return False
        model_dir = os.path.join(os.path.dirname(binary), "models")
        model_bin = os.path.join(model_dir, f"{ai.model}.bin")
        if not os.path.isfile(model_bin):
            self.app_state.log(f"Model not found: {model_bin}. Check your model selection in AI Upscaling settings.", "ERROR")
            return False
        cmd = [
            binary,
            "-i", src_dir,
            "-o", out_dir,
            "-s", str(ai.scale),
            "-n", ai.model,
            "-m", model_dir,
        ]
        if ai.tile_size > 0:
            cmd.extend(["-t", str(ai.tile_size)])
        cmd.extend(["-g", "0", "-f", "png"])

        self.app_state.log(f"Upscaling part {part_name}...", "INFO")

        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            self.current_process = proc
            self.is_encoding = True

            for line in iter(proc.stderr.readline, ''):
                line = line.strip()
                if line and "%" in line and not line.startswith("["):
                    self.app_state.log(f"📷 {part_name}: {line}", "INFO")

            proc.wait()
            if proc.returncode != 0:
                self.app_state.log(f"Upscale part {part_name} failed", "ERROR")
                return False
        except Exception as e:
            self.app_state.log(f"Upscale part error {part_name}: {e}", "ERROR")
            return False
        finally:
            self.current_process = None
            self.is_encoding = False

        if progress_callback:
            progress_callback(100)
        self.app_state.log(f"Part {part_name} upscaled", "SUCCESS")
        return True

    def cancel_upscale(self):
        if self.current_process:
            self.current_process.terminate()
            self.app_state.log("Upscaling cancelled by user", "INFO")
        else:
            self.backend.cancel_upscale = True
            if self.backend._current_upscale_proc:
                self.backend._current_upscale_proc.terminate()

    def recombine_frames(self, progress_callback=None) -> str:
        import os
        from pathlib import Path
        ai = self.app_state.ai_upscaling
        if not ai.frames_dir or not ai.frames_upscaled:
            self.app_state.log("No upscaled frames to recombine.", "ERROR")
            return ""

        input_path = self.app_state.input_files[0] if self.app_state.input_files else ""
        stem = Path(input_path).stem if input_path else "upscaled"
        output_path = os.path.join(ai.frames_dir, f"{stem}_ai_upscaled.mp4")
        fps = self.backend.get_fps(input_path) if input_path else 24000 / 1001

        self.app_state.log("Recombining upscaled frames into video...", "INFO")
        result = self.backend.recombine_frames(ai.frames_dir, output_path, fps, progress_callback)

        if result:
            ai.frames_recombined = True
            self.app_state.log(f"Recombined video: {output_path}", "SUCCESS")
            return output_path
        else:
            ai.frames_recombined = False
            self.app_state.log("Recombination failed", "ERROR")
            return ""
