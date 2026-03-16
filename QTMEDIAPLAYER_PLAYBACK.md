# QMediaPlayer Video Playback Implementation

**Goal**: Replace frame-by-frame FFmpeg playback with QMediaPlayer for smooth video playback, with filter overlay support.

**Started**: 2026-02-21

---

## Phase 1: Core QMediaPlayer Integration

- [x] Create `video_player.py` with QMediaPlayer-based video widget
- [x] Support basic play/pause/stop with QMediaPlayer
- [x] Implement timeline seeking with QMediaPlayer
- [x] Get video duration from QMediaPlayer instead of ffprobe
- [x] Test: Basic video playback works smoothly

---

## Phase 2: Video Widget Setup

- [x] Use QVideoWidget for video display
- [x] Handle video aspect ratio correctly
- [x] Support resizable preview (Small/Medium sizes)
- [x] Display video in "Original" panel
- [ ] Test: Video displays correctly in preview area

---

## Phase 3: Audio Integration

- [x] QMediaPlayer handles audio natively - remove separate AudioPlayer
- [x] Connect volume slider to QMediaPlayer volume
- [x] Connect mute button to QMediaPlayer muted property
- [ ] Test: Audio plays in sync with video

---

## Phase 4: Filter Overlay System

- [x] Create overlay widget that sits on top of video
- [x] Overlay draws processed frame preview (filters applied)
- [x] Use timer to capture current video frame periodically
- [x] Apply filters to captured frame and draw on overlay
- [x] Support subtitle overlay on processed view
- [ ] Test: Filters display in "Processed Preview" panel

---

## Phase 5: Timeline & Controls Integration

- [x] Connect timeline slider to QMediaPlayer position
- [x] Update slider position during playback (signal from QMediaPlayer)
- [x] Handle manual timeline seeking
- [x] Update speed controls to use QMediaPlayer playbackRate
- [x] Preserve cut markers on timeline slider
- [ ] Test: All playback controls work correctly

---

## Phase 6: Dual-View Layout

- [x] Split view: Original (QVideoWidget) | Processed (QLabel with overlay)
- [x] Both views sync to same timeline position
- [x] Handle video loading/unloading
- [ ] Test: Side-by-side comparison works

---

## Phase 7: Cleanup & Optimization

- [ ] Remove old frame-by-frame playback code from video_preview.py
- [ ] Remove AudioPlayer class (no longer needed)
- [ ] Handle edge cases (no video, invalid video, audio-only files)
- [ ] Error handling for unsupported formats
- [ ] Test: App is stable and handles errors gracefully

---

## Key Files to Modify

| File | Changes |
|------|---------|
| `video_player.py` | NEW - QMediaPlayer-based video player |
| `video_preview.py` | Major refactor - use VideoPlayer, add overlay |
| `audio_player.py` | DELETE - no longer needed |
| `controller.py` | Update imports if needed |

---

## Technical Notes

### QMediaPlayer Setup
```python
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

player = QMediaPlayer()
audio_output = QAudioOutput()
player.setAudioOutput(audio_output)
video_widget = QVideoWidget()
player.setVideoOutput(video_widget)
player.setSource(QUrl.fromLocalFile(video_path))
```

### Frame Capture for Filters
- Use QVideoSink to get current frame as QImage
- Apply filters to QImage
- Display in processed preview panel

### Playback Rate
```python
player.setPlaybackRate(1.5)  # 1.5x speed
```

---

## Status

**Current Phase**: Phase 6 Completed (Dual-View Layout)
**Progress**: 70%
