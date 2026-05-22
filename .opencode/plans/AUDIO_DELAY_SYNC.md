# Add Audio Delay/Sync Control

## Problem

Some video files have audio ahead of the video (audio plays earlier than corresponding video frames). Users need a control to add a delay to the audio stream to re-sync it.

## FFmpeg Solution

The `adelay` filter delays audio by N milliseconds:

```bash
# Delay audio by 500ms:
-af "adelay=500|500"    # 500ms on both left/right channels
```

For stereo: `adelay=500|500` (one value per channel).
For mono: `adelay=500` (single value).
FFmpeg auto-duplicates for matching channel count.

## GStreamer Solution

GStreamer uses `audiodelay` element:

```bash
gst-launch-1.0 ... ! audiodelay delay=500000000 ! ...   # delay in nanoseconds
```

Or via `audioqueue` with `min-threshold-time`.

## Architecture

### Model changes (`PySide6/models.py`)

Add to `FilterSettings` (after `audio_compressor`, line 129):

```python
# Audio delay/sync
audio_delay_enabled: bool = False
audio_delay_ms: int = 0       # milliseconds, 0 = no delay
```

### Controller changes (`PySide6/controller.py`)

Add to `build_filter_complex()` after the audio compressor block (before `return`, around line 950):

```python
# Audio Delay (sync)
if getattr(self.app_state.filters, 'audio_delay_enabled', False):
    delay_ms = self.app_state.filters.audio_delay_ms
    if delay_ms > 0:
        # Repeat delay value for each channel (FFmpeg needs N values for N channels)
        # adelay auto-duplicates if only one value given
        audio_filters.append(f"adelay={delay_ms}|{delay_ms}")
        self.app_state.log(f"Audio: Delaying by {delay_ms}ms", "INFO")
```

### UI changes (`PySide6/filters.py`)

Add after the Audio Compressor checkbox (around line 408), before the audio group closes:

```python
# Audio Delay / Sync
delay_layout = QHBoxLayout()
self.audio_delay_check = QCheckBox("Audio Delay:")
self.audio_delay_check.setChecked(self.app_state.filters.audio_delay_enabled)
self.audio_delay_check.setToolTip(
    "Delay audio to sync with video.\n"
    "Use when audio plays ahead of video.\n"
    "Values: 100-500ms for minor sync, 1000ms+ for major offset."
)
delay_layout.addWidget(self.audio_delay_check)

self.audio_delay_spin = QSpinBox()
self.audio_delay_spin.setRange(0, 10000)    # 0ms to 10 seconds
self.audio_delay_spin.setValue(self.app_state.filters.audio_delay_ms)
self.audio_delay_spin.setSuffix(" ms")
self.audio_delay_spin.setSingleStep(50)     # 50ms steps for fine tuning
self.audio_delay_spin.setEnabled(self.app_state.filters.audio_delay_enabled)
self.audio_delay_spin.setMinimumWidth(100)
self.audio_delay_spin.setToolTip(
    "Delay in milliseconds (0 = no delay).\n"
    "Common values:\n"
    "  100ms: Very slight sync fix\n"
    "  250ms: Minor offset\n"
    "  500ms: Notable offset\n"
    "  1000ms: Audio is ~1 second ahead\n"
    "  2000ms+: Major offset"
)
delay_layout.addWidget(self.audio_delay_spin)
delay_layout.addStretch()
audio_layout.addLayout(delay_layout)
```

### Signal connections (`filters.py`)

Add after line 459:

```python
self.audio_delay_check.toggled.connect(self.on_audio_delay_changed)
self.audio_delay_spin.valueChanged.connect(self.on_audio_delay_value_changed)
```

### Handler methods (`filters.py`)

Add after `on_compressor_changed` (after line 665):

```python
def on_audio_delay_changed(self, checked):
    self.app_state.filters.audio_delay_enabled = checked
    self.audio_delay_spin.setEnabled(checked)
    self.settings_changed.emit()

def on_audio_delay_value_changed(self, value):
    self.app_state.filters.audio_delay_ms = value
    self.settings_changed.emit()
```

### Reset function (`filters.py`)

Add to `reset_filters()` after line 707, and UI reset after line 764:

```python
# Model reset (after line 707):
self.app_state.filters.audio_delay_enabled = False
self.app_state.filters.audio_delay_ms = 0

# UI reset (after line 764):
self.audio_delay_check.setChecked(False)
self.audio_delay_spin.setValue(0)
self.audio_delay_spin.setEnabled(False)
```

## Edge Cases

| Scenario | Behavior |
|---|---|
| delay=0 or disabled | No filter added, no change |
| Audio copy mode (not re-encode) | `adelay` filter not applied (`-c:a copy` skips `-af` entirely). User needs to switch to encode mode. Log a warning. |
| External audio file | Delay applies to mapped audio stream normally |
| GStreamer backend | Use `audiodelay delay=NANOSECONDS` instead of `adelay` |
| Negative delay (audio behind video) | Not currently supported. `adelay` only pushes audio later. For negative, would need `setpts=PTS+delay/TB` on video. Document this limitation. |

## Files

| File | Change |
|---|---|
| `PySide6/models.py` | Add `audio_delay_enabled`, `audio_delay_ms` to `FilterSettings` |
| `PySide6/filters.py` | Add checkbox + spinbox UI, signal connections, handlers, reset |
| `PySide6/controller.py` | Add `adelay` filter in `build_filter_complex()` |
