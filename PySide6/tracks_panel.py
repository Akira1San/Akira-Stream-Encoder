"""
Track Selection Panel (PySide6)
"""
import os
import subprocess
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QGroupBox, QComboBox, QFrame
)
from PySide6.QtCore import Signal

from models import AppState, AudioTrackInfo


class TrackSelectionPanel(QGroupBox):
    """Panel for selecting video/audio/subtitle tracks"""
    
    tracks_changed = Signal()
    
    def __init__(self, app_state: AppState, parent=None):
        super().__init__("Track Selection", parent)
        self.app_state = app_state
        self.current_video_path = None
        
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)
        
        # Video Track
        video_layout = QHBoxLayout()
        self.video_check = QCheckBox("Video Track")
        self.video_check.setChecked(self.app_state.tracks.video_selected)
        video_layout.addWidget(self.video_check)
        
        self.video_info_label = QLabel(self.app_state.tracks.video_info)
        self.video_info_label.setStyleSheet("color: gray;")
        video_layout.addWidget(self.video_info_label)
        video_layout.addStretch()
        layout.addLayout(video_layout)
        
        # Separator line
        line1 = QFrame()
        line1.setFrameShape(QFrame.HLine)
        line1.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line1)
        
        # Audio Track Section
        audio_section_layout = QVBoxLayout()
        
        # Audio enable checkbox
        audio_enable_layout = QHBoxLayout()
        self.audio_check = QCheckBox("Audio Track")
        self.audio_check.setChecked(self.app_state.tracks.audio_selected)
        audio_enable_layout.addWidget(self.audio_check)
        
        self.audio_info_label = QLabel(self.app_state.tracks.audio_info)
        self.audio_info_label.setStyleSheet("color: gray;")
        audio_enable_layout.addWidget(self.audio_info_label)
        audio_enable_layout.addStretch()
        audio_section_layout.addLayout(audio_enable_layout)
        
        # Audio track selection (dropdown for multiple tracks)
        audio_track_layout = QHBoxLayout()
        audio_track_layout.addSpacing(25)  # Indent
        audio_track_layout.addWidget(QLabel("Select Track:"))
        
        self.audio_track_combo = QComboBox()
        self.audio_track_combo.setMinimumWidth(250)
        self.audio_track_combo.setEnabled(False)
        self.audio_track_combo.setToolTip("Select which audio track to use from the source video")
        audio_track_layout.addWidget(self.audio_track_combo)
        audio_track_layout.addStretch()
        audio_section_layout.addLayout(audio_track_layout)
        
        # Audio copy mode checkbox
        audio_copy_layout = QHBoxLayout()
        audio_copy_layout.addSpacing(25)  # Indent
        self.audio_copy_check = QCheckBox("Copy Original Audio (no re-encode)")
        self.audio_copy_check.setChecked(self.app_state.tracks.audio_copy_mode)
        self.audio_copy_check.setEnabled(False)
        self.audio_copy_check.setToolTip("Copy the original audio stream without re-encoding.\nFaster processing and preserves original quality.")
        audio_copy_layout.addWidget(self.audio_copy_check)
        audio_copy_layout.addStretch()
        audio_section_layout.addLayout(audio_copy_layout)
        
        layout.addLayout(audio_section_layout)
        
        # Separator line
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line2)
        
        # Subtitle Track (hidden if not available)
        self.subtitle_widget = QWidget()
        subtitle_layout = QHBoxLayout(self.subtitle_widget)
        subtitle_layout.setContentsMargins(0, 0, 0, 0)
        
        self.subtitle_check = QCheckBox("Subtitle Track")
        self.subtitle_check.setChecked(self.app_state.tracks.subtitle_selected)
        subtitle_layout.addWidget(self.subtitle_check)
        
        self.subtitle_info_label = QLabel(self.app_state.tracks.subtitle_info)
        self.subtitle_info_label.setStyleSheet("color: gray;")
        subtitle_layout.addWidget(self.subtitle_info_label)
        subtitle_layout.addStretch()
        
        layout.addWidget(self.subtitle_widget)
        self.subtitle_widget.setVisible(self.app_state.tracks.subtitle_available)
        
    def connect_signals(self):
        """Connect UI signals to handlers"""
        self.video_check.toggled.connect(self.on_video_changed)
        self.audio_check.toggled.connect(self.on_audio_changed)
        self.audio_track_combo.currentIndexChanged.connect(self.on_audio_track_changed)
        self.audio_copy_check.toggled.connect(self.on_audio_copy_changed)
        self.subtitle_check.toggled.connect(self.on_subtitle_changed)
        
    def on_video_changed(self, checked):
        """Handle video track checkbox change"""
        self.app_state.tracks.video_selected = checked
        self.tracks_changed.emit()
        
    def on_audio_changed(self, checked):
        """Handle audio track checkbox change"""
        self.app_state.tracks.audio_selected = checked
        self.audio_track_combo.setEnabled(checked and self.audio_track_combo.count() > 0)
        self.audio_copy_check.setEnabled(checked)
        self.tracks_changed.emit()
        
    def on_audio_track_changed(self, index):
        """Handle audio track selection change"""
        if index >= 0 and index < len(self.app_state.tracks.available_audio_tracks):
            track_info = self.app_state.tracks.available_audio_tracks[index]
            # Use relative index (0, 1, 2) for -map, not absolute stream index
            self.app_state.tracks.audio_stream_index = index
            self.audio_info_label.setText(f"{track_info.codec} ({track_info.channels}ch)")
            self.tracks_changed.emit()
            
    def on_audio_copy_changed(self, checked):
        """Handle audio copy mode checkbox change"""
        self.app_state.tracks.audio_copy_mode = checked
        self.tracks_changed.emit()
        
    def on_subtitle_changed(self, checked):
        """Handle subtitle track checkbox change"""
        self.app_state.tracks.subtitle_selected = checked
        self.tracks_changed.emit()
        
    def detect_tracks(self, video_path: str):
        """Detect available tracks in video file with detailed audio info"""
        self.current_video_path = video_path
        ffprobe_path = self.app_state.ffprobe_path
        
        # Try to find ffprobe if not set
        if not ffprobe_path or ffprobe_path == "ffprobe":
            ffmpeg_path = self.app_state.ffmpeg_path
            if ffmpeg_path != "ffmpeg" and os.path.exists(ffmpeg_path):
                base_dir = os.path.dirname(ffmpeg_path)
                candidate = os.path.join(base_dir, "ffprobe.exe" if os.name == 'nt' else "ffprobe")
                if os.path.exists(candidate):
                    ffprobe_path = candidate
                    self.app_state.ffprobe_path = ffprobe_path
                    
        try:
            # Get detailed stream info including audio metadata
            cmd = [
                ffprobe_path,
                "-v", "error",
                "-show_entries", "stream=index,codec_type,codec_name,channels,sample_rate,display_aspect_ratio:stream_tags=language,title",
                "-of", "json",
                video_path
            ]
            
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=15
            )
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                
                has_video = False
                has_audio = False
                has_subtitle = False
                audio_tracks = []
                
                video_info = ""
                subtitle_info = ""
                
                for stream in data.get('streams', []):
                    codec_type = stream.get('codec_type', '')
                    codec_name = stream.get('codec_name', 'unknown')
                    stream_index = stream.get('index', 0)
                    tags = stream.get('tags', {})
                    
                    if codec_type == 'video':
                        has_video = True
                        dar = stream.get('display_aspect_ratio', 'N/A')
                        video_info = f"{codec_name}, {dar}"
                    elif codec_type == 'audio':
                        has_audio = True
                        channels = stream.get('channels', 2)
                        sample_rate = stream.get('sample_rate', '')
                        language = tags.get('language', '')
                        title = tags.get('title', '')
                        
                        # Create audio track info
                        track_info = AudioTrackInfo(
                            index=stream_index,
                            codec=codec_name,
                            channels=channels,
                            sample_rate=sample_rate,
                            language=language,
                            title=title
                        )
                        audio_tracks.append(track_info)
                    elif codec_type == 'subtitle':
                        has_subtitle = True
                        subtitle_info = codec_name
                        
                # Store available audio tracks
                self.app_state.tracks.available_audio_tracks = audio_tracks
                
                # Update audio track dropdown
                self.audio_track_combo.clear()
                for i, track in enumerate(audio_tracks):
                    display_text = f"Track {i+1}"
                    if track.language:
                        display_text += f" [{track.language}]"
                    if track.title:
                        display_text += f" - {track.title}"
                    display_text += f" ({track.codec}, {track.channels}ch"
                    if track.sample_rate:
                        display_text += f", {track.sample_rate}Hz"
                    display_text += ")"
                    self.audio_track_combo.addItem(display_text)
                
                # Update UI
                self.video_info_label.setText(video_info)
                
                # Set default audio selection
                if audio_tracks:
                    default_index = 0  # Default to track 1 (index 0) - first audio track
                    self.audio_track_combo.setCurrentIndex(default_index)
                    self.app_state.tracks.audio_stream_index = default_index  # Use relative index
                    self.audio_info_label.setText(f"{audio_tracks[default_index].codec} ({audio_tracks[default_index].channels}ch)")
                else:
                    self.audio_info_label.setText("")
                    
                self.audio_track_combo.setEnabled(has_audio and self.audio_check.isChecked())
                self.audio_copy_check.setEnabled(has_audio and self.audio_check.isChecked())
                
                self.app_state.tracks.video_info = video_info
                self.app_state.tracks.subtitle_info = subtitle_info
                self.app_state.tracks.subtitle_available = has_subtitle
                
                if has_subtitle:
                    self.subtitle_info_label.setText(subtitle_info)
                    self.subtitle_widget.setVisible(True)
                else:
                    self.subtitle_widget.setVisible(False)
                    
                # Set default selections
                self.video_check.setChecked(has_video)
                self.audio_check.setChecked(has_audio)
                self.subtitle_check.setChecked(False)
                
                self.app_state.tracks.video_selected = has_video
                self.app_state.tracks.audio_selected = has_audio
                self.app_state.tracks.subtitle_selected = False
                
                # Log detected tracks
                self.app_state.log(f"Detected {len(audio_tracks)} audio track(s)", "INFO")
                for track in audio_tracks:
                    track_desc = f"  Track {track.index}: {track.codec}, {track.channels} channels"
                    if track.language:
                        track_desc += f", lang={track.language}"
                    self.app_state.log(track_desc, "INFO")
                
        except Exception as e:
            self.app_state.log(f"Track detection failed: {e}", "WARN")
            
    def get_selected_tracks_filter(self):
        """Get FFmpeg filter string for selected tracks"""
        filters = []
        
        if self.app_state.tracks.video_selected:
            filters.append("v:0")
        if self.app_state.tracks.audio_selected:
            filters.append("a:0")
        if self.app_state.tracks.subtitle_selected and self.app_state.tracks.subtitle_available:
            filters.append("s:0")
            
        return filters
