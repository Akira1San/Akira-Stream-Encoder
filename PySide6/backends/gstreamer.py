"""
GStreamer CLI Backend - Implements MediaBackend using gst-launch-1.0 / gst-discoverer-1.0

Known limitations (logged as warnings; switch to FFmpeg to resolve):
- DVD VOB concat files (ffmpeg concat demuxer format)
- Trim/clip extraction (start_time/duration not supported by gst-launch)
- Fast cut (stream copy not supported by GStreamer)
- Subtitle burning (DVD via dvdspu+dvdsubdec, SRT/ASS via subparse+textoverlay)
- Various filters: delogo, sharpen, CAS, deblock, deblock, audio denoise, dynaudnorm, audio compressor, white balance
"""
import os
import re
import subprocess
from typing import Optional, List

from backends.base import MediaBackend


class GStreamerBackend(MediaBackend):
    """Media backend using GStreamer CLI tools"""

    def __init__(self, app_state):
        self.app_state = app_state
        self._gst_path = "gst-launch-1.0"
        self._discoverer_path = "gst-discoverer-1.0"

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _log_unsupported(self, feature: str):
        self.app_state.log(
            f"[GStreamer] '{feature}' not yet implemented. Switch to FFmpeg engine.",
            "WARN"
        )

    def _is_dvd_concat(self, input_path: str) -> bool:
        return input_path.endswith('.txt') and self.app_state.dvd.is_dvd_source

    def _read_concat_vobs(self, input_path: str) -> list:
        """Extract VOB file paths from an ffmpeg concat file."""
        vobs = []
        try:
            with open(input_path) as f:
                for line in f:
                    m = re.match(r"file\s+'(.+)'", line.strip())
                    if m:
                        vobs.append(m.group(1))
        except Exception:
            pass
        return vobs

    def _vob_path_or_input(self, input_path: str) -> str:
        """If input is a DVD concat file, return the first VOB path instead."""
        if self._is_dvd_concat(input_path):
            vobs = self._read_concat_vobs(input_path)
            if vobs:
                return vobs[0]
        return input_path

    def _run_discoverer(self, input_path: str) -> str:
        probe_path = self._vob_path_or_input(input_path)
        cmd = [self._discoverer_path, probe_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        return result.stdout

    def _parse_discoverer_output(self, text: str) -> dict:
        info = {'duration_ns': 0, 'container': '', 'streams': []}
        dur_match = re.search(r'Duration:\s*(\d+):(\d+):(\d+)\.(\d+)', text)
        if dur_match:
            h, m, s, ns = map(int, dur_match.groups())
            info['duration_ns'] = ((h * 3600 + m * 60 + s) * 1000000000) + ns * 1000000
        container_match = re.search(r'container\s+#\d+:\s*(.+)', text)
        if container_match:
            info['container'] = container_match.group(1).strip()
        current = None
        for line in text.split('\n'):
            m = re.match(r'\s+(video|audio|subtitle)\s+#(\d+):\s*(.+)', line)
            if m:
                if current:
                    info['streams'].append(current)
                current = {
                    'type': m.group(1), 'id': int(m.group(2)),
                    'codec': m.group(3).strip(), 'width': 0, 'height': 0,
                    'channels': 0, 'sample_rate': '', 'bitrate': 0, 'language': ''
                }
                continue
            if current is None:
                continue
            for pattern, key, cast in [
                (r'\s+Width:\s+(\d+)', 'width', int),
                (r'\s+Height:\s+(\d+)', 'height', int),
                (r'\s+Channels:\s+(\d+)', 'channels', int),
                (r'\s+Sample rate:\s+(\d+)', 'sample_rate', str),
                (r'\s+Bitrate:\s+(\d+)', 'bitrate', int),
                (r'\s+Language:\s+(.+)', 'language', str),
            ]:
                vm = re.match(pattern, line)
                if vm:
                    current[key] = cast(vm.group(1))
                    break
        if current:
            info['streams'].append(current)
        return info

    # ------------------------------------------------------------------ #
    #  Probe methods
    # ------------------------------------------------------------------ #

    def get_duration(self, input_path: str) -> float:
        try:
            text = self._run_discoverer(input_path)
            info = self._parse_discoverer_output(text)
            if info['duration_ns'] > 0:
                return info['duration_ns'] / 1e9
        except Exception as e:
            self.app_state.log(f"GStreamer duration detection failed: {e}", "WARN")
        return 0.0

    def get_audio_tracks(self, input_path: str) -> List[dict]:
        tracks = []
        try:
            text = self._run_discoverer(input_path)
            info = self._parse_discoverer_output(text)
            for s in info['streams']:
                if s['type'] == 'audio':
                    tracks.append({
                        'index': s['id'],
                        'codec': s['codec'],
                        'channels': s['channels'],
                        'sample_rate': s['sample_rate'],
                        'language': s['language'],
                        'title': ''
                    })
        except Exception as e:
            self.app_state.log(f"GStreamer audio track detection failed: {e}", "WARN")
        return tracks

    def get_video_bitrate(self, input_path: str) -> Optional[int]:
        try:
            text = self._run_discoverer(input_path)
            info = self._parse_discoverer_output(text)
            for s in info['streams']:
                if s['type'] == 'video' and s['bitrate'] > 0:
                    return s['bitrate'] // 1000
        except Exception:
            pass
        return None

    def get_file_info(self, input_path: str) -> dict:
        info = {}
        try:
            text = self._run_discoverer(input_path)
        except Exception:
            return info
        dur_match = re.search(r'Duration:\s+(\d+:\d+:\d+\.\d+)', text)
        if dur_match:
            info['duration'] = dur_match.group(1)
        for s in self._parse_discoverer_output(text).get('streams', []):
            if s['type'] == 'video':
                info['codec'] = s['codec']
                info['resolution'] = f"{s['width']}x{s['height']}"
                break
        return info

    def extract_subtitle(self, input_path: str, stream_idx: int, output_path: str) -> Optional[str]:
        self._log_unsupported("Subtitle extraction")
        return None

    def validate(self, input_path: str) -> dict:
        result = {'is_valid': True, 'issues': [], 'stderr': ''}
        try:
            r = subprocess.run([self._gst_path, "--version"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            if r.returncode != 0:
                result['is_valid'] = False
                result['issues'].append("GStreamer not available")
                return result
            text = self._run_discoverer(input_path)
            if "error" in text.lower() or not text:
                result['is_valid'] = False
                result['issues'].append("Failed to discover file")
                result['stderr'] = text[:500]
        except Exception as e:
            result['is_valid'] = False
            result['issues'].append(str(e))
        return result

    # ------------------------------------------------------------------ #
    #  Filter string (unused in GStreamer mode; placeholder)
    # ------------------------------------------------------------------ #

    def build_filter_string(self, app_state) -> tuple:
        return ("", "")

    # ------------------------------------------------------------------ #
    #  Pipeline construction
    # ------------------------------------------------------------------ #

    def _build_video_encoder(self, encoding) -> List[str]:
        encoder = encoding.encoder.lower()
        params = []

        if "nvenc" in encoder:
            if "h265" in encoder or "hevc" in encoder:
                params.append("nvh265enc")
            else:
                params.append("nvh264enc")
            if encoding.use_original_bitrate or (encoding.target_bitrate and encoding.target_bitrate.isdigit()):
                br = self.get_video_bitrate(self.app_state.current_video_path or "")
                if not br:
                    br = int(encoding.target_bitrate) if encoding.target_bitrate and encoding.target_bitrate.isdigit() else 2000
                params.append(f"bitrate={br}")
            else:
                params.append(f"const-quality={encoding.cq}")
            params.append(f"preset={encoding.gpu_preset}")
            params.append("gop-size=144")
            if encoding.profile:
                params.append(f"profile={encoding.profile}")
        else:
            if "x265" in encoder:
                params.append("x265enc")
            else:
                params.append("x264enc")
            if encoding.use_original_bitrate or (encoding.target_bitrate and encoding.target_bitrate.isdigit()):
                br = self.get_video_bitrate(self.app_state.current_video_path or "")
                if not br:
                    br = int(encoding.target_bitrate) if encoding.target_bitrate and encoding.target_bitrate.isdigit() else 2000
                params.append(f"bitrate={br}")
            else:
                params.append(f"quantizer={encoding.cq}")
            params.append(f"speed-preset={encoding.cpu_preset}")
            if encoding.cpu_tune != "none":
                tune_flags = {"film": 1, "animation": 2, "grain": 4, "stillimage": 8,
                              "psnr": 16, "ssim": 32, "fastdecode": 64, "zerolatency": 128}
                flag = tune_flags.get(encoding.cpu_tune, 0)
                if flag:
                    params.append(f"tune={flag}")
            params.append("key-int-max=144")
            params.append("bframes=0")
            params.append("byte-stream=true")

        return params

    def _build_video_filters(self) -> List[str]:
        elements = []
        filters = self.app_state.filters
        encoding = self.app_state.encoding
        eq = self.app_state.eq

        if filters.deinterlace:
            elements.append("deinterlace")

        if encoding.scale_mode == "on" and encoding.resolution and encoding.resolution != "none":
            if "x" in encoding.resolution:
                w, h = encoding.resolution.split("x")
                elements.append("videoscale")
                elements.append(f"video/x-raw,width={w},height={h}")

        if getattr(filters, 'smart_crop_enabled', False):
            elements.append("videocrop")
            # Note: videocrop crops from edges (top/left/right/bottom pixels)
            # This maps FFmpeg crop=w:h:x:y to GStreamer crop:
            #   top=y, left=x, right=source_width-x-crop_w, bottom=source_height-y-crop_h
            # Without source dimensions, we use the x/y offsets directly and crop to 0 on right/bottom
            # A more accurate mapping would need source video dimensions
            elements.append(f"top={filters.smart_crop_y}")
            elements.append(f"left={filters.smart_crop_x}")
            elements.append("right=0")
            elements.append("bottom=0")

        if getattr(filters, 'delogo_enabled', False):
            self._log_unsupported("delogo")

        if eq.enabled:
            balance_parts = []
            if eq.brightness != 0:
                balance_parts.append(f"brightness={eq.brightness}")
            if eq.contrast != 1.0:
                balance_parts.append(f"contrast={eq.contrast}")
            if eq.saturation != 1.0:
                balance_parts.append(f"saturation={eq.saturation}")
            if balance_parts:
                elements.append("videobalance")
                elements.extend(balance_parts)
            if eq.gamma != 1.0:
                elements.append("gamma")
                elements.append(f"gamma={eq.gamma}")
            if eq.white_balance_enabled:
                self._log_unsupported("white balance (colorbalance)")

        if getattr(filters, 'sharpen', False):
            self._log_unsupported("sharpen (unsharp)")

        if getattr(filters, 'cas_enabled', False):
            self._log_unsupported("CAS (contrast adaptive sharpen)")

        if getattr(filters, 'deblock', False):
            self._log_unsupported("deblock")

        if getattr(filters, 'ar_convert_enabled', False):
            self._log_unsupported("aspect ratio conversion")

        return elements

    def _build_audio_chain(self) -> List[str]:
        tracks = self.app_state.tracks
        filters = self.app_state.filters
        encoding = self.app_state.encoding

        if not tracks.audio_selected:
            return []

        audio_copy = tracks.audio_copy_mode or encoding.audio_mode == "copy"
        elements = ["queue", "decodebin", "audioconvert"]

        if filters.volume_enabled:
            vol_val = 10 ** (filters.volume_db / 20)
            elements.append("volume")
            elements.append(f"volume={vol_val:.4f}")

        if getattr(filters, 'audio_denoise', False):
            self._log_unsupported("audio denoise (afftdn)")

        if getattr(filters, 'audio_dynnorm', False):
            self._log_unsupported("dynaudnorm")

        if getattr(filters, 'audio_compressor', False):
            self._log_unsupported("audio compressor")

        if getattr(filters, 'audio_delay_enabled', False) and filters.audio_delay_ms > 0:
            self._log_unsupported("audio delay")

        if audio_copy:
            elements.append("identity")
        else:
            elements.append("voaacenc")
            elements.append("bitrate=128000")

        return elements

    def _need_dvd_subtitles(self, input_path: str) -> bool:
        dvd = self.app_state.dvd
        return (self._is_dvd_concat(input_path)
                and dvd.selected_subtitle_index >= 0
                and self.app_state.subtitles.burn_subs)

    def find_subtitle_file(self, video_path: str) -> Optional[str]:
        if not video_path:
            return None
        selected = self.app_state.subtitles.selected_subtitle
        if selected and os.path.exists(selected):
            return selected
        base = os.path.splitext(video_path)[0]
        for ext in [".srt", ".ass", ".ssa", ".sub"]:
            sub_path = base + ext
            if os.path.exists(sub_path):
                return sub_path
        return None

    def _need_text_subtitles(self, input_path: str) -> bool:
        if not self.app_state.subtitles.burn_subs:
            return False
        if self._is_dvd_concat(input_path):
            return False
        return self.find_subtitle_file(input_path) is not None

    def _build_subtitle_chain(self, sub_path: str) -> List[str]:
        return [
            "filesrc", f"location={sub_path}",
            "!", "typefind",
            "!", "subparse"
        ]

    def _build_pipeline_list(self, input_path: str, output_path: str,
                             start_time=None, duration=None) -> List[str]:
        encoding = self.app_state.encoding
        tracks = self.app_state.tracks

        muxer_map = {"mp4": "mp4mux", "mkv": "matroskamux", "avi": "avimux"}
        muxer_el = muxer_map.get(encoding.container, "mp4mux")

        video_enc = self._build_video_encoder(encoding)
        video_filters = self._build_video_filters()
        audio_chain = self._build_audio_chain()

        has_audio = len(audio_chain) > 0
        source_has_audio = False
        if has_audio:
            try:
                source_has_audio = len(self.get_audio_tracks(input_path)) > 0
            except Exception:
                source_has_audio = True
            if has_audio and not source_has_audio:
                self.app_state.log("Source has no audio; falling back to video-only pipeline", "WARN")

        use_branches = has_audio and source_has_audio
        burn_subs = self._need_dvd_subtitles(input_path)
        text_subs = self._need_text_subtitles(input_path)

        # --- DVD concat handling ---
        is_concat = self._is_dvd_concat(input_path)
        vobs = self._read_concat_vobs(input_path) if is_concat else []

        if is_concat:
            if vobs:
                self.app_state.log(f"GStreamer: using {len(vobs)} VOB file(s) directly", "INFO")
            else:
                self.app_state.log("GStreamer: empty concat file, no VOBs to process", "ERROR")
        if burn_subs:
            self.app_state.log(
                f"GStreamer: burning DVD subtitle track {self.app_state.dvd.selected_subtitle_index}", "INFO")
        if text_subs:
            sub_path = self.find_subtitle_file(input_path)
            self.app_state.log(
                f"GStreamer: burning text subtitles from {os.path.basename(sub_path) if sub_path else 'unknown'}", "INFO")

        if start_time or duration:
            self.app_state.log("[GStreamer] Trim/clip extraction not supported. "
                               "Encoding full file without trimming. Switch to FFmpeg for trim support.", "WARN")

        pipeline = [self._gst_path, "-e"]

        # Determine source + demuxer
        if is_concat and vobs:
            use_vob = True
            is_multi = len(vobs) > 1
        else:
            use_vob = False
            is_multi = False

        if use_vob:
            demuxer = "mpegpsdemux"
            vid_pad = "video_00"
            aud_pad = "audio_00"
            sub_pad = f"subpicture_{self.app_state.dvd.selected_subtitle_index:02x}"
        else:
            demuxer = "qtdemux"
            vid_pad = "video_0"
            aud_pad = "audio_0"
            sub_pad = "subtitle_0"

        if use_branches or burn_subs or text_subs:
            # Multi-branch: mux defined first, then demux + branches
            pipeline += [f"{muxer_el}", "name=mux", "!",
                         "filesink", f"location={output_path}"]

            # Source + demuxer
            if use_vob:
                if is_multi:
                    pipeline += ["concat", "name=c", "!",
                                 f"{demuxer}", "name=demux"]
                    for vob in vobs:
                        pipeline += ["filesrc", f"location={vob}", "!", "c."]
                else:
                    pipeline += ["filesrc", f"location={vobs[0]}", "!",
                                 f"{demuxer}", "name=demux"]
            else:
                pipeline += ["filesrc", f"location={input_path}", "!",
                             f"{demuxer}", "name=demux"]

            if burn_subs:
                # 3-branch: video -> dvdspu -> encoder, subpicture -> dvdsubdec -> dvdspu, audio -> encoder
                subtitle_idx = self.app_state.dvd.selected_subtitle_index
                sub_pad_name = f"subpicture_{subtitle_idx:02x}"

                # Video -> dvdspu
                pipeline += [f"demux.{vid_pad}", "!", "queue", "!", "decodebin", "!",
                             "videoconvert", "!", "queue", "!",
                             "dvdspu", "name=spu"]
                # Subpicture -> dvdsubdec -> dvdspu.subpicture
                pipeline += [f"demux.{sub_pad_name}", "!", "queue", "!",
                             "dvdsubdec", "!", "spu.subpicture"]
                # dvdspu output -> filters -> encoder -> mux
                pipeline += ["spu.", "!", "queue", "!", "videoconvert", "!", "queue", "!"]
                pipeline += video_filters
                pipeline += video_enc + ["!", "queue", "!", "mux."]
                # Audio branch
                pipeline += [f"demux.{aud_pad}", "!", "queue", "!", "decodebin", "!",
                             "audioconvert", "!", "queue", "!"]
                pipeline += audio_chain[3:]
                pipeline += ["!", "queue", "!", "mux."]
            elif text_subs:
                sub_path = self.find_subtitle_file(input_path)
                subs = self.app_state.subtitles
                font_desc = f"{subs.font} {subs.size}"

                # Video -> textoverlay
                pipeline += [f"demux.{vid_pad}", "!", "queue", "!", "decodebin", "!",
                             "videoconvert", "!", "queue", "!",
                             "textoverlay", "name=txt", f"font-desc={font_desc}"]
                if subs.position == "top":
                    pipeline.append("valignment=top")
                elif subs.position == "center":
                    pipeline.append("valignment=center")
                else:
                    pipeline.append("valignment=bottom")
                if subs.bg_opacity > 0:
                    pipeline.append("shaded-background=true")
                if subs.vertical_offset > 0:
                    pipeline.append(f"deltay={subs.vertical_offset}")

                # textoverlay output -> filters -> encoder -> mux
                pipeline += ["txt.", "!", "queue", "!", "videoconvert", "!", "queue", "!"]
                pipeline += video_filters
                pipeline += video_enc + ["!", "queue", "!", "mux."]

                # Subtitle input branch
                sub_chain = self._build_subtitle_chain(sub_path)
                pipeline += sub_chain + ["!", "queue", "!", "txt.text_sink"]

                # Audio branch (if available)
                if use_branches:
                    pipeline += [f"demux.{aud_pad}", "!", "queue", "!", "decodebin", "!",
                                 "audioconvert", "!", "queue", "!"]
                    pipeline += audio_chain[3:]
                    pipeline += ["!", "queue", "!", "mux."]
            elif use_branches:
                # 2-branch (video + audio)
                pipeline += [f"demux.{vid_pad}", "!", "queue", "!", "decodebin", "!",
                             "videoconvert", "!", "queue", "!"]
                pipeline += video_filters
                pipeline += video_enc + ["!", "queue", "!", "mux."]
                pipeline += [f"demux.{aud_pad}", "!", "queue", "!", "decodebin", "!",
                             "audioconvert", "!", "queue", "!"]
                pipeline += audio_chain[3:]
                pipeline += ["!", "queue", "!", "mux."]
        else:
            # Single branch (video only)
            if use_vob:
                if is_multi:
                    pipeline += ["concat", "name=c", "!",
                                 f"{demuxer}", "!", "queue", "!",
                                 "decodebin", "!", "videoconvert", "!", "queue", "!"]
                    for vob in vobs:
                        pipeline += ["filesrc", f"location={vob}", "!", "c."]
                else:
                    pipeline += ["filesrc", f"location={vobs[0]}", "!",
                                 f"{demuxer}", "!", "queue", "!", "decodebin", "!",
                                 "videoconvert", "!", "queue", "!"]
            else:
                pipeline += ["filesrc", f"location={input_path}", "!",
                             f"{demuxer}", "!", "queue", "!", "decodebin", "!",
                             "videoconvert", "!", "queue", "!"]
            pipeline += video_filters
            pipeline += video_enc + ["!", "queue", "!"]
            pipeline += [f"{muxer_el}", "!", "filesink", f"location={output_path}"]

        return pipeline

    # ------------------------------------------------------------------ #
    #  Encode
    # ------------------------------------------------------------------ #

    def encode(self, input_path: str, output_path: str,
               app_state, start_time=None, duration=None) -> subprocess.Popen:
        pipeline = self._build_pipeline_list(input_path, output_path, start_time, duration)
        self.app_state.log(f"GStreamer pipeline: {' '.join(pipeline)}", "INFO")
        return subprocess.Popen(
            pipeline, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, bufsize=1
        )

    # ------------------------------------------------------------------ #
    #  Stub methods needed by controller (unsupported -> log + fallback)
    # ------------------------------------------------------------------ #

    def build_command(self, input_path: str, output_path: str,
                      start_time=None, duration=None) -> List[str]:
        return self._build_pipeline_list(input_path, output_path, start_time, duration)

    def fast_cut(self, input_path: str, output_path: str,
                 start_time=None, duration=None) -> subprocess.Popen:
        self.app_state.log("[GStreamer] Stream copy (fast cut) not supported. "
                           "Falling back to full re-encode.", "WARN")
        pipeline = self._build_pipeline_list(input_path, output_path)
        return subprocess.Popen(
            pipeline, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, bufsize=1
        )

    def join_segments(self, input_path: str, output_path: str,
                      segments: list, video_settings: dict, audio_settings: dict) -> subprocess.Popen:
        self._log_unsupported("segment joining")
        cmd = [self._gst_path, "--version"]
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True, bufsize=1)

    def align_to_keyframe(self, video_path: str, target_time: float) -> float:
        self._log_unsupported("keyframe alignment")
        return target_time

    def extract_track(self, video_path: str, track_info: dict, output_folder: str) -> Optional[str]:
        self._log_unsupported("track extraction")
        return None

    def extract_subtitle_streams(self, video_path: str) -> List[dict]:
        return []

    def get_streams(self, video_path: str) -> dict:
        return {'streams': []}

    def get_external_audio_info(self, file_path: str) -> Optional[dict]:
        return None

    def hex_to_ass(self, hex_color: str, opacity: float = 1.0) -> str:
        return ""

    def build_subtitle_filter(self, sub_path: str) -> str:
        self._log_unsupported("subtitle burn-in")
        return ""
