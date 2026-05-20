# DVD Subtitle & Encoding Issues

## 1. Subtitle Track Selection Mismatch ✅ Done

### Problem
User selects "track 0 bg" (Bulgarian) but English subtitles are burned in. The app's subtitle index doesn't match HandBrake's numbering.

### Root Cause
The app detects DVD subtitle tracks via FFmpeg/IFO probing and assigns 0-based indices. HandBrake uses its own 1-based numbering. The mapping `hb_track = subtitle_track + 1` assumes indices align, but FFmpeg and HandBrake may discover subtitle streams in different orders.

HandBrake scan shows:
- Track 1: English
- Track 2: Bulgarian (`bg`)
- Track 3: Spanish
- Track 4: Portuguese

If the app's internal list has Bulgarian at index 0, then `subtitle_track = 0` → `hb_track = 1` → English (wrong).

### Fix
Use HandBrake's JSON subtitle scan (`--json`) to get ISO 639-2 language codes, then map the app's ISO 639-1 (2-letter) codes to HandBrake's ISO 639-2 (3-letter) codes:

1. After title matching, call `handler.scan_subtitles(dvd_folder, title_number)` with `--json` flag
2. Map app's 2-letter code (e.g. `bg`) to 3-letter (`bul`) via `ISO639_1_TO_639_2` dict
3. Find the HandBrake track whose `language_code` matches
4. Use HandBrake's direct 1-based track number (no `+1` offset)

### Files changed
- `handbrake_handler.py`: rewrote `scan_subtitles()` to parse JSON output with `LanguageCode`
- `controller.py`: `_encode_with_handbrake()` maps by ISO code instead of name
- Added `ISO639_1_TO_639_2` mapping dict (ISO 639-1 → ISO 639-2)

---

## 2. `decavsub: track 1, invalid PTS` Warnings

### Problem
HandBrake logs `[warning] decavsub: track 1, invalid PTS` for every chapter.

### Root Cause
VOBSUB subtitle streams in this DVD have invalid/missing PTS for some packets. Generally harmless.

### Status
Cosmetic — ignore unless it causes subtitle desync (see issue 4). Bulgarian Cyrillic subtitles appear/disappear when scrubbing the timeline, likely related to these invalid PTS values.

---

## 3. Trim/Clip Extraction Ignored with HandBrake ✅ Done

### Problem
Enable clip extraction (start=3min, duration=1min) is ignored — encodes entire DVD (1h 27min).

### Root Cause
`_encode_with_handbrake()` doesn't forward `start_time`/`duration` from `encode_file()`. Additionally, the extract clip UI values (`extract_start_min`/`extract_duration_min`) were only read inside `build_ffmpeg_command()` — they were never forwarded to the HandBrake path.

```python
# controller.py:1118-1121
if use_handbrake:
    return self._encode_with_handbrake(
        input_path, output_path, progress_callback  # trim params missing!
    )
```

HandBrake supports: `--start-at duration:180 --stop-at duration:60`

### Fix
1. Added extract clip handler in `encode_file()` before HandBrake/FFmpeg branching reads `extract_start_min`/`extract_duration_min` from app_state and sets `start_time`/`duration`
2. Added `start_time`/`duration` params to `_encode_with_handbrake()`
3. Forwarded them from `encode_file()`
4. Added `--start-at`/`--stop-at` in `handbrake_handler.py:encode_with_subs()`

---

## 4. Subtitle Desync / Flicker ⏳ Needs Investigation

### Problem
Subtitles misalign/disappear after ~14 min. Also observed: Bulgarian subtitles appear and disappear when scrubbing the timeline in a short encode (5 min trim).

### Possible Causes
- Accumulated `invalid PTS` causing HandBrake sync loss
- VOB concat boundaries breaking subtitle stream timing
- DVD-specific stream structure issue

### Investigation
1. Check if desync happens on original DVD (not just encode)
2. Try encode without subtitle burn, compare
3. Check if `invalid PTS` correlates with VOB file boundaries
4. Test with another DVD

---

## 5. Preview Subtitle Display

### Problem
Video preview doesn't show burned subtitles, making it impossible to verify subtitle timing/position before encoding.

### Fix Options
**Option A: FFmpeg subtitles filter** (Recommended)
- Pass selected subtitle file (SRT/ASS) or DVD subtitle stream through FFmpeg's `subtitles` or `ass` filter
- For DVD subtitles: extract VOBSUB, use `subtitles=file.sub:original_size=720x576`

**Option B: Separate subtitle overlay**
- Render subtitle text independently and overlay on preview frame
- Text-based only (SRT/ASS), not bitmap DVD subs

**Option C: FFmpeg subprocess with burn**
- Run separate ffmpeg process with subtitle burn into preview pipe
- More robust, higher latency

### Notes
- SRT/ASS: use `subtitles=file.srt` filter (trivial)
- DVD VOBSUB: extract and use `subtitles=file.sub:original_size=720x576`
- Preview should respect font/size/position/color settings
