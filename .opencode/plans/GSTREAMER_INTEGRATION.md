# GStreamer Integration Plan

> **Status:** Phase 1-5 + refactoring complete. SRT/ASS and DVD subtitle burn-in implemented. `video_preview.py`, `trim_controller.py`, `video_validator.py` now route through backend.

---

## Overview

Add a `gst-launch-1.0` CLI backend alongside the existing FFmpeg CLI backend, with a global switch (engine combo in Config tab) to toggle between them.

---

## Architecture

### Media Backend Interface (`PySide6/backends/base.py`)

```python
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

class MediaBackend(ABC):
    @abstractmethod
    def encode(self, input_path: str, output_path: str,
               app_state, start_time=None, duration=None) -> subprocess.Popen:
        ...

    @abstractmethod
    def get_duration(self, input_path: str) -> float:
        ...

    @abstractmethod
    def get_audio_tracks(self, input_path: str) -> List[dict]:
        ...

    @abstractmethod
    def get_video_bitrate(self, input_path: str) -> Optional[int]:
        ...

    @abstractmethod
    def get_file_info(self, input_path: str) -> dict:
        ...

    @abstractmethod
    def extract_subtitle(self, input_path: str, stream_idx: int,
                         output_path: str) -> Optional[str]:
        ...

    @abstractmethod
    def validate(self, input_path: str) -> dict:
        ...

    @abstractmethod
    def build_filter_string(self, app_state) -> str:
        ...

    @abstractmethod
    def align_to_keyframe(self, video_path: str, target_time: float) -> float:
        ...

    @abstractmethod
    def extract_track(self, video_path: str, track_info: dict, output_folder: str) -> Optional[str]:
        ...

    @abstractmethod
    def extract_subtitle_streams(self, video_path: str) -> List[dict]:
        ...

    @abstractmethod
    def get_streams(self, video_path: str) -> dict:
        ...

    @abstractmethod
    def get_external_audio_info(self, file_path: str) -> Optional[dict]:
        ...

    @abstractmethod
    def find_subtitle_file(self, video_path: str) -> Optional[str]:
        ...

    @abstractmethod
    def build_subtitle_filter(self, sub_path: str) -> str:
        ...

    @abstractmethod
    def hex_to_ass(self, hex_color: str, opacity: float = 1.0) -> str:
        ...

    @abstractmethod
    def capture_frame(self, video_path: str, timestamp: float,
                      subtitle_filter: str = "", is_dvd_source: bool = False,
                      first_vob_path: str = None) -> Optional[bytes]:
        ...

    @abstractmethod
    def apply_video_filter(self, image_bytes: bytes, filter_str: str) -> Optional[bytes]:
        ...

    @abstractmethod
    def get_frame_rate(self, video_path: str) -> dict:
        ...

    @abstractmethod
    def get_full_info(self, video_path: str) -> dict:
        ...
```

### FFmpegBackend (`PySide6/backends/ffmpeg.py`)

Refactor existing code from:
- `controller.py` — `build_ffmpeg_command()`, `build_filter_complex()`, `get_video_duration()`, `get_audio_tracks()`, `get_video_bitrate()`, `encode_file()`, `fast_cut_file()`, `join_segments()`
- `config_tab.py` — `detect_and_show_info()`, `_extract_subs_from_video()`, `_do_extract_track()` (not yet refactored — still calls ffmpeg/ffprobe directly)
- `trim_controller.py` — trim operations (refactored ✓)
- `video_validator.py` — validation operations (refactored ✓)
- `dvd_handler.py` — DVD probing/extraction via ffprobe (not yet refactored)
- `video_preview.py` — capture_frame, apply_video_filter, load_video_metadata (refactored ✓)

Method signatures mirror the base class above. Internal implementation stays as-is (subprocess.run/Popen with FFmpeg CLI args).

### GStreamerBackend (`PySide6/backends/gstreamer.py`)

New class using `gst-launch-1.0` CLI via subprocess.

#### Pipeline Construction Patterns

**Basic encode (H.264):**
```python
# FFmpeg equivalent:
# ffmpeg -i input.mp4 -c:v libx264 -crf 23 -preset medium -c:a aac output.mp4

# GStreamer pipeline:
gst-launch-1.0 filesrc location=input.mp4 ! \
  qtdemux ! queue ! decodebin ! videoconvert ! \
  x264enc bitrate=2000 speed-preset=medium ! \
  mp4mux ! filesink location=output.mp4
```

**NVENC encode:**
```python
gst-launch-1.0 filesrc location=input.mp4 ! \
  qtdemux ! queue ! decodebin ! videoconvert ! \
  nvh264enc bitrate=2000 preset=p4 ! \
  mp4mux ! filesink location=output.mp4
```

**With video filters (deinterlace + scale):**
```python
gst-launch-1.0 filesrc location=input.mp4 ! \
  qtdemux ! queue ! decodebin ! \
  deinterlace ! videoscale ! video/x-raw,width=1280,height=720 ! \
  videoconvert ! x264enc ! mp4mux ! filesink location=output.mp4
```

**With audio re-encode:**
```python
gst-launch-1.0 filesrc location=input.mp4 ! \
  qtdemux name=demux \
  demux.video_0 ! queue ! decodebin ! videoconvert ! x264enc ! \
  mux.video_0 \
  demux.audio_0 ! queue ! decodebin ! audioconvert ! voaacenc bitrate=128000 ! \
  mux.audio_0 \
  mp4mux name=mux ! filesink location=output.mp4
```

#### Probe via `gst-discoverer-1.0`

```bash
gst-discoverer-1.0 --json input.mp4
```
Returns JSON with duration, streams (codec, resolution, sample rate), container info.

#### Filter Mapping (FFmpeg -> GStreamer)

| FFmpeg filter | GStreamer element(s) | Status |
|---|---|---|
| `scale=w:h` | `videoscale ! video/x-raw,width=W,height=H` | Full |
| `yadif` | `deinterlace` | Full |
| `hqdn3d` | `gaussianblur` | Approximate |
| `unsharp` | `sharpen` | Full |
| `deblock` | `gaussianblur` (approx) or `deblock` | Partial |
| `eq` (brightness/contrast/sat/gamma) | `videobalance` (only sat+contrast+brightness, no gamma) + `gamma` element | Partial |
| `colorbalance` | `gamma` + `videobalance` | Partial |
| `crop=w:h:x:y` | `videocrop top=B left=L right=R bottom=BT` | Full |
| `delogo` | `delogo` | Full |
| `subtitles` (SRT/ASS) | `filesrc ! typefind ! subparse ! textoverlay` | Full |
| `dvd_subtitle` burn | `mpegpsdemux` → `dvdsubdec` + `dvdspu` | Full (GStreamer only) |
| `volume=XdB` | `volume volume=X` | Full |
| `afftdn` | `webrtcdsp` or `audiochebband` | Partial |
| `dynaudnorm` | Custom: `audioconvert ! level ! volume` | Partial |
| `acompressor` | `audiocompressor` | Full |
| `scale_cuda` | `nvvideoconvert` | With GPU |
| `scale_vulkan` | `vulkanconvert` | With GPU |
| `libplacebo` tonemap | `glcolorbalance` + `gltransformation` | Partial |
| `pad` (black bars) | `videobox` | Full |
| `setsar` | `videoscale` (handles SAR) | Full |
| `drawbox` | `gdkpixbufoverlay` or `clockoverlay` | Partial |

#### Features NOT supported in GStreamer mode (graceful fallback)

These will log a warning and suggest switching to FFmpeg:
- Trim/clip extraction (falls back to FFmpeg subprocess — gst-launch has no native trim support)
- Fast cut (stream copy)
- `sharpen`, `delogo`, `audiocompressor`
- `dynaudnorm` (dynamic audio normalizer)
- `afftdn` (FFT-based audio denoise)
- CAS (Contrast Adaptive Sharpen)
- Deblock
- Audio delay
- White balance (`colorbalance`)
- Aspect ratio conversion
- Drawbox preview overlay
- Segment joining

---

## Global State Changes

### `PySide6/models.py` — AppState additions

```python
class AppState(QObject):
    # New signals
    media_engine_changed = Signal(str)
    gstreamer_path_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        # ...
        self._media_engine: str = "ffmpeg"  # "ffmpeg" | "gstreamer"
        self._gstreamer_path: str = "gst-launch-1.0"
        self._backend: Optional[MediaBackend] = None

    @Property(str, notify=media_engine_changed)
    def media_engine(self):
        return self._media_engine

    @media_engine.setter
    def media_engine(self, value):
        if self._media_engine != value:
            self._media_engine = value
            self._backend = None  # Reset backend on switch
            self.media_engine_changed.emit(value)

    @property
    def backend(self) -> MediaBackend:
        if self._backend is None:
            from backends.ffmpeg import FFmpegBackend
            from backends.gstreamer import GStreamerBackend
            if self._media_engine == "gstreamer":
                self._backend = GStreamerBackend(self)
            else:
                self._backend = FFmpegBackend(self)
        return self._backend
```

### `PySide6/config.py` — New constant

```python
GSTREAMER = "gst-launch-1.0"
```

### `PySide6/settings.json` — Persistence

```json
{
  "ffmpeg_path": "...",
  "gstreamer_path": "gst-launch-1.0",
  "media_engine": "ffmpeg",
  "output_folder": ""
}
```

---

## UI Changes

### `PySide6/config_tab.py` — New "Media Engine" group

Existing System Paths group gets new section:

```
+-- System Paths ------------------------------+
|                                                |
|  +-- Media Engine -------------------------+  |
|  | Engine:  [v FFmpeg / GStreamer        ] |  |
|  | Path:    [____________________] [Browse] |  |
|  |          [Auto Detect]                  |  |
|  +-----------------------------------------+  |
|                                                |
|  [FFmpeg Path:  ...]  (moved below)            |
|  [FFprobe Path: ...]                           |
|  [Output Folder: ...]                          |
+------------------------------------------------+
```

Behavior:
- Engine combo toggles the path label and line edit between ffmpeg_path/gstreamer_path
- Auto-detect searches PATH for `gst-launch-1.0` in GStreamer mode
- Version check button: `gst-launch-1.0 --version`
- Engine change resets `app_state._backend` (recreated on next access)

---

## Controller Refactoring

### `PySide6/controller.py` — Delegate to backend

```python
class VideoController:
    @property
    def backend(self) -> MediaBackend:
        return self.app_state.backend

    def get_video_duration(self, input_path):
        return self.backend.get_duration(input_path)

    def get_audio_tracks(self, input_path):
        return self.backend.get_audio_tracks(input_path)

    def encode_file(self, input_path, output_path, ...):
        # Common pre-encode logic stays here
        process = self.backend.encode(input_path, output_path,
                                       self.app_state, start_time, duration)
        # Progress parsing stays in controller
```

---

## Implementation Order

### Phase 1: Backend scaffold + FFmpegBackend extraction ✓
1. Create `backends/__init__.py`, `backends/base.py`
2. Create `backends/ffmpeg.py` — extract methods from `controller.py`
3. Refactor `VideoController` to delegate
4. Verify: exact same behavior, no regression

### Phase 2: GStreamerBackend — probing ✓
1. Create `backends/gstreamer.py`
2. Implement `get_duration()`, `get_audio_tracks()`, `get_video_bitrate()` via `gst-discoverer-1.0 --json`
3. Implement `get_file_info()`
4. Verify probe operations work in GStreamer mode

### Phase 3: GStreamerBackend — encode ✓
1. Basic encode pipeline (H.264)
2. NVENC support
3. Video copy mode
4. Filter support (deinterlace, videoscale, videocrop, videobalance, sharpen, delogo)
5. Audio support (voaacenc, audio copy, volume, audiocompressor)

### Phase 4: UI integration ✓
1. Engine combo box + path field in config_tab.py
2. Settings persistence for media_engine + gstreamer_path
3. Engine indicator in encoding_settings.py

### Phase 5: Edge cases + fallback ✓ (basic scaffolding, can be refined)
1. Feature availability check on startup
2. Graceful skip + log warning for unsupported features
3. Test all filter combinations

---

## File Changes Summary

| File | Action | Status |
|---|---|---|---|---|
| `PySide6/models.py` | Modify — add engine/gst path/backend | ✓ |
| `PySide6/config.py` | Modify — add GSTREAMER constant | ✓ |
| `PySide6/main_window.py` | Modify — persist new settings | ✓ |
| `PySide6/config_tab.py` | Modify — add engine UI | ✓ |
| `PySide6/encoding_settings.py` | Modify — add engine indicator | ✓ |
| `PySide6/controller.py` | Refactor — delegate to backend | ✓ |
| `PySide6/video_preview.py` | Modify — route through backend | ✓ (FrameLoader, load_video_metadata, apply_filters, seek_preview via backend) |
| `PySide6/trim_controller.py` | Modify — route through backend | ✓ (align_to_keyframe via backend) |
| `PySide6/video_validator.py` | Modify — route through backend | ✓ (validate, get_frame_rate, get_full_info via backend) |
| `PySide6/backends/__init__.py` | **New** | ✓ |
| `PySide6/backends/base.py` | **New** | ✓ |
| `PySide6/backends/ffmpeg.py` | **New** | ✓ |
| `PySide6/backends/gstreamer.py` | **New** | ✓ (probe ops (text-parsed gst-discoverer), encode pipeline with video/audio filters, multi-branch muxing, encoder settings, container selection, rate control, DVD VOB mpegpsdemux + concat, DVD dvdspu+dvdsubdec subtitle burn, SRT/ASS subparse+textoverlay subtitle burn, capture_frame (first frame), get_frame_rate, get_full_info) |
| `PySide6/backends/ffmpeg.py` | **New** | ✓ (all encode/probe/preview methods, including capture_frame, apply_video_filter, get_frame_rate, get_full_info extracted from consumer files) |
| `PySide6/backends/base.py` | **New** | ✓ (MediaBackend ABC with 18 abstract methods) |

---

## DVD Subtitle Status

DVD subtitles (`dvd_subtitle` bitmap format):
- **FFmpeg**: The concat demuxer hides subtitle streams; falls back to HandBrakeCLI
- **GStreamer**: Native DVD subtitle burning via `mpegpsdemux` → `dvdsubdec` + `dvdspu` (3-branch pipeline). DVD VOB concat files are handled by reading VOB paths and using `concat` element with `mpegpsdemux`.

### Known Issue: DVD Subtitle Preview

DVD subtitle _preview_ (the overlay shown in the preview panel during playback/pause) does **not** work with FFmpeg's native DVD subtitle burning. The preview uses `ffmpeg` pipe-to-image for frame capture, and `dvd_subtitle` bitmap streams cannot be rendered via the `subtitles` filter in a pipe.

---

## Testing

1. FFmpeg engine: full regression test (all existing flows)
2. GStreamer engine: probe operations (duration, audio tracks, bitrate)
3. GStreamer engine: basic encode with default settings
4. GStreamer engine: encode with filters (deinterlace, crop, scale, eq)
5. Engine switch mid-session: verify backend resets
6. Edge cases: no GStreamer installed, invalid path, unsupported features

---

## Dependencies

### GStreamer (required for GStreamer engine)
```bash
# Core
gstreamer1.0-tools           # gst-launch-1.0, gst-discoverer-1.0
gstreamer1.0-plugins-base    # videoconvert, audioconvert, queue, filesrc, etc.
gstreamer1.0-plugins-good    # qtdemux, mp4mux, videoscale, deinterlace, etc.

# Optional (for expanded features)
gstreamer1.0-plugins-bad     # dvdsuboverlay, nvh264enc, webrtcdsp, etc.
gstreamer1.0-plugins-ugly    # voaacenc, dvdsuboverlay, x264enc
python3-gi                   # GObject introspection (for gst-python if used later)
gstreamer1.0-vaapi           # VA-API hardware acceleration
```

### FFmpeg DVD support (linux)
```bash
# Rebuild ffmpeg with DVD navigation support:
# --enable-libdvdread --enable-libdvdnav --enable-libbluray
# This lets ffmpeg open VIDEO_TS folders directly without concat files.
# Current workaround: dvd_handler.py uses manual VOB concat instead.
```

---

## Next Steps — GStreamer Backend Expansion

These features are documented in the **Filter Mapping** table above but NOT yet implemented in `backends/gstreamer.py`. Each needs pipeline construction logic added.

### Completed
- [x] **Video filters**: `videoscale`, `deinterlace`, `videocrop`, `videobalance`, `gamma` — mapped to GStreamer elements
- [x] **Audio encode**: `voaacenc` with 128k bitrate, audio copy passthrough (identity)
- [x] **Audio filters**: `volume` — mapped to GStreamer `volume` element
- [x] **Subtitle burn-in (SRT/ASS)**: `filesrc ! typefind ! subparse ! textoverlay` with font-desc, valignment, shaded-background, deltay
- [x] **DVD subtitle burn-in**: `mpegpsdemux` → `dvdsubdec` + `dvdspu` (3-branch pipeline with subpicture pad routing)
- [x] **DVD VOB support**: VOB path extraction from concat files, `mpegpsdemux` demuxer, multi-VOB `concat` element chaining
- [x] **NVENC encode**: pipeline with `nvh264enc`/`nvh265enc` preset, bitrate, gop-size, const-quality
- [x] **Container support**: `.mp4` via `mp4mux`, `.mkv` via `matroskamux`, `.avi` via `avimux`

### High Priority
- [x] `delogo`, `audiocompressor` — unavailable in installed plugins; logged as unsupported with switch-to-FFmpeg warning
- [x] **Sharpen (unsharp) via `gaussianblur`**: implemented, requires `videoconvert ! queue` before/after since `gaussianblur` only supports AYUV format. Map FFmpeg `unsharp=5:5:amount` to `gaussianblur sigma=-N` (negative sigma = sharpen, range -20 to 0).
- [ ] **Dynamic filter disabling via `supported_filters()`**: Add abstract method `supported_filters() -> dict` to `MediaBackend` interface. FFmpegBackend returns `True` for all filters. GStreamerBackend returns per-filter support based on actual element availability. `filters.py` calls this on init and on engine switch to enable/disable UI controls (gray out unsupported filters with explanatory tooltips). Eliminates need for per-filter `_log_unsupported()` stubs.
- [ ] **High-quality videoscale with configurable method**: `_build_video_filters()` currently sends bare `videoscale ! video/x-raw,width=W,height=H` (defaults to bilinear — poor quality for upscaling). Needs to pass `method=` property based on selected scale algorithm. Recommended defaults: `catrom` for quality (sharp, minimal ringing, excellent for upscaling), `lanczos` as alternative. Also add `n-threads=4` for multi-threaded performance. `videoscale` supports: `nearest-neighbour`, `bilinear`, `4-tap`, `lanczos`, `bilinear2`, `sinc`, `hermite`, `spline`, `catrom`, `mitchell`. Additional options: `sharpen` (post-scale sharpening toggle), `sharpness=N` (filter sharpness control).

### Medium Priority
- [ ] **GPU filters**: `nvvideoconvert` for `scale_cuda` equivalent, `vulkanconvert` for `scale_vulkan`

### Low Priority
- [x] **libplacebo tonemap**: `glcolorbalance` + `gltransformation` pipeline
- [x] **drawbox / clockoverlay**: preview overlay equivalent (via `gdkpixbufoverlay`)
- [ ] **Video copy mode**: `identity` element or capsfilter passthrough
- [x] **Extract clip mode**: Implement in-process GStreamer pipeline via Python bindings (`gi.repository.Gst`) that sends segment events to `videosegmentclip`/`audiosegmentclip` for native trimming (infrastructure + FFmpeg fallback complete; native trim needs further caps-negotiation work)

  **The Fix for a Future Implementation**

  The `videosegmentclip`/`audiosegmentclip` elements work via **newsegment events**, not element properties. Three approaches were tested:

  1. **Pipeline seek with SEGMENT flag**: `pipeline.seek(1.0, Gst.Format.TIME, FLUSH|SEGMENT, SET, 0, SET, 3s)` — fails because `qtdemux` internally converts segment format from TIME to BYTES, triggering `gst_segment_do_seek: assertion 'segment->format == format'`

  2. **Newsegment events to segmentclip sink pads**: Using `Gst.Event.new_segment(segment)` sent to `vclip.get_static_pad('sink')` after PAUSED — works syntactically but the pipeline never produces output because caps aren't fully negotiated at the event-send point (dynamic pads from `qtdemux` + `decodebin` complicate lifecycle)

  3. **PadProbe-based filtering**: Adding a probe after `videoconvert` that drops buffers outside `[start_ns, stop_ns)` — fails because `decodebin`'s own `pad-added` signal creates link chain issues

  **Correct approach for a future re-attempt:**
  1. Use `decodebin`'s `pad-added` signal to build the pipeline **incrementally** — only link `videosegmentclip` AFTER `decodebin` emits `pad-added` with fully negotiated caps
  2. Set to PAUSED, wait for preroll (all caps negotiated), send `Gst.Event.new_segment(segment)` via a blocking pad probe on `videosegmentclip`'s sink pad, then set to PLAYING
  3. Alternative: use `input-selector` + `output-selector` elements which can clip streams based on segment boundaries without the dynamic-pad complexity
- [x] **Refactor**: `video_preview.py`, `trim_controller.py`, `video_validator.py` to route through backend
- [x] **Refactor remaining files**: `config_tab.py` (detect_and_show_info, _extract_subs_from_video, _extract_track_from_video, _do_extract_track, _get_media_params), `encoding_settings.py` (get_external_audio_info), `tracks_panel.py` (detect_tracks), `dvd_handler.py` (_get_video_duration, _get_title_audio_tracks) — all now route through backend
- [ ] **GStreamer Python bindings for DVD subtitle preview**: Use `gi.repository.Gst` (python3-gi) to create an in-process pipeline that seeks to a timestamp, composites DVD subtitles via `dvdspu`, and captures a single frame to a buffer. Required packages: `python3-gi`, `gstreamer1.0-plugins-bad`. Similar to how HandBrake renders previews internally instead of using a pipe-to-image subprocess.

### Additional GStreamer Filters (Available, Not Yet Integrated)
These GStreamer elements are already installed on the system and could be exposed in the UI. Each needs pipeline construction logic and UI controls added.

**Video effects (creative):**
- [ ] **`coloreffects`**: Color grading presets — heat, sepia, xray, cross-processing, yellow/blue. Could add a combo box dropdown in filters tab.
- [ ] **`agingtv`**: Old TV simulation — scanlines, flicker, color bleed. Retro/vintage effect checkbox.
- [ ] **`warptv`**: Funhouse mirror warping distortion. Creative effect checkbox.
- [ ] **`waterripple`**: Ripple distortion like water surface. Creative overlay checkbox.
- [ ] **`edgetv`**: Edge detection overlay (cartoon-like outlines). Artistic effect checkbox.
- [ ] **`radioactv`**: Glowing radioactive overlay. Cyberpunk/glow aesthetic checkbox.
- [ ] **`streaktv`**: Motion blur/trail effect. Stylized action scenes checkbox.

**Video processing:**
- [ ] **`videomedian`**: Median filter — reduces salt-and-pepper noise without blurring edges. Alternative denoise option.
- [ ] **`videoflip` / `video-direction`**: Rotate/flip video 90°/180°, horizontal/vertical mirror. Buttons in filters tab for phone video correction.
- [ ] **`aspectratiocrop`**: Smart auto-crop to aspect ratio (16:9/4:3/1:1) without black bars. Quick crop mode.

**Audio effects:**
- [ ] **`audioamplify`**: Amplify audio by a factor. Simple volume boost (alternative to `volume` element with dB).
- [ ] **`audiodynamic`**: Compressor/expander with ratio, threshold, soft/hard-knee. Better dynamic range control than FFmpeg's `acompressor`.
- [ ] **`audioecho`**: Delay + feedback echo effect. Creative audio effect checkbox.
- [ ] **`audiokaraoke`**: Voice removal (center channel cancellation) from stereo tracks. Karaoke mode.
- [ ] **`audiopanorama`**: Stereo pan from -1.0 (left) to 1.0 (right). Audio pan slider.
- [ ] **`scaletempo`**: Change playback speed without pitch change. Time-stretching (more relevant for preview/playback than encode).
- [ ] **`audiofirfilter`**: Custom FIR filter for advanced EQ/audio processing. Advanced audio tab (if custom EQ curves are desired).

**Vulkan GPU acceleration (already installed):**
- [ ] **`vulkancolorconvert`**: Vulkan-based color space conversion pipeline.
- [ ] **`vulkanviewconvert`**: Vulkan-based scaling/rotation (GPU alternative to `videoscale` + `videoflip`).
- [ ] **`vulkanoverlaycompositor`**: Vulkan-based overlay compositing for subtitle/preview overlays.

### Unsupported (graceful skip + log warning, already stubbed)
- [x] Trim/clip extraction (falls back to FFmpeg subprocess; native trim via Python bindings is a future task — see Extract clip mode above)
- [x] Fast cut (stream copy)
- [x] delogo, audiocompressor
- [x] deblock, audio denoise (afftdn), dynaudnorm
- [x] CAS, white balance, audio delay, aspect ratio conversion
- [x] Subtitle outline width (textoverlay has no outline width property; only binary on/off)
- [x] Segment joining, subtitle extraction, keyframe alignment
