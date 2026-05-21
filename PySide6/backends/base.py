"""
Media Backend Interface - Abstract Base Class for media backends
"""
from abc import ABC, abstractmethod
from typing import Optional, List
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
    def get_video_bitrate(self, input_path: str) -> Optional[int]:
        ...

    @abstractmethod
    def get_file_info(self, input_path: str) -> dict:
        ...

    @abstractmethod
    def extract_subtitle(self, input_path: str, stream_idx: int,
                         output_path: str) -> Optional[str]:
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
                      first_vob_path: str = None) -> Optional[bytes]:
        ...

    @abstractmethod
    def apply_video_filter(self, image_bytes: bytes, filter_str: str) -> Optional[bytes]:
        ...

    @abstractmethod
    def get_frame_rate(self, video_path: str) -> dict:
        ...

    @abstractmethod
    def get_full_info(self, video_path: str) -> dict:
        ...
