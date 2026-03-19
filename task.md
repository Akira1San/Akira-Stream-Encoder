# Task: Add Preview Size Selector ✅ DONE

## Overview
Add a combobox to let users pick the preview window size for both original and processed video panels.

## Files to Modify
- `PySide6/video_preview.py`
- `PySide6/video_workspace.py` (optional - adjust splitter ratio)

## Implementation Details

### 1. In `video_preview.py` - Add Size ComboBox

Add to `setup_ui()` in the playback_layout section (after speed_combo):

```python
playback_layout.addWidget(QLabel("Preview:"))
self.size_combo = QComboBox()
self.size_combo.addItems(["Small", "Medium", "Large", "X-Large"])
self.size_combo.setCurrentText("Medium")  # Default to Medium
self.size_combo.currentTextChanged.connect(self.on_size_changed)
self.size_combo.setMaximumWidth(80)
playback_layout.addWidget(self.size_combo)
```

Add handler method:

```python
def on_size_changed(self, size_text):
    sizes = {
        "Small": (320, 180),
        "Medium": (480, 270),
        "Large": (640, 360),
        "X-Large": (800, 450)
    }
    w, h = sizes.get(size_text, (480, 270))
    self.original_label.setMinimumSize(w, h)
    self.processed_label.setMinimumSize(w, h)
```

### 2. In `video_preview.py` - Update Default Minimum Size

Change line 333 and 346 from:
```python
self.original_label.setMinimumSize(320, 180)
self.processed_label.setMinimumSize(320, 180)
```
To:
```python
self.original_label.setMinimumSize(480, 270)  # Medium default
self.processed_label.setMinimumSize(480, 270)  # Medium default
```

### 3. Optional: In `video_workspace.py` - Adjust Splitter Ratio

Change line 138 from:
```python
main_splitter.setSizes([400, 800])
```
To:
```python
main_splitter.setSizes([350, 900])  # More space for preview
```

## Size Options Reference
| Label   | Width | Height | Aspect Ratio |
|---------|-------|--------|--------------|
| Small   | 320   | 180    | 16:9         |
| Medium  | 480   | 270    | 16:9         |
| Large   | 640   | 360    | 16:9         |
| X-Large | 800   | 450    | 16:9         |

## Testing
1. Launch application and load a video
2. Verify preview shows at Medium size by default
3. Change size via dropdown - verify both panels resize
4. Verify aspect ratio is maintained when resizing

---

# Task: Add Audio Normalization Options ✅ DONE

## Overview
Add dynamic audio normalizer and audio compressor options to help balance quiet dialogue with loud music/noise.

## Files to Modify
- `PySide6/models.py` - Add new filter settings
- `PySide6/filters.py` - Add UI controls
- `PySide6/controller.py` - Apply filters in FFmpeg command

## Implementation Details

### 1. In `models.py` - Add FilterSettings fields

In the `FilterSettings` dataclass (around line 66), add:

```python
# Audio normalization
audio_dynnorm: bool = False  # Dynamic audio normalizer
audio_compressor: bool = False  # Audio compressor
```

### 2. In `filters.py` - Add UI Controls

In `setup_ui()`, add to the audio_layout section (after volume controls, before `layout.addWidget(audio_group)`):

```python
# Dynamic Audio Normalizer
self.dynnorm_check = QCheckBox("Dynamic Normalizer (dynaudnorm)")
self.dynnorm_check.setChecked(self.app_state.filters.audio_dynnorm)
self.dynnorm_check.setToolTip(
    "Dynamically normalize audio volume.\n"
    "Best for videos with quiet dialogue and loud music.\n"
    "Automatically boosts quiet parts and reduces loud parts."
)
audio_layout.addWidget(self.dynnorm_check)

# Audio Compressor
self.compressor_check = QCheckBox("Audio Compressor (acompressor)")
self.compressor_check.setChecked(self.app_state.filters.audio_compressor)
self.compressor_check.setToolTip(
    "Reduce dynamic range of audio.\n"
    "Makes quiet sounds louder and loud sounds quieter.\n"
    "Good for dialogue clarity in movies/TV shows."
)
audio_layout.addWidget(self.compressor_check)
```

In `connect_signals()`, add:

```python
self.dynnorm_check.toggled.connect(self.on_dynnorm_changed)
self.compressor_check.toggled.connect(self.on_compressor_changed)
```

Add handler methods:

```python
def on_dynnorm_changed(self, checked):
    """Handle dynamic normalizer checkbox change"""
    self.app_state.filters.audio_dynnorm = checked
    self.settings_changed.emit()

def on_compressor_changed(self, checked):
    """Handle audio compressor checkbox change"""
    self.app_state.filters.audio_compressor = checked
    self.settings_changed.emit()
```

### 3. In `controller.py` - Apply FFmpeg Filters

In `build_filter_complex()` method (around line 438), add after the volume filter:

```python
# Dynamic Audio Normalizer
if self.app_state.filters.audio_dynnorm:
    audio_filters.append("dynaudnorm=f=150:g=15:r=0.95")

# Audio Compressor
if self.app_state.filters.audio_compressor:
    audio_filters.append("acompressor=threshold=0.15:ratio=3:attack=20:release=250")
```

## FFmpeg Filter Parameters Reference

### dynaudnorm (Dynamic Audio Normalizer)
| Parameter | Value | Description |
|-----------|-------|-------------|
| f | 150 | Frame length (ms) |
| g | 15 | Gaussian filter window size |
| r | 0.95 | Target peak level (0.95 = -0.5dB) |

### acompressor (Audio Compressor)
| Parameter | Value | Description |
|-----------|-------|-------------|
| threshold | 0.15 | Level above which compression starts |
| ratio | 3 | Compression ratio (3:1) |
| attack | 20 | Attack time (ms) - how fast compression starts |
| release | 250 | Release time (ms) - how fast compression stops |

## Testing
1. Load a video with quiet dialogue and loud music
2. Enable "Dynamic Normalizer" - verify dialogue is boosted
3. Enable "Audio Compressor" - verify dynamic range is reduced
4. Test both together - they can be combined
5. Verify encoding completes without errors

---

# Task: Code Review - Uncommitted Changes ✅ DONE

## Overview
Review uncommitted changes (staged and unstaged) on the `master` branch.

**Note:** The project has two codebases:
- **Root folder** - OLD tkinter-based code (legacy)
- **PySide6 folder** - NEW PySide6-based code (active development)

## Files Reviewed

### NEW PySide6 Code (PySide6 folder)
- `PySide6/video_preview.py` - Audio player integration
- `PySide6/video_workspace.py` - NLE tab addition
- `PySide6/audio_player.py` - New audio player component
- `PySide6/nle/` - New NLE module
- `PySide6/video_validator.py` - Video validation

### OLD Legacy Code (root folder)
- `main.py` - OLD tkinter application (has syntax error)
- `video_validator.py` - Audio validation methods added
- `video_tab.py` - Backward compatibility module
- `zve5.py` - VOB file support added

## Issues Found

### CRITICAL (OLD Code - Legacy)
| File | Line | Issue |
|------|------|-------|
| main.py | 145 | Duplicate docstring causing SyntaxError (OLD tkinter code) |

### WARNINGS (NEW PySide6 Code)
| File | Line | Issue |
|------|------|-------|
| PySide6/video_preview.py | 18 | Use relative import for audio_player |

### WARNINGS (OLD Legacy Code)
| File | Line | Issue |
|------|------|-------|
| video_validator.py | 287 | Import datetime at module level |
| video_validator.py | 236 | Import json at module level |

## Recommendation
The critical syntax error is in the OLD legacy tkinter code (`main.py`), not the new PySide6 code. The new PySide6 application in the `PySide6/` folder should work correctly. The legacy code issue can be ignored if only the PySide6 version is being used.

## Status
Review completed. User will fix issues manually.

---

# Task: Fix Subtitle Shadow Rendering in Encoded Output ✅ DONE

## Overview
Fixed subtitle shadow rendering not appearing in encoded output files when shadow was enabled in the UI.

## Root Cause
In `PySide6/controller.py`, the `build_subtitle_filter` method was not setting the required `BorderStyle=2` for shadow rendering in SSA/ASS subtitles. Without this BorderStyle, FFmpeg could not render shadows regardless of other shadow parameters being present.

## Files Modified
- `PySide6/controller.py` - Fixed shadow rendering logic in `build_subtitle_filter` method

## Implementation Details

### 1. In `PySide6/controller.py` - Fixed `build_subtitle_filter` method (lines 892-913):

**Before (broken):**
```python
# Shadow settings
if subs.shadow_enabled:
    # Only set BorderStyle if we want opaque background
    # BorderStyle=3 creates shadow but also solid background
    # Don't override BorderStyle when bg_opacity=0
    if subs.bg_opacity > 0.0 and "BorderStyle=4" not in style:
        style.append("BorderStyle=3")  # 3 = outline + shadow
    # Ensure there's an outline width (required for shadow to be visible)
    if subs.outline_width == 0:
        style.append("Outline=1")
    # Shadow color with opacity
    shadow_ass = self.hex_to_ass(subs.shadow_color, subs.shadow_opacity)
    style.append(f"Shadow={shadow_ass}")
    # Shadow offset X
    if subs.shadow_offset_x != 2:
        style.append(f"ShadowX={subs.shadow_offset_x}")
    # Shadow offset Y
    if subs.shadow_offset_y != 2:
        style.append(f"ShadowY={subs.shadow_offset_y}")
```

**After (fixed):**
```python
# Shadow and background settings (mutually exclusive in BorderStyle)
if subs.shadow_enabled:
    style.append("BorderStyle=2")  # 2 = outline + shadow
elif subs.bg_opacity > 0.0:
    style.append("BorderStyle=4")  # 4 = opaque box
else:
    style.append("BorderStyle=1")  # 1 = outline only (default)

# Ensure there's an outline width (required for shadow to be visible)
if subs.shadow_enabled and subs.outline_width == 0:
    style.append("Outline=1")

# Shadow color with opacity (only if shadow is enabled)
if subs.shadow_enabled:
    shadow_ass = self.hex_to_ass(subs.shadow_color, subs.shadow_opacity)
    style.append(f"Shadow={shadow_ass}")
    # Shadow offset X
    if subs.shadow_offset_x != 0:  # Default is 0, not 2
        style.append(f"ShadowX={subs.shadow_offset_x}")
    # Shadow offset Y
    if subs.shadow_offset_y != 0:  # Default is 0, not 2
        style.append(f"ShadowY={subs.shadow_offset_y}")
```

## Key Fixes:
1. **Correct BorderStyle**: Set `BorderStyle=2` (outline + shadow) when shadow is enabled
2. **Proper defaults**: Shadow offset defaults are 0, not 2
3. **Mutual exclusion**: Shadow and background BorderStyle are now properly mutually exclusive
4. **Outline requirement**: Ensured outline width ≥1 when shadow is enabled (required for visibility)
5. **Conditional application**: Shadow color/offset only applied when shadow is actually enabled

## Testing
1. Enable the "Enable Shadow" checkbox in the Subtitles panel
2. Configure shadow color, offset (X/Y), and opacity as desired
3. Encode a video with burned-in subtitles
4. Verify the output shows shadows behind the subtitle text

## Verification
The fix was verified by:
- Manual FFmpeg testing showing shadows work with correct BorderStyle
- Code review confirming the fix addresses the missing BorderStyle=2 requirement
- Validation that the generated FFmpeg command now includes proper shadow parameters

---
