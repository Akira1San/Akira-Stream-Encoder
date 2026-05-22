# Fix: Double Subtitle Overlay in Preview Window

## Bug

Two subtitle texts are rendered on top of each other in the preview window, at different font sizes, appearing as a double overlay.

## Root Cause

Subtitle text is rendered **twice** in the preview pipeline:

1. **First render** — `apply_filters()` bakes subtitles into the QImage pixel data via `VideoPreview.draw_subtitle_on_image()`
2. **Second render** — `FilterOverlay.paintEvent()` draws subtitles again on top of the already-subtitled image via `FilterOverlay.draw_subtitle_on_image()`

The two methods use different font sizing, making both layers clearly visible.

## Flow

```
_on_frame_captured() / on_frame_loaded()
  |-> apply_filters(frame)                    # draws subs into image pixels (1st render)
  |     |-> VideoPreview.draw_subtitle_on_image()   # uses raw subs.size (e.g. 24px)
  |     └-> returns image with subs baked in
  |-> filter_overlay.set_image(processed)     # stores image (already has subs)
  |-> filter_overlay.set_subtitle(sub_text)   # stores text, triggers update
  └-> FilterOverlay.paintEvent()
        |-> sees non-empty _subtitle_text
        └-> FilterOverlay.draw_subtitle_on_image()  # draws again (scaled font) (2nd render)
```

## Fix

Remove the first render path. `FilterOverlay` should be the sole owner of subtitle display.

### Changes

**`PySide6/video_preview.py`** — 3 locations:

1. **`apply_filters()` — "no FFmpeg filters" path** (around lines 1431-1451):
   - Remove the SRT lookup + `get_subtitle_text()` + `draw_subtitle_on_image()` call
   - Return plain `image.copy()` like the no-subtitle case

2. **`apply_filters()` — "with FFmpeg filters" path** (around lines 1497-1504):
   - Remove the SRT lookup + `get_subtitle_text()` + `draw_subtitle_on_image()` call
   - Return `image` as-is

3. **`draw_subtitle_on_image()` method** on `VideoPreview` (around lines 1508-1576):
   - This entire method becomes dead code after removing the calls above
   - **Keep it** — the caller (`apply_filters()`) is what gets cleaned up, not the method itself (future-proofing)

No changes needed to `FilterOverlay` — it already handles subtitle rendering correctly.
No changes needed to the callers (`_on_frame_captured`, `on_frame_loaded`) — they already call `self.filter_overlay.set_subtitle()` correctly.

## Files

| File | Lines | Change |
|---|---|---|
| `PySide6/video_preview.py` | ~1442-1451 | Remove subtitle drawing in no-filter path of `apply_filters()` |
| `PySide6/video_preview.py` | ~1497-1504 | Remove subtitle drawing in filter path of `apply_filters()` |
