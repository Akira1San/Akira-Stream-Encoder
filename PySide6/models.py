"""
Models and Shared State for Video Encoder Application
"""
from dataclasses import dataclass, field
from typing import List, Optional
from PySide6.QtCore import QObject, Signal, Property


@dataclass
class EncodingSettings:
    """Encoding configuration settings"""
    use_gpu: bool = True
    encoder: str = "h264_nvenc"
    video_mode: str = "encode"  # encode / copy
    audio_mode: str = "encode"  # encode / copy
    resolution: str = "none"
    framerate: str = "24000/1001"
    cq: int = 23
    use_original_bitrate: bool = False
    max_bitrate: int = 4000
    bitrate_mode: str = "CBR (Constant Bitrate)"
    target_bitrate: str = "2000"
    container: str = "mp4"
    # Preset settings
    cpu_preset: str = "medium"  # ultrafast/superfast/veryfast/faster/fast/medium/slow/slower/veryslow
    gpu_preset: str = "p4"  # p1-p7 for NVENC
    # Scale filter settings
    scale_mode: str = "off"  # off / on
    scale_algorithm: str = "bilinear"  # bilinear / bicubic / lanczos / spline / area
    scale_quality: str = "speed"  # speed / quality


@dataclass
class SubtitleSettings:
    """Subtitle burn-in settings"""
    burn_subs: bool = False
    font: str = "Arial"
    size: int = 24
    position: str = "bottom"
    vertical_offset: int = 0  # Pixels to shift subtitles (positive = down, for black bars)
    color: str = "#FFFFFF"
    outline_color: str = "#000000"
    bg_color: str = "#000000"
    outline_width: int = 2
    bg_opacity: float = 0.5
    delay_enabled: bool = False
    delay: int = 0
    selected_subtitle: str = ""


@dataclass
class EQSettings:
    """Color correction (EQ) settings"""
    enabled: bool = False
    bypass: bool = False
    brightness: float = 0.0
    contrast: float = 1.0
    saturation: float = 1.0
    gamma: float = 1.0
    gamma_r: float = 1.0
    gamma_g: float = 1.0
    gamma_b: float = 1.0


@dataclass
class FilterSettings:
    """Video and audio filter settings"""
    deinterlace: bool = False
    denoise: bool = False
    audio_denoise: bool = False
    volume_enabled: bool = False
    volume_db: float = 0.0
    stretch_fill: bool = False
    audio_dynnorm: bool = False
    audio_compressor: bool = False


@dataclass
class GeometrySettings:
    """Geometry and aspect ratio settings"""
    force_widescreen: bool = False
    offset: float = 0.0


@dataclass
class SplitSettings:
    """Video splitting settings"""
    enabled: bool = False
    split_duration_min: int = 30
    # Fast comparison split (single split at specific time)
    fast_split_enabled: bool = False
    fast_split_minutes: int = 5  # 1, 2, 5, or 10 minutes
    # Extract clip from specific time
    extract_clip_enabled: bool = False
    extract_start_min: int = 0  # Start time in minutes
    extract_duration_min: int = 1  # Duration in minutes


@dataclass
class AudioTrackInfo:
    """Information about a single audio track"""
    index: int = 0  # Stream index (0, 1, 2, etc.)
    codec: str = ""
    channels: int = 2
    sample_rate: str = ""
    language: str = ""
    title: str = ""


@dataclass
class TrackSettings:
    """Track selection settings"""
    video_selected: bool = True
    audio_selected: bool = True
    audio_copy_mode: bool = False  # True = copy original audio, False = re-encode to AAC
    audio_stream_index: int = 0  # Which audio stream to use (0 = first, 1 = second, etc.)
    subtitle_available: bool = False
    subtitle_selected: bool = False
    video_info: str = ""
    audio_info: str = ""  # Summary info of selected track
    subtitle_info: str = ""
    available_audio_tracks: List[AudioTrackInfo] = field(default_factory=list)


@dataclass
class CutPoint:
    """Individual cut point"""
    position: float  # timestamp in seconds
    time_display: str  # formatted time string (MM:SS or HH:MM:SS)
    cut_id: str  # unique identifier
    enabled: bool = True


@dataclass
class CutSettings:
    """Cut/trim settings - supports multiple cut points"""
    points: List[CutPoint] = field(default_factory=list)
    next_id: int = 1  # Counter for generating unique IDs
    
    def add_point(self, position: float, time_display: str) -> CutPoint:
        """Add a new cut point and return it"""
        cut_id = f"cut_{self.next_id}"
        self.next_id += 1
        point = CutPoint(position=position, time_display=time_display, cut_id=cut_id)
        self.points.append(point)
        return point
    
    def remove_point(self, cut_id: str) -> bool:
        """Remove a cut point by ID, return True if found and removed"""
        for i, point in enumerate(self.points):
            if point.cut_id == cut_id:
                self.points.pop(i)
                return True
        return False
    
    def clear_all(self):
        """Remove all cut points"""
        self.points.clear()
    
    def get_sorted_points(self) -> List[CutPoint]:
        """Return points sorted by position"""
        return sorted(self.points, key=lambda p: p.position)
    
    def get_segments(self, total_duration: float) -> List[tuple]:
        """
        Generate segments from cut points.
        Returns list of (start_time, end_time) tuples.
        """
        if not self.points or total_duration <= 0:
            return [(0.0, total_duration)]
        
        sorted_points = self.get_sorted_points()
        segments = []
        start = 0.0
        
        for point in sorted_points:
            if point.enabled and start < point.position <= total_duration:
                segments.append((start, point.position))
                start = point.position
        
        # Add final segment
        if start < total_duration:
            segments.append((start, total_duration))
        
        return segments


@dataclass
class DVDSettings:
    """DVD (VIDEO_TS) source settings"""
    is_dvd_source: bool = False
    dvd_folder_path: str = ""  # Path to VIDEO_TS folder
    available_titles: List = field(default_factory=list)  # List of DVDTitle objects
    selected_title_index: int = 0  # Index of selected title in available_titles
    concat_file_path: str = ""  # Path to temporary concat file
    selected_title_number: int = 1  # The actual DVD title number (1, 2, 3...)
    selected_subtitle_index: int = -1  # Subtitle stream index to burn (-1 = none)
    extracted_subtitle_path: str = ""  # Path to extracted .sub file for burning
    subtitle_tracks: List = field(default_factory=list)  # List of subtitle track dicts for selected title


class AppState(QObject):
    """
    Central application state manager with Qt signals for change notification.
    Replaces the Tkinter StringVar/BooleanVar system.
    """
    # Signals for various state changes
    input_files_changed = Signal(list)
    output_folder_changed = Signal(str)
    ffmpeg_path_changed = Signal(str)
    current_video_changed = Signal(str)
    encoding_started = Signal()
    encoding_finished = Signal(bool, str)  # success, message
    log_message = Signal(str, str)  # message, level
    preview_refresh_needed = Signal()
    dvd_titles_changed = Signal(list)  # List of DVD titles detected
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # File I/O
        self._input_files: List[str] = []
        self._output_folder: str = ""
        self._ffmpeg_path: str = "ffmpeg"
        self._ffprobe_path: str = "ffprobe"
        self._current_video_path: Optional[str] = None
        
        # Custom filename
        self._use_custom_filename: bool = False
        self._custom_filename: str = ""
        
        # Settings groups
        self.encoding = EncodingSettings()
        self.subtitles = SubtitleSettings()
        self.eq = EQSettings()
        self.filters = FilterSettings()
        self.geometry = GeometrySettings()
        self.split = SplitSettings()
        self.tracks = TrackSettings()
        self.cut = CutSettings()
        self.dvd = DVDSettings()
        
        # UI State
        self._is_encoding: bool = False
        self._current_process = None
    
    # Properties with getters/setters
    @Property(list, notify=input_files_changed)
    def input_files(self):
        return self._input_files
    
    @input_files.setter
    def input_files(self, value):
        if self._input_files != value:
            self._input_files = value
            self.input_files_changed.emit(value)
    
    @Property(str, notify=output_folder_changed)
    def output_folder(self):
        return self._output_folder
    
    @output_folder.setter
    def output_folder(self, value):
        if self._output_folder != value:
            self._output_folder = value
            self.output_folder_changed.emit(value)
    
    @Property(str, notify=ffmpeg_path_changed)
    def ffmpeg_path(self):
        return self._ffmpeg_path
    
    @ffmpeg_path.setter
    def ffmpeg_path(self, value):
        if self._ffmpeg_path != value:
            self._ffmpeg_path = value
            self.ffmpeg_path_changed.emit(value)
    
    @Property(str)
    def ffprobe_path(self):
        return self._ffprobe_path
    
    @ffprobe_path.setter
    def ffprobe_path(self, value):
        self._ffprobe_path = value
    
    @Property(str, notify=current_video_changed)
    def current_video_path(self):
        return self._current_video_path
    
    @current_video_path.setter
    def current_video_path(self, value):
        if self._current_video_path != value:
            self._current_video_path = value
            self.current_video_changed.emit(value)
    
    @Property(bool)
    def use_custom_filename(self):
        return self._use_custom_filename
    
    @use_custom_filename.setter
    def use_custom_filename(self, value):
        self._use_custom_filename = value
    
    @Property(str)
    def custom_filename(self):
        return self._custom_filename
    
    @custom_filename.setter
    def custom_filename(self, value):
        self._custom_filename = value
    
    @Property(bool)
    def is_encoding(self):
        return self._is_encoding
    
    @is_encoding.setter
    def is_encoding(self, value):
        self._is_encoding = value
    
    # Helper methods
    def add_input_file(self, file_path: str):
        """Add a file to the input list"""
        if file_path not in self._input_files:
            self._input_files.append(file_path)
            self.input_files_changed.emit(self._input_files)
    
    def remove_input_file(self, index: int):
        """Remove a file from the input list"""
        if 0 <= index < len(self._input_files):
            self._input_files.pop(index)
            self.input_files_changed.emit(self._input_files)
    
    def clear_input_files(self):
        """Clear all input files"""
        self._input_files.clear()
        self.input_files_changed.emit(self._input_files)
    
    def log(self, message: str, level: str = "INFO"):
        """Emit a log message"""
        self.log_message.emit(message, level)
