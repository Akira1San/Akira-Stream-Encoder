# Tracks Tab Feature Specification

## 1. Overview

### Feature Summary
Add a new "Tracks" tab to the video encoder application after the Trim/Cut tab. This tab provides a visual timeline interface for managing video and audio tracks extracted from loaded media files, with properties display and export capabilities.

### Target Users
- Users who need to extract or export specific tracks from video files
- Users who want to replace audio tracks with external audio files
- Users who need to export individual tracks (video-only or audio-only)

---

## 2. UI/UX Specification

### 2.1 Layout Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│  📊 Tracks                                                    [?] help  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                         TIMELINE VIEW                               │ │
│  │  ┌─────────┬────────────────────────────────────────────────────┐ │ │
│  │  │ ▶ Video │ [███████████████████████████████] 00:05:30         │ │ │
│  │  ├─────────┼────────────────────────────────────────────────────┤ │ │
│  │  │ 🔊 Audio│ [███████████████████████████████] 00:05:30         │ │ │
│  │  ├─────────┼────────────────────────────────────────────────────┤ │ │
│  │  │ 🔊 Audio│ [                                              ]    │ │ │
│  │  └─────────┴────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌───────────────────────────┐  ┌────────────────────────────────────┐  │
│  │    TRACK LIST             │  │      TRACK PROPERTIES              │  │
│  │  ┌───────────────────────┐ │  │  ┌──────────────────────────────┐ │  │
│  │  │ ☑ Video Track 1      │ │  │  │ Name: Video Track 1         │ │  │
│  │  │ ☑ Audio Track 1      │ │  │  │ Type: Video                  │ │  │
│  │  │ ☐ Audio Track 2     │ │  │  │ Source: video.mp4            │ │  │
│  │  │                      │ │  │  │ Stream Index: 0              │ │  │
│  │  └───────────────────────┘ │  │  │ Duration: 00:05:30           │ │  │
│  │                           │  │  │ Codec: h264                  │ │  │
│  │  [+ Add Track] [Replace] │  │  │ Resolution: 1920x1080        │ │  │
│  │  [Delete] [Select All]   │  │  │ Frame Rate: 24fps             │ │  │
│  │                           │  │  │ Bitrate: 5000 kbps           │ │  │
│  │                           │  │  │ ─────────────────────────── │ │  │
│  │                           │  │  │ Audio Codec: aac             │ │  │
│  │                           │  │  │ Channels: 2 (Stereo)        │ │  │
│  │                           │  │  │ Sample Rate: 48000 Hz       │ │  │
│  │                           │  │  └──────────────────────────────┘ │  │
│  │                           │  │                                    │  │
│  │                           │  │  [🔄 Refresh Tracks]              │  │
│  │                           │  │                                    │  │
│  └───────────────────────────┘  └────────────────────────────────────┘  │
│                                                                         │
│  ════════════════════════════════════════════════════════════════════════│
│                           EXPORT SECTION                                  │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  Export Mode:  [Selected Track Only ▼]                             │ │
│  │                 ○ Video only   ● Both (Video + Audio)   ○ Audio only│ │
│  │                                                                       │ │
│  │  Encoding:  ○ Copy (no re-encode)   ○ Encode (re-encode)           │ │
│  │                                                                       │ │
│  │  Output:   [............................................] [Browse]  │ │
│  │                                                                       │ │
│  │                        [ 🚀 Export Track ]                          │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Tab Position
- **Location**: After "Video" tab, before/after "Composition" tab (or replace NLE tab)
- **Default State**: Empty with "Load a video to see tracks" message

### 2.3 Component Specifications

#### Timeline View
| Component | Description |
|-----------|-------------|
| Track Header | Icon (▶ video/🔊 audio) + Track name, fixed width 100px |
| Track Row | Visual representation of track, 40px height |
| Progress Bar | Colored bar showing track duration (video=blue, audio=green) |
| Time Display | End time shown at right of each track |
| Selection | Click on track to select, highlighted with border |

#### Track List Panel
| Component | Description |
|-----------|-------------|
| Checkbox | Enable/disable track for export |
| Track Name | Display name with icon |
| Selection | Single selection for property viewing |
| Multi-select | Ctrl+click for multiple selection |

#### Track Properties Panel
| Component | Description |
|-----------|-------------|
| Read-only fields | Display track metadata |
| Refresh button | Re-detect tracks from source |
| Context | Shows properties of selected track |

#### Action Buttons
| Button | Function |
|--------|----------|
| Add Track | Open file dialog to add external audio/video file |
| Replace | Replace selected track with external file |
| Delete | Remove selected track from list |
| Select All | Check all tracks |
| Deselect All | Uncheck all tracks |
| Refresh | Re-scan source for tracks |

#### Export Section
| Component | Description |
|-----------|-------------|
| Export Mode | Dropdown: Selected Track, Video Only, Audio Only, Both |
| Encoding | Radio: Copy (stream copy), Encode (re-encode) |
| Output Path | Text field + Browse button |
| Export Button | Execute export |

### 2.4 Visual Design

#### Color Palette
| Element | Color | Hex |
|---------|-------|-----|
| Video Track | Blue | #3498db |
| Audio Track | Green | #2ecc71 |
| Selected Track | Orange border | #e67e22 |
| Background | Dark gray | #1e1e1e |
| Panel Background | Slightly lighter | #2d2d2d |
| Text Primary | White | #ffffff |
| Text Secondary | Gray | #aaaaaa |
| Button Primary | Blue | #2980b9 |
| Button Danger | Red | #c0392b |

#### Typography
| Element | Font | Size |
|---------|------|------|
| Tab Title | System default | 12px |
| Section Headers | Bold | 11px |
| Track Names | Regular | 10px |
| Properties | Monospace | 10px |
| Buttons | Regular | 10px |

#### Spacing
- Panel margins: 10px
- Component spacing: 8px
- Button padding: 8px 16px

### 2.5 Interaction Behaviors

| Action | Behavior |
|--------|----------|
| Load video | Auto-populate tracks from video file |
| Click track row | Select track, show properties |
| Double-click track | Open rename dialog |
| Drag track | Reorder tracks (optional) |
| Right-click track | Context menu (Select, Replace, Delete) |
| Checkbox toggle | Enable/disable for export |
| Export button | Show progress dialog, execute FFmpeg |

---

## 3. Functional Specification

### 3.1 Core Features

#### F1: Auto-detect Tracks
- When a video is loaded, automatically detect all streams
- Parse using FFprobe (existing functionality in tracks_panel.py)
- Create Track objects for each detected stream

#### F2: Display Timeline View
- Visual representation of track duration
- Track headers with type icons
- Time ruler (reuse from NLE timeline)
- Playhead (optional, for reference)

#### F3: Track Selection
- Single-click to select a track
- Multi-select with Ctrl+click
- Selection updates Properties panel

#### F4: Track Properties Display
- Show metadata for selected track:
  - Name
  - Type (Video/Audio)
  - Source file
  - Stream index
  - Duration
  - Codec
  - Resolution (video)
  - Frame rate (video)
  - Bitrate
  - Channels (audio)
  - Sample rate (audio)

#### F5: Add New Track
- File dialog to select external audio/video file
- Validate file format
- Add to track list
- Merge with existing tracks

#### F6: Replace Track
- Select existing track
- Click Replace button
- Select replacement file
- Update track in list

#### F7: Delete Track
- Select track(s)
- Click Delete
- Confirmation dialog
- Remove from list

#### F8: Export Track(s)
- Use existing encoding framework
- Options:
  - Video only (extract video stream)
  - Audio only (extract audio stream)
  - Both (mux video+audio)
- Encoding options:
  - Copy (stream copy, no re-encode)
  - Encode (re-encode with settings)

### 3.2 Data Flow

```
┌────────────────┐     ┌─────────────────┐     ┌────────────────┐
│  Video File    │────▶│  FFprobe        │────▶│  Track List    │
│  (Input)       │     │  (Detect)       │     │  (Model)       │
└────────────────┘     └─────────────────┘     └────────────────┘
                                                        │
                        ┌─────────────────┐             │
                        │  Properties    │◀────────────┤
                        │  Panel         │             │
                        └─────────────────┘             │
                                                        ▼
┌────────────────┐     ┌─────────────────┐     ┌────────────────┐
│  Output File   │◀────│  FFmpeg         │◀────│  Export        │
│  (Result)      │     │  (Execute)      │     │  Controller    │
└────────────────┘     └─────────────────┘     └────────────────┘
```

### 3.3 Key Classes/Modules

#### New Files to Create
| File | Purpose |
|------|---------|
| `tracks_tab.py` | Main Tracks tab widget |
| `tracks_tab/timeline.py` | Timeline view widget |
| `tracks_tab/track_list.py` | Track list panel |
| `tracks_tab/properties.py` | Properties panel |
| `tracks_tab/export.py` | Export functionality |

#### Modified Files
| File | Changes |
|------|---------|
| `main_window.py` | Add Tracks tab |
| `models.py` | Add Track model class |

#### Reuse Existing
| Module | Reuse Purpose |
|--------|---------------|
| `tracks_panel.py` | FFprobe detection logic |
| `nle_timeline.py` | TimeRuler widget |
| `encoding_settings.py` | Encoding options UI |
| `controller.py` | FFmpeg execution |

### 3.4 Edge Cases

| Scenario | Handling |
|----------|----------|
| No video loaded | Show "Load a video to see tracks" message |
| Video with no audio | Show video track only |
| Video with multiple audio | Show all audio tracks |
| Corrupted video file | Show error, don't crash |
| Export during encoding | Disable UI, show progress |
| Output path not writable | Show error message |
| Very long video (>1hr) | Lazy-load timeline, show warning |

---

## 4. Acceptance Criteria

### 4.1 Success Conditions

| ID | Criteria | Test Method |
|----|----------|-------------|
| AC1 | Tab appears in main window after Video tab | Visual inspection |
| AC2 | Loading a video populates track list | Load test video |
| AC3 | Timeline shows track duration visually | Visual inspection |
| AC4 | Clicking track shows properties | Click track |
| AC5 | Add Track adds external file | Click Add, select file |
| AC6 | Replace Track replaces existing | Select, click Replace |
| AC7 | Delete removes track | Select, click Delete |
| AC8 | Export produces valid output file | Run export, play result |
| AC9 | Copy mode works (no re-encode) | Export with copy |
| AC10 | Encode mode works (re-encode) | Export with encode |

### 4.2 Visual Checkpoints

1. **Empty State**: Shows placeholder text when no video loaded
2. **Populated State**: Shows tracks with checkboxes, timeline bars
3. **Selected State**: Selected track highlighted with border
4. **Properties Panel**: Shows metadata for selected track
5. **Export Progress**: Shows progress bar during export

---

## 5. Implementation Notes

### Phase 1: Core Infrastructure
1. Create Track model in models.py
2. Create TracksTab widget
3. Add to MainWindow
4. Basic track detection

### Phase 2: UI Components
1. Timeline view
2. Track list panel
3. Properties panel
4. Action buttons

### Phase 3: Functionality
1. Add track
2. Replace track
3. Delete track
4. Export functionality

### Phase 4: Polish
1. Error handling
2. Progress dialogs
3. Edge cases
4. Testing
