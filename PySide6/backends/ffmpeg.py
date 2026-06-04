"""
FFmpeg CLI Backend - Implements MediaBackend using ffmpeg/ffprobe subprocess calls
"""
import os
import re
import subprocess
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from backends.base import MediaBackend


class FFmpegBackend(MediaBackend):
    """Media backend using FFmpeg CLI"""

    def __init__(self, app_state):
        self.app_state = app_state
        self._current_upscale_proc = None
        self.cancel_upscale = False
        self._vob_duration_cache: Dict[str, float] = {}

    def _audio_channels_args(self) -> List[str]:
        ch = getattr(self.app_state.encoding, 'audio_channels', '2')
        layout = {"1": "mono", "2": "stereo", "6": "5.1", "8": "7.1"}.get(ch, "stereo")
        return ["-ac", ch, "-channel_layout", layout]

    def _audio_codec(self) -> str:
        """Return audio codec from user selection, with container-safe fallback."""
        codec = self.app_state.encoding.audio_codec
        if codec:
            return codec
        container = getattr(self.app_state.encoding, 'container', 'mp4')
        return "mp2" if container in ("mpg", "vob") else "aac"

    def _get_dvd_concat_input(self) -> Optional[str]:
        """Build concat: protocol input for DVD VOB files (byte-level concat).

        VOB files are byte-splits of a single MPEG-PS stream, so the concat:
        protocol (not the concat demuxer) produces a continuous stream with no
        PTS discontinuity at VOB boundaries.
        """
        dvd = self.app_state.dvd
        if not dvd.is_dvd_source or not dvd.available_titles:
            return None
        for title in dvd.available_titles:
            if title.title_number == dvd.selected_title_number and title.vob_files:
                return "concat:" + "|".join(title.vob_files)
        return None

    def _get_ffprobe_path(self) -> str:
        ffprobe = self.app_state.ffprobe_path
        ffmpeg = self.app_state.ffmpeg_path
        if ffmpeg != "ffmpeg" and os.path.exists(ffmpeg):
            base = os.path.dirname(ffmpeg)
            candidate = os.path.join(base, "ffprobe.exe" if os.name == 'nt' else "ffprobe")
            if os.path.exists(candidate):
                return candidate
        return ffprobe or "ffprobe"

    def get_duration(self, input_path: str) -> float:
        duration = 0.0
        ffprobe_path = self._get_ffprobe_path()
        ffmpeg_path = self.app_state.ffmpeg_path
        is_dvd_concat = input_path.endswith('.txt') and self.app_state.dvd.is_dvd_source
        dvd_concat_input = self._get_dvd_concat_input() if is_dvd_concat else None
        probe_path = dvd_concat_input if dvd_concat_input else input_path

        if ffprobe_path:
            try:
                cmd = [ffprobe_path, "-v", "error"]
                if dvd_concat_input:
                    cmd.extend(["-f", "mpeg"])
                cmd.extend(["-i", probe_path])
                cmd.extend(["-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1"])
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
                if result.returncode == 0 and result.stdout.strip() and result.stdout.strip() != 'N/A':
                    duration = float(result.stdout.strip())
                    return duration
            except subprocess.TimeoutExpired:
                self.app_state.log(f"ffprobe timed out for {os.path.basename(input_path)}.", "WARN")
            except Exception as e:
                self.app_state.log(f"ffprobe failed: {e}", "WARN")

        if is_dvd_concat and self.app_state.dvd.available_titles:
            for title in self.app_state.dvd.available_titles:
                if title.title_number == self.app_state.dvd.selected_title_number:
                    return title.duration

        try:
            cmd = [ffmpeg_path]
            cmd.extend(["-i", probe_path])
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
            match = re.search(r"Duration:\s*(\d{2}:\d{2}:\d{2})", result.stderr)
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
        audio_tracks = []
        ffprobe_path = self._get_ffprobe_path()
        is_dvd_concat = input_path.endswith('.txt') and self.app_state.dvd.is_dvd_source
        dvd_concat_input = self._get_dvd_concat_input() if is_dvd_concat else None

        try:
            cmd = [ffprobe_path, "-v", "error"]
            if dvd_concat_input:
                cmd.extend(["-f", "mpeg"])
                cmd.extend(["-i", dvd_concat_input])
            else:
                cmd.extend(["-i", input_path])
            cmd.extend(["-show_entries", "stream=index,codec_type,codec_name,channels,sample_rate:stream_tags=language,title"])
            cmd.extend(["-of", "json"])
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)

            if result.returncode == 0:
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

    def get_video_tracks(self, input_path: str) -> List[dict]:
        video_tracks = []
        ffprobe_path = self._get_ffprobe_path()
        is_dvd_concat = input_path.endswith('.txt') and self.app_state.dvd.is_dvd_source
        dvd_concat_input = self._get_dvd_concat_input() if is_dvd_concat else None

        try:
            cmd = [ffprobe_path, "-v", "error"]
            if dvd_concat_input:
                cmd.extend(["-f", "mpeg"])
                cmd.extend(["-i", dvd_concat_input])
            else:
                cmd.extend(["-i", input_path])
            cmd.extend(["-show_entries", "stream=index,codec_type,codec_name,width,height,r_frame_rate:stream_tags=language,title"])
            cmd.extend(["-of", "json"])
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)

            if result.returncode == 0:
                data = json.loads(result.stdout)
                for stream in data.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        tags = stream.get('tags', {})
                        track_info = {
                            'index': stream.get('index', 0),
                            'codec': stream.get('codec_name', 'unknown'),
                            'width': stream.get('width', 0),
                            'height': stream.get('height', 0),
                            'fps': stream.get('r_frame_rate', ''),
                            'language': tags.get('language', ''),
                            'title': tags.get('title', '')
                        }
                        video_tracks.append(track_info)
        except Exception as e:
            self.app_state.log(f"Video track detection failed: {e}", "WARN")

        return video_tracks

    def get_video_bitrate(self, input_path: str) -> Optional[int]:
        ffprobe_path = self._get_ffprobe_path()
        ffmpeg_path = self.app_state.ffmpeg_path

        try:
            cmd = [
                ffprobe_path, "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=bit_rate",
                "-of", "default=noprint_wrappers=1:nokey=1", input_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                br_kbps = int(result.stdout.strip()) // 1000
                return br_kbps
        except Exception:
            pass
        return None

    def build_extra_preview_filter(self, app_state) -> str:
        """Build just the drawtext filters from Extra panel for preview."""
        extra = app_state.extra
        drawtext_filters = []
        for item in extra.text_overlays:
            if item.enabled and item.text.strip():
                dt = self._build_drawtext_string(item)
                if dt:
                    drawtext_filters.append(dt)
        return ",".join(drawtext_filters)

    def has_preview_image_overlays(self, app_state) -> bool:
        """Check if there are image overlays to show in preview."""
        extra = app_state.extra
        return any(
            item.enabled and item.image_path and os.path.exists(item.image_path)
            for item in extra.image_overlays
        )

    def _get_vob_duration(self, vob_path: str) -> float:
        if vob_path in self._vob_duration_cache:
            return self._vob_duration_cache[vob_path]
        self.app_state.log(f"[DVD] Probing VOB: {os.path.basename(vob_path)}", "DEBUG")
        ffprobe = self._get_ffprobe_path()
        for probe_path in [ffprobe, self.app_state.ffmpeg_path]:
            try:
                cmd = [probe_path, "-v", "error", "-i", vob_path,
                       "-show_entries", "format=duration",
                       "-of", "default=noprint_wrappers=1:nokey=1"]
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=True, timeout=15)
                if result.returncode == 0 and result.stdout.strip() and result.stdout.strip() != 'N/A':
                    duration = float(result.stdout.strip())
                    if duration > 0:
                        self._vob_duration_cache[vob_path] = duration
                        self.app_state.log(f"[DVD] VOB duration: {duration:.1f}s", "DEBUG")
                        return duration
            except Exception as e:
                self.app_state.log(f"[DVD] Probe failed for {os.path.basename(vob_path)}: {e}", "DEBUG")
                continue
        self._vob_duration_cache[vob_path] = 0.0
        self.app_state.log(f"[DVD] VOB duration probe returned 0 for {os.path.basename(vob_path)}", "WARN")
        return 0.0

    def _find_dvd_vob_for_timestamp(self, timestamp: float):
        """
        Find the correct VOB file and relative timestamp for a DVD seek.
        Probes actual VOB durations with ffprobe (cached).
        Falls back to file-size proportion or simple first-VOB + concat.
        Returns (vob_path, adjusted_timestamp) or (None, timestamp) on failure.
        """
        if not self.app_state.dvd.available_titles:
            self.app_state.log(f"[DVD] No available titles", "WARN")
            return None, timestamp
        for title in self.app_state.dvd.available_titles:
            if title.title_number == self.app_state.dvd.selected_title_number:
                vobs = title.vob_files
                self.app_state.log(f"[DVD] Title {title.title_number}: {len(vobs)} VOBs, total duration={title.duration:.1f}s", "INFO")
                if not vobs:
                    self.app_state.log(f"[DVD] No VOB files for title {title.title_number}", "ERROR")
                    return None, timestamp
                # Try probing actual durations first
                vob_durs = [self._get_vob_duration(v) for v in vobs]
                all_zero = all(d <= 0 for d in vob_durs)
                if all_zero:
                    self.app_state.log(f"[DVD] All VOB probes failed, using file-size proportion fallback", "WARN")
                    sizes = []
                    total_size = 0
                    for v in vobs:
                        try:
                            sz = os.path.getsize(v)
                        except OSError:
                            sz = 0
                        sizes.append(sz)
                        total_size += sz
                    vob_durs = [
                        max(title.duration / max(len(vobs), 1), 1.0)
                        if total_size <= 0 else
                        max(title.duration * (sz / total_size), 1.0)
                        for sz in sizes
                    ]
                cum_time = 0.0
                for i, v in enumerate(vobs):
                    vob_dur = vob_durs[i]
                    self.app_state.log(f"[DVD] VOB[{i}]={os.path.basename(v)} dur={vob_dur:.1f}s cum={cum_time:.1f}s", "INFO")
                    if timestamp < cum_time + vob_dur or i == len(vobs) - 1:
                        adj_ts = max(0.0, min(timestamp - cum_time, vob_dur - 1.0))
                        self.app_state.log(f"[DVD] Seek ts={timestamp:.1f}s -> VOB[{i}] adjusted={adj_ts:.1f}s", "INFO")
                        return v, adj_ts
                    cum_time += vob_dur
                break
        self.app_state.log(f"[DVD] Could not find VOB for timestamp {timestamp:.1f}s", "ERROR")
        return None, timestamp

    def capture_frame(self, video_path: str, timestamp: float,
                      subtitle_filter: str = "", is_dvd_source: bool = False,
                      first_vob_path: str = None,
                      max_size: tuple = None,
                      extra_video_filter: str = "",
                      extra_image_paths: list = None) -> Optional[bytes]:
        ffmpeg_path = self.app_state.ffmpeg_path
        is_generated = self.app_state.extra.generate_video
        if is_generated:
            extra = self.app_state.extra
            res = extra.gen_resolution
            color = extra.gen_color
            cmd = [ffmpeg_path, "-f", "lavfi", "-i", f"color=c={color}:s={res}:r=1"]
        elif is_dvd_source:
            vob_path, adj_ts = self._find_dvd_vob_for_timestamp(timestamp)
            if vob_path and os.path.exists(vob_path):
                cmd = [ffmpeg_path, "-ss", str(adj_ts)]
                cmd.extend(["-i", vob_path])
            else:
                cmd = [ffmpeg_path, "-ss", str(timestamp)]
                cmd.extend(["-i", video_path])
        else:
            cmd = [ffmpeg_path, "-ss", str(timestamp)]
            cmd.extend(["-i", video_path])

        # Add image overlay inputs
        image_paths = extra_image_paths or []
        for img_path in image_paths:
            cmd.extend(["-i", img_path])

        scale_filter = ""
        if max_size:
            scale_filter = f"scale='min({max_size[0]},iw)':min'({max_size[1]},ih)':force_original_aspect_ratio=decrease"

        # Combine all video filters
        vf_parts = []
        if subtitle_filter:
            vf_parts.append(subtitle_filter)
        if extra_video_filter:
            vf_parts.append(extra_video_filter)
        if scale_filter:
            vf_parts.append(scale_filter)

        if image_paths:
            main_vf = ",".join(vf_parts) if vf_parts else ""
            fc, num_ov, last_label = self._build_overlay_filter_complex(self.app_state.extra, main_vf)
            if fc:
                cmd.extend(["-filter_complex", fc])
                cmd.extend(["-map", f"[{last_label}]"])
            elif main_vf:
                cmd.extend(["-vf", main_vf])
        elif vf_parts:
            cmd.extend(["-vf", ",".join(vf_parts)])

        cmd.extend(["-vframes", "1", "-q:v", "2", "-f", "image2pipe", "-vcodec", "png", "-"])
        self.app_state.log(f"[DVD] FFmpeg cmd: {' '.join(cmd[:6])} ... -vframes 1", "DEBUG")
        try:
            timeout = 30 if is_dvd_source else 10
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            self.app_state.log(f"[DVD] FFmpeg exit={result.returncode} stdout={len(result.stdout)}B stderr={result.stderr[:200]}", "DEBUG")
            if result.returncode == 0 and result.stdout:
                return result.stdout
            if result.returncode != 0 and subtitle_filter:
                retry = [x for x in cmd if x != "-vf" or True]
                i = 0
                while i < len(cmd):
                    if cmd[i] == "-vf":
                        i += 2
                        continue
                    retry.append(cmd[i])
                    i += 1
                if retry:
                    result = subprocess.run(retry, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
                    if result.returncode == 0 and result.stdout:
                        return result.stdout
        except Exception:
            pass
        return None

    def apply_video_filter(self, image_bytes: bytes, filter_str: str) -> Optional[bytes]:
        cmd = [
            self.app_state.ffmpeg_path,
            "-i", "-",
            "-vf", filter_str,
            "-f", "image2pipe",
            "-vcodec", "png",
            "-"
        ]
        try:
            result = subprocess.run(cmd, input=image_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            if result.returncode == 0 and result.stdout:
                return result.stdout
        except Exception:
            pass
        return None

    def get_frame_rate(self, video_path: str) -> dict:
        ffprobe_path = self._get_ffprobe_path()
        cmd = [
            ffprobe_path, "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split('/')
                if len(parts) == 2:
                    num, den = float(parts[0]), float(parts[1])
                    if den > 0:
                        fps = num / den
                        return {
                            'fps': fps,
                            'fps_str': result.stdout.strip(),
                            'is_vfr': False,
                            'is_problematic': fps < 15.0 or fps > 120.0
                        }
        except Exception:
            pass
        return {'fps': None, 'is_vfr': True, 'is_problematic': True}

    def get_full_info(self, video_path: str) -> dict:
        ffprobe_path = self._get_ffprobe_path()
        cmd = [ffprobe_path, "-v", "error", "-show_format", "-show_streams", "-of", "json", video_path]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
            if result.returncode == 0:
                return json.loads(result.stdout)
        except Exception:
            pass
        return {}

    def supported_filters(self) -> dict:
        """FFmpeg supports all filters natively."""
        return {
            # Video filters
            'deinterlace': True,
            'denoise': True,
            'sharpen': True,
            'cas': True,
            'deblock': True,
            'smart_crop': True,
            'ar_crop': True,
            'ar_convert': True,
            'video_rotate': True,
            'delogo': True,
            # Color correction (EQ)
            'eq_brightness': True,
            'eq_contrast': True,
            'eq_saturation': True,
            'eq_gamma': True,
            'white_balance': True,
            # Colorization (B&W → Color)
            'colorization': True,
            # Audio filters
            'volume': True,
            'audio_denoise': True,
            'audio_dynnorm': True,
            'audio_compressor': True,
            'audio_delay': True,
        }

    def get_file_info(self, input_path: str) -> dict:
        info = {}
        cmd = [self.app_state.ffmpeg_path, "-i", input_path, "-f", "null", "-"]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            stderr = result.stderr

            match = re.search(r"\d{3,4}x\d{3,4}", stderr)
            if match:
                info['resolution'] = match.group()
            match = re.search(r"Stream #0:0.*Video: (\w+)", stderr)
            if match:
                info['codec'] = match.group(1)
            match = re.search(r"bitrate: (\d+) kb/s", stderr)
            if match:
                info['bitrate'] = match.group(1)
            match = re.search(r"Duration: (\d{2}:\d{2}:\d{2})", stderr)
            if match:
                info['duration'] = match.group(1)
        except Exception:
            pass
        return info

    def extract_subtitle(self, input_path: str, stream_idx: int, output_path: str, codec_name: str = None) -> Optional[str]:
        cmd = [
            self.app_state.ffmpeg_path, "-y",
            "-analyzeduration", "100M", "-probesize", "100M",
            "-i", input_path,
            "-map", f"0:s:{stream_idx}"
        ]
        if codec_name in ("hdmv_pgs_subtitle", "pgssub"):
            cmd.extend(["-c:s", "copy"])
            out, ext = os.path.splitext(output_path)
            if ext.lower() != ".sup":
                output_path = out + ".sup"
        else:
            cmd.extend(["-c:s", "srt"])
        cmd.append(output_path)
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
            if result.returncode == 0 and os.path.exists(output_path):
                return output_path
        except Exception:
            pass
        return None

    def validate(self, input_path: str) -> dict:
        result = {'is_valid': True, 'issues': [], 'stderr': ''}
        cmd = [self.app_state.ffmpeg_path, "-v", "error", "-i", input_path, "-f", "null", "-"]
        try:
            r = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, timeout=30)
            result['is_valid'] = r.returncode == 0
            result['stderr'] = r.stderr[:500]
            if "Non-monotonic DTS" in r.stderr:
                result['issues'].append("DTS not monotonic")
            if "Application provided invalid" in r.stderr:
                result['issues'].append("Invalid timestamps")
        except subprocess.TimeoutExpired:
            result['is_valid'] = False
            result['issues'].append("Check timed out")
        except Exception as e:
            result['is_valid'] = False
            result['issues'].append(str(e))
        return result

    def build_filter_string(self, app_state) -> tuple:
        video_filters = []
        audio_filters = []
        encoding = app_state.encoding
        filters = app_state.filters
        eq = app_state.eq
        tracks = app_state.tracks

        if encoding.scale_mode == "on":
            res = encoding.resolution
            algorithm = encoding.scale_algorithm
            quality = encoding.scale_quality
            aspect_mode = getattr(encoding, 'aspect_ratio_mode', 'fit')
            src_width = getattr(tracks, 'video_width', 0)
            src_height = getattr(tracks, 'video_height', 0)

            def calc_fit_h(target_w):
                if src_width and src_height and target_w:
                    return int(round(target_w * src_height / src_width / 2) * 2)
                return None

            if res == "none" or not res:
                pass
            else:
                res_spec = getattr(encoding, 'custom_resolution', '1280x720') if res == "Custom" else res
                interl = "1" if quality == "quality" else "0"

                if algorithm == "bilinear":
                    scale_filter = f"scale={res_spec}:flags=lanczos:interl={interl}" if quality == "quality" else f"scale={res_spec}"
                elif algorithm == "bicubic":
                    scale_filter = f"scale={res_spec}:flags=bicubic:interl={interl}"
                elif algorithm == "lanczos":
                    scale_filter = f"scale={res_spec}:flags=lanczos:interl={interl}"
                elif algorithm == "spline":
                    scale_filter = f"scale={res_spec}:flags=spline:interl={interl}"
                elif algorithm == "area":
                    scale_filter = f"scale={res_spec}:flags=area:interl={interl}"
                elif algorithm == "zscale":
                    if "x" in res_spec:
                        w, h = res_spec.split("x")
                        scale_filter = f"zscale=w={w}:h={h}:filter=lanczos"
                    else:
                        scale_filter = "zscale=filter=lanczos"
                elif algorithm == "scale_cuda":
                    if "x" in res_spec:
                        w, h = res_spec.split("x")
                        w = int(w)
                        if aspect_mode == "fit":
                            nh = calc_fit_h(w)
                            if nh:
                                h = nh
                        scale_filter = f"scale_cuda=w={w}:h={h}"
                    else:
                        scale_filter = "scale_cuda"
                elif algorithm == "scale_vulkan":
                    if "x" in res_spec:
                        w, h = res_spec.split("x")
                        w = int(w)
                        if aspect_mode == "fit":
                            nh = calc_fit_h(w)
                            if nh:
                                h = nh
                        scale_filter = f"scale_vulkan=w={w}:h={h}"
                    else:
                        scale_filter = "scale_vulkan"
                elif algorithm == "libplacebo":
                    upscaler = "ewa_lanczos" if quality == "quality" else "bilinear"
                    tone_mapping = getattr(encoding, 'libplacebo_tonemapping', 'none')
                    if "x" in res_spec:
                        w, h = res_spec.split("x")
                        w = int(w)
                        if aspect_mode == "fit":
                            nh = calc_fit_h(w)
                            if nh:
                                h = nh
                        if tone_mapping != "none" and tone_mapping:
                            scale_filter = f"libplacebo=w={w}:h={h}:upscaler={upscaler}:tonemapping={tone_mapping}"
                        else:
                            scale_filter = f"libplacebo=w={w}:h={h}:upscaler={upscaler}"
                    else:
                        if tone_mapping != "none" and tone_mapping:
                            scale_filter = f"libplacebo=upscaler={upscaler}:tonemapping={tone_mapping}"
                        else:
                            scale_filter = f"libplacebo=upscaler={upscaler}"
                else:
                    scale_filter = f"scale={res_spec}"

                video_filters.append(scale_filter)

        if filters.deinterlace:
            video_filters.append("yadif")
        if filters.denoise:
            video_filters.append("hqdn3d")
        if getattr(filters, 'sharpen', False):
            amount = getattr(filters, 'sharpen_amount', 1.0)
            video_filters.append(f"unsharp=5:5:{amount}")
        if getattr(filters, 'cas_enabled', False):
            strength = getattr(filters, 'cas_strength', 0.0)
            video_filters.append(f"cas={strength}")
        if getattr(filters, 'deblock', False):
            strength = getattr(filters, 'deblock_strength', 0.5)
            video_filters.append(f"deblock=filter=strong:alpha={strength}:beta={strength}")

        if getattr(filters, 'smart_crop_enabled', False):
            crop_mode = getattr(filters, 'smart_crop_mode', 'manual')
            min_dim = 16
            if crop_mode == 'manual':
                w = max(filters.smart_crop_w, min_dim) // 2 * 2
                h = max(filters.smart_crop_h, min_dim) // 2 * 2
                x = filters.smart_crop_x
                y = filters.smart_crop_y
                video_filters.append(f"crop={w}:{h}:{x}:{y}")
                if getattr(filters, 'smart_crop_show_preview', False):
                    video_filters.append(f"drawbox=x={x}:y={y}:w={w}:h={h}:color=green:thickness=3")
            else:
                w = max(filters.smart_crop_w, min_dim) // 2 * 2
                h = max(filters.smart_crop_h, min_dim) // 2 * 2
                video_filters.append(f"crop={w}:{h}:(iw-{w})/2:(ih-{h})/2")
                if getattr(filters, 'smart_crop_show_preview', False):
                    video_filters.append(f"drawbox=x=(iw-{w})/2:y=(ih-{h})/2:w={w}:h={h}:color=green:thickness=3")

        if getattr(filters, 'ar_crop_enabled', False):
            ar_targets = {"16:9": 16.0/9.0, "4:3": 4.0/3.0, "1:1": 1.0, "2.35:1": 2.35}
            target_ar = ar_targets.get(getattr(filters, 'ar_crop_target', '16:9'), 16.0/9.0)
            video_filters.append(
                f"crop=ih*{target_ar:.4f}:ih:(ih*{target_ar:.4f}-iw)/2:0")

        video_dir = getattr(filters, 'video_rotate', 'none')
        if video_dir and video_dir != 'none':
            if video_dir == '90r':
                video_filters.append("transpose=1")
            elif video_dir == '90l':
                video_filters.append("transpose=2")
            elif video_dir == '180':
                video_filters.extend(["transpose=2,transpose=2"])
            elif video_dir == 'horiz':
                video_filters.append("hflip")
            elif video_dir == 'vert':
                video_filters.append("vflip")

        if getattr(filters, 'ar_convert_enabled', False):
            ar_targets = {"16:9": 16.0/9.0, "4:3": 4.0/3.0, "1:1": 1.0, "2.35:1": 2.35}
            target_ar = ar_targets.get(getattr(filters, 'ar_target', '16:9'), 16.0/9.0)
            ar_method = getattr(filters, 'ar_method', 'crop')

            if ar_method == "crop":
                video_filters.append(f"crop=ih*{target_ar:.4f}:ih:(ih*{target_ar:.4f}-iw)/2:0")
            elif ar_method == "pad":
                video_filters.append(f"pad=ih*{target_ar:.4f}:ih:(ih*{target_ar:.4f}-iw)/2:0:black")
            elif ar_method == "scale_2step":
                video_filters.append(f"scale=iw*min({target_ar:.4f}*(ih/iw),1):ih*min(1,({target_ar:.4f})/(ih/iw)),setsar=1")
            else:
                video_filters.append(f"scale=iw*{target_ar:.4f}:ih")
            video_filters.append("setsar=1:1")

        if getattr(filters, 'delogo_enabled', False):
            x = filters.delogo_x
            y = filters.delogo_y
            w = filters.delogo_w
            h = filters.delogo_h
            video_filters.append(f"delogo=x={x}:y={y}:w={w}:h={h}")
            if getattr(filters, 'delogo_show', False):
                video_filters.append(f"drawbox=x={x}:y={y}:w={w}:h={h}:color=red:thickness=2")

        if eq.enabled:
            eq_params = []
            if eq.brightness != 0:
                eq_params.append(f"brightness={eq.brightness}")
            if eq.contrast != 1.0:
                eq_params.append(f"contrast={eq.contrast}")
            if eq.saturation != 1.0:
                eq_params.append(f"saturation={eq.saturation}")
            if eq.gamma != 1.0:
                eq_params.append(f"gamma={eq.gamma}")
            if eq.gamma_r != 1.0:
                eq_params.append(f"gamma_r={eq.gamma_r}")
            if eq.gamma_g != 1.0:
                eq_params.append(f"gamma_g={eq.gamma_g}")
            if eq.gamma_b != 1.0:
                eq_params.append(f"gamma_b={eq.gamma_b}")
            if eq_params:
                video_filters.append(f"eq={':'.join(eq_params)}")

        if eq.white_balance_enabled:
            wb_params = []
            if eq.wb_shadows_r != 0:
                wb_params.append(f"rs={eq.wb_shadows_r}")
            if eq.wb_shadows_g != 0:
                wb_params.append(f"gs={eq.wb_shadows_g}")
            if eq.wb_shadows_b != 0:
                wb_params.append(f"bs={eq.wb_shadows_b}")
            if eq.wb_midtones_r != 0:
                wb_params.append(f"rm={eq.wb_midtones_r}")
            if eq.wb_midtones_g != 0:
                wb_params.append(f"gm={eq.wb_midtones_g}")
            if eq.wb_midtones_b != 0:
                wb_params.append(f"bm={eq.wb_midtones_b}")
            if eq.wb_highlights_r != 0:
                wb_params.append(f"rh={eq.wb_highlights_r}")
            if eq.wb_highlights_g != 0:
                wb_params.append(f"gh={eq.wb_highlights_g}")
            if eq.wb_highlights_b != 0:
                wb_params.append(f"bh={eq.wb_highlights_b}")
            if wb_params:
                video_filters.append(f"colorbalance={':'.join(wb_params)}")

        # === Colorization (B&W → Color) ===
        colorization = app_state.colorization
        if colorization.enabled:
            if colorization.method == "tint":
                h = colorization.tint_hue / 360.0
                s = min(colorization.tint_saturation, 1.0)
                tint_r, tint_g, tint_b = self._hsl_to_rgb(h, s, 0.5)
                strength = colorization.tint_strength
                rc = (1.0 - strength + strength * tint_g) / 3.0
                gc = (1.0 - strength + strength * tint_b) / 3.0
                bc = (1.0 - strength + strength * tint_r) / 3.0
                video_filters.append("format=gbrp")
                video_filters.append(
                    f"colorchannelmixer="
                    f"rr={rc:.6f}:rg={rc:.6f}:rb={rc:.6f}:"
                    f"gr={gc:.6f}:gg={gc:.6f}:gb={gc:.6f}:"
                    f"br={bc:.6f}:bg={bc:.6f}:bb={bc:.6f}"
                )
            elif colorization.method == "pseudocolor":
                preset = colorization.pseudocolor_preset
                opacity = colorization.pseudocolor_opacity
                video_filters.append(f"pseudocolor=colorpreset={preset}:opacity={opacity}")
            elif colorization.method == "lut":
                lut_path = colorization.lut_path
                if lut_path and os.path.exists(lut_path):
                    lut_type = colorization.lut_type
                    escaped = lut_path.replace("'", "'\\''")
                    if lut_type == "lut3d":
                        video_filters.append(f"lut3d=file='{escaped}'")
                    elif lut_type == "lutrgb":
                        video_filters.append(f"lutrgb=file='{escaped}'")
                    elif lut_type == "lutyuv":
                        video_filters.append(f"lutyuv=file='{escaped}'")

        if filters.volume_enabled:
            audio_filters.append(f"volume={filters.volume_db}dB")
        if getattr(filters, 'audio_denoise', False):
            audio_filters.append("afftdn=nf=-25")
        if getattr(filters, 'audio_dynnorm', False):
            audio_filters.append("dynaudnorm=f=150:g=15:r=0.95")
        if getattr(filters, 'audio_compressor', False):
            audio_filters.append("acompressor=threshold=0.15:ratio=3:attack=20:release=250")
        if getattr(filters, 'audio_delay_enabled', False):
            delay_ms = filters.audio_delay_ms
            if delay_ms > 0:
                audio_filters.append(f"adelay={delay_ms}|{delay_ms}")

        # ── Extra: Text overlays (drawtext) ──
        extra = app_state.extra
        for item in extra.text_overlays:
            if item.enabled and item.text.strip():
                dt = self._build_drawtext_string(item)
                if dt:
                    video_filters.append(dt)

        return (
            ",".join(video_filters) if video_filters else "",
            ",".join(audio_filters) if audio_filters else ""
        )

    # ── Extra: Text Overlays (drawtext) ─────────────────────────────

    @staticmethod
    def _build_drawtext_string(item) -> str:
        """Build a drawtext filter string for a single text overlay."""
        text = item.text.replace("'", "'\\''").replace(":", "\\:")
        fontcolor = item.font_color
        x, y = item.x, item.y
        anim = item.animation
        expr_x = str(x)
        expr_y = str(y)

        if anim == "Slide In Left":
            expr_x = f"if(between(t,0,1),-w+(t/1)*({x}+w),{x})"
            expr_y = str(y)
        elif anim == "Slide In Right":
            expr_x = f"if(between(t,0,1),W-(t/1)*(W-{x}),{x})"
        elif anim == "Slide In Top":
            expr_y = f"if(between(t,0,1),-h+(t/1)*({y}+h),{y})"
        elif anim == "Slide In Bottom":
            expr_y = f"if(between(t,0,1),H-(t/1)*(H-{y}),{y})"
        elif anim == "Bounce":
            expr_y = f"{y}+abs(sin(t*10))*20"
        elif anim == "Typewriter":
            speed = max(50, item.font_size * 3)
            expr_x = f"W-t*{speed}"

        dt = (
            f"drawtext=text='{text}'"
            f":fontsize={item.font_size}"
            f":fontcolor={fontcolor}"
            f":x={expr_x}"
            f":y={expr_y}"
            f":borderw=1"
            f":bordercolor=black@0.5"
        )
        return dt

    # ── Extra: Image Overlays (overlay) ─────────────────────────────

    @staticmethod
    def _build_overlay_filter_complex(extra, main_video_filter: str = "") -> tuple:
        """
        Build filter_complex string for image overlays on top of a main video chain.
        Args:
            main_video_filter: comma-joined video filter string for the main video
                               (includes drawtext, subtitles, etc.)
        Returns:
            (filter_complex_str, num_images, last_output_label)
        """
        enabled_images = [
            item for item in extra.image_overlays
            if item.enabled and item.image_path and os.path.exists(item.image_path)
        ]
        if not enabled_images:
            return "", 0, ""

        parts = []
        if main_video_filter:
            parts.append(f"[0:v]{main_video_filter}[base]")
        else:
            parts.append("[0:v]null[base]")

        current_label = "base"
        img_idx = 1

        for item in enabled_images:
            stream_label = f"ov{img_idx}"
            out_label = f"out{img_idx}"
            scale_pct = item.scale
            x, y = item.x, item.y
            opacity = item.opacity
            anim = item.animation

            overlay_x = str(x)
            overlay_y = str(y)
            overlay_alpha = str(opacity)
            scale_w = f"iw*{scale_pct}"
            scale_h = f"ih*{scale_pct}"

            if anim == "Fade In":
                overlay_alpha = f"if(between(t,0,1),t/1,{opacity})"
            elif anim == "Fade Out":
                overlay_alpha = f"if(between(t,0,1),{opacity},{opacity}*max(0,1-(t-1)/1))"
            elif anim == "Slide In Left":
                overlay_x = f"if(between(t,0,1),-w+(t/1)*({x}+w),{x})"
            elif anim == "Slide In Right":
                overlay_x = f"if(between(t,0,1),W-(t/1)*(W-{x}),{x})"
            elif anim == "Slide In Top":
                overlay_y = f"if(between(t,0,1),-h+(t/1)*({y}+h),{y})"
            elif anim == "Slide In Bottom":
                overlay_y = f"if(between(t,0,1),H-(t/1)*(H-{y}),{y})"
            elif anim == "Bounce":
                overlay_y = f"{y}+abs(sin(t*10))*20"
            elif anim == "Pulse":
                pulse = "1+0.1*sin(t*5)"
                scale_w = f"iw*{scale_pct}*({pulse})"
                scale_h = f"ih*{scale_pct}*({pulse})"

            # Format + scale the image input
            scale_expr = (
                f"scale='min({scale_w},iw)':min'({scale_h},ih)':force_original_aspect_ratio=decrease"
            )
            parts.append(f"[{img_idx}:v]format=rgba,{scale_expr}[{stream_label}]")

            # Overlay onto current chain
            parts.append(
                f"[{current_label}][{stream_label}]"
                f"overlay=x={overlay_x}:y={overlay_y}:alpha={overlay_alpha}[{out_label}]"
            )

            current_label = out_label
            img_idx += 1

        return ",".join(parts), len(enabled_images), current_label

    # ── Extra: Standalone Generated Video ───────────────────────────

    def build_generate_video_command(self, output_path: str) -> list:
        """Build command for generating a standalone color video with overlays."""
        extra = self.app_state.extra
        encoding = self.app_state.encoding

        color = extra.gen_color
        res = extra.gen_resolution
        duration = extra.gen_duration_sec
        framerate = extra.gen_framerate

        cmd = [self.app_state.ffmpeg_path]

        # Color video source via lavfi
        cmd.extend(["-f", "lavfi"])
        cmd.extend(["-i", f"color=c={color}:s={res}:d={duration}:r={framerate}"])

        # Image overlay inputs
        image_paths = []
        for item in extra.image_overlays:
            if item.enabled and item.image_path and os.path.exists(item.image_path):
                image_paths.append(item.image_path)
                cmd.extend(["-i", item.image_path])

        # Optional silent audio
        if extra.gen_include_audio:
            cmd.extend(["-f", "lavfi"])
            cmd.extend(["-i", "anullsrc=r=44100:cl=stereo"])

        # Build text overlay filters (drawtext)
        text_parts = []
        for item in extra.text_overlays:
            if item.enabled and item.text.strip():
                dt = self._build_drawtext_string(item)
                if dt:
                    text_parts.append(dt)
        text_filter = ",".join(text_parts)

        if image_paths:
            fc, num_ov, last_label = self._build_overlay_filter_complex(extra, text_filter)
            if fc:
                cmd.extend(["-filter_complex", fc])
                cmd.extend(["-map", f"[{last_label}]"])
            elif text_filter:
                cmd.extend(["-vf", text_filter])
        elif text_filter:
            cmd.extend(["-vf", text_filter])

        # Video encoder settings
        encoder = encoding.encoder
        cmd.extend(["-c:v", encoder])
        if encoding.use_gpu and "nvenc" in encoder:
            cmd.extend(["-preset", encoding.gpu_preset])
            cmd.extend(["-cq", str(encoding.cq)])
        elif encoder == "mpeg2video":
            cmd.extend(["-b:v", "6000k"])
        else:
            cmd.extend(["-crf", str(encoding.cq)])
            cmd.extend(["-preset", encoding.cpu_preset])
            if encoding.cpu_tune != "none":
                cmd.extend(["-tune", encoding.cpu_tune])

        pix_fmt = getattr(encoding, 'pixel_format', 'yuv420p')
        if not (encoding.use_gpu and "nvenc" in encoder and pix_fmt == "yuv420p"):
            cmd.extend(["-pix_fmt", pix_fmt])

        if encoder == "libx265":
            cmd.extend(["-x265-params", "keyint=144:min-keyint=144:bframes=0:level=4.0"])
        elif encoder == "mpeg2video":
            cmd.extend(["-g", encoding.gop_size])
            cmd.extend(["-bf", encoding.bframes])
            cmd.extend(["-profile:v", encoding.profile])
        else:
            cmd.extend(["-g", encoding.gop_size])
            cmd.extend(["-bf", encoding.bframes])
            cmd.extend(["-profile:v", encoding.profile])
            cmd.extend(["-level:v", encoding.level])

        if extra.gen_include_audio:
            cmd.extend(["-c:a", self._audio_codec(), "-b:a", "128k", "-ar", encoding.audio_sample_rate, *self._audio_channels_args()])

        if not image_paths:
            cmd.extend(["-map", "0:v"])
        if extra.gen_include_audio:
            audio_idx = len(image_paths) + 1
            cmd.extend(["-map", f"{audio_idx}:a"])

        # Force duration to prevent lavfi PTS drift
        cmd.extend(["-t", str(duration)])

        cmd.extend(["-y", output_path])
        return cmd

    @staticmethod
    def _hsl_to_rgb(h: float, s: float, l: float) -> tuple:
        """Convert HSL (all 0.0-1.0) to RGB (0.0-1.0)"""
        if s == 0.0:
            return l, l, l
        def hue_to_rgb(p, q, t):
            if t < 0.0: t += 1.0
            if t > 1.0: t -= 1.0
            if t < 1.0 / 6.0: return p + (q - p) * 6.0 * t
            if t < 1.0 / 2.0: return q
            if t < 2.0 / 3.0: return p + (q - p) * (2.0 / 3.0 - t) * 6.0
            return p
        q = l * (1.0 + s) if l < 0.5 else l + s - l * s
        p = 2.0 * l - q
        return hue_to_rgb(p, q, h + 1.0 / 3.0), hue_to_rgb(p, q, h), hue_to_rgb(p, q, h - 1.0 / 3.0)

    def find_subtitle_file(self, video_path: str) -> Optional[str]:
        if not video_path:
            return None
        # Prefer auto-detect based on current video's basename.
        # This ensures each video in a batch gets its own matching subtitle
        # instead of a stale selected_subtitle from a previous file.
        base = os.path.splitext(video_path)[0]
        for ext in [".srt", ".ass", ".ssa", ".sub"]:
            sub_path = base + ext
            if os.path.exists(sub_path):
                return sub_path
        # Fall back to user-selected subtitle (UI combo box)
        selected = self.app_state.subtitles.selected_subtitle
        if selected and os.path.exists(selected):
            return selected
        return None

    def hex_to_ass(self, hex_color: str, opacity: float = 1.0) -> str:
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        alpha = 255 - int(opacity * 255)
        return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"

    def build_subtitle_filter(self, sub_path: str) -> str:
        subs = self.app_state.subtitles
        is_vobsub = sub_path.lower().endswith('.sub')
        escaped_path = sub_path.replace("\\", "/").replace("'", "'\\''")
        escaped_path = escaped_path.replace("[", "\\[").replace("]", "\\]")
        escaped_path = re.sub(r'^([A-Z]):/', r'\1\:/', escaped_path, flags=re.IGNORECASE)

        if is_vobsub:
            return f"subtitles='{escaped_path}'"

        style = []
        if subs.font != "Arial":
            style.append(f"Fontname={subs.font}")
        style.append(f"Fontsize={subs.size}")
        if subs.color != "#FFFFFF":
            style.append(f"PrimaryColour={self.hex_to_ass(subs.color)}")
        if subs.outline_color != "#000000":
            style.append(f"OutlineColour={self.hex_to_ass(subs.outline_color)}")
        if subs.outline_width != 2:
            style.append(f"Outline={subs.outline_width}")

        if subs.shadow_enabled and subs.bg_opacity > 0.0:
            shadow_ass = self.hex_to_ass(subs.shadow_color, subs.shadow_opacity)
            style.append(f"BackColour={shadow_ass}")
            style.append("BorderStyle=3")
            shadow_distance = max(subs.shadow_offset_x, subs.shadow_offset_y, 2)
            style.append(f"Shadow={shadow_distance}")
        elif subs.shadow_enabled:
            outline_ass = self.hex_to_ass(subs.shadow_color, subs.shadow_opacity)
            style.append(f"OutlineColour={outline_ass}")
            style.append("BorderStyle=2")
            shadow_distance = max(subs.shadow_offset_x, subs.shadow_offset_y, 2)
            style.append(f"Shadow={shadow_distance}")
        elif subs.bg_opacity > 0.0:
            ass_bg = self.hex_to_ass(subs.bg_color, subs.bg_opacity)
            style.append(f"BackColour={ass_bg}")
            style.append("BorderStyle=4")
        else:
            style.append("BorderStyle=1")

        if subs.shadow_enabled and subs.outline_width == 0:
            style.append("Outline=1")

        pos_map = {"bottom": 2, "top": 8, "center": 10}
        if subs.position != "bottom":
            style.append(f"Alignment={pos_map.get(subs.position, 2)}")
        if subs.vertical_offset > 0:
            if subs.position == "bottom":
                margin_v = max(0, 20 - subs.vertical_offset)
                style.append(f"MarginV={margin_v}")
            else:
                style.append(f"MarginV={subs.vertical_offset}")

        force_style = f":force_style='{','.join(style)}'" if style else ""
        return f"subtitles='{escaped_path}'{force_style}"

    def build_command(self, input_path: str, output_path: str,
                      start_time: Optional[str] = None,
                      duration: Optional[str] = None) -> List[str]:
        cmd = [self.app_state.ffmpeg_path]
        encoding = self.app_state.encoding
        filters = self.app_state.filters
        eq = self.app_state.eq
        tracks = self.app_state.tracks
        subtitles = self.app_state.subtitles
        dvd = self.app_state.dvd

        encoder = encoding.encoder
        is_dvd_source = dvd.is_dvd_source and input_path.endswith('.txt')
        if encoding.use_gpu and "nvenc" in encoder:
            cmd.extend(["-hwaccel", "cuda"])

        # ── Extra: Standalone generated video ──
        if self.app_state.extra.generate_video:
            return self.build_generate_video_command(output_path)

        if self.app_state.split.extract_clip_enabled:
            start_min = self.app_state.split.extract_start_min
            duration_min = self.app_state.split.extract_duration_min
            start_time = str(int(start_min * 60))
            duration = str(int(duration_min * 60))

            burn_subs = subtitles.burn_subs
            sub_path = self.find_subtitle_file(input_path) if burn_subs else None

            burning_dvd_subs = is_dvd_source and dvd.selected_subtitle_index >= 0
            if burning_dvd_subs:
                pass

            dvd_concat_input = self._get_dvd_concat_input() if is_dvd_source else None

            if burn_subs and sub_path:
                cmd.extend(["-ss", start_time])
                cmd.extend(["-i", dvd_concat_input if dvd_concat_input else input_path])
                ext_audio_enabled = getattr(tracks, 'external_audio_enabled', False)
                ext_audio_path = getattr(tracks, 'external_audio_path', '')
                if ext_audio_enabled and ext_audio_path and os.path.exists(ext_audio_path):
                    cmd.extend(["-i", ext_audio_path])
                    self._external_audio = True
                else:
                    self._external_audio = False
                cmd.extend(["-t", duration])
                video_filters_str, audio_filters_str = self.build_filter_string(self.app_state)
                subs_filter = self.build_subtitle_filter(sub_path)
                filter_parts = []
                if video_filters_str:
                    filter_parts.append(video_filters_str)
                if subs_filter:
                    filter_parts.append(subs_filter)
                filter_parts.append("setpts=PTS-STARTPTS")
                cmd.extend(["-vf", ",".join(filter_parts)])
                cmd.extend(["-af", "asetpts=PTS-STARTPTS"])
            else:
                cmd.extend(["-ss", start_time])
                cmd.extend(["-i", dvd_concat_input if dvd_concat_input else input_path])
                ext_audio_enabled = getattr(tracks, 'external_audio_enabled', False)
                ext_audio_path = getattr(tracks, 'external_audio_path', '')
                if ext_audio_enabled and ext_audio_path and os.path.exists(ext_audio_path):
                    cmd.extend(["-i", ext_audio_path])
                    self._external_audio = True
                else:
                    self._external_audio = False
                cmd.extend(["-t", duration])
                video_filters_str, audio_filters_str = self.build_filter_string(self.app_state)
                if video_filters_str:
                    cmd.extend(["-vf", video_filters_str])
                elif encoding.resolution != "none" and encoding.scale_mode == "off":
                    res_value = encoding.custom_resolution if encoding.resolution == "Custom" else encoding.resolution
                    cmd.extend(["-s", res_value])
                if burn_subs and not is_dvd_source:
                    pass

            video_mode = getattr(encoding, 'video_mode', 'encode')
            if video_mode == "copy":
                cmd.extend(["-c:v", "copy"])
            else:
                cmd.extend(["-c:v", encoder])
                bitrate_is_set = encoding.use_original_bitrate or (
                    encoding.target_bitrate and encoding.target_bitrate.isdigit() and int(encoding.target_bitrate) > 0
                )
                if encoding.use_gpu and "nvenc" in encoder:
                    cmd.extend(["-preset", encoding.gpu_preset])
                    if not bitrate_is_set:
                        cmd.extend(["-cq", str(encoding.cq)])
                else:
                    if encoder == "mpeg2video":
                        if not bitrate_is_set:
                            cmd.extend(["-b:v", "6000k"])
                    else:
                        if not bitrate_is_set:
                            cmd.extend(["-crf", str(encoding.cq)])
                        cmd.extend(["-preset", encoding.cpu_preset])
                        if encoding.cpu_tune != "none":
                            cmd.extend(["-tune", encoding.cpu_tune])
                if encoding.resolution != "none" and encoding.scale_mode == "off":
                    res_value = encoding.custom_resolution if encoding.resolution == "Custom" else encoding.resolution
                    cmd.extend(["-s", res_value])
                pix_fmt = getattr(encoding, 'pixel_format', 'yuv420p')
                if not (encoding.use_gpu and "nvenc" in encoder and pix_fmt == "yuv420p"):
                    cmd.extend(["-pix_fmt", pix_fmt])
                if encoder == "libx265":
                    cmd.extend(["-x265-params", "keyint=144:min-keyint=144:bframes=0:level=4.0"])
                elif encoder == "mpeg2video":
                    cmd.extend(["-g", encoding.gop_size])
                    cmd.extend(["-bf", encoding.bframes])
                    cmd.extend(["-profile:v", encoding.profile])
                else:
                    cmd.extend(["-g", encoding.gop_size])
                    cmd.extend(["-bf", encoding.bframes])
                    cmd.extend(["-profile:v", encoding.profile])
                    cmd.extend(["-level:v", encoding.level])
                cmd.extend(["-force_key_frames:v", "0"])
                if encoding.use_original_bitrate:
                    orig_br = self.get_video_bitrate(input_path)
                    if orig_br:
                        cmd.extend(["-b:v", f"{orig_br}k"])
                        if encoding.use_max_bitrate:
                            cmd.extend(["-maxrate", f"{encoding.max_bitrate}k"])
                            cmd.extend(["-bufsize", f"{encoding.max_bitrate * 2}k"])
                        else:
                            cmd.extend(["-maxrate", f"{orig_br}k"])
                            cmd.extend(["-bufsize", f"{orig_br * 2}k"])
                else:
                    target_br = encoding.target_bitrate
                    if target_br and target_br.isdigit():
                        target_br_int = int(target_br)
                        cmd.extend(["-b:v", f"{target_br_int}k"])
                        if encoding.use_max_bitrate:
                            cmd.extend(["-maxrate", f"{encoding.max_bitrate}k"])
                            cmd.extend(["-bufsize", f"{encoding.max_bitrate * 2}k"])
                        else:
                            cmd.extend(["-maxrate", f"{target_br_int}k"])
                            cmd.extend(["-bufsize", f"{target_br_int * 2}k"])

            if tracks.video_selected:
                video_stream_idx = tracks.video_stream_index
                if video_stream_idx is None or video_stream_idx < 0:
                    video_stream_idx = 0
                cmd.extend(["-map", f"0:v:{video_stream_idx}"])

            if tracks.audio_selected:
                audio_stream_idx = tracks.audio_stream_index
                if audio_stream_idx is None or audio_stream_idx < 0:
                    audio_stream_idx = 0
                cmd.extend(["-map", f"0:a:{audio_stream_idx}"])

            # Exclude embedded subtitle streams when burning external subs
            if burn_subs and sub_path:
                cmd.extend(["-map", "-0:s"])

            _, audio_filters_str = self.build_filter_string(self.app_state)

            if getattr(self, '_external_audio', False):
                cmd.extend(["-map", "1:a"])
                if tracks.audio_copy_mode:
                    ext_path = tracks.external_audio_path
                    ext = os.path.splitext(ext_path)[1].lower()
                    if ext in ['.mp3', '.aac', '.ac3', '.m4a', '.flac', '.ogg', '.wav']:
                        cmd.extend(["-c:a", "copy"])
                    else:
                        cmd.extend(["-c:a", self._audio_codec(), "-b:a", "128k", *self._audio_channels_args()])
                else:
                    cmd.extend(["-c:a", self._audio_codec(), "-b:a", "128k", *self._audio_channels_args()])
                cmd.extend(["-shortest"])
            elif tracks.audio_copy_mode:
                cmd.extend(["-c:a", "copy"])
            else:
                cmd.extend(["-c:a", self._audio_codec(), "-b:a", "128k", *self._audio_channels_args()])
                if audio_filters_str:
                    cmd.extend(["-af", audio_filters_str])
            cmd.extend(["-y", output_path])
            return cmd

        # DVD VOB: use concat: protocol (byte-level) instead of concat demuxer
        # to avoid PTS discontinuity at VOB boundaries
        dvd_concat_input = self._get_dvd_concat_input() if is_dvd_source else None
        if dvd_concat_input:
            if start_time and float(start_time) > 0:
                cmd.extend(["-ss", start_time])
            cmd.extend(["-i", dvd_concat_input])
        else:
            if is_dvd_source:
                cmd.extend(["-f", "concat", "-safe", "0"])
                cmd.extend(["-fflags", "+genpts"])

            # Fast seek to keyframe for non-zero start times
            if start_time and float(start_time) > 0:
                cmd.extend(["-ss", start_time])

            cmd.extend(["-i", input_path])

        ext_audio_enabled = getattr(tracks, 'external_audio_enabled', False)
        ext_audio_path = getattr(tracks, 'external_audio_path', '')
        if ext_audio_enabled and ext_audio_path and os.path.exists(ext_audio_path):
            cmd.extend(["-i", ext_audio_path])
        else:
            ext_audio_enabled = False
        self._external_audio = ext_audio_enabled

        # ── Extra: Image overlay inputs ──
        extra = self.app_state.extra
        self._extra_img_count = 0
        for item in extra.image_overlays:
            if item.enabled and item.image_path and os.path.exists(item.image_path):
                cmd.extend(["-i", item.image_path])
                self._extra_img_count += 1

        # ── Extra: Audio track addition ──
        self._extra_audio_path = ""
        if extra.add_audio_track and extra.audio_track_path and os.path.exists(extra.audio_track_path):
            self._extra_audio_path = extra.audio_track_path
            cmd.extend(["-i", extra.audio_track_path])

        if start_time and float(start_time) == 0:
            cmd.extend(["-ss", start_time])
        if duration:
            cmd.extend(["-t", duration])

        video_mode = getattr(encoding, 'video_mode', 'encode')
        if video_mode == "copy":
            cmd.extend(["-c:v", "copy"])
        else:
            cmd.extend(["-c:v", encoder])
            bitrate_is_set = encoding.use_original_bitrate or (
                encoding.target_bitrate and encoding.target_bitrate.isdigit() and int(encoding.target_bitrate) > 0
            )
            if encoding.use_gpu and "nvenc" in encoder:
                cmd.extend(["-preset", encoding.gpu_preset])
                if not bitrate_is_set:
                    cmd.extend(["-cq", str(encoding.cq)])
            else:
                if encoder == "mpeg2video":
                    if not bitrate_is_set:
                        cmd.extend(["-b:v", "6000k"])
                else:
                    if not bitrate_is_set:
                        cmd.extend(["-crf", str(encoding.cq)])
                    cmd.extend(["-preset", encoding.cpu_preset])
                    if encoding.cpu_tune != "none":
                        cmd.extend(["-tune", encoding.cpu_tune])
            if encoding.resolution != "none" and encoding.scale_mode == "off":
                res_value = encoding.custom_resolution if encoding.resolution == "Custom" else encoding.resolution
                ar_enabled = getattr(filters, 'ar_convert_enabled', False)
                if not ar_enabled:
                    cmd.extend(["-s", res_value])
            cmd.extend(["-r", encoding.framerate])
            if encoder == "libx265":
                cmd.extend(["-x265-params", "keyint=144:min-keyint=144:bframes=0:level=4.0"])
            elif encoder == "mpeg2video":
                cmd.extend(["-g", encoding.gop_size])
                cmd.extend(["-bf", encoding.bframes])
            else:
                cmd.extend(["-g", encoding.gop_size])
                cmd.extend(["-bf", encoding.bframes])
            pix_fmt = getattr(encoding, 'pixel_format', 'yuv420p')
            if not (encoding.use_gpu and "nvenc" in encoder and pix_fmt == "yuv420p"):
                cmd.extend(["-pix_fmt", pix_fmt])
            if encoder == "libx265":
                cmd.extend(["-profile:v", "main"])
            elif encoder == "mpeg2video":
                cmd.extend(["-profile:v", encoding.profile])
            else:
                cmd.extend(["-profile:v", encoding.profile])
                cmd.extend(["-level:v", encoding.level])
            cmd.extend(["-force_key_frames:v", "0"])
            if encoding.use_original_bitrate:
                orig_br = self.get_video_bitrate(input_path)
                if orig_br:
                    cmd.extend(["-b:v", f"{orig_br}k"])
                    if encoding.use_max_bitrate:
                        cmd.extend(["-maxrate", f"{encoding.max_bitrate}k"])
                        cmd.extend(["-bufsize", f"{encoding.max_bitrate * 2}k"])
                    else:
                        cmd.extend(["-maxrate", f"{orig_br}k"])
                        cmd.extend(["-bufsize", f"{orig_br * 2}k"])
            else:
                target_br = encoding.target_bitrate
                if target_br and target_br.isdigit():
                    target_br_int = int(target_br)
                    cmd.extend(["-b:v", f"{target_br_int}k"])
                    if encoding.use_max_bitrate:
                        cmd.extend(["-maxrate", f"{encoding.max_bitrate}k"])
                        cmd.extend(["-bufsize", f"{encoding.max_bitrate * 2}k"])
                    else:
                        cmd.extend(["-maxrate", f"{target_br_int}k"])
                        cmd.extend(["-bufsize", f"{target_br_int * 2}k"])

        if tracks.video_selected:
            video_stream_idx = tracks.video_stream_index
            if video_stream_idx is None or video_stream_idx < 0:
                video_stream_idx = 0
            cmd.extend(["-map", f"0:v:{video_stream_idx}"])

        audio_mode = getattr(encoding, 'audio_mode', 'encode')
        audio_copy = (audio_mode == "copy") or tracks.audio_copy_mode
        use_external = (self._external_audio and tracks.audio_selected and getattr(tracks, 'external_audio_path', ''))
        use_extra_audio = bool(self._extra_audio_path)
        self._extra_audio_mix = False

        # extra audio is added as the last extra input (after images)
        extra_audio_ix = 1 + (1 if use_external else 0) + self._extra_img_count

        if use_extra_audio:
            mix_mode = extra.audio_mix_mode
            if mix_mode == "replace":
                cmd.extend(["-map", f"{extra_audio_ix}:a"])
                ext = os.path.splitext(self._extra_audio_path)[1].lower()
                if ext in ['.mp3', '.aac', '.ac3', '.m4a', '.flac', '.ogg', '.wav']:
                    cmd.extend(["-c:a", "copy"])
                else:
                    cmd.extend(["-c:a", self._audio_codec(), "-b:a", "128k", "-ar", encoding.audio_sample_rate, *self._audio_channels_args()])
            elif mix_mode == "mix":
                audio_stream_idx = tracks.audio_stream_index
                if audio_stream_idx is None or audio_stream_idx < 0:
                    audio_stream_idx = 0
                cmd.extend(["-map", f"0:a:{audio_stream_idx}"])
                cmd.extend(["-map", f"{extra_audio_ix}:a"])
                self._extra_audio_mix = True
                cmd.extend(["-c:a", self._audio_codec(), "-b:a", "256k", "-ar", encoding.audio_sample_rate, *self._audio_channels_args()])
            else:  # add_track
                if tracks.audio_selected:
                    audio_stream_idx = tracks.audio_stream_index
                    if audio_stream_idx is None or audio_stream_idx < 0:
                        audio_stream_idx = 0
                    cmd.extend(["-map", f"0:a:{audio_stream_idx}"])
                cmd.extend(["-map", f"{extra_audio_ix}:a"])
                ext = os.path.splitext(self._extra_audio_path)[1].lower()
                if ext in ['.mp3', '.aac', '.ac3', '.m4a', '.flac', '.ogg', '.wav']:
                    cmd.extend(["-c:a", "copy"])
                else:
                    cmd.extend(["-c:a", self._audio_codec(), "-b:a", "128k", "-ar", encoding.audio_sample_rate, *self._audio_channels_args()])
        elif use_external:
            cmd.extend(["-map", "1:a"])
            if audio_copy:
                ext_path = tracks.external_audio_path
                ext = os.path.splitext(ext_path)[1].lower()
                if ext in ['.mp3', '.aac', '.ac3', '.m4a', '.flac', '.ogg', '.wav']:
                    cmd.extend(["-c:a", "copy"])
                else:
                    cmd.extend(["-c:a", self._audio_codec(), "-b:a", "128k", "-ar", encoding.audio_sample_rate, *self._audio_channels_args()])
            else:
                cmd.extend(["-c:a", self._audio_codec(), "-b:a", "128k", "-ar", encoding.audio_sample_rate, *self._audio_channels_args()])
            cmd.extend(["-shortest"])
        elif tracks.audio_selected:
            audio_stream_idx = tracks.audio_stream_index
            if audio_stream_idx is None or audio_stream_idx < 0:
                audio_stream_idx = 0
            cmd.extend(["-map", f"0:a:{audio_stream_idx}"])
            if audio_copy:
                cmd.extend(["-c:a", "copy"])
            else:
                cmd.extend(["-c:a", self._audio_codec(), "-b:a", "128k", "-ar", encoding.audio_sample_rate, *self._audio_channels_args()])
        else:
            cmd.extend(["-an"])
            audio_copy = True

        video_filters_str, audio_filters_str = self.build_filter_string(self.app_state)

        # Subtitle burning (text subtitles)
        skip_vf = (video_mode == "copy")
        sub_path = None
        if subtitles.burn_subs:
            if skip_vf:
                self.app_state.log(
                    "Cannot burn subtitles with video stream copy mode. "
                    "Switch video mode to 'Encode' for subtitle burning.", "WARN")
            else:
                sub_path = self.find_subtitle_file(input_path)
        burn_dvd_subs = subtitles.burn_subs and is_dvd_source and dvd.selected_subtitle_index >= 0
        if burn_dvd_subs:
            sub_path = None  # DVD subs handled by HandBrake fallback in controller

        # ── Build the full video filter string (may include subtitles + drawtext) ──
        full_vf_str = video_filters_str
        if sub_path:
            subs_filter = self.build_subtitle_filter(sub_path)
            # When seeking, PTS is shifted to 0 by accurate input seeking.
            # Restore original PTS before subtitle filter so it looks up correct subs,
            # then reset to 0 for the output.
            seeking = start_time and float(start_time) > 0
            if seeking:
                subs_filter = (
                    f"setpts=PTS+{float(start_time)}/TB,"
                    f"{subs_filter}"
                    f",setpts=PTS-STARTPTS"
                )
            if full_vf_str:
                full_vf_str = f"{full_vf_str},{subs_filter}"
            else:
                full_vf_str = subs_filter

        # ── Extra: Image overlays (filter_complex) ──
        overlay_fc, num_overlays, last_label = self._build_overlay_filter_complex(extra, full_vf_str)
        if overlay_fc and num_overlays > 0:
            cmd.extend(["-filter_complex", overlay_fc])
            cmd.extend(["-map", f"[{last_label}]"])
            if sub_path:
                cmd.extend(["-map", "-0:s"])
        elif sub_path:
            cmd.extend(["-vf", full_vf_str])
            cmd.extend(["-map", "-0:s"])
        elif full_vf_str:
            cmd.extend(["-vf", full_vf_str])

        # ── Extra: Audio mix from extra audio track ──
        if getattr(self, '_extra_audio_mix', False):
            audio_stream_idx = tracks.audio_stream_index
            if audio_stream_idx is None or audio_stream_idx < 0:
                audio_stream_idx = 0
            if overlay_fc:
                self.app_state.log("Audio mixing with image overlays not supported in this version. Skipping audio mix.", "WARN")
                self._extra_audio_mix = False
            else:
                audio_mix_fc = (
                    f"[0:a:{audio_stream_idx}][{extra_audio_ix}:a]"
                    f"amix=inputs=2:duration=first[outa]"
                )
                cmd.extend(["-filter_complex", audio_mix_fc])
                cmd.extend(["-map", "[outa]"])

        if audio_filters_str and not audio_copy and not self._extra_audio_mix:
            cmd.extend(["-af", audio_filters_str])

        cmd.extend(["-y", output_path])
        return cmd

    def _save_command_log(self, output_path: str, cmd: list):
        log_path = output_path + ".log"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] Command: {' '.join(cmd)}\n"
        with open(log_path, "a") as f:
            f.write(entry)

    def encode(self, input_path: str, output_path: str,
               app_state, start_time=None, duration=None) -> subprocess.Popen:
        cmd = self.build_command(input_path, output_path, start_time, duration)
        self.app_state.log(f"Command: {' '.join(cmd)}", "INFO")
        self._save_command_log(output_path, cmd)
        return subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, bufsize=1
        )

    def fast_cut(self, input_path: str, output_path: str,
                 start_time: Optional[str] = None,
                 duration: Optional[str] = None) -> subprocess.Popen:
        is_dvd_source = input_path.endswith('.txt') and self.app_state.dvd.is_dvd_source
        dvd_concat_input = self._get_dvd_concat_input() if is_dvd_source else None
        cmd = [self.app_state.ffmpeg_path]
        if start_time:
            cmd.extend(["-ss", start_time])
        cmd.extend(["-i", dvd_concat_input if dvd_concat_input else input_path])
        if duration:
            cmd.extend(["-t", duration])
        cmd.extend(["-c:v", "copy"])

        tracks = self.app_state.tracks
        ext_audio_enabled = getattr(tracks, 'external_audio_enabled', False)
        ext_audio_path = getattr(tracks, 'external_audio_path', '')
        has_ext_audio = ext_audio_enabled and ext_audio_path and os.path.exists(ext_audio_path)
        if has_ext_audio:
            cmd.extend(["-i", ext_audio_path])

        if tracks.video_selected:
            video_stream_idx = tracks.video_stream_index
            if video_stream_idx is None or video_stream_idx < 0:
                video_stream_idx = 0
            cmd.extend(["-map", f"0:v:{video_stream_idx}"])

        if tracks.audio_selected:
            if has_ext_audio:
                cmd.extend(["-map", "1:a"])
                ext = os.path.splitext(ext_audio_path)[1].lower()
                if ext in ['.mp3', '.mp2']:
                    cmd.extend(["-c:a", "copy"])
                elif ext == '.wav':
                    cmd.extend(["-c:a", "pcm_s16le"])
                elif ext == '.flac':
                    cmd.extend(["-c:a", "copy"])
                else:
                    cmd.extend(["-c:a", self._audio_codec(), "-b:a", "128k", "-ar", encoding.audio_sample_rate, *self._audio_channels_args()])
            else:
                audio_stream_idx = tracks.audio_stream_index
                cmd.extend(["-map", f"0:a:{audio_stream_idx}"])
                audio_mode = getattr(self.app_state.encoding, 'audio_mode', 'encode')
                audio_copy = (audio_mode == 'copy') or tracks.audio_copy_mode
                if audio_copy:
                    cmd.extend(["-c:a", "copy"])
                else:
                    cmd.extend(["-c:a", self._audio_codec(), "-b:a", "128k", "-ar", encoding.audio_sample_rate, *self._audio_channels_args()])
        else:
            cmd.extend(["-an"])

        cmd.extend(["-y", output_path])
        self.app_state.log(f"Command: {' '.join(cmd)}", "INFO")
        self._save_command_log(output_path, cmd)
        return subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, bufsize=1
        )

    def join_segments(self, input_path: str, output_path: str,
                      segments: list, video_settings: dict, audio_settings: dict) -> subprocess.Popen:
        cmd = [self.app_state.ffmpeg_path]
        for seg_start, seg_end in segments:
            seg_dur = seg_end - seg_start
            cmd.extend(["-ss", str(seg_start), "-t", str(seg_dur), "-i", input_path])

        filter_parts = []
        for i in range(len(segments)):
            filter_parts.append(f"[{i}:v]")
            filter_parts.append(f"[{i}:a]")
        filter_complex = f"{''.join(filter_parts)}concat=n={len(segments)}:v=1:a=1[outv][outa]"
        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "[outv]"])
        cmd.extend(["-map", "[outa]"])
        cmd.extend(["-c:v", video_settings.get("codec", "libx264")])
        cmd.extend(["-crf", str(video_settings.get("crf", 23))])
        cmd.extend(["-preset", video_settings.get("preset", "medium")])
        cmd.extend(["-c:a", audio_settings.get("codec", self._audio_codec())])
        cmd.extend(["-b:a", audio_settings.get("bitrate", "128k")])
        cmd.extend(["-y", output_path])
        self.app_state.log(f"Command: {' '.join(cmd)}", "INFO")
        self._save_command_log(output_path, cmd)
        return subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, bufsize=1
        )

    def align_to_keyframe(self, video_path: str, target_time: float) -> float:
        ffprobe_path = self._get_ffprobe_path()
        try:
            cmd = [
                ffprobe_path, "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "frame=pts_time",
                "-of", "csv=p=0",
                "-skip_frame", "nokey", video_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            if result.returncode == 0 and result.stdout:
                keyframe_times = []
                for line in result.stdout.split('\n'):
                    try:
                        keyframe_times.append(float(line.strip()))
                    except ValueError:
                        continue
                if keyframe_times:
                    return min(keyframe_times, key=lambda t: abs(t - target_time))
        except Exception:
            pass
        return target_time

    def extract_track(self, video_path: str, track_info: dict, output_folder: str) -> Optional[str]:
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        track_type = track_info['type']
        track_idx = track_info['index']

        if track_type == 'video':
            output_filename = f"{base_name}_video_track{track_idx}.mkv"
            cmd = [
                self.app_state.ffmpeg_path, "-y",
                "-i", video_path,
                "-map", f"0:v:{track_info['video_index']}",
                "-c", "copy",
                os.path.join(output_folder, output_filename)
            ]
        else:
            cmd_probe = [
                self._get_ffprobe_path(), "-v", "error",
                "-select_streams", f"a:{track_info['audio_index']}",
                "-show_entries", "stream=codec_name",
                "-of", "json", video_path
            ]
            codec = 'aac'
            try:
                r = subprocess.run(cmd_probe, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
                if r.returncode == 0:
                    data = json.loads(r.stdout)
                    streams = data.get('streams', [])
                    if streams:
                        codec = streams[0].get('codec_name', 'aac').lower()
            except Exception:
                pass

            codec_ext = {
                'aac': '.aac', 'mp3': '.mp3', 'ac3': '.ac3', 'dts': '.dts',
                'flac': '.flac', 'ogg': '.ogg', 'opus': '.opus',
                'wav': '.wav', 'pcm_s16le': '.wav'
            }
            output_ext = codec_ext.get(codec, '.aac')
            output_filename = f"{base_name}_audio_track{track_idx}{output_ext}"
            cmd = [
                self.app_state.ffmpeg_path, "-y",
                "-i", video_path,
                "-map", f"0:a:{track_info['audio_index']}",
                "-c", "copy",
                os.path.join(output_folder, output_filename)
            ]

        output_path = os.path.join(output_folder, output_filename)
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
            if result.returncode == 0 and os.path.exists(output_path):
                return output_path
        except Exception:
            pass
        return None

    def extract_subtitle_streams(self, video_path: str) -> List[dict]:
        ffprobe_path = self._get_ffprobe_path()
        cmd = [
            ffprobe_path, "-v", "error",
            "-show_entries", "stream=index,codec_type,codec_name:stream_tags=language",
            "-of", "json", video_path
        ]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return [s for s in data.get('streams', []) if s.get('codec_type') == 'subtitle']
        except Exception:
            pass
        return []

    def get_streams(self, video_path: str) -> dict:
        ffprobe_path = self._get_ffprobe_path()
        is_dvd_concat = video_path.endswith('.txt') and self.app_state.dvd.is_dvd_source
        dvd_concat_input = self._get_dvd_concat_input() if is_dvd_concat else None
        cmd = [ffprobe_path, "-v", "error"]
        if dvd_concat_input:
            cmd.extend(["-f", "mpeg"])
            cmd.extend(["-i", dvd_concat_input])
        else:
            cmd.extend(["-i", video_path])
        cmd.extend([
            "-show_entries", "stream=index,codec_type,codec_name,width,height,channels,sample_rate,display_aspect_ratio:stream_tags=language,title",
            "-of", "json"
        ])
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            if result.returncode == 0:
                return json.loads(result.stdout)
        except Exception:
            pass
        return {'streams': []}

    def get_external_audio_info(self, file_path: str) -> Optional[dict]:
        ffprobe_path = self._get_ffprobe_path()
        cmd = [
            ffprobe_path, "-v", "error",
            "-show_entries", "stream=index,codec_name,codec_type,channels,sample_rate:format=duration",
            "-of", "json", file_path
        ]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                for stream in data.get('streams', []):
                    if stream.get('codec_type') == 'audio':
                        info = {
                            'codec': stream.get('codec_name', 'unknown'),
                            'channels': stream.get('channels', 0),
                            'sample_rate': stream.get('sample_rate', '')
                        }
                        if data.get('format') and data['format'].get('duration'):
                            d = float(data['format']['duration'])
                            mins, secs = divmod(int(d), 60)
                            hours, mins = divmod(mins, 60)
                            if hours > 0:
                                info['duration'] = f"{hours}:{mins:02d}:{secs:02d}"
                            else:
                                info['duration'] = f"{mins}:{secs:02d}"
                        return info
        except Exception:
            pass
        return None

    # ── AI Upscaling Pipeline ──────────────────────────────────────

    def get_fps(self, input_path: str) -> float:
        ffprobe_path = self._get_ffprobe_path()
        try:
            cmd = [
                ffprobe_path, "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=r_frame_rate",
                "-of", "default=noprint_wrappers=1:nokey=1",
                input_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, timeout=30)
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split('/')
                if len(parts) == 2:
                    num, den = float(parts[0]), float(parts[1])
                    if den > 0:
                        return num / den
                return float(parts[0])
        except Exception:
            pass
        return 24000 / 1001  # fallback

    def extract_frames(self, input_path: str, frames_dir: str,
                       part_duration_min: int, fps: float,
                       progress_callback=None) -> bool:
        import math
        import os

        os.makedirs(frames_dir, exist_ok=True)
        duration = self.get_duration(input_path)
        part_sec = part_duration_min * 60
        total_parts = max(1, math.ceil(duration / part_sec))

        ffmpeg_path = self.app_state.ffmpeg_path

        for part_idx in range(total_parts):
            start = part_idx * part_sec
            end = min(start + part_sec, duration)
            part_label = f"{part_idx + 1:03d}_{int(start // 60)}m-{int(end // 60)}m"
            part_dir = os.path.join(frames_dir, part_label)

            if os.path.isdir(part_dir) and os.listdir(part_dir):
                continue

            os.makedirs(part_dir, exist_ok=True)
            output_pattern = os.path.join(part_dir, "frame_%08d.png")
            part_dur = part_sec if end == start + part_sec else duration - start

            cmd = [
                ffmpeg_path, "-y",
                "-ss", str(start),
                "-i", input_path,
                "-t", str(part_dur),
                "-q:v", "2",
                "-vf", f"fps={fps}",
                "-pix_fmt", "rgb24",
                output_pattern
            ]

            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                proc.wait()
                if proc.returncode != 0:
                    self.app_state.log(f"Extract failed {part_label}: {proc.stderr.read()[:200]}", "ERROR")
                    return False
            except Exception as e:
                self.app_state.log(f"Extract error {part_label}: {e}", "ERROR")
                return False

            if progress_callback:
                progress_callback(int((part_idx + 1) / total_parts * 100))

        return True

    def _resolve_upscaler_binary(self, upscaler: str) -> str:
        import os
        from config import REALESRGAN_NCNN, ANIME4K_NCNN

        if upscaler == "realesrgan":
            return self.app_state.realesrgan_path or REALESRGAN_NCNN
        elif upscaler == "anime4k":
            return self.app_state.anime4k_path or ANIME4K_NCNN
        return ""

    def upscale_frames(self, frames_dir: str, upscaler: str,
                       model: str, scale: int, tile_size: int,
                       progress_callback=None) -> bool:
        import os

        self.cancel_upscale = False

        binary = self._resolve_upscaler_binary(upscaler)
        if not binary or not os.path.isfile(binary):
            self.app_state.log(f"Upscaler binary not found: {binary}", "ERROR")
            return False
        if not os.access(binary, os.X_OK):
            self.app_state.log(f"Upscaler binary is not executable: {binary}. Run 'chmod +x \"{binary}\"' to fix.", "ERROR")
            return False

        model_dir = os.path.join(os.path.dirname(binary), "models")
        model_bin = os.path.join(model_dir, f"{model}.bin")
        if not os.path.isfile(model_bin):
            self.app_state.log(f"Model not found: {model_bin}. Check your model selection in AI Upscaling settings.", "ERROR")
            return False

        part_dirs = self.get_part_dirs(frames_dir)
        if not part_dirs:
            self.app_state.log("No parts found to upscale. Extract frames first.", "ERROR")
            return False

        processed = 0
        for part in part_dirs:
            if self.cancel_upscale:
                self.app_state.log("Upscaling cancelled", "WARN")
                return False

            src_dir = os.path.join(frames_dir, part)
            out_dir = os.path.join(frames_dir, f"{part}_{upscaler}.png")
            if os.path.isdir(out_dir) and os.listdir(out_dir):
                processed += 1
                continue

            os.makedirs(out_dir, exist_ok=True)

            cmd = [
                binary,
                "-i", src_dir,
                "-o", out_dir,
                "-s", str(scale),
                "-n", model,
                "-m", model_dir,
            ]
            if tile_size > 0:
                cmd.extend(["-t", str(tile_size)])
            cmd.extend(["-g", "0", "-f", "png"])

            self.app_state.log(f"Upscaling part {part}...", "INFO")

            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                self._current_upscale_proc = proc

                for line in iter(proc.stderr.readline, ''):
                    if self.cancel_upscale:
                        proc.terminate()
                        self.app_state.log("Upscaling cancelled", "WARN")
                        return False
                    line = line.strip()
                    if line and "%" in line and not line.startswith("["):
                        self.app_state.log(f"📷 {part}: {line}", "INFO")

                proc.wait()
                if proc.returncode != 0:
                    self.app_state.log(f"Upscale failed {part}", "ERROR")
                    return False
            except Exception as e:
                self.app_state.log(f"Upscale error {part}: {e}", "ERROR")
                return False
            finally:
                self._current_upscale_proc = None

            processed += 1
            if progress_callback:
                progress_callback(int(processed / len(part_dirs) * 100))

        return True

    def recombine_frames(self, frames_dir: str, output_path: str,
                         fps: float, progress_callback=None) -> bool:
        import os

        ffmpeg_path = self.app_state.ffmpeg_path
        tmp_parts = []
        upscaler_suffix = None

        for d in os.listdir(frames_dir):
            if d.endswith("_realesrgan.png") or d.endswith("_anime4k.png"):
                upscaler_suffix = d.rsplit("_", 1)[1]
                break

        if not upscaler_suffix:
            self.app_state.log("No upscaled frame directories found", "ERROR")
            return False

        part_dirs = sorted([
            d for d in os.listdir(frames_dir)
            if d.endswith(f"_{upscaler_suffix}")
        ])

        total = len(part_dirs)
        for idx, part in enumerate(part_dirs):
            src_dir = os.path.join(frames_dir, part)
            tmp_mp4 = os.path.join(frames_dir, f"tmp_{part}.mp4")
            tmp_parts.append(tmp_mp4)

            if os.path.isfile(tmp_mp4):
                continue

            input_pattern = os.path.join(src_dir, "frame_%08d.png")
            cmd = [
                ffmpeg_path, "-y",
                "-framerate", str(fps),
                "-i", input_pattern,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "fast",
                "-crf", "18",
                tmp_mp4
            ]

            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                proc.wait()
                if proc.returncode != 0:
                    self.app_state.log(f"Recombine failed {part}: {proc.stderr.read()[:200]}", "ERROR")
                    return False
            except Exception as e:
                self.app_state.log(f"Recombine error {part}: {e}", "ERROR")
                return False

            if progress_callback:
                progress_callback(int((idx + 1) / total * 100))

        concat_file = os.path.join(frames_dir, "concat_list.txt")
        try:
            with open(concat_file, "w") as f:
                for tmp_mp4 in tmp_parts:
                    if os.path.isfile(tmp_mp4):
                        f.write(f"file '{tmp_mp4}'\n")

            cmd = [
                ffmpeg_path, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-c", "copy",
                output_path
            ]
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            proc.wait()
            if proc.returncode != 0:
                self.app_state.log(f"Concat failed: {proc.stderr.read()[:200]}", "ERROR")
                return False
        except Exception as e:
            self.app_state.log(f"Concat error: {e}", "ERROR")
            return False
        finally:
            for tmp_mp4 in tmp_parts:
                try:
                    os.remove(tmp_mp4)
                except OSError:
                    pass
            try:
                os.remove(concat_file)
            except OSError:
                pass

        return True

    def get_part_dirs(self, frames_dir: str) -> list:
        import os
        if not os.path.isdir(frames_dir):
            return []
        return sorted([
            d for d in os.listdir(frames_dir)
            if os.path.isdir(os.path.join(frames_dir, d))
            and not d.endswith("_realesrgan.png")
            and not d.endswith("_anime4k.png")
            and not d.startswith("tmp_")
        ])

    def get_upscaled_part_dirs(self, frames_dir: str) -> list:
        import os
        if not os.path.isdir(frames_dir):
            return []
        return sorted([
            d for d in os.listdir(frames_dir)
            if os.path.isdir(os.path.join(frames_dir, d))
            and (d.endswith("_realesrgan.png") or d.endswith("_anime4k.png"))
        ])
