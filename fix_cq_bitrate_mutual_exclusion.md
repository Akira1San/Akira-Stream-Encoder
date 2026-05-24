# Fix: CQ vs Bitrate Mutual Exclusion in FFmpeg Backend

## Goal
Make the FFmpeg backend treat CQ and target bitrate as mutually exclusive, matching the GStreamer backend's existing behavior. Currently, both `-crf`/`-cq` and `-b:v` are passed simultaneously, but ffmpeg ignores `-crf` when `-b:v` is present.

## Problem
- `backends/ffmpeg.py` lines 656-665 **always** add `-crf` or `-cq` regardless of whether a bitrate is set
- `backends/ffmpeg.py` lines 764-776 **independently** add `-b:v` when a bitrate is set
- The UI clears bitrate when CQ slider moves (`encoding_settings.py:951-964`), but does NOT clear CQ when bitrate is manually set
- This means both values can coexist, leading to confusion about which one is actually used

## Files to modify

### `PySide6/backends/ffmpeg.py` (lines ~656-776)
Wrap the CRF/CQ args in an `if/else` that skips them when a bitrate is set:

```python
# Before:
cmd.extend(["-c:v", encoder])
if encoding.use_gpu and "nvenc" in encoder:
    cmd.extend(["-preset", encoding.gpu_preset])
    cmd.extend(["-cq", str(encoding.cq)])
else:
    cmd.extend(["-crf", str(encoding.cq)])
    cmd.extend(["-preset", encoding.cpu_preset])

# After:
cmd.extend(["-c:v", encoder])
bitrate_is_set = encoding.use_original_bitrate or (
    encoding.target_bitrate and encoding.target_bitrate.isdigit() and int(encoding.target_bitrate) > 0
)
if not bitrate_is_set:
    if encoding.use_gpu and "nvenc" in encoder:
        cmd.extend(["-preset", encoding.gpu_preset])
        cmd.extend(["-cq", str(encoding.cq)])
    else:
        cmd.extend(["-crf", str(encoding.cq)])
        cmd.extend(["-preset", encoding.cpu_preset])
```

### `PySide6/encoding_settings.py`
Add these handlers (mirroring the existing `on_cq_changed`):

```python
def on_target_bitrate_changed(self, text):
    if text and text.isdigit() and int(text) > 0:
        self.app_state.encoding.cq = 23  # reset to default
        self.cq_slider.setValue(23)
        self.cq_label.setText("23")

def on_orig_br_changed(self, checked):
    if checked:
        self.app_state.encoding.cq = 23
        self.cq_slider.setValue(23)
        self.cq_label.setText("23")
```

Wire these to the existing signal connections (around lines 946-980).

### `PySide6/backends/gstreamer.py`
- Already correct (uses `if/else`), no changes needed

### `PySide6/handbrake_handler.py`
- Already correct (uses `if/else`), but note the controller only passes CQ — the HandBrake path always uses CQ. Keep this in mind if adding bitrate to HandBrake later.
