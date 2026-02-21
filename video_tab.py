"""
Video Tab - Coordinator module for backward compatibility
This module imports and re-exports all video tab components to maintain backward compatibility
"""

# Import all components
from ui_components import CollapsibleFrame
from config_tab import ConfigTab
from video_workspace import VideoTab
from video_preview import VideoPreview
from main_app import VideoEncoderApp

# Re-export for backward compatibility
__all__ = [
    'CollapsibleFrame',
    'ConfigTab', 
    'VideoTab',
    'VideoPreview',
    'VideoEncoderApp'
]

# Check for PIL (Pillow) - keep this for compatibility
try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageEnhance
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("Warning: PIL (Pillow) not found. Video preview features will be disabled.")

# Keep the io import for compatibility
import io