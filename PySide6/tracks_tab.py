"""
Tracks Tab - Track management and export for Video Encoder
"""
import os
import subprocess
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QListWidget, QListWidgetItem, QGroupBox, QComboBox,
    QRadioButton, QLineEdit, QFileDialog, QMessageBox, QFrame,
    QScrollArea, QProgressDialog, QApplication
)
from PySide6.QtCore import Qt, Signal, QTimer, QRect
from PySide6.QtGui import QPainter, QColor, QFont, QBrush, QPen

from models import AppState, Track, TrackType


class TimelineView(QWidget):
    """Timeline view showing tracks as horizontal bars"""
    
    track_selected = Signal(str)  # track_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tracks: List[Track] = []
        self._pixels_per_second = 20.0
        self._duration = 0.0
        self._selected_track_id = None
        
        self.setMinimumHeight(120)
        self.setStyleSheet("background-color: #1e1e1e;")
        self.setCursor(Qt.PointingHandCursor)
    
    def set_tracks(self, tracks: List[Track]):
        """Set tracks to display"""
        self.tracks = tracks
        # Calculate max duration
        if tracks:
            self._duration = max(t.duration for t in tracks)
        else:
            self._duration = 0.0
        self.update()
    
    def set_zoom(self, pixels_per_second: float):
        """Set zoom level"""
        self._pixels_per_second = max(5.0, min(100.0, pixels_per_second))
        self.update()
    
    def select_track(self, track_id: str):
        """Select a track"""
        self._selected_track_id = track_id
        self.update()
    
    def paintEvent(self, event):
        """Paint the timeline"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), QColor("#1e1e1e"))
        
        if not self.tracks:
            # Show placeholder
            painter.setPen(QColor("#666666"))
            font = QFont()
            font.setPointSize(11)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignCenter, "Load a video to see tracks")
            return
        
        # Draw time markers
        self._draw_time_ruler(painter)
        
        # Draw tracks
        row_height = 35
        header_width = 100
        y = 30
        
        for track in self.tracks:
            # Draw header background
            header_rect = QFrame().rect()
            header_rect.setRect(0, y, header_width, row_height)
            painter.fillRect(header_rect, QColor("#2d2d2d"))
            
            # Draw track type icon
            icon_color = QColor("#3498db") if track.track_type == TrackType.VIDEO else QColor("#2ecc71")
            icon = "▶" if track.track_type == TrackType.VIDEO else "🔊"
            painter.setPen(QColor("#ffffff"))
            painter.drawText(5, y + 22, icon)
            
            # Draw track name
            painter.drawText(25, y + 22, track.name[:12])
            
            # Draw track bar
            bar_x = header_width + 5
            bar_width = int(track.duration * self._pixels_per_second)
            bar_height = row_height - 8
            bar_rect = QFrame().rect()
            bar_rect.setRect(bar_x, y + 4, bar_width, bar_height)
            
            # Bar color
            bar_color = QColor("#3498db") if track.track_type == TrackType.VIDEO else QColor("#2ecc71")
            if not track.enabled:
                bar_color = QColor("#555555")
            painter.fillRect(bar_rect, bar_color)
            
            # Selection border
            if track.track_id == self._selected_track_id:
                painter.setPen(QPen(QColor("#e67e22"), 2))
                painter.drawRect(bar_x - 2, y + 2, bar_width + 4, bar_height + 4)
            
            # Draw duration at end
            painter.setPen(QColor("#888888"))
            painter.drawText(bar_x + bar_width + 5, y + 22, track.duration_str)
            
            y += row_height
        
        # Draw time axis line
        painter.setPen(QColor("#333333"))
        painter.drawLine(0, 25, self.width(), 25)
    
    def _draw_time_ruler(self, painter: QPainter):
        """Draw time ruler"""
        painter.setPen(QColor("#333333"))
        ruler_rect = QRect(0, 0, self.width(), 25)
        painter.fillRect(ruler_rect, QColor("#333333"))
        
        # Draw ticks based on zoom
        if self._pixels_per_second >= 50:
            interval = 1.0
        elif self._pixels_per_second >= 20:
            interval = 5.0
        elif self._pixels_per_second >= 10:
            interval = 10.0
        else:
            interval = 30.0
        
        painter.setPen(QColor("#666666"))
        font = QFont("monospace", 8)
        painter.setFont(font)
        
        time = 0.0
        while time <= self._duration:
            x = 100 + int(time * self._pixels_per_second)
            if x > self.width():
                break
            painter.drawLine(x, 20, x, 25)
            time_str = self._format_time(time)
            painter.drawText(x + 2, 18, time_str)
            time += interval
    
    def _format_time(self, seconds: float) -> str:
        """Format time as MM:SS or HH:MM:SS"""
        total_secs = int(seconds)
        hours = total_secs // 3600
        minutes = (total_secs % 3600) // 60
        secs = total_secs % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    def mousePressEvent(self, event):
        """Handle mouse click to select track"""
        if not self.tracks:
            return
        
        row_height = 35
        header_width = 100
        y = 30
        
        for track in self.tracks:
            if event.y() >= y and event.y() < y + row_height:
                if event.x() >= header_width:
                    self.track_selected.emit(track.track_id)
                    return
            y += row_height


class TrackListPanel(QGroupBox):
    """Panel showing list of tracks with checkboxes"""
    
    track_selected = Signal(str)  # track_id
    track_enabled_changed = Signal(str, bool)  # track_id, enabled
    add_track_clicked = Signal()
    replace_track_clicked = Signal(str)  # track_id to replace
    delete_track_clicked = Signal(str)  # track_id to delete
    
    def __init__(self, parent=None):
        super().__init__("Track List", parent)
        self.tracks: List[Track] = []
        self._selected_id = None
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)
        
        # Track list
        self.track_list = QListWidget()
        self.track_list.setMaximumHeight(150)
        self.track_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.track_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("+ Add Track")
        self.add_btn.clicked.connect(self.add_track_clicked.emit)
        btn_layout.addWidget(self.add_btn)
        
        self.replace_btn = QPushButton("Replace")
        self.replace_btn.clicked.connect(self._on_replace_clicked)
        self.replace_btn.setEnabled(False)
        btn_layout.addWidget(self.replace_btn)
        
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        self.delete_btn.setEnabled(False)
        btn_layout.addWidget(self.delete_btn)
        
        layout.addLayout(btn_layout)
        
        # Select/Deselect buttons
        sel_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self._on_select_all)
        sel_layout.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self._on_deselect_all)
        sel_layout.addWidget(self.deselect_all_btn)
        
        layout.addLayout(sel_layout)
    
    def set_tracks(self, tracks: List[Track]):
        """Set tracks to display"""
        self.tracks = tracks
        self._refresh_list()
    
    def _refresh_list(self):
        """Refresh the track list"""
        self.track_list.clear()
        
        for track in self.tracks:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, track.track_id)
            
            # Create widget with checkbox
            from PySide6.QtWidgets import QWidget, QHBoxLayout
            widget = QWidget()
            w_layout = QHBoxLayout(widget)
            w_layout.setContentsMargins(5, 2, 5, 2)
            
            checkbox = QCheckBox()
            checkbox.setChecked(track.enabled)
            checkbox.setText(f"{'▶' if track.track_type == TrackType.VIDEO else '🔊'} {track.name}")
            checkbox.stateChanged.connect(lambda state, t=track: self.track_enabled_changed.emit(t.track_id, bool(state)))
            
            w_layout.addWidget(checkbox)
            w_layout.addStretch()
            
            item.setSizeHint(widget.sizeHint())
            self.track_list.addItem(item)
            self.track_list.setItemWidget(item, widget)
    
    def _on_item_clicked(self, item):
        """Handle item click"""
        track_id = item.data(Qt.UserRole)
        self._selected_id = track_id
        self.track_selected.emit(track_id)
        self.replace_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
    
    def _on_replace_clicked(self):
        """Handle replace button click"""
        if self._selected_id:
            self.replace_track_clicked.emit(self._selected_id)
    
    def _on_delete_clicked(self):
        """Handle delete button click"""
        if self._selected_id:
            self.delete_track_clicked.emit(self._selected_id)
    
    def _on_select_all(self):
        """Select all tracks"""
        for track in self.tracks:
            track.enabled = True
        self._refresh_list()
    
    def _on_deselect_all(self):
        """Deselect all tracks"""
        for track in self.tracks:
            track.enabled = False
        self._refresh_list()


class PropertiesPanel(QGroupBox):
    """Panel showing properties of selected track"""
    
    refresh_clicked = Signal()
    
    def __init__(self, parent=None):
        super().__init__("Track Properties", parent)
        self.current_track: Optional[Track] = None
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)
        
        # Scroll area for properties
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(200)
        
        scroll_content = QWidget()
        self.props_layout = QVBoxLayout(scroll_content)
        
        # Placeholder
        self.placeholder_label = QLabel("Select a track to view properties")
        self.placeholder_label.setStyleSheet("color: #666666;")
        self.props_layout.addWidget(self.placeholder_label)
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Refresh button
        self.refresh_btn = QPushButton("🔄 Refresh Tracks")
        self.refresh_btn.clicked.connect(self.refresh_clicked.emit)
        layout.addWidget(self.refresh_btn)
    
    def set_track(self, track: Optional[Track]):
        """Set track to display properties for"""
        self.current_track = track
        
        # Clear existing widgets
        while self.props_layout.count():
            item = self.props_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not track:
            self.placeholder_label = QLabel("Select a track to view properties")
            self.placeholder_label.setStyleSheet("color: #666666;")
            self.props_layout.addWidget(self.placeholder_label)
            return
        
        # Add properties
        self._add_property("Name", track.name)
        self._add_property("Type", "Video" if track.track_type == TrackType.VIDEO else "Audio")
        self._add_property("Source", os.path.basename(track.source_file) if track.source_file else "N/A")
        self._add_property("Stream Index", str(track.stream_index))
        self._add_property("Duration", track.duration_str)
        self._add_property("Codec", track.codec)
        
        if track.track_type == TrackType.VIDEO:
            self._add_property("Resolution", track.resolution)
            self._add_property("Frame Rate", track.framerate)
            self._add_property("Bitrate", track.bitrate)
        else:
            self._add_property("Channels", f"{track.channels}")
            self._add_property("Sample Rate", track.sample_rate)
        
        self.props_layout.addStretch()
    
    def _add_property(self, label: str, value: str):
        """Add a property row"""
        row = QHBoxLayout()
        
        lbl = QLabel(f"{label}:")
        lbl.setStyleSheet("color: #888888;")
        lbl.setMinimumWidth(100)
        row.addWidget(lbl)
        
        val = QLabel(str(value))
        val.setStyleSheet("color: #ffffff; font-family: monospace;")
        row.addWidget(val)
        
        self.props_layout.addLayout(row)


class ExportPanel(QGroupBox):
    """Panel for export options"""
    
    export_clicked = Signal()  # Signal to trigger export
    
    def __init__(self, parent=None):
        super().__init__("Export", parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)
        
        # Export mode
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Export Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Selected Track Only", "Video Only", "Audio Only", "Both (Video + Audio)"])
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)
        
        # Encoding mode
        encoding_layout = QHBoxLayout()
        encoding_layout.addWidget(QLabel("Encoding:"))
        
        self.copy_radio = QRadioButton("Copy (stream copy)")
        self.copy_radio.setChecked(True)
        encoding_layout.addWidget(self.copy_radio)
        
        self.encode_radio = QRadioButton("Encode (re-encode)")
        encoding_layout.addWidget(self.encode_radio)
        
        encoding_layout.addStretch()
        layout.addLayout(encoding_layout)
        
        # Output path
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output:"))
        
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Select output file...")
        output_layout.addWidget(self.output_edit)
        
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self._on_browse)
        output_layout.addWidget(self.browse_btn)
        
        layout.addLayout(output_layout)
        
        # Export button
        self.export_btn = QPushButton("🚀 Export Track")
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #2980b9;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #3498db;
            }
            QPushButton:disabled {
                background-color: #555555;
            }
        """)
        self.export_btn.clicked.connect(self.export_clicked.emit)
        layout.addWidget(self.export_btn)
    
    def _on_browse(self):
        """Browse for output file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Export As",
            "",
            "Video Files (*.mp4 *.mkv *.avi);;All Files (*.*)"
        )
        if file_path:
            self.output_edit.setText(file_path)
    
    def get_export_mode(self) -> str:
        """Get selected export mode"""
        return self.mode_combo.currentText()
    
    def is_copy_mode(self) -> bool:
        """Check if copy mode is selected"""
        return self.copy_radio.isChecked()
    
    def get_output_path(self) -> str:
        """Get output file path"""
        return self.output_edit.text()
    
    def set_enabled(self, enabled: bool):
        """Enable/disable export controls"""
        self.mode_combo.setEnabled(enabled)
        self.copy_radio.setEnabled(enabled)
        self.encode_radio.setEnabled(enabled)
        self.output_edit.setEnabled(enabled)
        self.browse_btn.setEnabled(enabled)
        self.export_btn.setEnabled(enabled)


class TracksTab(QWidget):
    """Main Tracks Tab widget"""
    
    # Signal when tracks are loaded
    tracks_loaded = Signal(list)
    
    def __init__(self, app_state: AppState, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.current_video: Optional[str] = None
        
        self.setup_ui()
        self.connect_signals()
        
        # Listen for video changes
        self.app_state.current_video_changed.connect(self._on_video_changed)
    
    def setup_ui(self):
        """Setup main UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Timeline view
        self.timeline = TimelineView()
        self.timeline.track_selected.connect(self._on_track_selected)
        layout.addWidget(self.timeline)
        
        # Track list and properties side by side
        middle_layout = QHBoxLayout()
        
        # Track list panel
        self.track_list_panel = TrackListPanel()
        self.track_list_panel.track_selected.connect(self._on_track_selected)
        self.track_list_panel.track_enabled_changed.connect(self._on_track_enabled_changed)
        self.track_list_panel.add_track_clicked.connect(self._on_add_track)
        self.track_list_panel.replace_track_clicked.connect(self._on_replace_track)
        self.track_list_panel.delete_track_clicked.connect(self._on_delete_track)
        middle_layout.addWidget(self.track_list_panel, 1)
        
        # Properties panel
        self.props_panel = PropertiesPanel()
        self.props_panel.refresh_clicked.connect(self._on_refresh_tracks)
        middle_layout.addWidget(self.props_panel, 1)
        
        layout.addLayout(middle_layout)
        
        # Export panel
        self.export_panel = ExportPanel()
        self.export_panel.export_clicked.connect(self._on_export)
        layout.addWidget(self.export_panel)
        
        # Initial state
        self._update_empty_state()
    
    def connect_signals(self):
        """Connect signals"""
        pass
    
    def _update_empty_state(self):
        """Update UI for empty state"""
        has_tracks = len(self.app_state.track_list) > 0
        self.track_list_panel.setEnabled(has_tracks)
        self.props_panel.setEnabled(has_tracks)
        self.export_panel.set_enabled(has_tracks)
    
    def _on_video_changed(self, video_path: str):
        """Handle video path changed"""
        if video_path:
            self.current_video = video_path
            self._detect_tracks(video_path)
    
    def _detect_tracks(self, video_path: str):
        """Detect tracks using FFprobe"""
        ffprobe_path = self.app_state.ffprobe_path
        
        # Try to find ffprobe if not set
        if not ffprobe_path or ffprobe_path == "ffprobe":
            ffmpeg_path = self.app_state.ffmpeg_path
            if ffmpeg_path != "ffmpeg" and os.path.exists(ffmpeg_path):
                base_dir = os.path.dirname(ffmpeg_path)
                candidate = os.path.join(base_dir, "ffprobe.exe" if os.name == 'nt' else "ffprobe")
                if os.path.exists(candidate):
                    ffprobe_path = candidate
        
        try:
            # Get stream info
            cmd = [
                ffprobe_path,
                "-v", "error",
                "-show_entries", "stream=index,codec_type,codec_name,width,height,r_frame_rate,bit_rate,duration,channels,sample_rate:stream_tags=language,title",
                "-of", "json",
                video_path
            ]
            
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=30
            )
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                
                tracks = []
                
                for stream in data.get('streams', []):
                    codec_type = stream.get('codec_type', '')
                    
                    if codec_type == 'video':
                        track = self._create_video_track(stream, video_path)
                        tracks.append(track)
                    
                    elif codec_type == 'audio':
                        track = self._create_audio_track(stream, video_path)
                        tracks.append(track)
                
                # Update app state
                self.app_state.track_list = tracks
                self.app_state.tracks_updated.emit(tracks)
                
                # Update UI
                self._update_ui_with_tracks(tracks)
                
                self.app_state.log(f"Detected {len(tracks)} track(s)", "INFO")
            else:
                self.app_state.log(f"FFprobe error: {result.stderr}", "ERROR")
        
        except Exception as e:
            self.app_state.log(f"Track detection failed: {e}", "ERROR")
    
    def _create_video_track(self, stream: dict, source_file: str) -> Track:
        """Create video track from stream info"""
        import math
        
        track = Track()
        track.track_id = f"video_{stream.get('index', 0)}"
        track.name = "Video Track"
        track.track_type = TrackType.VIDEO
        track.source_file = source_file
        track.stream_index = stream.get('index', 0)
        track.codec = stream.get('codec_name', 'unknown')
        
        # Duration
        duration = stream.get('duration')
        if duration:
            track.duration = float(duration)
            track.duration_str = self._format_time(track.duration)
        
        # Resolution
        width = stream.get('width', 0)
        height = stream.get('height', 0)
        if width and height:
            track.width = width
            track.height = height
            track.resolution = f"{width}x{height}"
        
        # Frame rate
        fr = stream.get('r_frame_rate', '')
        if fr and '/' in fr:
            try:
                num, den = fr.split('/')
                fps = float(num) / float(den)
                track.framerate = f"{fps:.2f} fps"
            except:
                track.framerate = fr
        else:
            track.framerate = fr
        
        # Bitrate
        bitrate = stream.get('bit_rate')
        if bitrate:
            try:
                bps = int(bitrate)
                kbps = bps // 1000
                track.bitrate = f"{kbps} kbps"
            except:
                track.bitrate = bitrate
        
        track.enabled = True
        return track
    
    def _create_audio_track(self, stream: dict, source_file: str) -> Track:
        """Create audio track from stream info"""
        track = Track()
        track.track_id = f"audio_{stream.get('index', 0)}"
        
        # Get track name from tags
        tags = stream.get('tags', {})
        title = tags.get('title', '')
        language = tags.get('language', '')
        
        if title:
            track.name = title
        elif language:
            track.name = f"Audio [{language}]"
        else:
            idx = stream.get('index', 0)
            track.name = f"Audio Track {idx}"
        
        track.track_type = TrackType.AUDIO
        track.source_file = source_file
        track.stream_index = stream.get('index', 0)
        track.codec = stream.get('codec_name', 'unknown')
        
        # Duration
        duration = stream.get('duration')
        if duration:
            track.duration = float(duration)
            track.duration_str = self._format_time(track.duration)
        
        # Channels
        channels = stream.get('channels', 0)
        track.channels = channels
        
        # Sample rate
        sample_rate = stream.get('sample_rate', '')
        track.sample_rate = f"{sample_rate} Hz" if sample_rate else ""
        
        track.enabled = True
        return track
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS"""
        total_secs = int(seconds)
        hours = total_secs // 3600
        minutes = (total_secs % 3600) // 60
        secs = total_secs % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    def _update_ui_with_tracks(self, tracks: List[Track]):
        """Update UI with detected tracks"""
        # Update timeline
        self.timeline.set_tracks(tracks)
        
        # Update track list
        self.track_list_panel.set_tracks(tracks)
        
        # Clear properties
        self.props_panel.set_track(None)
        
        # Update empty state
        self._update_empty_state()
        
        # Set default output path
        if tracks and self.current_video:
            base, ext = os.path.splitext(self.current_video)
            self.export_panel.output_edit.setText(f"{base}_export.mp4")
    
    def _on_track_selected(self, track_id: str):
        """Handle track selection"""
        # Update timeline
        self.timeline.select_track(track_id)
        
        # Find and update properties
        for track in self.app_state.track_list:
            if track.track_id == track_id:
                track.selected = True
                self.props_panel.set_track(track)
            else:
                track.selected = False
    
    def _on_track_enabled_changed(self, track_id: str, enabled: bool):
        """Handle track enabled state change"""
        for track in self.app_state.track_list:
            if track.track_id == track_id:
                track.enabled = enabled
                break
        self.timeline.update()
    
    def _on_add_track(self):
        """Handle add track button"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio/Video File",
            "",
            "Media Files (*.mp4 *.mkv *.avi *.mp3 *.wav *.aac *.flac);;All Files (*.*)"
        )
        
        if file_path:
            # Detect tracks in the file
            self._detect_and_add_tracks(file_path)
    
    def _detect_and_add_tracks(self, file_path: str):
        """Detect tracks in external file and add to list"""
        ffprobe_path = self.app_state.ffprobe_path
        
        try:
            cmd = [
                ffprobe_path,
                "-v", "error",
                "-show_entries", "stream=index,codec_type,codec_name,width,height,channels,sample_rate:stream_tags=title",
                "-of", "json",
                file_path
            ]
            
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=30
            )
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                
                tracks_added = 0
                for stream in data.get('streams', []):
                    codec_type = stream.get('codec_type', '')
                    
                    if codec_type == 'video':
                        track = self._create_video_track(stream, file_path)
                        track.name = f"External Video {len(self.app_state.track_list) + 1}"
                        self.app_state.track_list.append(track)
                        tracks_added += 1
                    
                    elif codec_type == 'audio':
                        track = self._create_audio_track(stream, file_path)
                        track.name = f"External Audio {len(self.app_state.track_list) + 1}"
                        self.app_state.track_list.append(track)
                        tracks_added += 1
                
                if tracks_added > 0:
                    self._update_ui_with_tracks(self.app_state.track_list)
                    self.app_state.log(f"Added {tracks_added} track(s) from {os.path.basename(file_path)}", "INFO")
        
        except Exception as e:
            self.app_state.log(f"Failed to add track: {e}", "ERROR")
    
    def _on_replace_track(self, track_id: str):
        """Handle replace track"""
        # Find the track
        track_to_replace = None
        for track in self.app_state.track_list:
            if track.track_id == track_id:
                track_to_replace = track
                break
        
        if not track_to_replace:
            return
        
        # Open file dialog
        if track_to_replace.track_type == TrackType.VIDEO:
            filter_str = "Video Files (*.mp4 *.mkv *.avi *.mov);;All Files (*.*)"
        else:
            filter_str = "Audio Files (*.mp3 *.wav *.aac *.flac *.m4a);;All Files (*.*)"
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Replace {track_to_replace.name}",
            "",
            filter_str
        )
        
        if file_path:
            # Detect tracks in the new file
            ffprobe_path = self.app_state.ffprobe_path
            
            try:
                cmd = [
                    ffprobe_path,
                    "-v", "error",
                    "-show_entries", "stream=index,codec_type,codec_name,width,height,channels,sample_rate,duration",
                    "-of", "json",
                    file_path
                ]
                
                result = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, timeout=30
                )
                
                if result.returncode == 0:
                    import json
                    data = json.loads(result.stdout)
                    
                    streams = data.get('streams', [])
                    if streams:
                        stream = streams[0]  # Use first stream
                        codec_type = stream.get('codec_type', '')
                        
                        if track_to_replace.track_type == TrackType.VIDEO and codec_type == 'video':
                            new_track = self._create_video_track(stream, file_path)
                            new_track.track_id = track_id
                            new_track.name = track_to_replace.name
                            new_track.enabled = track_to_replace.enabled
                            
                            # Replace in list
                            idx = self.app_state.track_list.index(track_to_replace)
                            self.app_state.track_list[idx] = new_track
                            
                            self._update_ui_with_tracks(self.app_state.track_list)
                            self.app_state.log(f"Replaced track with {os.path.basename(file_path)}", "INFO")
                            
                        elif track_to_replace.track_type == TrackType.AUDIO and codec_type == 'audio':
                            new_track = self._create_audio_track(stream, file_path)
                            new_track.track_id = track_id
                            new_track.name = track_to_replace.name
                            new_track.enabled = track_to_replace.enabled
                            
                            # Replace in list
                            idx = self.app_state.track_list.index(track_to_replace)
                            self.app_state.track_list[idx] = new_track
                            
                            self._update_ui_with_tracks(self.app_state.track_list)
                            self.app_state.log(f"Replaced track with {os.path.basename(file_path)}", "INFO")
                        else:
                            QMessageBox.warning(self, "Invalid Track", "Selected file does not contain the expected track type")
            
            except Exception as e:
                self.app_state.log(f"Failed to replace track: {e}", "ERROR")
    
    def _on_delete_track(self, track_id: str):
        """Handle delete track"""
        reply = QMessageBox.question(
            self,
            "Delete Track",
            "Are you sure you want to delete this track?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Remove from list
            self.app_state.track_list = [t for t in self.app_state.track_list if t.track_id != track_id]
            self._update_ui_with_tracks(self.app_state.track_list)
            self.app_state.log("Track deleted", "INFO")
    
    def _on_refresh_tracks(self):
        """Handle refresh button"""
        if self.current_video:
            self._detect_tracks(self.current_video)
    
    def _on_export(self):
        """Handle export button"""
        output_path = self.export_panel.get_output_path()
        
        if not output_path:
            QMessageBox.warning(self, "No Output", "Please select an output file path")
            return
        
        # Get enabled tracks
        enabled_tracks = [t for t in self.app_state.track_list if t.enabled]
        
        if not enabled_tracks:
            QMessageBox.warning(self, "No Tracks", "Please enable at least one track for export")
            return
        
        # Show progress
        progress = QProgressDialog("Exporting...", "Cancel", 0, 100, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        
        # Build FFmpeg command
        is_copy = self.export_panel.is_copy_mode()
        
        try:
            # Get source file from first enabled track
            source_file = enabled_tracks[0].source_file
            
            cmd = [self.app_state.ffmpeg_path, "-y", "-i", source_file]
            
            # Add stream mappings based on export mode
            export_mode = self.export_panel.get_export_mode()
            
            if export_mode == "Video Only":
                cmd.extend(["-map", "v:0"])
                if is_copy:
                    cmd.extend(["-c:v", "copy"])
                else:
                    cmd.extend(["-c:v", "libx264", "-c:a", "aac", "-b:a", "192k"])
            
            elif export_mode == "Audio Only":
                cmd.extend(["-map", "a:0"])
                if is_copy:
                    cmd.extend(["-c:a", "copy"])
                else:
                    cmd.extend(["-c:v", "none", "-c:a", "aac", "-b:a", "192k"])
            
            else:  # Both or Selected Track Only
                # Map video if available
                video_tracks = [t for t in enabled_tracks if t.track_type == TrackType.VIDEO]
                audio_tracks = [t for t in enabled_tracks if t.track_type == TrackType.AUDIO]
                
                if video_tracks:
                    cmd.extend(["-map", f"v:{video_tracks[0].stream_index}"])
                if audio_tracks:
                    cmd.extend(["-map", f"a:{audio_tracks[0].stream_index}"])
                
                if is_copy:
                    cmd.extend(["-c", "copy"])
                else:
                    # Re-encode with default settings
                    cmd.extend(["-c:v", "libx264", "-c:a", "aac", "-b:a", "192k"])
            
            # Output
            cmd.extend(["-progress", "pipe:1", output_path])
            
            # Disable UI
            self.export_panel.set_enabled(False)
            progress.setValue(10)
            QApplication.processEvents()
            
            # Run FFmpeg
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Monitor progress
            while process.poll() is None:
                if progress.wasCanceled():
                    process.terminate()
                    break
                
                # Try to read progress
                line = process.stdout.readline()
                if line and "out_time_ms" in line:
                    try:
                        # Parse progress
                        progress.setValue(50)
                    except:
                        pass
                
                QApplication.processEvents()
            
            progress.setValue(100)
            
            if process.returncode == 0:
                self.app_state.log(f"Export completed: {output_path}", "SUCCESS")
                QMessageBox.information(self, "Export Complete", f"File exported successfully!\n\n{output_path}")
            else:
                stderr = process.stderr.read()
                self.app_state.log(f"Export failed: {stderr}", "ERROR")
                QMessageBox.critical(self, "Export Failed", f"Export failed:\n{stderr}")
        
        except Exception as e:
            self.app_state.log(f"Export error: {e}", "ERROR")
            QMessageBox.critical(self, "Export Error", f"Export failed:\n{str(e)}")
        
        finally:
            # Re-enable UI
            self.export_panel.set_enabled(True)
            progress.close()
    
    def load_video(self, video_path: str):
        """Load video and detect tracks"""
        self.current_video = video_path
        self._detect_tracks(video_path)
