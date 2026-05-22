# DVD Subtitle Support via HandBrakeCLI

## Problem

DVD subtitles (`dvd_subtitle` bitmap format inside MPEG-2 VOBs) cannot be burned into video using FFmpeg or GStreamer CLI. The concat demuxer hides subtitle streams, and direct overlay is unreliable. Currently the app logs: *"Use HandBrake or mencoder"* and skips.

HandBrakeCLI v1.9.2 is now installed and handles this natively.

---

## How HandBrakeCLI handles DVD subtitles

HandBrake reads DVD structures (VOB/IFO) directly and understands DVD subtitle streams. Key commands:

**Scan for subtitle tracks:**
```bash
HandBrakeCLI -i /path/to/VIDEO_TS -t 1 --scan 2>/dev/null
# Output includes:
#   + subtitle tracks:
#     + 1, English (track 0, id 0x20) VOBSUB
```

**Encode with subtitle burn-in:**
```bash
HandBrakeCLI -i /path/to/VIDEO_TS -t 1 \
  --subtitle 1 --subtitle-burned \
  -o output.mp4
```

**Encode with subtitle passthrough (not burned, just muxed):**
```bash
HandBrakeCLI -i /path/to/VIDEO_TS -t 1 \
  --subtitle 1 \
  -o output.mp4
```

**Encode with external subtitle file burned:**
```bash
HandBrakeCLI -i input.mp4 \
  --subtitle /path/to/sub.srt --subtitle-burned \
  -o output.mp4
```

---

## Integration Architecture

### New file: `PySide6/handbrake_handler.py`

Class `HandBrakeHandler` encapsulating all HandBrakeCLI operations.

**Methods:**
```python
class HandBrakeHandler:
    def __init__(self, handbrake_path: str, log_callback: Callable):
        ...

    def scan_titles(self, dvd_path: str) -> List[dict]:
        """Run --scan on VIDEO_TS folder, return list of title info dicts"""
        ...

    def scan_subtitles(self, dvd_path: str, title_number: int) -> List[dict]:
        """Get subtitle tracks for a specific title"""
        ...

    def encode_with_subs(self, input_path: str, output_path: str,
                         title_number: int,
                         subtitle_track: int,
                         burn: bool = True,
                         video_encoder: str = "x264",
                         quality: int = 23,
                         audio_track: int = 1,
                         **kwargs) -> subprocess.Popen:
        """Encode video with subtitle burn-in using HandBrakeCLI"""
        ...

    def check_available(self) -> bool:
        """Check if HandBrakeCLI is on PATH and runnable"""
        ...
```

### Workflow: DVD import with subtitles

Current flow:
```
User clicks "Open DVD" in Config tab
  -> DVDHandler scans titles (ffprobe/ffmpeg)
  -> Title selection dialog
  -> Concatenates VOBs into concat file
  -> Sets app_state.dvd flags
  -> Switches to Video tab for encoding
```

New flow (when HandBrake is available):
```
User clicks "Open DVD" in Config tab
  -> DVDHandler scans titles (ffprobe/ffmpeg)  -- same
  -> Title selection dialog                      -- same
  -> User selects title
  -> NEW: Check if HandBrakeCLI is available
  -> NEW: If yes, store DVD folder path for HandBrake-based encoding
  -> NEW: If no, fall back to current FFmpeg-only (subs skipped)
  -> Switches to Video tab
```

### Encoding flow change

Current:
```
User clicks "Start Encoding"
  -> VideoController.encode_file()
  -> Checks dvd.selected_subtitle_index >= 0
  -> Logs "not supported, skipping" if true
  -> build_ffmpeg_command() -> subprocess.Popen(ffmpeg)
```

New (when DVD subs requested + HandBrake available):
```
User clicks "Start Encoding"
  -> VideoController.encode_file()
  -> Checks dvd.selected_subtitle_index >= 0
  -> NEW: if HandBrake available:
       -> handbrake_handler.encode_with_subs(
            dvd_folder=dvd_folder,
            title_number=selected_title,
            subtitle_track=selected_sub_track,
            burn=True,
            video_encoder=map_to_handbrake_encoder(app_state.encoding.encoder),
            quality=app_state.encoding.cq,
            ...
          )
       -> Parse progress from HandBrake stderr (different format from ffmpeg)
  -> NEW: if HandBrake not available:
       -> Log "install HandBrake for DVD subs" (current behavior)
```

---

## HandBrake Encoder Mapping

| App encoder | HandBrake encoder | Notes |
|---|---|---|
| `h264_nvenc` | `nvenc_h264` | |
| `hevc_nvenc` | `nvenc_h265` | |
| `libx264` | `x264` | |
| `libx265` | `x265` | |
| `copy` (video passthrough) | Not supported by HandBrake | Stay on FFmpeg in this case |

Other setting mappings (from AppState -> HandBrakeCLI args):

| App setting | HandBrake flag |
|---|---|
| `cq` (quality) | `-q` |
| `resolution` | `--width W --height H` |
| `framerate` | `-r` |
| `target_bitrate` | `-b` |
| `audio_mode: encode` | `-E aac -B 128` |
| `audio_mode: copy` | `-E copy` |
| `container` | `-f mp4` / `-f mkv` |

Unsupported HandBrake features (fall back to FFmpeg):
- Deinterlace (handbrake has `--deinterlace` but simpler)
- Smart crop / AR conversion (handbrake has `--crop` but different API)
- Scale algorithms (handbrake just scales, no algorithm choice)
- Audio filters (volume, denoise, compressor)
- Subtitle styling (handbrake burns as-is)

**Strategy**: Only use HandBrake when:
1. DVD source is detected (`app_state.dvd.is_dvd_source`)
2. Subtitle burn is requested (`app_state.dvd.selected_subtitle_index >= 0`)
3. Video mode is encode (not copy)
4. HandBrakeCLI is available

Otherwise, keep using FFmpeg.

---

## Progress Parsing

HandBrakeCLI outputs progress differently from FFmpeg:

```
Encoding: task 1 of 1, 12.34 % (21.45 fps, avg 20.12 fps, ETA 00h05m23s)
```

Parse with regex: `r"(\d+\.?\d*)\s*%"` — extract percentage from lines containing "Encoding:".

---

## UI Changes

### `PySide6/subtitles.py`

The existing DVD subtitle combo (`dvd_subtitle_combo`) already works for track selection. Need to add:

- A label showing "HandBrakeCLI available" / "HandBrakeCLI not installed" status
- Disable subtitle selection if HandBrake is not available (or keep the current skip behavior)

### `PySide6/config_tab.py`

- Optionally add a HandBrake path config in System Paths (auto-detect on startup)
- Currently `handbrake-cli` package installs to `/usr/bin/HandBrakeCLI`

---

## Files to Modify

| File | Action | Change |
|---|---|---|
| `PySide6/handbrake_handler.py` | **New** | HandBrakeCLI wrapper class |
| `PySide6/models.py` | Modify | Add `_handbrake_path` property to AppState |
| `PySide6/config.py` | Modify | Add `HANDBRAKE` constant |
| `PySide6/main_window.py` | Modify | Persist handbrake_path in settings |
| `PySide6/config_tab.py` | Modify | Optional HandBrake path config |
| `PySide6/controller.py` | Modify | Route DVD subtitle encoding to HandBrake handler |
| `PySide6/subtitles.py` | Modify | Show HandBrake availability status |
| `PySide6/settings.json` | Modify | Add `handbrake_path` field |

---

## Feature Detection

```python
def check_handbrake() -> bool:
    """Check if HandBrakeCLI is available and working"""
    import subprocess, shutil
    path = shutil.which("HandBrakeCLI")
    if not path:
        return False
    try:
        result = subprocess.run(
            [path, "--version"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False
```

Run on app startup, store result in `app_state._handbrake_available` for quick checks.

---

## Implementation Order

1. Create `handbrake_handler.py` with `scan_titles()`, `scan_subtitles()`, `encode_with_subs()`
2. Add `handbrake_path` / `handbrake_available` to AppState
3. Add HandBrake path to config.py and settings.json persistence
4. Modify `VideoController.encode_file()`:
   - Check if DVD source + subtitle selected
   - If yes + HandBrake available -> delegate to HandBrakeHandler.encode_with_subs()
   - If yes + HandBrake not available -> log current skip message
   - Parse HandBrake progress output
5. Update subtitles UI to show HandBrake availability
6. Test with a real DVD folder

---

## Testing

1. Scan a DVD folder -> verify subtitle tracks are detected
2. Encode DVD with subtitle track 1 burned in -> verify subs appear in output
3. Encode DVD with "None" subtitles -> verify FFmpeg path used (no subs)
4. Encode DVD without HandBrake installed -> verify current skip message shown
5. Non-DVD file with external SRT subs -> verify FFmpeg path used (unchanged)
6. DVD + video copy mode -> verify FFmpeg path used (HandBrake doesn't support copy)
