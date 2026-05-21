"""
Media Backend Interface - Abstract Base Class for media backends
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
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
