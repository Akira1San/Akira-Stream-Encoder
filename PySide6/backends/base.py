"""
Media Backend Interface - Abstract Base Class for media backends
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict
import subprocess


class MediaBackend(ABC):
    """Abstract base class for media encoding backends"""

    @abstractmethod
    def encode(self, input_path: str, output_path: str,
               app_state, start_time=None, duration=None) -> subprocess.Popen:
        ...

    @abstractmethod
    def get_duration(self, input_path: str) -> float:
        ...

    @abstractmethod
    def get_audio_tracks(self, input_path: str) -> List[dict]:
        ...

    @abstractmethod
    def get_subtitle_tracks(self, input_path: str) -> List[dict]:
        ...

    @abstractmethod
    def get_video_tracks(self, input_path: str) -> List[dict]:
        ...

    @abstractmethod
    def get_video_bitrate(self, input_path: str) -> Optional[int]:
        ...

    @abstractmethod
    def get_file_info(self, input_path: str) -> dict:
        ...

    @abstractmethod
    def extract_subtitle(self, input_path: str, stream_idx: int,
                         output_path: str, codec_name: str = None) -> Optional[str]:
        ...

    @abstractmethod
    def validate(self, input_path: str) -> dict:
        ...

    @abstractmethod
    def build_filter_string(self, app_state) -> tuple:
        ...

    @abstractmethod
    def build_command(self, input_path: str, output_path: str,
                      start_time=None, duration=None) -> list:
        ...

    @abstractmethod
    def fast_cut(self, input_path: str, output_path: str,
                 start_time=None, duration=None) -> subprocess.Popen:
        ...

    @abstractmethod
    def join_segments(self, input_path: str, output_path: str,
                      segments: list, video_settings: dict, audio_settings: dict) -> subprocess.Popen:
        ...

    @abstractmethod
    def align_to_keyframe(self, video_path: str, target_time: float) -> float:
        ...

    @abstractmethod
    def extract_track(self, video_path: str, track_info: dict, output_folder: str) -> Optional[str]:
        ...

    @abstractmethod
    def extract_subtitle_streams(self, video_path: str) -> List[dict]:
        ...

    @abstractmethod
    def get_streams(self, video_path: str) -> dict:
        ...

    @abstractmethod
    def get_external_audio_info(self, file_path: str) -> Optional[dict]:
        ...

    @abstractmethod
    def find_subtitle_file(self, video_path: str) -> Optional[str]:
        ...

    @abstractmethod
    def build_subtitle_filter(self, sub_path: str) -> str:
        ...

    @abstractmethod
    def hex_to_ass(self, hex_color: str, opacity: float = 1.0) -> str:
        ...

    @abstractmethod
    def capture_frame(self, video_path: str, timestamp: float,
                      subtitle_filter: str = "", is_dvd_source: bool = False,
                      first_vob_path: str = None,
                      max_size: tuple = None,
                      extra_video_filter: str = "",
                      extra_image_paths: list = None) -> Optional[bytes]:
        ...

    def build_extra_preview_filter(self, app_state) -> str:
        """Build extra drawtext filters for preview. Override in backends that support it."""
        return ""

    def has_preview_image_overlays(self, app_state) -> bool:
        """Check if there are image overlays for preview."""
        return False

    @abstractmethod
    def apply_video_filter(self, image_bytes: bytes, filter_str: str) -> Optional[bytes]:
        ...

    @abstractmethod
    def get_frame_rate(self, video_path: str) -> dict:
        ...

    @abstractmethod
    def get_full_info(self, video_path: str) -> dict:
        ...

    @abstractmethod
    def get_fps(self, input_path: str) -> float:
        ...

    @abstractmethod
    def extract_frames(self, input_path: str, frames_dir: str,
                       part_duration_min: int, fps: float,
                       progress_callback=None) -> bool:
        ...

    @abstractmethod
    def upscale_frames(self, frames_dir: str, upscaler: str,
                       model: str, scale: int, tile_size: int,
                       progress_callback=None) -> bool:
        ...

    @abstractmethod
    def recombine_frames(self, frames_dir: str, output_path: str,
                         fps: float, progress_callback=None) -> bool:
        ...

    @abstractmethod
    def get_part_dirs(self, frames_dir: str) -> list:
        ...

    @abstractmethod
    def get_upscaled_part_dirs(self, frames_dir: str) -> list:
        ...

    @abstractmethod
    def supported_filters(self) -> Dict[str, bool]:
        """
        Returns a dict mapping filter feature names to bool indicating
        whether that filter/feature is supported by this backend.

        Standard feature keys (used by UI panels):
          Video filters:
            - 'deinterlace'
            - 'denoise'
            - 'sharpen'
            - 'cas'
            - 'deblock'
            - 'smart_crop'          (videocrop / crop)
            - 'ar_convert'          (aspect ratio conversion)
            - 'delogo'

          Color correction (EQ):
            - 'eq_brightness'       (videobalance brightness)
            - 'eq_contrast'         (videobalance contrast)
            - 'eq_saturation'       (videobalance saturation)
            - 'eq_gamma'            (gamma element)
            - 'white_balance'       (colorbalance)

          Colorization (B&W → Color):
            - 'colorization'        (colorchannelmixer / pseudocolor / lut3d)

          Audio filters:
            - 'volume'
            - 'audio_denoise'
            - 'audio_dynnorm'
            - 'audio_compressor'
            - 'audio_delay'
        """
        ...