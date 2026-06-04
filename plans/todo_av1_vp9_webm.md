# AV1, VP9, WebM Support — Investigation & TODO

## Goal

Add support for encoding to AV1 (libaom-av1 / SVT-AV1), VP9 (libvpx-vp9), and the WebM container format alongside the existing mp4/mkv/avi/mpg/vob options.

## Current State

| Feature | Supported | Notes |
|---------|-----------|-------|
| Encoders | h264_nvenc, hevc_nvenc, libx264, libx265, mpeg2video | No AV1 or VP9 |
| Containers | mp4, mkv, avi, mpg, vob | No webm |
| GPU encoders | NVENC only | No AMD/Intel encoders, no VAAPI |
| Pixel formats | yuv420p (8-bit), yuv420p10le (10-bit), yuv444p, yuv444p10le | AV1/VP9 need specific formats |

## Encoders to Add

| Encoder name | Description | Container |
|---|---|---|
| `libaom-av1` | Reference AV1 encoder (slow, best quality) | mp4, mkv, webm |
| `libsvtav1` | SVT-AV1 (fast, good quality, recommended) | mp4, mkv, webm |
| `libvpx-vp9` | VP9 encoder (good for web) | webm, mkv |
| `libvpx` | VP8 encoder (older, fallback) | webm |
| `av1_nvenc` | NVIDIA GPU AV1 encoder (if available) | mp4, mkv |
| `av1_amf` | AMD GPU AV1 encoder (if available) | mp4, mkv |

## Container Changes

### `encoding_settings.py`
- Add `"webm"` to the container combo (line 342)
- Update container tooltip to mention WebM

### `models.py`
- No change needed — `container: str = "mp4"` is just a string

### `backends/ffmpeg.py`
- `_audio_codec()` must handle webm container:
  ```python
  if container == "webm":
      return "libopus"  # WebM requires Opus or Vorbis
  ```
- For mpg/vob, it currently returns "mp2". Other containers default to "aac". Add webm → libopus/vorbis.

## Codec-Specific Parameter Handling

### Current encoder branching (ffmpeg.py)

| Encoder | Quality | Preset | Extra params |
|---------|---------|--------|-------------|
| NVENC (h264/hevc) | `-cq N` | `-preset pN` | — |
| libx264/libx265 | `-crf N` | `-preset name` | `-tune name` |
| mpeg2video | `-b:v 6000k` | — | — |

### Add for new encoders:

**libaom-av1:**
- Quality: `-crf N` (0-63, default 23)
- Preset: `-cpu-used N` (0-6, slower=better)
- Extra: `-row-mt 1` (row-based multi-threading)
- Pixel format: yuv420p (default), yuv420p10le for 10-bit
- No profile/level (use `-strict experimental` for older ffmpeg)

**libsvtav1:**
- Quality: `-crf N` (0-63, default 30)
- Preset: `-preset N` (0-13, lower=slower/better)
- Extra: `-svtav1-params "keyint=144"` or use `-g 144`
- Pixel format: yuv420p (default), yuv420p10le

**libvpx-vp9:**
- Quality: `-crf N` (0-63, default 23, but 15-35 is typical range)
- Preset: `-cpu-used N` (0-5, 0=best quality, 5=fastest)
- Bitrate: `-b:v N` (for 2-pass or CBR)
- Extra: `-deadline realtime/good/best`, `-row-mt 1`
- Pixel format requires `-pix_fmt yuv420p` or `yuv420p10le`

## Branch Logic to Add in `build_command()` (ffmpeg.py)

After the current encoder if/elif chain (NVENC → mpeg2video → fallback), add new branches:

```
elif encoder in ("libaom-av1", "libsvtav1"):
    cmd += ["-crf", str(encoding.cq)]
    if encoder == "libaom-av1":
        cmd += ["-cpu-used", "2"]
        cmd += ["-row-mt", "1"]
        cmd += ["-strict", "experimental"]   # older ffmpeg needs this
    elif encoder == "libsvtav1":
        cmd += ["-preset", "8"]
    # no profile/level/tune for these — skip them
    cmd += ["-g", encoding.gop_size]
    pix_fmt = "yuv420p"   # force 8-bit for now
    cmd += ["-pix_fmt", pix_fmt]

elif encoder in ("libvpx-vp9", "libvpx"):
    cmd += ["-crf", str(encoding.cq)]
    cmd += ["-cpu-used", "2"]
    cmd += ["-row-mt", "1"]
    cmd += ["-deadline", "good"]
    cmd += ["-g", encoding.gop_size]
    pix_fmt = "yuv420p"
    cmd += ["-pix_fmt", pix_fmt]
```

The `-tune`, `-profile:v`, `-level:v` flags should be skipped for these encoders (they don't support them).

## Pixel Format Restrictions

| Encoder | 8-bit | 10-bit | 12-bit |
|---------|-------|--------|--------|
| libaom-av1 | yuv420p | yuv420p10le | — |
| libsvtav1 | yuv420p | yuv420p10le | — |
| libvpx-vp9 | yuv420p | yuv420p10le | — |
| libvpx | yuv420p | — | — |

Only allow compatible pixel formats per encoder (can use a whitelist in the UI).

## Audio Codec for WebM

WebM container only supports:
- **Opus** (`libopus`) — preferred, best quality
- **Vorbis** (`libvorbis`) — fallback

Update `_audio_codec()` in `backends/ffmpeg.py`:

```python
if container == "webm":
    return "libopus"
# existing logic...
```

Add "libopus" to the audio codec combo options in `encoding_settings.py`.

## Files to Modify

| File | Changes |
|------|---------|
| `encoding_settings.py` | Add new encoders to combo, add "webm" to container combo, add "libopus" to audio codec |
| `backends/ffmpeg.py` | Add encoder branches in `build_command()`, add container logic in `_audio_codec()`, skip incompatible params |
| `backends/gstreamer.py` | Add encoder elements for vp9/av1 if GStreamer plugins are available |
| `models.py` | May not need changes (encoders are just strings) |
