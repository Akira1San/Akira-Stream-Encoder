# AI Upscaling Integration for MyEncoder

## Overview

Add AI-based super-resolution upscaling to MyEncoder using external Vulkan-powered binaries. Users can upscale video via a 3-step pipeline: **Extract Frames** → **Upscale Frames** → **Recombine Video**, with support for resumable chunked processing.

---

## Supported Upscalers

| Upscaler | Type | Source | Models |
|---|---|---|---|
| **Real-ESRGAN-ncnn-vulkan** | Neural network (ncnn) | https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan | `realesrgan-x4plus`, `realesrnet-x4plus`, `realesrgan-x4plus-anime`, `reales-animevideov3` |
| **Anime4K-ncnn-vulkan** | GLSL shader (ncnn port) | https://github.com/Tps-F/Anime4K-ncnn-vulkan | `A`, `B`, `C` (strength presets) |

### Download links (Linux)

- Real-ESRGAN: https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-ubuntu.zip
- Anime4K: https://github.com/Tps-F/Anime4K-ncnn-vulkan/releases

Extract both into `PySide6/backends/` as `realesrgan-ncnn-vulkan/` and `anime4k-ncnn-vulkan/`.

---

## Pipeline Architecture

### Chunked Frame Structure

```
frames_workdir/
└── <video_stem>/
    ├── 001_00m-01m/                 ← extracted frames (60s @ 24fps ≈ 1440 files)
    │   ├── frame_00000001.png
    │   ├── frame_00000002.png
    │   └── ...
    ├── 001_00m-01m_upscaled/        ← AI upscaled frames (mirrored structure)
    │   ├── frame_00000001.png
    │   ├── frame_00000002.png
    │   └── ...
    ├── 002_01m-02m/
    ├── 002_01m-02m_upscaled/
    ├── 003_02m-03m/
    ├── 003_02m-03m_upscaled/
    └── ...
```

- Each part resets numbering at `frame_00000001.png`.
- Each part has its own `_upscaled/` mirror directory.
- **Resume logic**: if a part/upscaled folder exists with the expected frame count, skip it.
- `*_upscaled/` folders are recombined into temp part MP4s, then concatenated.

### 3-Step Pipeline

```
User clicks                    System does
───────────────────────────────────────────────────────────────────
[⬇ Extract Frames]     ffprobe get duration / fps
                       → split into N parts (configurable part size)
                       → for each part: ffmpeg -i input -ss start -t dur -q:v 2 part_NNN/frame_%08d.png
                       (skips existing part folders)

[🔄 Upscale All]        For each part folder without _upscaled/:
                          realesrgan-ncnn-vulkan -i part_NNN/ -o part_NNN_upscaled/ -s scale -n model
                       Anime4K alternative:
                          anime4k-ncnn-vulkan -i part_NNN/ -o part_NNN_upscaled/ -p preset

[🎬 Recombine Video]    For each _upscaled/ folder:
                          ffmpeg -i part_NNN_upscaled/frame_%08d.png -c:v libx264 -r fps -pix_fmt yuv420p tmp_part_NNN.mp4
                       → concat all tmp mp4s → final_upscaled.mp4
                       → clean up tmp part mp4s
```

---

## Files to Modify

### 1. `PySide6/config.py`
Add constants:
- `REALESRGAN_NCNN` — path to Real-ESRGAN binary
- `ANIME4K_NCNN` — path to Anime4K binary
- `UPSCALING_MODELS` — dict of model info per upscaler

### 2. `PySide6/models.py`
Add `AIUpscalingSettings` dataclass:
- `enabled`, `upscaler`, `model`, `scale`, `tile_size`, `part_duration`
- `frames_dir`, `frames_extracted`, `frames_upscaled`, `frames_recombined`
- `cleanup_temp`

Add to `AppState.__init__`: `self.ai_upscaling = AIUpscalingSettings()`

### 3. `PySide6/encoding_settings.py`
Add AI upscaling UI in the Scale section (after existing scale controls):
- "AI Upscaling" checkbox with model/scale/tile config
- "Part Duration" selector (1 min / 5 min / custom)
- Frames directory chooser
- 3 pipeline buttons with status labels
- Progress bar for Upscale All
- Cleanup checkbox
- Resume-aware: buttons enable/disable based on state

### 4. `PySide6/backends/base.py`
Add abstract methods:
- `get_video_fps(input_path) -> float`
- `extract_frames(input_path, frames_dir, part_duration) -> bool`
- `upscale_frames(frames_dir, upscaler, model, scale, tile_size) -> bool`
- `recombine_frames(frames_dir, output_path, fps) -> bool`
- `get_part_dirs(frames_dir) -> list`

### 5. `PySide6/backends/ffmpeg.py`
Implement all pipeline methods using subprocess.

### 6. `PySide6/controller.py`
Add orchestration methods that wrap backend calls with progress reporting and state management.

---

## UI Design

Inserted inside the Scale section of `encoding_settings.py`, after the aspect ratio control:

```
▸ AI Upscaling  [☐ Enable]        [Auto-cleanup frames ☐]
─────────────────────────────────────
  Upscaler: [Real-ESRGAN ▾]        Model: [realesrgan-x4plus ▾]
  Scale:    [4x ▾]                 Tile:  [0 (auto)]

  Frames:   [/tmp/myencoder_frames/] [Browse]
  Part:     [1 min ▾]

  ── Pipeline ──

  [⬇ Extract Frames]     Status: Done ✓ (12 parts)

  Part: [001_00m-01m ▾]  [🔄 Upscale Part]  

  [🔄 Upscale All (remaining)]     ████░░░░░░ 5/12 parts

  [🎬 Recombine Video]    Status: Waiting...

─────────────────────────────────────
```

---

## Controls & Signals

| Control | Signal | Handler |
|---|---|---|
| AI Upscaling checkbox | `toggled` | `on_ai_upscaling_toggled` |
| Upscaler combo | `currentTextChanged` | `on_upscaler_changed` |
| Model combo | `currentTextChanged` | `on_ai_model_changed` |
| Scale combo | `currentTextChanged` | `on_ai_scale_changed` |
| Tile size spinbox | `valueChanged` | `on_ai_tile_changed` |
| Part duration combo | `currentTextChanged` | `on_part_duration_changed` |
| Extract button | `clicked` | `on_extract_frames` |
| Upscale Part button | `clicked` | `on_upscale_part` |
| Upscale All button | `clicked` | `on_upscale_all` |
| Recombine button | `clicked` | `on_recombine_frames` |

---

## Resume Logic

| Step | Resume Check |
|---|---|
| Extract | Part folder exists AND has `ceil(fps * part_duration)` files → skip |
| Upscale | `*_upscaled/` folder exists AND has matching frame count → skip |
| Recombine | Temp part MP4 exists → skip; only concat missing ones |

---

## Future Improvements

- **Python Real-ESRGAN backend** — optional PyTorch-based backend for users who want CUDA acceleration and face enhancement
- **Preview** — show a before/after comparison of a sample frame after upscaling
- **Batch queue** — process multiple videos in sequence
- **GPU selection** — for multi-GPU systems
- **Auto mode** — skip manual buttons, run the full pipeline automatically on encode
