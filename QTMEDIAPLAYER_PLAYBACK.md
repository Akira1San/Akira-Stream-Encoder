# QMediaPlayer Video Playback Implementation

**Goal**: Replace frame-by-frame FFmpeg playback with QMediaPlayer for smooth video playback, with filter overlay support.

**Started**: 2026-02-21

---

## Phase 1: Core QMediaPlayer Integration

- [ ] Create `video_player.py` with QMediaPlayer-based video widget
- [ ] Support basic play/pause/stop with QMediaPlayer
- [ ] Implement timeline seeking with QMediaPlayer
- [ ] Get video duration from QMediaPlayer instead of ffprobe
- [ ] Test: Basic video playback works smoothly

---

## Phase 2: Video Widget Setup

- [ ] Use QVideoWidget for video display
- [ ] Handle video aspect ratio correctly
- [ ] Support resizable preview (Small/Medium sizes)
- [ ] Display video in "Original" panel
- [ ] Test: Video displays correctly in preview area

---

## Phase 3: Audio Integration

- [ ] QMediaPlayer handles audio natively - remove separate AudioPlayer
- [ ] Connect volume slider to QMediaPlayer volume
- [ ] Connect mute button to QMediaPlayer muted property
- [ ] Test: Audio plays in sync with video

---

## Phase 4: Filter Overlay System

- [ ] Create overlay widget that sits on top of video
- [ ] Overlay draws processed frame preview (filters applied)
- [ ] Use timer to capture current video frame periodically
- [ ] Apply filters to captured frame and draw on overlay
- [ ] Support subtitle overlay on processed view
- [ ] Test: Filters display in "Processed Preview" panel

---

## Phase 5: Timeline & Controls Integration

- [ ] Connect timeline slider to QMediaPlayer position
- [ ] Update slider position during playback (signal from QMediaPlayer)
- [ ] Handle manual timeline seeking
- [ ] Update speed controls to use QMediaPlayer playbackRate
- [ ] Preserve cut markers on timeline slider
- [ ] Test: All playback controls work correctly

---

## Phase 6: Dual-View Layout

- [ ] Split view: Original (QVideoWidget) | Processed (QLabel with overlay)
- [ ] Both views sync to same timeline position
- [ ] Handle video loading/unloading
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

**Current Phase**: Not started
**Progress**: 0%
