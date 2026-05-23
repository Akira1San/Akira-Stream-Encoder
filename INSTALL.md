# Video Encoder — Installation & Dependencies

This document lists everything needed to run the Video Encoder application on a **fresh MX Linux** installation.

---

## Table of Contents

1. [System Packages (apt)](#1-system-packages-apt)
2. [FFmpeg (external binary)](#2-ffmpeg-external-binary)
3. [Python Virtual Environment](#3-python-virtual-environment)
4. [Post-Install Checklist](#4-post-install-checklist)

---

## 1. System Packages (apt)

Install these first using `apt`. Some are required, others are optional but recommended.

### Required (Python GObject + GStreamer bindings)

```bash
sudo apt install \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-base-1.0
```

| Package | Why |
|---|---|
| `python3-gi` | Provides the `gi` Python module (PyGObject) |
| `python3-gi-cairo` | Cairo bindings for gi |
| `gir1.2-gstreamer-1.0` | GObject introspection data for core GStreamer |
| `gir1.2-gst-plugins-base-1.0` | Introspection data for GStreamer base plugins |

### Recommended (GStreamer plugins for encoding)

```bash
sudo apt install \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav
```

| Package | What it provides |
|---|---|
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

If you place it elsewhere, update `PySide6/settings.json` → `ffmpeg_path`.

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

**This is critical!** Without it, the venv won't see `gi` (python3-gi) and other system-installed Python packages.

### Install Python packages (inside venv)

```bash
# Activate the venv
source /home/akira/akira/myencoder/MyEncoder/venv/bin/activate

# Install PySide6 (Qt6 bindings)
pip install PySide6

# Optional but useful
pip install Pillow   # image processing (used for frame previews)
pip install mutagen  # media metadata reading
```

### Verify installation

```bash
source /home/akira/akira/myencoder/MyEncoder/venv/bin/activate
python3 -c "import gi; gi.require_version('Gst', '1.0'); from gi.repository import Gst; print('OK:', Gst.version_string())"
```

Expected output: `OK: GStreamer 1.26.2` (or similar)

---

## 4. Post-Install Checklist

After a fresh OS install, run through this checklist:

- [ ] **System packages installed** — `python3-gi`, `python3-gi-cairo`, GStreamer introspection, GStreamer plugins
- [ ] **FFmpeg downloaded** and extracted to `~/Downloads/ffmpeg-n8.1-latest-linux64-gpl-8.1/`
- [ ] **Virtual environment created** with `include-system-site-packages = true`
- [ ] **PySide6 installed** in the venv via `pip install PySide6`
- [ ] **Media engine setting** — if the app doesn't start, make sure `PySide6/settings.json` has `"media_engine": "ffmpeg"` as a fallback
- [ ] **Launch via the .desktop file** or directly: `source venv/bin/activate && python3 PySide6/main.py`

### Quick test

```bash
cd /home/akira/akira/myencoder/MyEncoder
source venv/bin/activate
python3 -c "
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
Gst.init(None)
print('GStreamer version:', Gst.version_string())
print('All imports OK!')
"