# NLE (Non-Linear Editor) Implementation Tasks

## Overview
Implement a Blender-inspired video editing tab with multi-track timeline, 
clip management, effects, and rendering to single output file.

---

## Phase 1: Core Infrastructure ✅ DONE

### Task 1.1: Create NLE Data Models ✅
**File:** `PySide6/nle/nle_models.py`

Create dataclasses for:
- [x] `NLEClip` - source_path, source_start, source_end, timeline_start, track_id, effects
- [x] `NLETrack` - id, name, type (video/audio), clips list, effects, muted, locked
- [x] `Effect` - id, type, params dict
- [x] `NLEProject` - tracks list, duration, fps, resolution, methods for add/remove/move clips

**Acceptance:** 
- All dataclasses defined with type hints
- NLEProject has add_track(), add_clip(), remove_clip(), move_clip(), split_clip() methods

---

### Task 1.2: Create NLE Tab Skeleton ✅
**File:** `PySide6/nle/nle_tab.py`

Create empty NLE tab with layout structure:
- [x] QHBoxLayout for toolbar
- [x] QSplitter for: Source Bin | Preview | Properties
- [x] QSplitter for: Above | Timeline
- [x] Add placeholder widgets for each section

**Acceptance:**
- Tab visible in VideoWorkspace
- Layout matches design mockup structure

---

### Task 1.3: Create Basic Timeline Widget ✅
**File:** `PySide6/nle/nle_timeline.py`

Create timeline widget with:
- [x] Time ruler (horizontal scale showing 00:00, 00:30, 01:00, etc.)
- [x] Playhead (vertical draggable line)
- [x] Zoom controls (+/- buttons)
- [x] Track container (vertical layout for tracks)
- [x] Signals: playhead_moved(float), zoom_changed(float)

**Acceptance:**
- Timeline shows time ruler
- Playhead can be dragged
- Zoom changes time scale

---

### Task 1.4: Integrate NLE Tab into VideoWorkspace ✅
**File:** `PySide6/nle/__init__.py`, `PySide6/video_workspace.py`

- [x] Create `PySide6/nle/` directory structure
- [x] Create `__init__.py` with exports
- [x] Add NLE tab to VideoWorkspace tabs
- [x] Pass app_state to NLE tab

**Acceptance:**
- NLE tab appears next to Trim/Cut tab
- No import errors

---

## Phase 2: Track & Clip Management ✅ DONE

### Task 2.1: Create Track Widget ✅
**File:** `PySide6/nle/nle_track.py`

Create track row widget:
- [x] Track header (name, mute button, lock button)
- [x] Clip container area (QWidget for clips)
- [x] Visual track background
- [x] Signal: clip_clicked(clip_id), clip_moved(clip_id, new_start)

**Acceptance:**
- Track displays with header
- Can toggle mute/lock states

---

### Task 2.2: Create Clip Widget ✅
**File:** `PySide6/nle/nle_clip.py`

Create clip block widget:
- [x] Colored rectangle with rounded corners
- [x] Display: source filename + time range
- [x] Resize handles on left/right edges
- [x] Drag handle for moving
- [x] Selected state visual (border highlight)
- [x] Signals: clicked, moved, trimmed

**Acceptance:**
- Clip displays with source info
- Clip can be selected
- Edge dragging signals trim

---

### Task 2.3: Implement Track Management ✅
**File:** `PySide6/nle/nle_tab.py`

Add track management:
- [x] "Add Video Track" button
- [x] "Add Audio Track" button  
- [x] Track appears in timeline
- [x] Tracks stored in NLEProject model

**Acceptance:**
- Can add unlimited video tracks
- Can add unlimited audio tracks
- Tracks numbered sequentially (Video 1, Video 2, etc.)

---

### Task 2.4: Implement Basic Clip Adding ✅
**File:** `PySide6/nle/nle_tab.py`, `PySide6/nle/nle_timeline.py`

Add clip programmatically:
- [x] Method to add clip to track
- [x] Clip widget created and positioned
- [x] Clip position calculated from timeline_start
- [x] Clip width calculated from duration

**Acceptance:**
- Calling add_clip() shows clip on timeline
- Multiple clips on same track don't overlap visually

---

## Phase 3: Source Management

### Task 3.1: Create Source Bin Panel
**File:** `PySide6/nle/nle_source_bin.py`

Create source file manager:
- [ ] List widget for source files
- [ ] "Add Source" button with file dialog
- [ ] Show filename and duration
- [ ] Double-click to preview source
- [ ] Store list of source paths with metadata

**Acceptance:**
- Can add multiple video files
- Each source shows filename and duration
- Sources persist in project

---

### Task 3.2: Detect Source Properties
**File:** `PySide6/nle/nle_source_bin.py`

Use FFprobe to detect:
- [ ] Duration
- [ ] Resolution
- [ ] Frame rate
- [ ] Has audio flag
- [ ] Store in source metadata dict

**Acceptance:**
- Adding source extracts metadata
- Metadata displayed in source list

---

### Task 3.3: Drag Source to Timeline
**File:** `PySide6/nle/nle_source_bin.py`, `PySide6/nle/nle_timeline.py`

Implement drag & drop:
- [ ] Source item is draggable
- [ ] Timeline accepts drop
- [ ] Drop creates new clip at drop position
- [ ] Clip spans full source duration initially

**Acceptance:**
- Drag source file to timeline creates clip
- Clip appears on appropriate track type

---

## Phase 4: Timeline Interactions

### Task 4.1: Move Clips
**File:** `PySide6/nle/nle_clip.py`, `PySide6/nle/nle_timeline.py`

Implement clip dragging:
- [ ] Clip can be dragged horizontally
- [ ] Snap to other clip edges (with snap toggle)
- [ ] Update model on drag end
- [ ] Prevent clips from overlapping on same track

**Acceptance:**
- Clip moves smoothly during drag
- Snapping works when enabled
- Model updated with new position

---

### Task 4.2: Trim Clips
**File:** `PySide6/nle/nle_clip.py`

Implement edge trimming:
- [ ] Left edge drag = adjust source_start
- [ ] Right edge drag = adjust source_end
- [ ] Minimum clip duration (0.1s)
- [ ] Update model on trim end

**Acceptance:**
- Dragging edges changes clip duration
- Source in/out points update

---

### Task 4.3: Split Clip at Playhead
**File:** `PySide6/nle/nle_timeline.py`

Implement clip splitting:
- [ ] "Split at Playhead" button
- [ ] Find clip under playhead
- [ ] Create two clips from split point
- [ ] Maintain source in/out points correctly

**Acceptance:**
- Split creates two clips
- Total duration preserved
- Playhead position is split point

---

### Task 4.4: Delete Clips
**File:** `PySide6/nle/nle_timeline.py`

Implement clip deletion:
- [ ] Delete key or context menu
- [ ] Remove clip from model
- [ ] Remove clip widget from UI
- [ ] Optional: ripple delete (close gap)

**Acceptance:**
- Selected clip deleted
- UI and model synchronized

---

### Task 4.5: Context Menu
**File:** `PySide6/nle/nle_clip.py`, `PySide6/nle/nle_timeline.py`

Add right-click menu:
- [ ] Delete
- [ ] Split
- [ ] Properties/Effects
- [ ] Mute (for tracks)

**Acceptance:**
- Right-click on clip shows menu
- Menu actions functional

---

## Phase 5: Preview Integration

### Task 5.1: Create NLE Preview Widget
**File:** `PySide6/nle/nle_preview.py`

Create preview panel:
- [ ] QLabel for frame display
- [ ] Play/Pause/Stop buttons
- [ ] Time display (current / total)
- [ ] Frame extraction at playhead

**Acceptance:**
- Preview widget displays frames
- Controls are functional

---

### Task 5.2: Frame Extraction at Playhead
**File:** `PySide6/nle/nle_preview.py`

Implement preview rendering:
- [ ] Find active clip at playhead time
- [ ] Calculate source frame position
- [ ] Extract frame using FFmpeg
- [ ] Display in preview widget

**Acceptance:**
- Preview shows frame at playhead
- Correct source frame displayed

---

### Task 5.3: Playback Control
**File:** `PySide6/nle/nle_preview.py`

Implement timeline playback:
- [ ] Play button starts auto-advance
- [ ] Pause stops at current frame
- [ ] Stop returns to start
- [ ] Playhead syncs with preview

**Acceptance:**
- Play/Pause/Stop work correctly
- Preview updates during playback

---

## Phase 6: Effects System

### Task 6.1: Create Effects Panel
**File:** `PySide6/nle/nle_effects.py`

Create effects property panel:
- [ ] Show when clip selected
- [ ] List of available effects
- [ ] Effect parameter controls (sliders, checkboxes)
- [ ] Enable/disable per effect

**Acceptance:**
- Panel shows selected clip effects
- Can add/remove effects

---

### Task 6.2: Implement Per-Clip Effects
**File:** `PySide6/nle/nle_effects.py`, `PySide6/nle/nle_renderer.py`

Add clip-level effects:
- [ ] Brightness/Contrast/Saturation
- [ ] Fade In/Out
- [ ] Speed adjustment
- [ ] Store in NLEClip.effects list

**Acceptance:**
- Effects stored per clip
- Preview shows effect result

---

### Task 6.3: Implement Track-Level Effects
**File:** `PySide6/nle/nle_effects.py`

Add track-level effects:
- [ ] Effects apply to all clips on track
- [ ] Opacity (for video tracks)
- [ ] Volume (for audio tracks)
- [ ] Store in NLETrack.effects list

**Acceptance:**
- Track effects apply to all clips
- Can toggle track effects

---

## Phase 7: Rendering

### Task 7.1: Create NLE Renderer
**File:** `PySide6/nle/nle_renderer.py`

Build FFmpeg command from project:
- [ ] Generate filter_complex string
- [ ] Handle multiple input files
- [ ] Apply trim filters per clip
- [ ] Concatenate clips in order
- [ ] Apply effects as filters

**Acceptance:**
- Renderer generates valid FFmpeg command
- Command produces correct output

---

### Task 7.2: Render Dialog
**File:** `PySide6/nle/nle_tab.py`

Create render settings UI:
- [ ] Output file path selector
- [ ] Encoder selection (reuse existing settings)
- [ ] Quality/bitrate settings
- [ ] Progress bar during render

**Acceptance:**
- User can configure output
- Progress shown during render

---

### Task 7.3: Execute Render
**File:** `PySide6/nle/nle_renderer.py`

Run FFmpeg and monitor:
- [ ] Execute generated command
- [ ] Parse progress from FFmpeg output
- [ ] Handle errors gracefully
- [ ] Signal completion

**Acceptance:**
- Render completes successfully
- Output file is playable

---

## Phase 8: Polish

### Task 8.1: Save/Load Project
**File:** `PySide6/nle/nle_project_io.py`

Implement project persistence:
- [ ] Export NLEProject to JSON
- [ ] Import JSON to NLEProject
- [ ] File dialog for save/load
- [ ] Recent projects list

**Acceptance:**
- Project saves to JSON
- Project loads from JSON
- All clips/tracks/effects preserved

---

### Task 8.2: Keyboard Shortcuts
**File:** `PySide6/nle/nle_tab.py`

Add shortcuts:
- [ ] Space - Play/Pause
- [ ] Delete - Delete selected clip
- [ ] S - Split at playhead
- [ ] Ctrl+S - Save project
- [ ] +/- - Zoom in/out

**Acceptance:**
- All shortcuts functional
- Shortcuts don't conflict

---

### Task 8.3: Undo/Redo System
**File:** `PySide6/nle/nle_history.py`

Implement command history:
- [ ] Store actions in stack
- [ ] Undo reverses last action
- [ ] Redo reapplies undone action
- [ ] Clear history on new project

**Acceptance:**
- Ctrl+Z undoes last action
- Ctrl+Y redoes
- Multiple undo levels work

---

## Dependencies Between Tasks

```
Phase 1 (1.1-1.4) - Foundation, no dependencies
Phase 2 (2.1-2.4) - Depends on Phase 1
Phase 3 (3.1-3.3) - Depends on Phase 2
Phase 4 (4.1-4.5) - Depends on Phase 3
Phase 5 (5.1-5.3) - Depends on Phase 4
Phase 6 (6.1-6.3) - Depends on Phase 5, parallel with Phase 7
Phase 7 (7.1-7.3) - Depends on Phase 4
Phase 8 (8.1-8.3) - Depends on Phase 7
```

---

## Testing Checklist

After each phase:
- [ ] No Python errors in console
- [ ] No Qt warnings
- [ ] Feature works as described
- [ ] Model and UI stay synchronized
- [ ] Memory usage reasonable (no leaks)
