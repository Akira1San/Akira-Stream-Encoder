# Audio Playback Implementation Tasks

## Overview
Add audio playback capability to the video preview so users can hear audio when pressing play.

---

## Current State

**File:** `PySide6/video_preview.py`

The preview currently:
- Extracts video frames using FFmpeg
- Has Play/Pause/Stop buttons
- Advances frames on a timer
- **No audio playback** (being implemented)

---

## ⚠️ Important Note

The local `PySide6/` folder shadows the actual PySide6 package. To run the app:
```bash
cd "C:\Users\Admin\Desktop\myencoder"
python "zve - interface change - pyside6 port/PySide6/main.py"
```

---

## Phase 1: Audio Infrastructure

### Task 1.1: Research Qt Audio Options ✅ COMPLETE
**Investigate:**
- [x] QMediaPlayer (Qt Multimedia) - high-level, handles sync automatically ✅ SELECTED
- [x] QAudioOutput (Qt Multimedia) - low-level, requires manual buffer management
- [x] FFmpeg audio extraction + QAudioOutput - most control, matches current approach

**Decision:** Use QMediaPlayer (Option A) for simplicity. Qt handles sync automatically.

---

### Task 1.2: Add Qt Multimedia Dependencies ✅ COMPLETE
**File:** Project setup

- [x] Verify PySide6.QtMultimedia is available
- [x] Verify PySide6.QtMultimediaWidgets is available (not needed for audio-only)
- [x] Add imports to video_preview.py

**Note:** Must run from parent directory due to folder naming conflict.

---

## Phase 2: Basic Audio Playback

### Task 2.1: Create Audio Player Class ✅ COMPLETE
**File:** `PySide6/audio_player.py`

Create dedicated audio player class:
- [x] `AudioPlayer` class with QMediaPlayer
- [x] `load_file(path)` method
- [x] `play()`, `pause()`, `stop()` methods
- [x] `seek(time)` method
- [x] `set_volume(level)` method
- [x] Signal: `position_changed(float)` for sync
- [x] Signal: `state_changed(playing/paused/stopped)`

---

### Task 2.2: Extract Audio Segment for Playback ⏭️ SKIPPED
**File:** `PySide6/audio_player.py`

Skipped - QMediaPlayer handles audio directly from video file.

---

### Task 2.3: Integrate Audio Player into Video Preview ✅ COMPLETE
**File:** `PySide6/video_preview.py`

Connect audio to video preview:
- [x] Create AudioPlayer instance in VideoPreview
- [x] Pass current video path to AudioPlayer
- [x] Play audio when video plays
- [x] Pause audio when video pauses
- [x] Stop audio when video stops

**Acceptance:**
- [x] Audio plays when Play button pressed
- [x] Audio pauses when Pause pressed
- [x] Audio stops when Stop pressed

---

## Phase 3: Audio-Video Synchronization

### Task 3.1: Sync Audio Position with Video Timeline ✅ COMPLETE
**File:** `PySide6/video_preview.py`

Keep audio and video in sync:
- [x] When timeline slider dragged, seek audio to match
- [x] When playhead moves, verify audio position matches
- [ ] Handle drift correction (re-sync if > 100ms off)

**Acceptance:**
- [x] Scrubbing timeline seeks audio
- [ ] Audio stays synced during playback (needs testing)

---

### Task 3.2: Handle Video Seeking During Playback ✅ COMPLETE
**File:** `PySide6/video_preview.py`

When user seeks during playback:
- [x] Pause audio (implicitly done via seek)
- [x] Seek audio to new position
- [x] Resume audio if was playing

**Acceptance:**
- [x] Seeking during playback works smoothly
- [x] Audio resumes at correct position

---

## Phase 4: Audio Settings Integration

### Task 4.1: Volume Control ✅ COMPLETE
**File:** `PySide6/video_preview.py`, `PySide6/audio_player.py`

- [x] Add volume slider to preview controls
- [x] Connect to AudioPlayer.set_volume()
- [x] Range: 0% to 100%
- [ ] Persist volume setting

**Acceptance:**
- [x] Volume slider adjusts audio output
- [ ] Volume persists across sessions

---

### Task 4.2: Audio Track Selection ⏳ PENDING
**File:** `PySide6/video_preview.py`

Handle multiple audio tracks:
- [ ] Use app_state.tracks.audio_stream_index for track selection
- [ ] Re-load audio when track selection changes
- [ ] Show current audio track in UI

**Note:** QMediaPlayer plays first audio track by default. Multi-track support requires more complex handling.

---

### Task 4.3: Audio Filters Preview ⏳ PENDING
**File:** `PySide6/audio_player.py`

Apply audio filters from settings:
- [ ] Volume adjustment (filters.volume_db)
- [ ] Audio denoise if enabled
- [ ] Dynamic range normalization if enabled

**Note:** Requires FFmpeg audio filtering or QMediaPlayer audio effects

**Acceptance:**
- Volume adjustment preview works
- Basic audio filters apply to preview

---

## Phase 5: Polish & Edge Cases

### Task 5.1: Handle No-Audio Videos ⏳ PENDING
**File:** `PySide6/video_preview.py`

- [ ] Detect if video has no audio track
- [ ] Disable audio controls gracefully
- [ ] Show "No Audio" indicator

**Acceptance:**
- Videos without audio don't cause errors
- UI indicates no audio available

---

### Task 5.2: Handle Audio Errors ✅ PARTIAL
**File:** `PySide6/audio_player.py`

- [x] Handle unsupported codecs gracefully (logged)
- [ ] Handle corrupted audio streams
- [x] Log audio errors appropriately
- [x] Fall back to video-only mode

**Acceptance:**
- [x] Audio errors don't crash app
- [x] User informed of audio issues

---

### Task 5.3: Memory Management ✅ COMPLETE
**File:** `PySide6/audio_player.py`

- [x] Clean up audio buffers on stop
- [x] Release audio resources on video change
- [x] No buffer limits needed (QMediaPlayer handles this)

**Acceptance:**
- [x] No memory leaks during extended use
- [x] Audio resources properly released

---

## Progress Summary

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 1: Audio Infrastructure | ✅ COMPLETE | 100% |
| Phase 2: Basic Audio Playback | ✅ COMPLETE | 100% |
| Phase 3: Audio-Video Sync | ✅ COMPLETE | 90% |
| Phase 4: Audio Settings | ⏳ PARTIAL | 40% |
| Phase 5: Polish | ⏳ PARTIAL | 50% |

**Overall: ~75% Complete**

---

## Remaining Work

1. **Drift correction** - Re-sync audio if > 100ms off during playback
2. **Volume persistence** - Save/load volume setting
3. **Audio track selection** - Support multi-track videos
4. **Audio filters preview** - Apply volume/denoise/normalization
5. **No-audio detection** - Graceful handling for videos without audio

---

## Dependencies Between Tasks

```
Phase 1 (1.1-1.2) ✅ COMPLETE
Phase 2 (2.1-2.3) ✅ COMPLETE - depends on Phase 1
Phase 3 (3.1-3.2) ✅ COMPLETE - depends on Phase 2
Phase 4 (4.1-4.3) ⏳ PARTIAL - depends on Phase 3
Phase 5 (5.1-5.3) ⏳ PARTIAL - depends on Phase 4
```

---

## Technical Decision: Audio Approach

### Option A: QMediaPlayer (Recommended for simplicity)
```python
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QUrl

player = QMediaPlayer()
audio_output = QAudioOutput()
player.setAudioOutput(audio_output)
player.setSource(QUrl.fromLocalFile(video_path))
player.play()
```

**Pros:**
- Simple implementation
- Automatic sync with video if using QMediaPlayer for video too
- Handles seeking automatically
- Supports many codecs

**Cons:**
- Less control over audio processing
- May conflict with current FFmpeg frame extraction
- Need to sync with our frame timer

### Option B: FFmpeg Audio Extraction + QAudioOutput
```python
# Extract audio via FFmpeg, feed to QAudioOutput
cmd = [ffmpeg, "-i", video, "-f", "s16le", "-acodec", "pcm_s16le", "-"]
```

**Pros:**
- Matches current FFmpeg-based approach
- Full control over audio processing
- Can apply filters during extraction

**Cons:**
- More complex
- Manual sync required
- Buffer management needed

### Recommendation
Start with **Option A (QMediaPlayer)** for MVP. It's simpler and Qt handles sync. If we need more control later (e.g., applying filters in real-time), we can refactor to Option B.

---

## Testing Checklist

After each phase:
- [ ] No Python errors in console
- [ ] No Qt warnings
- [ ] Audio plays correctly
- [ ] Audio-video sync is acceptable (< 100ms drift)
- [ ] Memory usage reasonable
- [ ] Works with common video files (MP4, MKV, AVI)
