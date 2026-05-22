# Fix: Preview Playback Freezes for ~15 Seconds on Play

## Problem

Pressing Play on the Original preview causes ~15 second pauses. The Processed preview timer fires every 500ms and each update runs a synchronous `subprocess.run(ffmpeg)` on the main thread via `apply_filters()`, blocking the entire UI (including QMediaPlayer playback).

## Fix: Freeze Processed Preview During Playback

**The Processed preview is for checking filter settings — it doesn't need real-time updates during playback.** On pause, we refresh it once.

### Changes in `PySide6/video_preview.py`

#### 1. `on_play_clicked()` — stop the overlay timer

Current (line 1601):
```python
def on_play_clicked(self):
    ...
    self._video_player.seek(position)
    self._video_player.play()
    self._overlay_timer.start()       # <-- BAD: triggers FFmpeg every 500ms
    ...
```

New:
```python
def on_play_clicked(self):
    ...
    self._overlay_timer.stop()        # stop updates during playback
    self._video_player.seek(position)
    self._video_player.play()
    # Show a brief "frozen" indicator on the overlay
    self.filter_overlay.set_frozen(True)
```

#### 2. `on_pause_clicked()` — refresh processed preview once

Current (line 1664):
```python
def on_pause_clicked(self):
    self.is_playing = False
    self._is_user_seeking = False
    self._overlay_timer.stop()
    self._video_player.pause()
    ...
```

New:
```python
def on_pause_clicked(self):
    self.is_playing = False
    self._is_user_seeking = False
    self._overlay_timer.stop()
    self._video_player.pause()
    self.filter_overlay.set_frozen(False)
    # Refresh processed preview at paused position
    current_pos = self._video_player.get_position()
    self.seek_preview(current_pos)
```

#### 3. `on_stop_clicked()` — no change needed

Already calls `seek_preview(0)` which refreshes the processed frame.

#### 4. `_update_filter_overlay()` — optional: remove or keep for non-playback

This method becomes dead code during playback (timer is stopped). Can keep for future use or remove.

#### 5. `FilterOverlay` — add frozen indicator

Add a faint overlay message: `"Preview frozen during playback\nResumes on pause"` so the user understands why the processed preview isn't updating.

New method:
```python
class FilterOverlay(QWidget):
    def __init__(self, ...):
        ...
        self._frozen = False

    def set_frozen(self, frozen: bool):
        self._frozen = frozen
        self.update()

    def paintEvent(self, event):
        ...
        if self._frozen:
            painter.setPen(QColor(128, 128, 128, 180))
            painter.setFont(QFont("Arial", 10))
            painter.drawText(rect, Qt.AlignCenter,
                "Preview frozen during playback\nChanges apply on pause")
```

#### 6. `_on_frame_captured()` — skip during playback

The QVideoSink frame capture path can be skipped if we're playing (no point processing frames we won't display):

```python
def _on_frame_captured(self, frame: QImage):
    if frame.isNull() or self.is_playing:
        return
    processed = self.apply_filters(frame)
    ...
```

## Edge Cases

| Scenario | Behavior |
|---|---|
| User presses Play | Processed preview freezes, Original plays smooth |
| User changes filter settings during playback | No visible change (frozen message shown) |
| User pauses | Processed preview refreshes at current position with new filters applied |
| User scrubs timeline during playback | Timeline seek → seek_preview() refreshes processed frame |
| User scrubs timeline while paused | Already works (calls seek_preview) |
| User changes filter settings while paused | settings_changed → refresh_preview() → seek_preview() → processed updates |

## Files

| File | Line | Change |
|---|---|---|
| `PySide6/video_preview.py` | ~1601 `on_play_clicked()` | Stop timer, set frozen flag |
| `PySide6/video_preview.py` | ~1664 `on_pause_clicked()` | Call seek_preview(), clear frozen flag |
| `PySide6/video_preview.py` | ~1038 `_on_frame_captured()` | Return early if playing |
| `PySide6/video_preview.py` | ~472 `FilterOverlay` | Add `set_frozen()` + frozen message in paintEvent |
