# Video Encoder — Installation & Dependencies

This document lists everything needed to run the Video Encoder application on a **fresh MX Linux** installation.

---

## Table of Contents

1. [System Packages (apt)](#1-system-packages-apt)
2. [FFmpeg (external binary)](#2-ffmpeg-external-binary)
3. [Python Virtual Environment](#3-python-virtual-environment)
4. [AI Upscaling (optional)](#4-ai-upscaling-optional)
5. [Post-Install Checklist](#5-post-install-checklist)

---

## 1. System Packages (apt)

Install these first using `apt`. Some are required, others are optional but recommended.

> **The app defaults to the FFmpeg backend** (`media_engine: "ffmpeg"`).  
> The GStreamer backend is only used if you manually switch in Settings.  
> **Skip this section unless you intend to use GStreamer.**

### GStreamer backend (optional)

```bash
sudo apt install \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-base-1.0 \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav
```

| Package | What it provides |
|---|---|
| `python3-gi` | PyGObject — GStreamer Python bindings |
| `gstreamer1.0-plugins-good` | MP4 muxer, AAC encoder, videoscale, deinterlace, etc. |
| `gstreamer1.0-plugins-bad` | NVENC encoders (nvh264enc, nvh265enc), x265enc, etc. |
| `gstreamer1.0-plugins-ugly` | x264enc, MP3 encoder, etc. |
| `gstreamer1.0-libav` | FFmpeg-based codecs (libav GStreamer wrapper) |

### Optional (HandBrake CLI — for DVD subtitle burning)

```bash
sudo apt install handbrake-cli
```

If you don't need DVD subtitle burning, this can be skipped.

---

## 2. FFmpeg (external binary)

The application expects a **static FFmpeg build** at a specific path.

### Download

Get the latest **Linux 64-bit GPL static build** from:

- **https://johnvansickle.com/ffmpeg/**
- Select `ffmpeg-release-amd64-static.tar.xz`

### Install

```bash
cd ~/Downloads
tar -xf ffmpeg-release-amd64-static.tar.xz
# Rename the folder for consistency (optional but helpful)
mv ffmpeg-*-amd64-static ffmpeg-n8.1-latest-linux64-gpl-8.1   # adjust version as needed
```

### Path

The application's `settings.json` expects:

```
/home/akira/Downloads/ffmpeg-n8.1-latest-linux64-gpl-8.1/bin/ffmpeg
```

If you place it elsewhere, update `settings.json` → `ffmpeg_path`.

---

## 3. Python Virtual Environment

The application runs inside a Python 3 venv with `include-system-site-packages = true`.

### Create the venv (first time only)

```bash
cd /home/akira/akira/myencoder/MyEncoder
python3 -m venv venv
```

### Enable system site-packages

Edit `/home/akira/akira/myencoder/MyEncoder/venv/pyvenv.cfg` and set:

```
include-system-site-packages = true
```

Needed so the venv sees system-installed Python packages (e.g. `gi` for the GStreamer backend, if you use it).

### Install Python packages (inside venv)

```bash
# Activate the venv
source /home/akira/akira/myencoder/MyEncoder/venv/bin/activate

# Install core dependencies (PySide6, numpy, Pillow, mutagen)
pip install -r requirements.txt

# Optional: AI colorization (adds ~8 GB of torch, CUDA, etc.)
# pip install -r requirements-colorizer.txt
```

### Verify installation

```bash
source /home/akira/akira/myencoder/MyEncoder/venv/bin/activate
python3 -c "import PySide6; print('PySide6 OK:', PySide6.__version__)"
```

If using the GStreamer backend, also verify:

```bash
python3 -c "import gi; gi.require_version('Gst', '1.0'); from gi.repository import Gst; print('GStreamer OK:', Gst.version_string())"
```

---

## 4. AI Upscaling (optional)

The app supports AI upscaling via external **Vulkan** binaries (no Python ML packages needed).
Place them in `PySide6/backends/` and set the paths in the app's Settings → AI Upscaling (the "Auto Detect" button will find them there).

### Real-ESRGAN

```bash
cd ~/Downloads
wget https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-ubuntu.zip
unzip realesrgan-ncnn-vulkan-20220424-ubuntu.zip
mv realesrgan-ncnn-vulkan-20220424-ubuntu /home/akira/akira/myencoder/MyEncoder/PySide6/backends/realesrgan-ncnn-vulkan
chmod +x /home/akira/akira/myencoder/MyEncoder/PySide6/backends/realesrgan-ncnn-vulkan/realesrgan-ncnn-vulkan
```

### Anime4K

```bash
# Download the latest Linux release from:
# https://github.com/Tps-F/Anime4K-ncnn-vulkan/releases
cd /home/akira/akira/myencoder/MyEncoder/PySide6/backends
# Extract the archive to a directory named anime4k-ncnn-vulkan/
chmod +x anime4k-ncnn-vulkan/anime4k-ncnn-vulkan
```

---

## 5. Post-Install Checklist

After a fresh OS install, run through this checklist:

- [ ] **(Optional) GStreamer packages** — only if using the GStreamer backend (app defaults to FFmpeg)
- [ ] **FFmpeg downloaded** and extracted to `~/Downloads/ffmpeg-n8.1-latest-linux64-gpl-8.1/`
- [ ] **Virtual environment created** with `include-system-site-packages = true`
- [ ] **Core Python packages installed** — `pip install -r requirements.txt`
- [ ] **(Optional) AI colorization packages** — `pip install -r requirements-colorizer.txt`
- [ ] **(Optional) Real-ESRGAN downloaded** — extracted to `PySide6/backends/realesrgan-ncnn-vulkan/`
- [ ] **(Optional) Anime4K downloaded** — extracted to `PySide6/backends/anime4k-ncnn-vulkan/`
- [ ] **Media engine setting** — if the app doesn't start, make sure `settings.json` has `"media_engine": "ffmpeg"` as a fallback
- [ ] **Launch via the .desktop file** or directly: `source venv/bin/activate && python3 PySide6/main.py`

### Quick test

```bash
cd /home/akira/akira/myencoder/MyEncoder
source venv/bin/activate
python3 -c "
import PySide6
print('PySide6 version:', PySide6.__version__)
print('All imports OK!')
"