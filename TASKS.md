# FFmpeg 8.1 Enhancement Tasks

## Overview
This document outlines planned enhancements for the encoder program leveraging FFmpeg 8.1's new features including Vulkan, CUDA, and advanced filters.

---

## Priority 1: GPU-Accelerated Filters (High Impact)

### 1.1 Add nlmeans_vulkan (GPU Denoise)
- **Filter**: `nlmeans_vulkan`
- **Use**: Replace HQDN3D for faster GPU-accelerated denoising
- **Location**: Filters panel → Video filters
- **Implementation**: Add as alternative to HQDN3D
- **Preview Support**: Yes - add to `video_preview.py:apply_filters()`
- **Example**: `nlmeans_vulkan=s=7`

### 1.2 Add bm3d (Premium Denoise)
- **Filter**: `bm3d` (Block-Matching 3D)
- **Use**: Best quality software denoising
- **Note**: Slower but much better results for old video
- **Preview Support**: Check if supported in preview
- **Example**: `bm3d=sigma=15`

---

## Priority 2: Enhancement Filters

### 2.1 Add Deband Filter
- **Filter**: `deband`
- **Use**: Remove compression banding artifacts (common in old DVDs)
- **Parameters**: `deband=threshold=4:range=8:blur=yes`
- **Location**: Filters panel (near sharpen/deblock)
- **Preview Support**: Add to `video_preview.py`
- **Example**: `deband=filter=strong:threshold=4:range=8`

### 2.2 Add CAS (Contrast Adaptive Sharpen) ✅ DONE
- **Filter**: `cas` (Contrast Adaptive Sharpen)
- **Use**: Better sharpening than unsharp (edge-aware, no halos)
- **Parameters**: `cas=0.0` to `3.0` (strength)
- **Location**: Filters panel → Alternative to Sharpen
- **Preview Support**: Add to `video_preview.py`
- **Example**: `cas=1.0`
- **NOTE**: This is a CPU software filter (NOT GPU). Uses libavfilter, available since FFmpeg 4.3. Different from AMD FidelityFX CAS (GPU).

---

## Priority 3: GPU Deinterlace Options

### 3.1 Add yadif_cuda
- **Filter**: `yadif_cuda`
- **Use**: NVIDIA GPU deinterlace (faster than yadif)
- **Location**: Filters panel → Alternative to Yadif
- **Example**: `yadif_cuda=mode=1`

### 3.2 Add bwdif_vulkan
- **Filter**: `bwdif_vulkan`
- **Use**: Vulkan GPU deinterlace
- **Location**: Filters panel → Alternative to Yadif
- **Example**: `bwdif_vulkan=mode=1`

---

## Priority 4: Color Enhancement

### 4.1 Add colorcorrect Filter ⚠️ REDUNDANT
- **Filter**: `colorcorrect`
- **Use**: Selective color correction for blacks/whites/gamma
- **Preview**: Add to `video_preview.py`
- **Parameters**: `colorcorrect=gamma=1.0:contrast=1.0:saturation=1.0`
- **NOTE**: Redundant - existing color correction panel already uses `eq` filter with similar functionality (brightness, contrast, saturation, gamma, RGB gamma, white balance)

### 4.2 Add libplacebo Tone Mapping ✅ DONE
- **Filter**: `libplacebo` with tone mapping
- **Use**: HDR to SDR conversion, better colors, film grain
- **Note**: Advanced feature, requires testing
- **Example**: `libplacebo=w=1920:h=1080:tonemapping=bt2390`
- **Options**: bt2390, bt2446, reinhard, mobius, linear, clip, spline

---

## Priority 5: Encoder Settings

### 5.1 HEVC Profile Selection
- **Current**: Hardcoded to "main" profile
- **Options**: main (8-bit), main10 (10-bit), mainstill (still images)
- **Location**: Encoding settings → Profile dropdown
- **Default**: main
- **Use**: Allow users to select Main 10 for better color quality (10-bit)
- **NOTE**: Main 10 may have less compatibility but provides better quality with HDR content

---

## Priority 6: DVD Support (Future)

### 6.1 DVD Preview Fix
- **Issue**: DVD preview not showing in Original window, errors not visible
- **Location**: `video_preview.py:load_frame()`
- **Problem**: DVD frame extraction fails silently, no proper error display
- **Fix**: Improve error handling and logging when loading DVD frames

### 6.2 DVD Subtitle Extraction Fix
- **Issue**: DVD subtitle extraction fails
- **Location**: `dvd_handler.py:extract_subtitle()`
- **Methods**: MKV intermediate, mplayer, FFmpeg direct
- **Problem**: All methods can fail depending on DVD structure
- **Fix**: Debug and improve extraction reliability

### 6.3 DVD Subtitle Burning
- **Status**: NOT SUPPORTED (by design)
- **Reason**: DVD subtitles are bitmap images, not text
- **Current behavior**: Shows warning message, skips burning
- **Note**: Recommend HandBrake or mencoder for DVD subtitle burning

---

## Implementation Checklist

### Files to Modify:
- [ ] `models.py` - Add new filter settings (FilterSettings dataclass)
- [ ] `filters.py` - Add UI controls (checkboxes, sliders)
- [ ] `controller.py` - Add filter building logic (build_filter_complex)
- [ ] `video_preview.py` - Add preview support (apply_filters method)

### Testing:
- [ ] Test with "La leggenda di Enea" sample
- [ ] Verify GPU acceleration works (scale_vulkan, nlmeans_vulkan)
- [ ] Compare quality vs speed between options

---

## Current Algorithm Options (Implemented)
- bilinear, bicubic, lanczos, spline, area
- zscale (modern software resizer)
- scale_cuda (NVIDIA GPU)
- scale_vulkan (Vulkan GPU)
- libplacebo (Advanced GPU with color management)

---

## Notes
- AI Super-Resolution (sr filter) still not available in FFmpeg builds
- For true AI upscaling: Recommend Topaz Video AI or DaVinci Resolve
- FFmpeg 8.1 supports Vulkan encoding: h264_vulkan, hevc_vulkan, av1_vulkan

---

## Resolution Options (Implemented)
- original, 480p, 720p, 1080p, 1440p, 4K
- Custom (user-defined WxH)
