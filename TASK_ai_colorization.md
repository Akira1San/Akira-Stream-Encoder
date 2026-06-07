# AI Colorization Integration Task

Integrate deep learning-based video colorization into MyEncoder using **ECCV16**
(Zhang et al.) and **DeOldify** (J. Antic) models, building on the existing
non-AI colorization (Tint/Pseudocolor/LUT) from the Color Correction panel.

---

## 1. Overview

### ECCV16 ("Lightweight")
- **Paper:** *Colorful Image Colorization* (ECCV 2016)
- **Author:** Richard Zhang et al.
- **Model:** Small CNN (~1.5 MB weights); runs on **CPU** comfortably
- **Approach:** Predicts `ab` channels in CIE Lab color space from `L` channel
- **Output:** Plausible but often washed-out / desaturated colors
- **Weight URL:** https://colorizers.s3.us-east-2.amazonaws.com/colorization_release_v2-9b330a0b.pth
- **PyTorch code:** https://github.com/richzhang/colorization/blob/master/colorizers/eccv16.py

### DeOldify (Video model)
- **Author:** Jason Antic
- **Model:** ResNet101 U-Net, NoGAN training
- **Weights:** ~834 MB (`ColorizeVideo_gen.pth`), plus critic weights
- **Dependency:** Requires **fastai** (PyTorch wrapper) or raw PyTorch
- **Output:** Vibrant, temporally-stable colors for video
- **Repo:** https://github.com/jantic/DeOldify
- **Modern fork:** https://github.com/thookham/DeOldify (PyTorch 2.5+, CUDA 12.x)

---

## 2. Environment Assessment

| Item | Status |
|---|---|
| Python | 3.13.5 | ✅ |
| PyTorch | 2.6.0 (cu124) | ✅ |
| torchvision | 0.21.0 | ✅ |
| fastai | **Installed (broken on Python 3.13)** — used pure PyTorch reimplementation |
| OpenCV (cv2) | 4.13.0 (headless) | ✅ |
| CUDA Driver | 580.142 (CUDA 13.0) | ✅ |
| GPU | NVIDIA (available) | ✅ |
| ONNX Runtime | Not installed |
| FFmpeg | Available |

**Python packages to install:**
```
torch torchvision --index-url https://download.pytorch.org/whl/cu124
fastai  (only needed for DeOldify)
opencv-python-headless
numpy
Pillow             (already optional dep)
```

**DeOldify model weights to download:**
- `ColorizeVideo_gen.pth` (834 MB) — video model
- `ColorizeArtistic_gen.pth` (243 MB) — artistic image model
- `ColorizeStable_gen.pth` (834 MB) — stable image model

**ECCV16 model weights to download:**
- `colorization_release_v2-9b330a0b.pth` (128 MB)

**SIGGRAPH17 model weights to download:**
- `siggraph17-df00044c.pth` (137 MB)

---

## 3. Architecture

### 3.1 New Module: `PySide6/colorizers/`

```
PySide6/
  colorizers/
    __init__.py
    base.py              # Abstract base class for all colorizers
    eccv16.py            # ECCV16 implementation
    deoldify.py          # DeOldify implementation (wraps fastai/PyTorch)
    utils.py             # Frame pre/post-processing, Lab/RGB conversions
    models/              # Downloaded weight files (gitignored)
```

### 3.2 Abstract Interface (`base.py`)

```python
from abc import ABC, abstractmethod
import numpy as np

class Colorizer(ABC):
    @abstractmethod
    def colorize_frame(self, l_channel: np.ndarray) -> np.ndarray:
        """Take L channel (HxW float32 0-1), return RGB (HxWx3 uint8)"""
        ...

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def supports_batch(self) -> bool: ...

    @abstractmethod
    def supported_filters(self) -> dict: ...
```

### 3.3 Integration into Backend — Segment Pipeline

The AI colorization pipeline splits the video into **fixed-duration segments**
(1 or 5 min), processes each independently, then concatenates the results.

```
Input video
  → FFmpeg split into N segments (keyframe-aligned)
      → segment_001.mp4
          → FFmpeg decode raw frames
          → AI Colorizer (batched GPU inference)
          → FFmpeg encode segment_001_colorized.mp4
      → segment_002.mp4 → ... (same as above)
      → segment_003.mp4 → ...
  → FFmpeg concat segments → output_colorized.mp4
  → Copy original audio stream (unchanged)
```

**Why segments?**
| Benefit | Detail |
|---|---|
| Bounded GPU memory | Only holds frames for one segment (e.g. 1 min at 30 fps = 1800 frames) |
| Cancel/resume | Failed segment can be retried independently |
| Progress tracking | Reports which segment + frame are being processed |
| Parallelism | Segments can run in parallel across multiple GPUs or processes |
| Temp disk | Each segment's raw frames stored temporarily, then cleaned up |

**Segment sizing logic:**
- Short videos (< 5 min): single segment, no split
- Long videos: split into `segment_duration` segments (default 1 min)
- Segments aligned to nearest keyframe for clean concatenation

### 3.4 New Settings Model

```python
@dataclass
class AIColorizationSettings:
    enabled: bool = False
    engine: str = "eccv16"              # "eccv16" / "deoldify"
    deoldify_model: str = "video"       # "video" / "artistic" / "stable"
    render_factor: int = 21             # DeOldify quality/speed (10-45)
    saturation: float = 1.0             # 0.1 - 2.0 (both engines)
    fp16: bool = True                   # Half-precision on GPU
    gpu_device: str = "cuda:0"          # "cuda:0" / "cpu"
    batch_size: int = 4                 # Frames per GPU inference batch
    segment_duration: int = 1           # Minutes per segment (1 or 5)
```

Add to `AppState`:
```python
self.ai_colorization = AIColorizationSettings()
```

---

## 4. Implementation Steps

### Phase 1 — ECCV16 + SIGGRAPH17 ✅

| # | Step | Files | Details |
|---|---|---|---|
| 1.1 | Install deps | — | `pip install torch torchvision opencv-python-headless numpy` | ✅ |
| 1.2 | Download ECCV16 weights | `PySide6/colorizers/models/` | 128 MB, `colorization_release_v2-9b330a0b.pth` | ✅ |
| 1.3 | Port ECCV16 model | `colorizers/eccv16.py` | Copy architecture from `richzhang/colorization/colorizers/eccv16.py`; strip training code, load `.pth` weights | ✅ |
| 1.4 | Base class + utils | `colorizers/base.py`, `colorizers/utils.py` | Abstract colorizer interface; Lab↔RGB, frame I/O helpers | ✅ |
| 1.5 | Frame pipeline test | — | Script that decodes a frame with FFmpeg, colorizes with ECCV16, encodes output | ✅ |
| 1.6 | Full video pipeline | — | Pipe all frames through FFmpeg decode → ECCV16 → FFmpeg encode | ✅ |
| 1.7 | Port SIGGRAPH17 model | `colorizers/siggraph17.py` | UNet architecture (~40M params), better quality than ECCV16 | ✅ |
| 1.8 | Download SIGGRAPH17 weights | `PySide6/colorizers/models/` | 137 MB, `siggraph17-df00044c.pth` | ✅ |
| 1.9 | Disk-based pipeline | `controller.py` | Extract → Colorize → Recombine with pipeline UI buttons | ✅ |
| 1.10 | Post-processing | `colorizers/utils.py` | Saturation, contrast, denoise sliders | ✅ |

**ECCV16 inference flow:**
```
FFmpeg:  -f rawvideo -pix_fmt gray -s {W}x{H} -r {fps} -i -
Python:  read raw luma bytes → reshape → normalize → torch → model.forward()
         → ab channels → combine with L → Lab→RGB → write raw RGB bytes
FFmpeg:  -f rawvideo -pix_fmt rgb24 -s {W}x{H} -r {fps} -i -
```

### Phase 2 — DeOldify Integration ✅

| # | Step | Files | Details |
|---|---|---|---|---|
| 2.1 | Install fastai | — | `pip install fastai` — SKIPPED: fastai 2.8.7 broken on Python 3.13 (callback.py vs callback/ shadow); used pure PyTorch reimplementation instead | ❌ (see note) |
| 2.2 | Download weights | `colorizers/models/` | `ColorizeVideo_gen.pth` (834 MB), `ColorizeArtistic_gen.pth` (243 MB) | ✅ |
| 2.3 | Port DeOldify | `colorizers/deoldify.py` | Pure PyTorch reimplementation matching checkpoint architecture: `DynamicUnetWide` (Video/Stable) + `DynamicUnetDeep` (Artistic); 0 missing / 0 unexpected weights | ✅ |
| 2.4 | Render factor support | `colorizers/deoldify.py` | Map `render_factor` to internal resolution scaling (10-45) | ✅ |
| 2.5 | Temporal smoothing | `colorizers/deoldify.py` | Frame overlap / optical flow blending for flicker reduction | ⏳ |

### Phase 3 — Integration into App ✅

| # | Step | Files | Details |
|---|---|---|---|---|
| 3.1 | Add AI colorization panel | `colorizers/panel.py` OR extend `color_correction.py` | New "AI Colorization" section: engine selector, DeOldify model variant, render factor, saturation, device | ✅ |
| 3.2 | Wire into controller | `controller.py` | New `encode_with_ai_colorization()` method; orchestrates FFmpeg decode → colorizer → FFmpeg encode pipeline | ✅ |
| 3.3 | Preview support | `video_preview.py` — `apply_filters()` | If AI colorization enabled and frame is grayscale, run it through the colorizer; **performance concern**: run on separate thread, cache result |
| 3.4 | Progress reporting | `controller.py` | Report per-frame progress during encode | ✅ |
| 3.5 | GPU memory management | `colorizers/base.py` | Batch sizing, CUDA memory cleanup, fallback to CPU | ✅ |

### Phase 4 — Polish

| # | Step | Details |
|---|---|---|
| 4.1 | Lazy model loading | Load model on first use, not at app startup | ✅ |
| 4.2 | Weight download UI | In-app download of missing weights with progress bar |
| 4.3 | Batch size auto-tune | Auto-detect optimal batch size from GPU memory |
| 4.4 | Cancel support | Interrupt colorization mid-stream | ✅ |
| 4.5 | ONNX export (optional) | Convert ECCV16 to ONNX for faster CPU inference via onnxruntime |

### Phase 4b — DeOldify Bugfixes & Color Quality

| # | Step | Details |
|---|---|---|
| 4b.1 | Fix button-stuck bug | Replace `QTimer.singleShot` from worker thread with proper `Signal` (`_ai_single_done`) |
| 4b.2 | Fix crash-safety | `try/finally` wrapper in `on_ai_colorize_single_image` |
| 4b.3 | Fix Stable download URL | `thookham/DeOldify` → `spensercai/DeOldify` in `MODEL_URLS` |
| 4b.4 | Fix ECCV16/SIGGRAPH17 double-centering | `_prepare_input` changed from `l_channel * 100.0 - 50.0` to `l_channel * 100.0` |
| 4b.5 | Fix fp16/OpenCV crash | Add `.float()` before `.numpy()` in `_post` |
| 4b.6 | SelfAttention gamma fix | Zero gamma on load for Video/Stable (negative gamma caused resolution-dependent color instability at >128px) |
| 4b.7 | Aspect-ratio fix | `_pre` changed from squaring to `(sz, sz)` to preserving aspect ratio (short side = rf×16) |
| 4b.8 | Switch to `(o+3)/6` denorm | Replace `(o * std + mean)` with `(o + 3) / 6` (version B) per user preference |
| 4b.9 | Per-model color cast correction | UV offset correction in YUV space after blend; configurable via `color_correct_strength` slider (0-1, default 0.5) |
| 4b.10 | Saturation slider | Already existed; wired through `apply_postprocessing` |
| 4b.11 | DeOldify-only widget visibility | DeOldify-specific controls hidden when other engine selected |

### Debug results — uniform-gray model response (SelfAttention fixed, (o+3)/6)

| Variant | R | G | B | U offset | V offset |
|---|---|---|---|---|---|
| Video | 0.453 | 0.547 | 0.531 | +1.7 | -14.5 |
| Artistic | 0.301 | 0.475 | 0.802 | +42.9 | -35.6 |
| Stable | 0.103 | 0.575 | 0.957 | +60.2 | -83.6 |

Offsets computed as BT.601 YUV center deviation from 128 (neutral gray).

### Commits

| Commit | Description |
|---|---|
| `8f8fe3a` | Initial DeOldify pure PyTorch reimplementation |
| `7771c98` | Wire DeOldify into controller, UI, settings |
| `02e493e` | Fix single-image colorize button stuck disabled |
| `105cc90` | Fix Stable model download URL |
| `36873e2` | Fix colorizer bugs causing desaturated 'blob' output |
| `773e202` | Fix cv2.resize crash with fp16 tensors in DeOldify _post |
| `b98ff84` | Fix DeOldify Video/Stable resolution-dependent color instability |
| `466cd75` | Switch DeOldify to (o+3)/6 denorm, add per-model YUV color cast correction |
| `ee6b397` | Add Color Correct strength slider to DeOldify UI panel |

### Phase 5 — Single-Image UI Redesign

Current `Colorize Single Image` button is slow (loads model, processes, saves all in one click).
Redesign to a list-based workflow for faster iteration:

| # | Step | Details |
|---|---|---|
| 5.1 | Replace button with list + controls | `QListWidget` + Load / Remove buttons |
| 5.2 | Load button | File dialog (multi-select images), adds paths to list |
| 5.3 | Remove button | Removes selected item from list |
| 5.4 | Colorize button | Enabled when an item is selected; processes that single image |
| 5.5 | Auto output dir | Create `{filename}_colorized/` folder next to input image, save result there |
| 5.6 | Model stays loaded | Keep colorizer instance alive so subsequent colorizations are fast |

---

## 5. UI Design

The AI Colorization panel should be placed as a **new section inside the Color Correction panel** (or as a collapsible sub-section), below the existing non-AI colorization controls:

```
┌─ Color Correction (Collapsible) ──────────────────────────┐
│  ☑ Enable Color Correction                                 │
│  [Brightness] ────●──────                                  │
│  ...                                                       │
│  ─────────────────────────────────────                     │
│  ☑ Enable Colorization (B&W → Color)  [Method: Tint ▼]   │
│  ... (existing non-AI controls)                            │
│  ─────────────────────────────────────                     │
│  ☑ Enable AI Colorization                                  │
│  Engine: [ECCV16 ▼]  Device: [GPU (CUDA) ▼]              │
│  ┌─ AI Settings ──────────────────────────────────┐       │
│  │ Saturation:  ●───────  (0.1 – 2.0)             │       │
│  │ Batch Size:  [4]  Frames                       │       │
│  │ Render Factor: [21]   (DeOldify only, 10-45)   │       │
│  │ Model: [Video ▼]     (DeOldify only)           │       │
│  │ FP16: ☑  (GPU only, ~2x faster)               │       │
│  │ ┌──────────────────────────────────────────┐   │       │
│  │ │ ⚠ Model weights not found                │   │       │
│  │ │ [Download ECCV16 weights (1.5 MB)]       │   │       │
│  │ └──────────────────────────────────────────┘   │       │
│  └────────────────────────────────────────────────┘       │
│                                                           │
│  [Reset All]                                              │
└───────────────────────────────────────────────────────────┘
```

### Key UI considerations:
- **Engine selection** defaults to ECCV16 (lightweight, CPU-friendly)
- **DeOldify** is the premium option; show GPU memory warning on first use
- **Model weight status** shown inline with download button if missing
- **Render factor** only visible when DeOldify selected
- **Batch size** visible for both

---

## 6. Performance Expectations

| Engine | Device | Speed (720p) | Quality | Memory |
|---|---|---|---|---|
| ECCV16 | CPU | ~15 fps | Washed-out | ~200 MB |
| ECCV16 | GPU (CUDA) | ~60 fps | Washed-out | ~500 MB |
| DeOldify Video | GPU (CUDA) | ~8-12 fps | Vibrant, stable | ~3 GB |
| DeOldify Artistic | GPU (CUDA) | ~5-8 fps | Most vibrant | ~3 GB |

For video longer than a few minutes, ECCV16 on GPU is recommended as the
practical default.

---

## 7. Files to Modify / Create

### New files
| File | Purpose |
|---|---|---|
| `PySide6/colorizers/__init__.py` | Package init |
| `PySide6/colorizers/base.py` | Abstract `Colorizer` base class |
| `PySide6/colorizers/eccv16.py` | ECCV16 model + inference |
| `PySide6/colorizers/siggraph17.py` | SIGGRAPH17 model + inference |
| `PySide6/colorizers/deoldify.py` | DeOldify model + inference |
| `PySide6/colorizers/utils.py` | Frame I/O, color space conversions |
| `PySide6/colorizers/models/` | Downloaded weights (gitignored) |

### Modified files
| File | Changes |
|---|---|
| `PySide6/models.py` | Add `AIColorizationSettings` dataclass, wire into `AppState` |
| `PySide6/color_correction.py` | Add AI Colorization section below existing colorization |
| `PySide6/backends/base.py` | Add ai_colorization to `supported_filters()` |
| `PySide6/backends/ffmpeg.py` | Add ai_colorization filter support |
| `PySide6/backends/gstreamer.py` | Mark ai_colorization as False |
| `PySide6/controller.py` | Add AI colorization encode pipeline |
| `PySide6/video_preview.py` | Add AI colorization preview support |
| `PySide6/video_workspace.py` | Wire AI colorization signals |

---

## 8. Dependencies

```
# Core ML
torch>=2.0.0
torchvision>=0.15.0

# DeOldify (optional, only if using DeOldify engine)
fastai>=2.7.0

# Image processing
opencv-python-headless>=4.8.0
numpy>=1.24.0

# Already installed (or optional):
Pillow>=10.0.0
```

### Model weight URLs

```
ECCV16:
  https://colorizers.s3.us-east-2.amazonaws.com/colorization_release_v2-9b330a0b.pth

SIGGRAPH17:
  https://colorizers.s3.us-east-2.amazonaws.com/siggraph17-df00044c.pth

DeOldify (modern fork, PyTorch 2.5+):
  https://huggingface.co/thookham/DeOldify/resolve/main/ColorizeVideo_gen.pth
  https://huggingface.co/thookham/DeOldify/resolve/main/ColorizeArtistic_gen.pth
  https://huggingface.co/thookham/DeOldify/resolve/main/ColorizeStable_gen.pth
```

---

## 9. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| fastai dep is heavy (800+ MB) | Offer as optional; use raw PyTorch inference for DeOldify if possible |
| GPU OOM on large video | Batch size auto-tuning, CPU fallback |
| Preview too slow for real-time | Run preview on downscaled frame, cache result |
| Python GIL limits frame pipeline | Use `multiprocessing.Queue` for parallel decode/colorize/encode |
| Model weights copyright | Both are MIT licensed; host weights separately |
| Temporal flickering (frame inconsistency) | Apply temporal smoothing (DeOldify video model already handles this) |

---

### Phase 6 — DDColor Integration

**DDColor** (Tencent ARC 2023, ICCV) — ConvNeXt-L/T encoder + transformer-based color decoder. MIT license.

| # | Step | Files | Details |
|---|---|---|---|
| 6.1 | Create `ddcolor.py` | `colorizers/ddcolor.py` | Self-contained model definition: `DDColor`, `ImageEncoder` (ConvNeXt-L/T), `DuelDecoder`, `MultiScaleColorDecoder` + inlined utilities (ConvNeXt blocks, transformer attention layers, position encoding, UNet blocks) — no `basicsr` dependency |
| 6.2 | `DDColorColorizer` class | `colorizers/ddcolor.py` | Implements `Colorizer` ABC: `_load()` builds model + loads weights; `colorize_frame(l)` converts L→grayscale RGB→model→AB→`luma_to_rgb()`; `colorize_batch(b)` loops over batch; `supports_batch()→True` |
| 6.3 | Export in `__init__.py` | `colorizers/__init__.py` | Add `from colorizers.ddcolor import DDColorColorizer` |
| 6.4 | Settings model | `models.py` | Add `ddcolor_model: str = "modelscope"` (variants: "modelscope", "paper_tiny") and `ddcolor_input_size: int = 512` (256–1024) to `AIColorizationSettings` |
| 6.5 | Controller dispatch | `controller.py` | Add `"ddcolor"` branch in `_get_colorizer()`: load variant weight, select ConvNeXt size automatically (tiny for paper_tiny, large for modelscope), pass `input_size` |
| 6.6 | UI: engine selector | `color_correction.py` | Add `"DDColor (ConvNeXt)"` to `ai_engine_combo`; map in `on_ai_engine_changed` |
| 6.7 | UI: variant dropdown | `color_correction.py` | DDColor-specific widgets: model variant combo (modelscope/paper_tiny), input size spinner; show/hide based on engine |
| 6.8 | Weight URLs | `TASK_ai_colorization.md` (docs) | Document HuggingFace download URLs for both variants |

**DDColor variants and sizes:**

| Variant | Size | Encoder | Weight Size | HF Repo |
|---|---|---|---|---|
| modelscope (default) | large | ConvNeXt-L | ~700 MB | `piddnad/ddcolor_modelscope` |
| paper_tiny | tiny | ConvNeXt-T | ~350 MB | `piddnad/ddcolor_paper_tiny` |

**Key differences from existing engines:**
- Takes grayscale **RGB** (3-channel, AB=0) instead of raw L channel
- Internal ImageNet normalization (mean=[0.485,0.456,0.406], std=[0.229,0.224,0.225])
- Works at fixed input resolution (default 512px, user-configurable)
- ConvNeXt decoder may be sensitive to fp16 — default FP16 off for DDColor

---

### Other Engines — Future Testing

| Model | Year | Approach | Weight Size | Notes |
|---|---|---|---|---|
| **BigColor** | CVPR 2022 | BigGAN-based, gray→color + mask| ~200 MB | [github.com/KIMGEONUNG/BigColor](https://github.com/KIMGEONUNG/BigColor) — small, creative results. Low risk: only requires `timm` + `scikit-image` beyond torch/numpy/cv2 |
