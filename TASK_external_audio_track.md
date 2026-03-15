# Task Specification: External Audio Track Loading Feature

## 1. Overview

**Feature Name:** External Audio Track Loading  
**Module:** Video Tab → Advanced Encoding Settings  
**Priority:** High  
**Estimated Complexity:** Medium

### Summary
Allow users to load an external audio file (MP3, AAC, WAV, FLAC, etc.) to replace or supplement the video's embedded audio track during encoding. This feature enables scenarios where the original audio is poor quality, users want to add background music, or need to replace audio with a clean track.

---

## 2. Current State Analysis

### Existing Components
- **EncodingPanel** ([`PySide6/encoding_settings.py`](PySide6/encoding_settings.py:1)): Contains audio-related settings
  - Line 385-395: Audio Mode selector (Encode/Copy)
  - Line 398-405: Audio Track dropdown for selecting from embedded tracks
  - Line 468-493: `populate_audio_tracks()` method for listing embedded audio streams

- **TrackSettings** ([`PySide6/models.py`](PySide6/models.py:179)): Data model for track selection
  - Line 184: `audio_stream_index` - currently tracks embedded audio stream selection
  - Line 190: `available_audio_tracks` - list of embedded AudioTrackInfo objects

- **VideoWorkspace** ([`PySide6/video_workspace.py`](PySide6/video_workspace.py:53)): Main video tab UI
  - Line 261-292: `on_video_changed()` - detects and populates audio tracks when video loads

### Gap
No capability exists to:
1. Browse and select an external audio file
2. Store the external audio file path in the application state
3. Use the external audio file during FFmpeg encoding

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Description |
|----|-------------|-------------|
| FR-1 | External Audio File Selection | Provide a file browser to select audio files (mp3, aac, wav, flac, ogg, m4a, ac3) |
| FR-2 | External Audio Display | Show selected external audio file path/name in the UI |
| FR-3 | External Audio Toggle | Allow enabling/disabling external audio (use embedded vs external) |
| FR-4 | Audio Source Selection | Allow user to choose between: (a) Embedded audio track, (b) External audio file |
| FR-5 | External Audio Info | Display info about external file (duration, codec, channels) |
| FR-6 | External Audio Timing | Sync external audio to video - use shorter duration if audio is shorter than video |
| FR-7 | Encoding Integration | Pass external audio file to FFmpeg encoding pipeline |

### 3.2 UI/UX Requirements

| ID | Requirement | Description |
|----|-------------|-------------|
| UX-1 | Clear Visual Distinction | External audio section should be visually distinct from embedded audio options |
| UX-2 | File Path Display | Show truncated file path with tooltip for full path |
| UX-3 | Quick Clear | Provide button to quickly remove external audio selection |
| UX-4 | Validation Feedback | Show error if selected audio file is invalid or inaccessible |
| UX-5 | Audio Mode Integration | External audio option should work with "Copy" audio mode (recommended) or "Encode" |

### 3.3 Technical Requirements

| ID | Requirement | Description |
|----|-------------|-------------|
| TR-1 | Supported Formats | Support: mp3, aac, wav, flac, ogg, m4a, ac3 |
| TR-2 | File Validation | Validate file exists and is readable before accepting |
| TR-3 | FFmpeg Integration | Pass `-i <external_audio> -map 0:v -map 1:a` to FFmpeg command |
| TR-4 | Duration Handling | Handle case where external audio duration ≠ video duration |
| TR-5 | State Persistence | Store external audio path in AppState/TrackSettings |

---

## 4. Implementation Plan

### Phase 1: Data Model Updates

#### 4.1.1 Update TrackSettings in models.py

Add new fields to [`TrackSettings`](PySide6/models.py:179) dataclass:

```python
@dataclass
class TrackSettings:
    # ... existing fields ...
    
    # External audio support
    external_audio_enabled: bool = False
    external_audio_path: str = ""  # Full path to external audio file
    external_audio_info: str = ""  # Display info (codec, duration, channels)
```

### Phase 2: UI Implementation

#### 4.2.1 Add External Audio Section in EncodingPanel

Location: [`PySide6/encoding_settings.py`](PySide6/encoding_settings.py:338) - Inside "Advanced Encoding Settings" collapsible frame, after Audio Track selection.

New UI components:
1. **CheckBox**: "Use External Audio" toggle
2. **LineEdit + Browse Button**: File path display with browse button
3. **Clear Button**: Remove external audio selection
4. **Info Label**: Display audio file info (codec, duration, channels)

#### 4.2.2 Import Required Modules

Add to [`encoding_settings.py`](PySide6/encoding_settings.py:1) imports:
```python
from PySide6.QtWidgets import QFileDialog
from PySide6.QtCore import QTimer
```

### Phase 3: Controller Updates

#### 4.3.1 Add External Audio Detection Method

Add to [`VideoController`](PySide6/controller.py:14) class:
```python
def get_external_audio_info(self, audio_path: str) -> dict:
    """Get information about external audio file using ffprobe"""
    # Return: {duration, codec, channels, sample_rate}
```

### Phase 4: FFmpeg Integration

#### 4.4.1 Update encode_file Method

Modify encoding logic to handle external audio. The FFmpeg command should:

**When using external audio:**
```bash
ffmpeg -i input_video.mp4 -i external_audio.mp3 -map 0:v -map 1:a [encoding_options] output.mp4
```

**Key considerations:**
- Use `-map 0:v` to select video from first input
- Use `-map 1:a` to select audio from second input (external)
- Handle duration mismatch (use `-shortest` or let audio end naturally)
- Ensure audio sync is maintained

---

## 5. UI Mockup

```
┌─────────────────────────────────────────────────────────┐
│ Advanced Encoding Settings                              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Audio Mode: [Encode ▼] [Copy]                           │
│                                                         │
│ ┌─ Embedded Audio ───────────────────────────────────┐ │
│ │ Audio Track: [Track 1 - English (aac, 6ch)     ▼] │ │
│ └────────────────────────────────────────────────────┘ │
│                                                         │
│ ┌─ External Audio ──────────────────────────────────┐ │
│ │ ☑ Use External Audio File                         │ │
│ │                                                  │ │
│ │ [______________________________] [Browse...]  │ │
│ │ External: music_track.mp3                        │ │
│ │ Info: MP3, 3:45, Stereo, 44100Hz                 │ │
│ │                                           [Clear]│ │
│ └────────────────────────────────────────────────────┘ │
│                                                         │
│ Profile: [main ▼]   Level: [4.0 ▼]   B-Frames: [0 ▼]  │
└─────────────────────────────────────────────────────────┘
```

---

## 6. Acceptance Criteria

### 6.1 Functional Acceptance

| ID | Criterion | Test Scenario |
|----|-----------|---------------|
| AC-1 | Browse button opens file dialog | Click "Browse" → File dialog opens with audio filter |
| AC-2 | Selected file path displays | Select "music.mp3" → Path shown in text field |
| AC-3 | External audio info displays | Select valid audio → Shows codec, duration, channels |
| AC-4 | Toggle enables/disables external audio | Uncheck "Use External Audio" → Uses embedded audio |
| AC-5 | Clear button removes selection | Click "Clear" → Field cleared, checkbox unchecked |
| AC-6 | Invalid file shows error | Select non-audio file → Error message displayed |
| AC-7 | Encoding uses external audio | Start encode with external audio → FFmpeg receives both inputs |

### 6.2 Edge Cases

| ID | Edge Case | Expected Behavior |
|----|-----------|-------------------|
| EC-1 | External audio shorter than video | Use `-shortest` or encode until audio ends |
| EC-2 | External audio longer than video | Trim audio to video duration |
| EC-3 | Video has no embedded audio | Allow encoding with only external audio |
| EC-4 | External audio file deleted after selection | Show error, revert to embedded audio |
| EC-5 | Both copy and encode modes work | External audio works with both audio modes |

---

## 7. File Changes Summary

| File | Changes |
|------|---------|
| [`PySide6/models.py`](PySide6/models.py:179) | Add `external_audio_enabled`, `external_audio_path`, `external_audio_info` to TrackSettings |
| [`PySide6/encoding_settings.py`](PySide6/encoding_settings.py:338) | Add external audio UI section with browse/clear functionality |
| [`PySide6/controller.py`](PySide6/controller.py:14) | Add `get_external_audio_info()` method, update encoding logic |
| [`PySide6/video_workspace.py`](PySide6/video_workspace.py:53) | Update video changed handler to reset external audio when new video loads |

---

## 8. Dependencies

- **FFprobe**: Used to get external audio file metadata (codec, duration, channels)
- **PySide6.QtWidgets**: QFileDialog for file browser
- **os.path**: File path validation

---

## 9. Related Features

- **Audio Track Selection** (existing): Selection of embedded audio streams
- **Audio Mode** (existing): Encode/Copy toggle
- **Trim/Cut**: External audio should respect trim points

---

## 10. Notes

- External audio is particularly useful when the original video has:
  - Poor audio quality
  - Wrong language
  - No audio (silent video)
  - Watermark noise
- Recommended audio mode when using external audio is "Copy" (faster, maintains quality)
- Consider adding a "Mix with original" option in future iteration for ducking/overlaying
