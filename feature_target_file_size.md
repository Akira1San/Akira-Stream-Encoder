# Feature: Target File Size Input

## Goal
Allow user to input a desired output file size (in MB), and have the app automatically calculate and set the appropriate bitrate to hit that target.

## How it works
1. Add a "Target File Size (MB)" field + "Calculate" button to the encoding settings UI
2. On click, the app probes the input video duration via ffprobe
3. Calculates required total bitrate: `total_bitrate_kbps = target_mb * 8192 / duration_seconds`
4. Subtracts expected audio bitrate: `video_bitrate = total_bitrate - audio_bitrate_for_selected_codec`
5. Sets the result into the `target_bitrate` field and enables 2-pass mode
6. Clears any CQ setting (mutual exclusion)

## Files to modify

### `PySide6/models.py`
- Add `target_file_size_mb: int = 0` field to `EncodingSettings` (optional, could be UI-only state)

### `PySide6/encoding_settings.py`
- Add QSpinBox or QLineEdit for target MB (range ~50-10000)
- Add "Calculate" QPushButton
- Handler:
  - Get duration via `ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 <input>`
  - `bitrate = file_size_mb * 8192 / duration_secs`
  - Subtract audio bitrate (~128-256k depending on codec/config)
  - Set `target_bitrate`, check 2-pass, clear CQ slider
  - Set `use_original_bitrate = False`

### `PySide6/backends/ffmpeg.py`
- No changes needed if 2-pass + `-b:v` already works (it does)

### `PySide6/controller.py`
- No changes needed — passes `app_state` which already contains `target_bitrate`

## Edge cases
- Multiple input files (batch): duration must be handled per-file or averaged
- Audio bitrate unknown: assume a default or probe the source audio bitrate
- Calculated bitrate below codec minimum: warn user
- Target too large/small for video duration: clamp or warn
