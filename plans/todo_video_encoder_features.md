# Video Encoder Features — TODO

## ✅ Done

### 1. Quick audio-copy toggle button (one-shot)

**Feature**: A one-shot **Auto** button next to the Video mode combo.  
Clicking it sets Audio Mode (in Advanced Encoding Settings) to match the current Video mode.

- Button added after the Video `[Encode/Copy]` combo in `encoding_settings.py`
- One-shot (not a toggle): each click syncs audio to video
- Tooltip: *"Set audio mode (Advanced section) to match current video mode"*

**Files**: `encoding_settings.py` only

### 2. Audio Channels exposed in Advanced Settings

**Feature**: New **Audio Channels** combo in the Advanced Encoding Settings section,  
defaulting to `2 (Stereo)`. Options: `1 (Mono)`, `2 (Stereo)`, `6 (5.1)`, `8 (7.1)`.

- Field `audio_channels: str = "2"` added to `EncodingSettings` in `models.py`
- Combo added after Audio Codec row in `encoding_settings.py`
- Helper `_audio_channels_args()` added to `FFmpegBackend` in `backends/ffmpeg.py`
- All 12 hardcoded `-ac 2 -channel_layout stereo` occurrences replaced with the helper

**Files**: `models.py`, `encoding_settings.py`, `backends/ffmpeg.py`

### 3. AI Colorization (Phase 1 + SIGGRAPH17)

**Feature**: Deep learning-based video colorization using ECCV16 and SIGGRAPH17 models.

- `PySide6/colorizers/` package with `base.py` (ABC), `eccv16.py`, `siggraph17.py`, `utils.py`
- ECCV16: lightweight CNN, ~3.5M params, runs on CPU/GPU (~0.021s/batch@256x256)
- SIGGRAPH17: UNet, ~40M params, better quality, richer colors (~0.048s/batch@256x256)
- Pipe-based pipeline: FFmpeg rawvideo → AI colorizer (batch GPU) → FFmpeg encode + audio passthrough
- Disk-based pipeline: Extract → Colorize → Recombine with pipeline buttons in UI panel
- Post-processing: saturation (0.1–2.0), contrast (0.5–2.0), denoise (0–5)
- `AIColorizationSettings` dataclass in `models.py`, wired to `AppState`
- Weights downloaded to `PySide6/colorizers/models/` (gitignored)
- Single-image test script: `test/test_colorize_image.py`

**Files**: `PySide6/colorizers/` (5 files), `controller.py`, `models.py`, `color_correction.py`, `test/test_colorize_image.py`

---

## ❌ Remaining

### 3. Encoding presets combobox and dialog

Add an encoding presets system:

- A **presets combobox** + **manage/save button** placed after the Video `[Encode/Copy]` combo
- Clicking the manage button opens a dialog where the user can tweak all encoding settings
- The user types a name and clicks "Add" / "Save" to create a new preset
- Presets are persisted in `settings.json` under a `video_presets` key
- Selecting a preset from the combobox applies all stored settings
- Selecting a built-in "Default" option resets to app defaults
