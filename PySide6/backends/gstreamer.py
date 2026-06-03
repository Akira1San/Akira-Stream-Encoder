"""
GStreamer CLI Backend - Implements MediaBackend using gst-launch-1.0 / gst-discoverer-1.0

Known limitations (logged as warnings; switch to FFmpeg to resolve):
- DVD VOB concat files (ffmpeg concat demuxer format)
- Trim/clip extraction: falls back to FFmpeg subprocess (native trim via
  GStreamer Python bindings requires further pipeline refactoring)
- Fast cut (stream copy not supported by GStreamer)
- Subtitle burning (DVD via dvdspu, SRT/ASS via subparse+textoverlay)
- Various filters: delogo, sharpen, CAS, deblock, deblock, audio denoise, dynaudnorm, audio compressor, white balance
"""
import io
import os
import re
import struct
from datetime import datetime
import subprocess
import tempfile
import threading
import time
import zlib
from typing import Optional, List, Dict

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

from backends.base import MediaBackend
from backends.ffmpeg import FFmpegBackend


# ------------------------------------------------------------------ #
#  GStreamer init (once)
# ------------------------------------------------------------------ #

_gst_initialized = False

def _ensure_gst_init():
    global _gst_initialized
    if not _gst_initialized:
        Gst.init(None)
        _gst_initialized = True


# ------------------------------------------------------------------ #
#  PopenWrapper – mimics subprocess.Popen for in-process pipelines
# ------------------------------------------------------------------ #

class _PopenWrapper:
    """Mimics subprocess.Popen by wrapping an in-process GStreamer pipeline.

    The controller expects a subprocess.Popen-like object with:
      - .stdout  : iterable of text lines (StringIO)
      - .wait()  : blocks until completion, returns exit code
      - .poll()  : non-blocking status check
      - .returncode
    """

    def __init__(self, pipeline_fn):
        self._buf = io.StringIO()
        self._returncode = [-1]
        self._done = threading.Event()
        self._thread = threading.Thread(
            target=self._thread_main, args=(pipeline_fn,), daemon=True
        )
        self._thread.start()

    # ---- public API ----

    @property
    def stdout(self):
        return self._buf

    @property
    def returncode(self):
        return self._returncode[0]

    def poll(self):
        if self._thread.is_alive():
            return None
        return self._returncode[0]

    def wait(self, timeout=None):
        self._done.wait(timeout=timeout)
        self._thread.join(timeout=5)
        return self._returncode[0]

    # ---- internal ----

    def _thread_main(self, pipeline_fn):
        try:
            rc = pipeline_fn(self._buf)
            self._returncode[0] = rc if rc is not None else 0
        except Exception as exc:
            self._buf.write(f"Pipeline error: {exc}\n")
            self._buf.flush()
            self._returncode[0] = 1
        finally:
            self._buf.seek(0)
            self._done.set()


# ------------------------------------------------------------------ #
#  Backend class
# ------------------------------------------------------------------ #

class GStreamerBackend(MediaBackend):
    """Media backend using GStreamer CLI tools"""

    # Cache for element availability checks (class-level, persists across instances)
    _element_cache = {}

    def __init__(self, app_state):
        self.app_state = app_state
        self._gst_path = "gst-launch-1.0"
        self._discoverer_path = "gst-discoverer-1.0"
        self._vob_duration_cache: Dict[str, float] = {}

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _log_unsupported(self, feature: str):
        self.app_state.log(
            f"[GStreamer] '{feature}' not yet implemented. Switch to FFmpeg engine.",
            "WARN"
        )

    def _element_available(self, element_name: str) -> bool:
        """Check whether a GStreamer element is available on the system.

        Uses ``gst-inspect-1.0`` and caches results per element name
        for the lifetime of the process.
        """
        if element_name in self._element_cache:
            return self._element_cache[element_name]
        try:
            r = subprocess.run(
                ["gst-inspect-1.0", element_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            available = r.returncode == 0
        except Exception:
            available = False
        self._element_cache[element_name] = available
        return available

    def _create_rect_png(self, width: int, height: int, color: tuple, alpha: int = 180) -> str:
        """Create a colored rectangle PNG and return cached path."""
        cache = os.path.join(tempfile.gettempdir(), 'myencoder_overlays')
        os.makedirs(cache, exist_ok=True)
        r, g, b = color
        path = os.path.join(cache, f'rect_{width}x{height}_{r:x}{g:x}{b:x}_a{alpha:x}.png')
        if os.path.exists(path):
            return path
        raw = bytearray()
        for _ in range(height):
            raw.append(0)
            raw.extend([r, g, b, alpha] * width)
        def _chunk(tag, data):
            c = tag + data
            return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
        png = b'\x89PNG\r\n\x1a\n'
        png += _chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
        png += _chunk(b'IDAT', zlib.compress(bytes(raw)))
        png += _chunk(b'IEND', b'')
        with open(path, 'wb') as f:
            f.write(png)
        return path

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
        ffprobe = self.app_state.ffprobe_path
        if ffprobe and ffprobe != "ffprobe":
            try:
                r = subprocess.run(
                    [ffprobe, "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", input_path],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5
                )
                if r.returncode == 0 and r.stdout.strip():
                    return float(r.stdout.strip())
            except Exception:
                pass
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

    def get_video_tracks(self, input_path: str) -> List[dict]:
        tracks = []
        try:
            text = self._run_discoverer(input_path)
            info = self._parse_discoverer_output(text)
            for s in info['streams']:
                if s['type'] == 'video':
                    tracks.append({
                        'index': s['id'],
                        'codec': s['codec'],
                        'width': s.get('width', 0),
                        'height': s.get('height', 0),
                        'fps': s.get('fps', ''),
                        'language': s.get('language', ''),
                        'title': ''
                    })
        except Exception as e:
            self.app_state.log(f"GStreamer video track detection failed: {e}", "WARN")
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

    def extract_subtitle(self, input_path: str, stream_idx: int, output_path: str, codec_name: str = None) -> Optional[str]:
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
            if encoding.use_original_bitrate or (encoding.target_bitrate and encoding.target_bitrate.isdigit() and encoding.target_bitrate != "0"):
                br = self.get_video_bitrate(self.app_state.current_video_path or "")
                if not br:
                    br = int(encoding.target_bitrate) if encoding.target_bitrate and encoding.target_bitrate.isdigit() else 2000
                params.append("rc-mode=cbr")
                params.append(f"bitrate={br}")
            else:
                params.append("rc-mode=vbr")
                params.append(f"const-quality={encoding.cq}")
            params.append(f"preset={encoding.gpu_preset}")
            params.append("gop-size=144")
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
                if "x265" in encoder:
                    params.append(f"qp={encoding.cq}")
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
            if "x264" in encoder:
                params.append("bframes=0")
                params.append("byte-stream=true")
            elif "x265" in encoder:
                params.append("h265parse")
                params.append("config-interval=-1")

        return params

    def _build_video_filters(self) -> List[str]:
        elements = []
        filters = self.app_state.filters
        encoding = self.app_state.encoding
        eq = self.app_state.eq

        if filters.deinterlace:
            elements.append("deinterlace")

        if filters.denoise:
            elements.extend(["videoconvert", "queue",
                             "gaussianblur sigma=1.5",
                             "queue", "videoconvert"])

        # Tone mapping (HDR->SDR) approximation via GL elements
        if encoding.scale_algorithm == "libplacebo":
            tone_map = getattr(encoding, 'libplacebo_tonemapping', 'none')
            if tone_map and tone_map != "none":
                if self._element_available('gltransformation') and self._element_available('glcolorbalance'):
                    elements.append("gltransformation")
                    elements.append("output-colorimetry=bt709:bt709:bt709:full")
                    elements.append("glcolorbalance")
                    elements.append("saturation=1.1")
                else:
                    self.app_state.log(
                        "GStreamer: gltransformation/glcolorbalance not available; "
                        "install gst-plugins-gl for HDR->SDR tonemapping", "WARN")

        if encoding.scale_mode == "on" and encoding.resolution and encoding.resolution != "none":
            if "x" in encoding.resolution:
                w, h = encoding.resolution.split("x")

                elements.append("videoscale")
                elements.append(f"method={encoding.gst_scale_algorithm}")
                elements.append("n-threads=4")
                if getattr(filters, 'sharpen', False):
                    elements.append("sharpen=true")
                    amount = getattr(filters, 'sharpen_amount', 1.0)
                    elements.append(f"sharpness={max(0.0, min(1.0, amount))}")
                elements.append(f"video/x-raw,width={w},height={h}")

        if getattr(filters, 'smart_crop_enabled', False):
            elements.append("videocrop")
            elements.append(f"top={filters.smart_crop_y}")
            elements.append(f"left={filters.smart_crop_x}")
            elements.append("right=0")
            elements.append("bottom=0")

        if getattr(filters, 'ar_crop_enabled', False):
            if self._element_available('aspectratiocrop'):
                elements.append("aspectratiocrop")
                ar_target = getattr(filters, 'ar_crop_target', '16:9')
                elements.append(f"aspect-ratio={ar_target.replace(':', '/')}")
            else:
                self._log_unsupported("aspect ratio crop (aspectratiocrop)")

        video_dir = getattr(filters, 'video_rotate', 'none')
        if video_dir and video_dir != 'none':
            if self._element_available('videoflip'):
                elements.append("videoflip")
                elements.append(f"video-direction={video_dir}")
            else:
                self._log_unsupported("video rotate/flip (videoflip)")

        if getattr(filters, 'delogo_enabled', False):
            if self._element_available('delogo'):
                elements.extend(["delogo",
                                 f"x={filters.delogo_x}",
                                 f"y={filters.delogo_y}",
                                 f"width={filters.delogo_w}",
                                 f"height={filters.delogo_h}",
                                 f"band={filters.delogo_band}"])
            else:
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
            amount = getattr(filters, 'sharpen_amount', 1.0)
            sigma = -amount * 10
            sigma = max(-20.0, min(-0.01, sigma))
            elements.extend(["videoconvert", "queue",
                             f"gaussianblur sigma={sigma}",
                             "queue", "videoconvert"])

        if getattr(filters, 'cas_enabled', False):
            self._log_unsupported("CAS (contrast adaptive sharpen)")

        if getattr(filters, 'deblock', False):
            self._log_unsupported("deblock")

        if getattr(filters, 'ar_convert_enabled', False):
            self._log_unsupported("aspect ratio conversion")

        # Smart crop preview overlay (green semi-transparent box)
        if getattr(filters, 'smart_crop_enabled', False) and getattr(filters, 'smart_crop_show_preview', False):
            w = max(filters.smart_crop_w, 1)
            h = max(filters.smart_crop_h, 1)
            if self._element_available('gdkpixbufoverlay'):
                png = self._create_rect_png(w, h, (0, 204, 0))
                elements.extend(["gdkpixbufoverlay",
                                 f"location={png}",
                                 f"offset-x={filters.smart_crop_x}",
                                 f"offset-y={filters.smart_crop_y}"])
            else:
                self._log_unsupported("smart crop preview (gdkpixbufoverlay)")

        # Delogo preview overlay (red semi-transparent box)
        if getattr(filters, 'delogo_enabled', False) and getattr(filters, 'delogo_show', False):
            w = max(filters.delogo_w, 1)
            h = max(filters.delogo_h, 1)
            if self._element_available('gdkpixbufoverlay'):
                png = self._create_rect_png(w, h, (204, 0, 0))
                elements.extend(["gdkpixbufoverlay",
                                 f"location={png}",
                                 f"offset-x={filters.delogo_x}",
                                 f"offset-y={filters.delogo_y}"])
            else:
                self._log_unsupported("delogo preview (gdkpixbufoverlay)")

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
            codec_map = {
                "aac": "voaacenc",
                "mp2": "avenc_mp2",
                "ac3": "avenc_ac3",
                "mp3": "lamemp3enc",
            }
            gst_codec = codec_map.get(encoding.audio_codec, "voaacenc")
            elements.append(gst_codec)
            if gst_codec != "identity":
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
        base = os.path.splitext(video_path)[0]
        for ext in [".srt", ".ass", ".ssa", ".sub"]:
            sub_path = base + ext
            if os.path.exists(sub_path):
                return sub_path
        selected = self.app_state.subtitles.selected_subtitle
        if selected and os.path.exists(selected):
            return selected
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
            "!", "subparse", "subtitle-encoding=utf-8"
        ]

    def _build_pipeline_list(self, input_path: str, output_path: str) -> List[str]:
        """Build a ``gst-launch-1.0`` pipeline argument list (no trim)."""
        encoding = self.app_state.encoding
        tracks = self.app_state.tracks

        muxer_map = {"mp4": "mp4mux", "mkv": "matroskamux", "avi": "avimux", "mpg": "mpegpsmux", "vob": "mpegpsmux"}
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

        pipeline = [self._gst_path, "-e"]

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
            ext = os.path.splitext(input_path)[1].lower()
            if ext == ".mkv":
                demuxer = "matroskademux"
            elif ext == ".avi":
                demuxer = "avidemux"
            elif ext in (".ts", ".mts", ".m2ts"):
                demuxer = "tsdemux"
            elif ext in (".webm",):
                demuxer = "matroskademux"
            else:
                demuxer = "qtdemux"
            vid_pad = "video_0"
            aud_pad = "audio_0"
            sub_pad = "subtitle_0"

        if use_branches or burn_subs or text_subs:
            pipeline += [f"{muxer_el}", "name=mux", "!",
                         "filesink", f"location={output_path}"]

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
                subtitle_idx = self.app_state.dvd.selected_subtitle_index
                sub_pad_name = f"subpicture_{subtitle_idx:02x}"

                pipeline += [f"demux.{vid_pad}", "!", "queue", "!", "decodebin", "!",
                             "videoconvert", "!", "queue", "!",
                             "dvdspu", "name=spu"]
                pipeline += [f"demux.{sub_pad_name}", "!", "queue", "!", "spu.subpicture"]
                pipeline += ["spu.", "!", "queue", "!", "videoconvert", "!", "queue", "!"]
                pipeline += video_filters
                pipeline += video_enc + ["!", "queue", "!", "mux."]
                pipeline += [f"demux.{aud_pad}", "!", "queue", "!", "decodebin", "!",
                             "audioconvert", "!", "queue", "!"]
                pipeline += audio_chain[3:]
                pipeline += ["!", "queue", "!", "mux."]
            elif text_subs:
                sub_path = self.find_subtitle_file(input_path)
                subs = self.app_state.subtitles
                font_desc = f"{subs.font} {subs.size}"

                pipeline += [f"demux.{vid_pad}", "!", "queue", "!", "decodebin", "!",
                             "videoconvert", "!", "queue", "!",
                             "textoverlay", "name=txt", "auto-resize=false",
                             f"font-desc={font_desc}"]
                if subs.outline_width > 0:
                    self.app_state.log(
                        "GStreamer: outline width not supported by textoverlay "
                        "(use FFmpeg engine for outline width control)", "WARN")
                ol_color = subs.outline_color.lstrip("#")
                if len(ol_color) == 6:
                    argb = int("ff" + ol_color, 16)
                    pipeline.append(f"outline-color={argb}")
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

                pipeline += ["txt.", "!", "queue", "!", "videoconvert", "!", "queue", "!"]
                pipeline += video_filters
                pipeline += video_enc + ["!", "queue", "!", "mux."]

                sub_chain = self._build_subtitle_chain(sub_path)
                pipeline += sub_chain + ["!", "queue", "!", "txt.text_sink"]

                if use_branches:
                    pipeline += [f"demux.{aud_pad}", "!", "queue", "!", "decodebin", "!",
                                 "audioconvert", "!", "queue", "!"]
                    pipeline += audio_chain[3:]
                    pipeline += ["!", "queue", "!", "mux."]
            elif use_branches:
                pipeline += [f"demux.{vid_pad}", "!", "queue", "!", "decodebin", "!",
                             "videoconvert", "!", "queue", "!"]
                pipeline += video_filters
                pipeline += video_enc + ["!", "queue", "!", "mux."]
                pipeline += [f"demux.{aud_pad}", "!", "queue", "!", "decodebin", "!",
                             "audioconvert", "!", "queue", "!"]
                pipeline += audio_chain[3:]
                pipeline += ["!", "queue", "!", "mux."]
        else:
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
        """Encode a video file.

        When *start_time* and *duration* are provided (trim/clip mode), falls
        back to FFmpeg since native GStreamer trimming via Python bindings is
        not yet stable (see _run_trimmed_pipeline stub below).
        """
        if start_time and duration:
            self.app_state.log(
                "GStreamer: trimming falls back to FFmpeg backend. "
                "Native GStreamer trim needs further development.",
                "WARN"
            )
            fb = FFmpegBackend(app_state)
            cmd = fb.build_command(input_path, output_path, start_time, duration)
            self.app_state.log(f"FFmpeg fallback command: {' '.join(cmd)}", "INFO")
            log_path = output_path + ".log"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(log_path, "a") as f:
                f.write(f"[{timestamp}] Command: {' '.join(cmd)}\n")
            return subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True, bufsize=1
            )

        pipeline = self._build_pipeline_list(input_path, output_path)
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
        if start_time and duration:
            fb = FFmpegBackend(self.app_state)
            return fb.build_command(input_path, output_path, start_time, duration)
        return self._build_pipeline_list(input_path, output_path)

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

    @staticmethod
    def _sample_data(sample):
        if not sample:
            return None
        buf = sample.get_buffer()
        if not buf:
            return None
        ok, info = buf.map(Gst.MapFlags.READ)
        if not ok:
            return None
        data = bytes(info.data)
        buf.unmap(info)
        return data

    def _capture_frame_gst(self, target: str, timestamp: float,
                            max_size: tuple = None) -> Optional[bytes]:
        _ensure_gst_init()

        ts = timestamp
        scale = ""
        if max_size:
            scale = f" ! videoscale ! video/x-raw,width={max_size[0]},height={max_size[1]}"

        def _run_mpegpsdemux():
            p = Gst.Pipeline.new("capture")
            filesrc = Gst.ElementFactory.make("filesrc", "src")
            filesrc.set_property("location", target)
            p.add(filesrc)
            demux = Gst.ElementFactory.make("mpegpsdemux", "demux")
            p.add(demux)
            filesrc.link(demux)
            vq = Gst.ElementFactory.make("queue", "vq")
            dec = Gst.ElementFactory.make("decodebin", "dec")
            vc = Gst.ElementFactory.make("videoconvert", "vc")
            vq2 = Gst.ElementFactory.make("queue", "vq2")
            spu = Gst.ElementFactory.make("dvdspu", "spu")
            oq = Gst.ElementFactory.make("queue", "oq")
            oc = Gst.ElementFactory.make("videoconvert", "oc")
            enc = Gst.ElementFactory.make("pngenc", "enc")
            sink = Gst.ElementFactory.make("appsink", "sink")
            for e in [vq, dec, vc, vq2, spu, oq, oc, enc, sink]:
                if e: p.add(e)
            if not all([vq, dec, vc, vq2, spu, oq, oc, enc, sink]):
                return None
            if max_size:
                vs = Gst.ElementFactory.make("videoscale", "vs")
                cf = Gst.ElementFactory.make("capsfilter", "cf")
                caps = Gst.Caps.from_string(f"video/x-raw,width={max_size[0]},height={max_size[1]}")
                cf.set_property("caps", caps)
                p.add(vs); p.add(cf)
            vq.link(dec)
            dec.connect("pad-added", lambda d, pad: pad.link(vc.get_static_pad("sink")))
            vc.link(vq2)
            vq2.get_static_pad("src").link(spu.get_static_pad("video"))
            spu.get_static_pad("src").link(oq.get_static_pad("sink"))
            oq.link(oc)
            if max_size:
                oc.link(vs); vs.link(cf); cf.link(enc)
            else:
                oc.link(enc)
            enc.link(sink)
            sink.set_property("max-buffers", 1)
            sink.set_property("drop", False)
            demux.connect("pad-added", lambda d, pad: (
                pad.link(vq.get_static_pad("sink")) if pad.name.startswith("video_") else None
            ))
            return _run(p, sink, p.get_bus())

        def _run_decodebin():
            pipe = f"filesrc location={target} ! decodebin ! videoconvert{scale} ! pngenc ! appsink name=sink"
            p = Gst.parse_launch(pipe)
            if not p: return None
            sink = p.get_by_name("sink")
            if not sink: p.set_state(Gst.State.NULL); return None
            sink.set_property("max-buffers", 1)
            sink.set_property("drop", False)
            return _run(p, sink, p.get_bus())

        def _run(p, sink, bus):
            r = p.set_state(Gst.State.PAUSED)
            if r == Gst.StateChangeReturn.ASYNC:
                r, s, pend = p.get_state(20 * Gst.SECOND)
            if r != Gst.StateChangeReturn.SUCCESS:
                p.set_state(Gst.State.NULL); return None
            data = self._sample_data(sink.get_property("last-sample"))
            if data and ts <= 0:
                p.set_state(Gst.State.NULL); return data
            ev = Gst.Event.new_seek(1.0, Gst.Format.TIME,
                Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                Gst.SeekType.SET, int(ts * Gst.SECOND), Gst.SeekType.NONE, 0)
            p.send_event(ev)
            r, s, pend = p.get_state(20 * Gst.SECOND)
            if r != Gst.StateChangeReturn.SUCCESS:
                p.set_state(Gst.State.NULL); return None
            data = self._sample_data(sink.get_property("last-sample"))
            p.set_state(Gst.State.NULL)
            return data

        result = _run_mpegpsdemux()
        if result:
            return result
        return _run_decodebin()

    def _get_vob_duration(self, vob_path: str) -> float:
        if vob_path in self._vob_duration_cache:
            return self._vob_duration_cache[vob_path]
        probes = [self.app_state.ffprobe_path or "ffprobe", self.app_state.ffmpeg_path]
        for probe in probes:
            try:
                cmd = [probe, "-v", "error", "-i", vob_path,
                       "-show_entries", "format=duration",
                       "-of", "default=noprint_wrappers=1:nokey=1"]
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=True, timeout=15)
                if result.returncode == 0 and result.stdout.strip() and result.stdout.strip() != 'N/A':
                    duration = float(result.stdout.strip())
                    if duration > 0:
                        self._vob_duration_cache[vob_path] = duration
                        return duration
            except Exception:
                continue
        self._vob_duration_cache[vob_path] = 0.0
        return 0.0

    def _find_dvd_vob_for_timestamp(self, timestamp: float):
        """
        Find the correct VOB file and relative timestamp for a DVD seek.
        Probes actual VOB durations with ffprobe (cached).
        Falls back to file-size proportion.
        Returns (vob_path, adjusted_timestamp) or (None, timestamp) on failure.
        """
        if not self.app_state.dvd.available_titles:
            return None, timestamp
        for title in self.app_state.dvd.available_titles:
            if title.title_number == self.app_state.dvd.selected_title_number:
                vobs = title.vob_files
                if not vobs:
                    return None, timestamp
                vob_durs = [self._get_vob_duration(v) for v in vobs]
                all_zero = all(d <= 0 for d in vob_durs)
                if all_zero:
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
                    if timestamp < cum_time + vob_dur or i == len(vobs) - 1:
                        return v, max(0.0, min(timestamp - cum_time, vob_dur - 1.0))
                    cum_time += vob_dur
                break
        return None, timestamp

    def capture_frame(self, video_path: str, timestamp: float,
                      subtitle_filter: str = "", is_dvd_source: bool = False,
                      first_vob_path: str = None,
                      max_size: tuple = None,
                      extra_video_filter: str = "",
                      extra_image_paths: list = None) -> Optional[bytes]:
        vob_path, adj_ts = self._find_dvd_vob_for_timestamp(timestamp) if is_dvd_source else (None, timestamp)
        target = vob_path if (is_dvd_source and vob_path and os.path.exists(vob_path)) else video_path
        if not os.path.exists(target):
            return None

        result = self._capture_frame_gst(target, adj_ts if is_dvd_source else timestamp, max_size)
        if result:
            return result

        ffmpeg = self.app_state.ffmpeg_path
        if not ffmpeg or ffmpeg == "ffmpeg" or not os.path.exists(ffmpeg):
            self._log_unsupported("frame capture (no FFmpeg path)")
            return None
        if is_dvd_source and vob_path and os.path.exists(vob_path):
            cmd = [ffmpeg, "-ss", str(adj_ts), "-i", vob_path]
        elif is_dvd_source:
            cmd = [ffmpeg, "-ss", str(timestamp),
                   "-f", "concat", "-safe", "0", "-i", video_path]
        else:
            cmd = [ffmpeg, "-ss", str(timestamp), "-i", video_path]
        scale_filter = ""
        if max_size:
            scale_filter = f"scale='min({max_size[0]},iw)':min'({max_size[1]},ih)':force_original_aspect_ratio=decrease"
        if subtitle_filter and scale_filter:
            cmd.extend(["-vf", f"{subtitle_filter},{scale_filter}"])
        elif subtitle_filter:
            cmd.extend(["-vf", subtitle_filter])
        elif scale_filter:
            cmd.extend(["-vf", scale_filter])
        cmd.extend(["-vframes", "1", "-q:v", "2", "-f", "image2pipe", "-vcodec", "png", "-"])
        timeout = 30 if is_dvd_source else 10
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            if result.returncode == 0 and result.stdout:
                return result.stdout
            if result.returncode != 0 and subtitle_filter:
                retry = []
                i = 0
                while i < len(cmd):
                    if cmd[i] == "-vf":
                        i += 2
                        continue
                    retry.append(cmd[i])
                    i += 1
                if retry and retry != cmd:
                    result = subprocess.run(retry, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
                    if result.returncode == 0 and result.stdout:
                        return result.stdout
        except Exception:
            pass
        return None

    def apply_video_filter(self, image_bytes: bytes, filter_str: str) -> Optional[bytes]:
        self._log_unsupported("preview video filters")
        return None

    def get_frame_rate(self, video_path: str) -> dict:
        text = self._run_discoverer(video_path)
        fps = None
        for line in text.split("\n"):
            if "fps" in line.lower():
                m = re.search(r"(\d+\.?\d*)\s*fps", line)
                if m:
                    fps = float(m.group(1))
                    break
        is_prob = fps is None or fps < 15.0 or fps > 120.0
        return {"fps": fps, "fps_str": str(fps) if fps else "", "is_vfr": fps is None, "is_problematic": is_prob}

    def get_full_info(self, video_path: str) -> dict:
        text = self._run_discoverer(video_path)
        info = {"raw": text}
        for line in text.split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                info[k.strip().lower().replace(" ", "_")] = v.strip()
        return info

    def get_fps(self, input_path: str) -> float:
        return 24000 / 1001

    def extract_frames(self, input_path: str, frames_dir: str,
                       part_duration_min: int, fps: float,
                       progress_callback=None) -> bool:
        self.app_state.log("GStreamer: frame extraction not supported, use FFmpeg backend", "WARN")
        return False

    def upscale_frames(self, frames_dir: str, upscaler: str,
                       model: str, scale: int, tile_size: int,
                       progress_callback=None) -> bool:
        self.app_state.log("GStreamer: AI upscaling not supported, use FFmpeg backend", "WARN")
        return False

    def recombine_frames(self, frames_dir: str, output_path: str,
                         fps: float, progress_callback=None) -> bool:
        self.app_state.log("GStreamer: frame recombination not supported, use FFmpeg backend", "WARN")
        return False

    def get_part_dirs(self, frames_dir: str) -> list:
        return []

    def get_upscaled_part_dirs(self, frames_dir: str) -> list:
        return []

    def supported_filters(self) -> dict:
        """GStreamer per-filter support based on actual element availability."""
        return {
            # Video filters
            'deinterlace': self._element_available('deinterlace'),
            'denoise': self._element_available('gaussianblur'),
            'sharpen': self._element_available('gaussianblur'),
            'cas': False,           # not available in GStreamer
            'deblock': False,       # not available in GStreamer
            'smart_crop': self._element_available('videocrop'),
            'ar_crop': self._element_available('aspectratiocrop'),
            'ar_convert': False,    # aspect ratio conversion not implemented
            'delogo': self._element_available('delogo'),
            'video_rotate': self._element_available('videoflip'),
            'tonemapping': self._element_available('gltransformation') and self._element_available('glcolorbalance'),
            # Color correction (EQ)
            'eq_brightness': self._element_available('videobalance'),
            'eq_contrast': self._element_available('videobalance'),
            'eq_saturation': self._element_available('videobalance'),
            'eq_gamma': self._element_available('gamma'),
            'white_balance': False,  # colorbalance not available in GStreamer
            # Colorization (B&W → Color)
            'colorization': False,
            # Audio filters
            'volume': self._element_available('volume'),
            'audio_denoise': False,  # webrtcdsp / audiochebband not implemented
            'audio_dynnorm': False,  # not available in GStreamer
            'audio_compressor': self._element_available('audiocompressor'),
            'audio_delay': False,    # audio delay not implemented
        }
