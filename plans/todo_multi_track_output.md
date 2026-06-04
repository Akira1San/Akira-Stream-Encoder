# Multi-Track Audio Output — Investigation & TODO

## Goal

Allow users to select **multiple** audio tracks from the source to include in the output, not just a single track. Each selected track should be mappable independently (copy or re-encode).

## Design

Two modes should coexist for **both** audio and subtitle tracks:

1. **Single baked track** (default, current behavior) — pick one track, encode/burn it into the output. Works exactly like today.
2. **Multi-track passthrough** — check which tracks to keep. Each can be individually set to copy or re-encode (audio) or passthrough (subs). All selected tracks are mapped into the output container.

A toggle (e.g., checkbox "Enable Multi-Track" or a mode switch) determines which mode is active. When multi-track is off, the UI collapses to the familiar single-track dropdown.

## Current Limitation — Audio

| Layer | File | Bottleneck |
|-------|------|------------|
| Model | `models.py:TrackSettings` | `audio_stream_index: int` — single index |
| UI 1  | `tracks_panel.py` | `audio_track_combo` — single `QComboBox` |
| UI 2  | `encoding_settings.py` | `audio_track_combo` — single `QComboBox` |
| Backend (FFmpeg) | `backends/ffmpeg.py:build_command()` | Single `-map 0:a:N`, single `-c:a` flag |
| Backend (GStreamer) | `backends/gstreamer.py` | Hardcoded `demux.audio_0` pad, single chain |

## Current Limitation — Subtitles

| Layer | File | Bottleneck |
|-------|------|------------|
| Model | `models.py:SubtitleSettings` | `selected_subtitle: str` — path to an *external* file only |
| Model | `models.py:TrackSettings` | `subtitle_selected: bool` — no track index, no `available_subtitle_tracks` |
| Backend | `backends/ffmpeg.py` | Subtitle support is only burn-in via `subtitles=` filter or external `.srt/.ass` — no `-map` for passthrough |
| UI | `subtitles.py` | Only external file selector and burn-in toggle, no embedded track browser |
| Detection | Various | No ffprobe detection of embedded subtitle streams (unlike audio which has `get_audio_tracks`) |

## Required Changes — Audio

### 1. Model (`models.py`)

Replace `audio_stream_index: int` with a list:

```
selected_audio_indices: List[int]              — which tracks to include
```

Optionally, for per-track codec/copy control, add a dataclass:

```
AudioTrackAssignment
  - stream_index: int
  - mode: "copy" | "encode"
  - codec: str (override global)
```

### 2. UI — Track Selection (`tracks_panel.py`)

Replace single `QComboBox` with multi-select widget:

- **Option A**: `QListWidget` with `MultiSelection` mode + checkboxes per item
- **Option B**: Dynamic `QCheckBox` list (one per audio stream) + per-track encode/copy toggle

### 3. UI — Encoding Panel (`encoding_settings.py`)

Same multi-select change as `tracks_panel.py`. The `on_audio_track_changed` handler must update a list of indices instead of a single index.

### 4. FFmpeg Backend (`backends/ffmpeg.py`)

**`build_command()`** — iterate over selected tracks:

```
for i, idx in enumerate(selected_audio_indices):
    cmd += ["-map", f"0:a:{idx}"]
    if per_track_copy:
        cmd += [f"-c:a:{i}", "copy"]
    else:
        cmd += [f"-c:a:{i}", codec, ...]
```

Also update `fast_cut()` and the extract-clip code path. The `-an` fallback is fine as-is.

### 5. GStreamer Backend (`backends/gstreamer.py`)

Route multiple audio pads from the demuxer:

```
for i, idx in enumerate(selected_audio_indices):
    pad = f"audio_{idx:02x}"
    chain = [f"demux.{pad}", "!", "queue", "!", "decodebin", "!",
             "audioconvert", "!", "queue", "!", encoder, "!",
             "queue", "!", "mux."]
```

`_build_audio_chain()` must accept a stream index parameter.

### 6. Other Impacted Files (Audio)

- `tracks_panel.py:get_selected_tracks_filter()` — return `[f"a:{i}" for i in selected_indices]`
- `handbrake_handler.py` — if used for DVD, may need its own multi-track logic
- `controller.py:join_segments()` — concat filter_complex must handle multiple audio maps

## Required Changes — Subtitles

### 1. Model (`models.py`)

Add embedded subtitle track support to `TrackSettings`:

```
SubtitleTrackInfo
  - index: int
  - codec: str (e.g. subrip, ass, hdmv_pgs)
  - language: str
  - title: str

TrackSettings additions:
  - available_subtitle_tracks: List[SubtitleTrackInfo]
  - selected_subtitle_indices: List[int]          # tracks to passthrough
  - subtitle_burn_index: int = -1                 # which embedded track to burn (-1 = use external file)
```

### 2. Detection

Add `get_subtitle_tracks()` to backends (ffprobe filter for `codec_type == 'subtitle'`) — mirrors the existing `get_audio_tracks()` pattern.

### 3. UI — Subtitles Panel (`subtitles.py`)

Add:
- Embedded subtitle track browser with checkboxes (multi-select for passthrough)
- Radio/choice for "Burn which track?" (pick one embedded track OR external file)
- Each selected track can be flagged for passthrough (`-c:s copy`)

### 4. FFmpeg Backend

**`build_command()`** — add subtitle passthrough maps:

```
for idx in selected_subtitle_indices:
    cmd += ["-map", f"0:s:{idx}"]
    cmd += ["-c:s:output_index", "copy"]
```

Ensure `-map -0:s` is only applied when burning subs (to exclude embedded from passthrough). Currently the code already does `-map -0:s` when burning external subs, but this would conflict with multi-track passthrough.

### 5. GStreamer Backend

Add subtitle pad routing similar to audio, using `subtitle_N` pads from the demuxer.
