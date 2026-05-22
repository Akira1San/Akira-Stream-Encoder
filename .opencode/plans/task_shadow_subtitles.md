# Add Shadow Support to Subtitles

## Overview
Implement shadow effect for burned-in subtitles by adding shadow controls to the subtitle settings panel and updating FFmpeg command generation.

## Related Files
- `PySide6/models.py` - Contains SubtitleSettings dataclass
- `PySide6/subtitles.py` - Subtitle settings UI panel
- FFmpeg command generation logic (to be located)

## Tasks

### 1. Update Subtitle Settings Model
- [ ] Add shadow properties to `SubtitleSettings` class in `models.py`:
  - `shadow_enabled: bool = False`
  - `shadow_color: str = "#000000"`
  - `shadow_offset_x: int = 2`  # Horizontal shadow offset
  - `shadow_offset_y: int = 2`  # Vertical shadow offset
  - `shadow_opacity: float = 0.5`  # Shadow opacity (0.0-1.0)

### 2. Add Shadow Controls to UI
- [ ] Add shadow controls to `SubtitlesPanel.setup_ui()` in `subtitles.py`:
  - Shadow enable checkbox
  - Shadow color button (similar to text/outline/bg color buttons)
  - Shadow offset controls (X and Y sliders with labels)
  - Shadow opacity slider

### 3. Connect Shadow Signals
- [ ] Connect shadow UI controls to handler methods in `SubtitlesPanel.connect_signals()`
- [ ] Implement handler methods for shadow property changes:
  - `on_shadow_changed()`
  - `on_shadow_color_clicked()`
  - `on_shadow_offset_x_changed()`
  - `on_shadow_offset_y_changed()`
  - `on_shadow_opacity_changed()`

### 4. Update FFmpeg Command Generation
- [ ] Locate where subtitle FFmpeg filters are generated
- [ ] Update subtitle filter string to include shadow parameters when shadow is enabled:
  - Example: `subtitles=file.srt:force_style='OutlineColour=&H80000000,BorderStyle=3,Shadow=&H80000000,ShadowX=2,ShadowY=2'`
  - Research proper ASS subtitle shadow syntax
  - Ensure shadow parameters are only added when `shadow_enabled` is True

### 5. Update State Synchronization
- [ ] Ensure shadow properties are properly loaded from/saved to AppState
- [ ] Verify shadow settings persist between sessions

### 6. Testing
- [ ] Test shadow functionality with various subtitle formats
- [ ] Verify shadow appears correctly in encoded output
- [ ] Test with and without shadow enabled
- [ ] Verify performance impact is minimal

## Notes
- Shadow effect in FFmpeg subtitles is typically implemented through ASS subtitle styling parameters
- Need to research proper syntax for shadow in FFmpeg subtitles filter
- May need to handle different subtitle formats differently (SRT vs ASS vs etc.)
- Should maintain consistency with existing UI patterns in the subtitles panel

## Dependencies
- None beyond existing subtitle functionality