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
    use_max_bitrate: bool = False
    max_bitrate: int = 4000
    bitrate_mode: str = "CBR (Constant Bitrate)"
    target_bitrate: str = "2000"
    container: str = "mp4"
    # Preset settings
    cpu_preset: str = "medium"  # ultrafast/superfast/veryfast/faster/fast/medium/slow/slower/veryslow
    cpu_tune: str = "none"  # none/film/animation/grain/fastdecode/zerolatency
    gpu_preset: str = "p5"  # p1-p7 for NVENC
    # CPU-used for AV1/VP9 encoders (0-6 for libaom, 0-5 for VP9, 0-13 for SVT-AV1)
    cpu_used: str = "2"
    # Scale filter settings
    scale_mode: str = "off"  # off / on
    scale_algorithm: str = "bilinear"  # bilinear / bicubic / lanczos / spline / area
    scale_quality: str = "speed"  # speed / quality
    aspect_ratio_mode: str = "fit"  # fit (preserve aspect), stretch
    # Pixel format
    pixel_format: str = "yuv420p"  # yuv420p (8-bit), yuv420p10le (10-bit)
    # Custom resolution (e.g., "1920x1080")
    custom_resolution: str = ""
    # Audio codec selection
    audio_codec: str = "aac"  # aac, mp2, ac3, mp3
    audio_channels: str = "2"  # 1, 2, 6, 8
    # Advanced settings
    profile: str = "main"  # baseline, main, high
    level: str = "4.0"  # 3.0, 3.1, 4.0, 4.1, 4.2, 5.0, 5.1
    bframes: str = "0"  # 0-3
    gop_size: str = "144"  # keyframe interval
    audio_sample_rate: str = "44100"  # 44100, 48000, 96000
    # Libplacebo tone mapping settings
    libplacebo_tonemapping: str = "none"  # none, bt2390, bt2446, reinhard, mobius, linear, clip, spline
    libplacebo_tonemapping_mode: str = "auto"  # auto, rgb, max, lum
    # GStreamer-specific scale algorithm (native videoscale method names)
    gst_scale_algorithm: str = "catrom"  # nearest-neighbour/bilinear/4-tap/lanczos/bilinear2/sinc/hermite/spline/catrom/mitchell


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
    # Shadow settings
    shadow_enabled: bool = False
    shadow_color: str = "#000000"
    shadow_offset_x: int = 2  # Horizontal shadow offset
    shadow_offset_y: int = 2  # Vertical shadow offset
    shadow_opacity: float = 0.5  # Shadow opacity (0.0-1.0)
    # Other settings
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
    # White Balance settings (colorbalance filter)
    white_balance_enabled: bool = False
    wb_shadows_r: float = 0.0  # -1.0 to 1.0
    wb_shadows_g: float = 0.0
    wb_shadows_b: float = 0.0
    wb_midtones_r: float = 0.0
    wb_midtones_g: float = 0.0
    wb_midtones_b: float = 0.0
    wb_highlights_r: float = 0.0
    wb_highlights_g: float = 0.0
    wb_highlights_b: float = 0.0


@dataclass
class FilterSettings:
    """Video and audio filter settings"""
    deinterlace: bool = False
    denoise: bool = False
    sharpen: bool = False
    sharpen_amount: float = 1.0
    cas_enabled: bool = False
    cas_strength: float = 0.0
    deblock: bool = False
    deblock_strength: float = 0.5
    # Delogo (logo removal)
    delogo_enabled: bool = False
    delogo_x: int = 0  # X position of logo area
    delogo_y: int = 0  # Y position of logo area
    delogo_w: int = 100  # Width of logo area
    delogo_h: int = 30  # Height of logo area
    delogo_band: int = 1  # Band size (edge softness)
    delogo_show: bool = False  # Show debug rectangle
    # Smart Crop (black bar removal)
    smart_crop_enabled: bool = False
    smart_crop_mode: str = "auto"  # auto / manual
    smart_crop_w: int = 640  # Crop width (default: 640)
    smart_crop_h: int = 480  # Crop height (default: 480)
    smart_crop_x: int = 0  # Crop X offset
    smart_crop_y: int = 0  # Crop Y offset
    smart_crop_show_preview: bool = False  # Show crop preview
    # Aspect Ratio conversion
    ar_convert_enabled: bool = False
    ar_target: str = "16:9"  # 16:9 / 4:3 / 1:1 / 2.35:1
    ar_method: str = "crop"  # crop / pad / stretch
    # Quick Aspect Ratio Crop (auto-detect black bars, crop to target AR)
    ar_crop_enabled: bool = False
    ar_crop_target: str = "16:9"  # 16:9 / 4:3 / 1:1 / 2.35:1
    # Video Orientation / Flip (phone video correction)
    video_rotate: str = "none"  # none / 90r / 180 / 90l / horiz / vert
    # Audio filters
    audio_denoise: bool = False
    volume_enabled: bool = False
    volume_db: float = 0.0
    stretch_fill: bool = False
    audio_dynnorm: bool = False
    audio_compressor: bool = False
    # Audio delay/sync
    audio_delay_enabled: bool = False
    audio_delay_ms: int = 0       # milliseconds, 0 = no delay


@dataclass
class GeometrySettings:
    """Geometry and aspect ratio settings"""
    force_widescreen: bool = False
    offset_x: float = 0.0  # Horizontal offset for crop position
    offset_y: float = 0.0  # Vertical offset for crop position


@dataclass
class ColorizationSettings:
    """Colorization settings for B&W to color conversion (non-AI)"""
    enabled: bool = False
    method: str = "tint"  # "tint", "pseudocolor", "lut"

    # Tint settings
    tint_hue: float = 30.0        # 0-360 degrees (30 = sepia-like orange)
    tint_saturation: float = 0.6  # 0.0-2.0
    tint_strength: float = 1.0    # 0.0-1.0 mix with original

    # Pseudocolor settings
    pseudocolor_preset: str = "rainbow"  # rainbow, heat, cool, cold_warm, stripes
    pseudocolor_opacity: float = 1.0     # 0.0-1.0

    # LUT settings
    lut_path: str = ""
    lut_type: str = "lut3d"  # "lut3d", "lutrgb", "lutyuv"


@dataclass
class SplitSettings:
    """Video splitting settings"""
    enabled: bool = False
    split_duration_min: int = 30
    split_subs: bool = False
    # Fast comparison split (single split at specific time)
    fast_split_enabled: bool = False
    fast_split_minutes: int = 5  # 1, 2, 5, or 10 minutes
    # Extract clip from specific time
    extract_clip_enabled: bool = False
    extract_start_min: int = 0  # Start time in minutes
    extract_duration_min: int = 1  # Duration in minutes


@dataclass
class VideoTrackInfo:
    """Information about a single video track"""
    index: int = 0    # Stream index (0, 1, 2, etc.)
    codec: str = ""
    width: int = 0
    height: int = 0
    fps: str = ""
    language: str = ""
    title: str = ""


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
class AudioTrackAssignment:
    """Per-track audio assignment for multi-track output"""
    stream_index: int = 0  # Relative stream index within available_audio_tracks
    mode: str = "encode"  # "copy" or "encode"
    is_external: bool = False  # True if this is an external audio file


@dataclass
class ExternalAudioTrack:
    """An externally loaded audio file treated as a track"""
    file_path: str = ""
    codec: str = ""
    channels: int = 2
    sample_rate: str = ""
    title: str = ""


@dataclass
class SubtitleTrackInfo:
    """Information about a single embedded subtitle track"""
    index: int = 0  # Stream index (0, 1, 2, etc.)
    codec: str = ""
    language: str = ""
    title: str = ""


@dataclass
class ExternalSubtitleTrack:
    """An externally loaded subtitle file treated as a track"""
    file_path: str = ""
    codec: str = "subrip"
    language: str = ""
    title: str = ""


@dataclass
class SubtitleTrackAssignment:
    """Per-track subtitle assignment for multi-track output"""
    stream_index: int = 0  # Relative index within available/external list
    is_external: bool = False  # True if this is an external subtitle file
    mode: str = "copy"  # "copy" or "burn"


@dataclass
class TrackSettings:
    """Track selection settings"""
    video_selected: bool = True
    video_stream_index: int = 0  # Which video stream to use (0 = first, 1 = second, etc.)
    audio_selected: bool = True
    audio_copy_mode: bool = False  # True = copy original audio, False = re-encode to AAC
    audio_stream_index: int = 0  # Which audio stream to use (0 = first, 1 = second, etc.)

    # Multi-track audio support
    multi_track_audio_enabled: bool = False  # Toggle between single and multi-track mode
    selected_audio_indices: List[int] = field(default_factory=list)  # Which tracks to include (relative indices)
    audio_track_assignments: List[AudioTrackAssignment] = field(default_factory=list)  # Per-track control
    external_audio_tracks: List[ExternalAudioTrack] = field(default_factory=list)  # Externally loaded audio files

    subtitle_available: bool = False
    subtitle_selected: bool = False

    # Multi-track subtitle support (embedded tracks)
    multi_track_subtitle_enabled: bool = False
    available_subtitle_tracks: List[SubtitleTrackInfo] = field(default_factory=list)
    selected_subtitle_indices: List[int] = field(default_factory=list)  # Tracks to passthrough
    subtitle_track_assignments: List[SubtitleTrackAssignment] = field(default_factory=list)  # Per-track control
    external_subtitle_tracks: List[ExternalSubtitleTrack] = field(default_factory=list)  # Externally loaded subtitle files
    subtitle_burn_index: int = -1  # Which embedded track to burn (-1 = use external file)
    subtitle_passthrough: bool = False  # Copy subtitle tracks instead of burning

    video_info: str = ""
    video_width: int = 0  # Source video width
    video_height: int = 0  # Source video height
    video_dar: str = ""  # Display aspect ratio (e.g., "16:9")
    audio_info: str = ""  # Summary info of selected track
    subtitle_info: str = ""
    available_video_tracks: List[VideoTrackInfo] = field(default_factory=list)
    available_audio_tracks: List[AudioTrackInfo] = field(default_factory=list)
    # External audio support
    external_audio_enabled: bool = False
    external_audio_path: str = ""  # Full path to external audio file
    external_audio_info: str = ""  # Display info (codec, duration, channels)


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
    deleted_segments: List[tuple] = field(default_factory=list)  # List of (start, end) tuples for deleted segments
    
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
    
    def add_deleted_segment(self, start: float, end: float):
        """Add a deleted segment"""
        self.deleted_segments.append((start, end))
    
    def clear_deleted_segments(self):
        """Clear all deleted segments"""
        self.deleted_segments.clear()
    
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
class AIUpscalingSettings:
    """AI upscaling settings (Real-ESRGAN / Anime4K via ncnn-vulkan)"""
    enabled: bool = False
    upscaler: str = "realesrgan"  # "realesrgan" or "anime4k"
    model: str = "realesrgan-x4plus"
    scale: int = 4
    tile_size: int = 0             # 0 = auto
    part_duration_minutes: int = 1  # 1 or 5
    frames_dir: str = ""
    frames_extracted: bool = False
    frames_upscaled: bool = False
    frames_recombined: bool = False
    cleanup_temp: bool = False
    current_part_index: int = 0
    total_parts: int = 0


@dataclass
class TextOverlay:
    """Single text overlay item"""
    enabled: bool = True
    text: str = "Your Text"
    font_size: int = 36
    font_color: str = "#FFFFFF"
    x: int = 10
    y: int = 10
    animation: str = "none"


@dataclass
class ImageOverlay:
    """Single image overlay item"""
    enabled: bool = True
    image_path: str = ""
    x: int = 10
    y: int = 10
    scale: float = 1.0
    opacity: float = 1.0
    animation: str = "none"


@dataclass
class ExtraSettings:
    """Extra overlay and video generation settings"""
    text_overlays: List[TextOverlay] = field(default_factory=list)
    image_overlays: List[ImageOverlay] = field(default_factory=list)
    generate_video: bool = False
    gen_color: str = "#0000FF"
    gen_resolution: str = "1920x1080"
    gen_duration_sec: int = 30
    gen_framerate: str = "30"
    gen_include_audio: bool = True
    add_audio_track: bool = False
    audio_track_path: str = ""
    audio_mix_mode: str = "replace"


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
    vob_path_for_subs: str = ""  # Path to first VOB file for dual-input subtitle overlay


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
    handbrake_path_changed = Signal(str)
    handbrake_available_changed = Signal(bool)
    media_engine_changed = Signal(str)
    gstreamer_path_changed = Signal(str)
    realesrgan_path_changed = Signal(str)
    anime4k_path_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # File I/O
        self._input_files: List[str] = []
        self._output_folder: str = ""
        self._ffmpeg_path: str = "ffmpeg"
        self._ffprobe_path: str = "ffprobe"
        self._current_video_path: Optional[str] = None
        
        # HandBrake
        self._handbrake_path: str = "HandBrakeCLI"
        self._handbrake_available: bool = False

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
        self.colorization = ColorizationSettings()
        self.ai_upscaling = AIUpscalingSettings()
        self.extra = ExtraSettings()
        
        # Media engine
        self._media_engine: str = "ffmpeg"
        self._gstreamer_path: str = "gst-launch-1.0"
        self._backend = None

        # AI Upscaling paths
        self._realesrgan_path: str = ""
        self._anime4k_path: str = ""

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
    
    @Property(str, notify=handbrake_path_changed)
    def handbrake_path(self):
        return self._handbrake_path

    @handbrake_path.setter
    def handbrake_path(self, value):
        if self._handbrake_path != value:
            self._handbrake_path = value
            self.handbrake_path_changed.emit(value)

    @Property(bool, notify=handbrake_available_changed)
    def handbrake_available(self):
        return self._handbrake_available

    @handbrake_available.setter
    def handbrake_available(self, value):
        if self._handbrake_available != value:
            self._handbrake_available = value
            self.handbrake_available_changed.emit(value)

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
    
    @Property(str, notify=media_engine_changed)
    def media_engine(self):
        return self._media_engine

    @media_engine.setter
    def media_engine(self, value):
        if self._media_engine != value:
            self._media_engine = value
            self._backend = None
            self.media_engine_changed.emit(value)

    @Property(str, notify=gstreamer_path_changed)
    def gstreamer_path(self):
        return self._gstreamer_path

    @gstreamer_path.setter
    def gstreamer_path(self, value):
        if self._gstreamer_path != value:
            self._gstreamer_path = value
            self.gstreamer_path_changed.emit(value)

    @Property(str, notify=realesrgan_path_changed)
    def realesrgan_path(self):
        return self._realesrgan_path

    @realesrgan_path.setter
    def realesrgan_path(self, value):
        if self._realesrgan_path != value:
            self._realesrgan_path = value
            self.realesrgan_path_changed.emit(value)

    @Property(str, notify=anime4k_path_changed)
    def anime4k_path(self):
        return self._anime4k_path

    @anime4k_path.setter
    def anime4k_path(self, value):
        if self._anime4k_path != value:
            self._anime4k_path = value
            self.anime4k_path_changed.emit(value)

    @property
    def backend(self):
        if self._backend is None:
            if self._media_engine == "gstreamer":
                from backends.gstreamer import GStreamerBackend
                self._backend = GStreamerBackend(self)
            else:
                from backends.ffmpeg import FFmpegBackend
                self._backend = FFmpegBackend(self)
        return self._backend

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
