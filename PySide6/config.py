# config.py
from pathlib import Path

# App directories
APP_DIR = Path(__file__).parent.resolve()

# Paths
FFMPEG = "/home/akira/Downloads/ffmpeg-n8.1-latest-linux64-gpl-8.1/bin/ffmpeg"
FFPROBE = "/home/akira/Downloads/ffmpeg-n8.1-latest-linux64-gpl-8.1/bin/ffprobe"
HANDBRAKE = "HandBrakeCLI"
GSTREAMER = "gst-launch-1.0"

# AI Upscaling binary paths
REALESRGAN_NCNN = str(APP_DIR / "backends" / "realesrgan-ncnn-vulkan" / "realesrgan-ncnn-vulkan")
ANIME4K_NCNN = str(APP_DIR / "backends" / "anime4k-ncnn-vulkan" / "anime4k-ncnn-vulkan")

UPSCALING_MODELS = {
    "realesrgan": {
        "label": "Real-ESRGAN",
        "binary": REALESRGAN_NCNN,
        "models": [
            ("realesrgan-x4plus", "General (4x, best quality)"),
            ("realesrnet-x4plus", "General (4x, faster)"),
            ("realesrgan-x4plus-anime", "Anime (4x, small model)"),
            ("reales-animevideov3", "Anime video (lightweight)"),
        ],
        "default_model": "realesrgan-x4plus",
        "scales": [2, 3, 4],
    },
    "anime4k": {
        "label": "Anime4K",
        "binary": ANIME4K_NCNN,
        "models": [
            ("A", "Preset A (fast)"),
            ("B", "Preset B (balanced)"),
            ("C", "Preset C (best quality)"),
        ],
        "default_model": "A",
        "scales": [2, 4],
    },
}

OUTPUT_DIR = APP_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Settings file
SETTINGS_FILE = APP_DIR / "settings.json"

# Last opened folder (for file dialogs)
LAST_OPENED_FOLDER = str(Path.home())

def load_last_folder():
    """Load the last opened folder from settings"""
    global LAST_OPENED_FOLDER
    try:
        if SETTINGS_FILE.exists():
            import json
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
                LAST_OPENED_FOLDER = settings.get('last_opened_folder', str(Path.home()))
    except Exception:
        pass
    return LAST_OPENED_FOLDER

def save_last_folder(folder_path: str):
    """Save the last opened folder to settings"""
    global LAST_OPENED_FOLDER
    LAST_OPENED_FOLDER = folder_path
    try:
        import json
        settings = {}
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
        settings['last_opened_folder'] = folder_path
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass
