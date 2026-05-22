# CPU Encoding Options Task

## Problem
GPU hardware encoding (HEVC/NVENC) has issues with AV1 source videos when using trim/cut, causing frozen/still frames in output.

## Solution
Use CPU encoding (x264/x265) instead of GPU encoding for problematic sources.

---

## x264/x265 Presets

Presets control encoding speed vs compression efficiency (faster = larger files for same quality):

| Preset | Speed | Quality | Use Case |
|--------|-------|---------|----------|
| ultrafast | Fastest | Lowest | Live streaming, quick previews |
| superfast | Very Fast | Low | Fast encodes |
| **veryfast** | Fast | Medium | **Recommended for daily use** |
| faster | Moderate | Medium-Good | Balance of speed |
| fast | Slower | Good | Standard encoding |
| **medium** | Slower | Good | Default, balanced |
| slow | Slow | Better | High quality archives |
| slower | Very Slow | Best | Maximum quality |
| veryslow | Slowest | Best | Quality over speed |

### Recommendation
- Use **veryfast** for speed, switch to **medium** or **slow** for better compression
- For 1080p: veryfast → faster → medium

---

## x264/x265 Tune Options

The `-tune` parameter optimizes encoding for different content types:

| Tune | Best For | What It Does |
|------|----------|--------------|
| **film** | Movies, TV shows | Balances quality, reduces grain |
| animation | Cartoons, anime | Handles flat colors better |
| grain | Old movies | Preserves film grain texture |
| fastdecode | Weak playback devices | Faster decoding, lower quality |
| zerolatency | Live streaming | Minimizes encoding delay |
| psnr/ssim | Testing | Optimizes for metrics (not for actual use) |

### Recommendation
- **film** - Best for Blu-ray movies (your use case)

---

## Thread Options

Control CPU thread usage for parallel encoding:

| Option | Description |
|--------|-------------|
| -threads 0 | Auto-detect (use all CPU cores) - **recommended default** |
| -threads 1 | Single thread (slowest) |
| -threads 4 | Use 4 threads |
| -threads 8 | Use 8 threads |

### Example Commands

```bash
# Fast encoding with film tune
x264 -preset veryfast -tune film -crf 23 -threads 0 -output video.mp4

# Higher quality encoding
x264 -preset medium -tune film -crf 20 -threads 0 -output video.mp4

# Maximum quality (slower)
x265 -preset slow -tune film -crf 20 -threads 0 -output video.mp4
```

---

## Implementation

Add to encoding_settings.py:
1. Preset dropdown: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
2. Tune dropdown: film, animation, grain, fastdecode, zerolatency
3. Threads dropdown: 0 (Auto), 1, 2, 4, 8, 16

## Testing Checklist
- [ ] Test veryfast preset with AV1 source
- [ ] Test medium preset encoding speed
- [ ] Test film vs grain tune
- [ ] Test thread options (0 vs specific numbers)
- [ ] Verify no still frames with CPU encoding
