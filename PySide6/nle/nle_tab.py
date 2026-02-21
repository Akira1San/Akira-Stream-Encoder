"""
NLE Tab - Main Non-Linear Editor Tab Widget
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal

from models import AppState
from nle.nle_models import NLEProject, TrackType, NLEClip
from nle.nle_source_bin import SourceBinPanel


class PlaceholderPanel(QFrame):
    """Placeholder panel with centered label"""
    
    def __init__(self, title: str, color: str = "#2d2d2d", parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.StyledPanel)
        self.setStyleSheet(f"""
            PlaceholderPanel {{
                background-color: {color};
                border: 1px solid #3d3d3d;
                border-radius: 4px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.label = QLabel(title)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color: #888; font-size: 14px;")
        layout.addWidget(self.label)


class PreviewPanel(PlaceholderPanel):
    """Preview Panel - for video preview"""
    
    def __init__(self, parent=None):
        super().__init__("Preview\n\nSelect a clip to preview", "#1a1a1a", parent)
        self.setMinimumWidth(320)
        self.setMinimumHeight(180)


class PropertiesPanel(PlaceholderPanel):
    """Properties Panel - for clip/track properties and effects"""
    
    def __init__(self, parent=None):
        super().__init__("Properties\n\nSelect a clip to edit", "#252525", parent)
        self.setMinimumWidth(200)


class NLETab(QWidget):
    """
    Non-Linear Editor Tab
    
    Layout structure:
    ┌─────────────────────────────────────────────────────────────┐
    │  Toolbar                                                     │
    ├──────────────┬──────────────────────────┬───────────────────┤
    │              │                          │                   │
    │  Source Bin  │        Preview           │    Properties     │
    │              │                          │                   │
    ├──────────────┴──────────────────────────┴───────────────────┤
    │                                                              │
    │                     Timeline                                 │
    │                                                              │
    └─────────────────────────────────────────────────────────────┘
    """
    
    # Signals
    project_changed = Signal()
    
    def __init__(self, app_state: AppState, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.project = NLEProject()
        
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """Setup the main layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # === Toolbar ===
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # === Main Content Area ===
        # Vertical splitter for top panels and timeline
        main_splitter = QSplitter(Qt.Vertical)
        
        # Top section: Horizontal splitter for Source Bin | Preview | Properties
        top_splitter = QSplitter(Qt.Horizontal)
        
        # Source Bin Panel
        self.source_bin = SourceBinPanel()
        top_splitter.addWidget(self.source_bin)
        
        # Preview Panel
        self.preview = PreviewPanel()
        top_splitter.addWidget(self.preview)
        
        # Properties Panel
        self.properties = PropertiesPanel()
        top_splitter.addWidget(self.properties)
        
        # Set initial sizes for top splitter (Source:Preview:Properties = 1:2:1)
        top_splitter.setSizes([200, 400, 200])
        
        main_splitter.addWidget(top_splitter)
        
        # === Timeline Section ===
        timeline_widget = self._create_timeline_section()
        main_splitter.addWidget(timeline_widget)
        
        # Set initial sizes (top:timeline = 1:1)
        main_splitter.setSizes([300, 300])
        
        layout.addWidget(main_splitter)
    
    def _create_toolbar(self) -> QWidget:
        """Create the toolbar with action buttons"""
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
            }
        """)
        
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Project actions
        new_btn = QPushButton("📄 New")
        new_btn.setToolTip("New Project")
        new_btn.clicked.connect(self.on_new_project)
        layout.addWidget(new_btn)
        
        open_btn = QPushButton("📂 Open")
        open_btn.setToolTip("Open Project")
        open_btn.clicked.connect(self.on_open_project)
        layout.addWidget(open_btn)
        
        save_btn = QPushButton("💾 Save")
        save_btn.setToolTip("Save Project")
        save_btn.clicked.connect(self.on_save_project)
        layout.addWidget(save_btn)
        
        layout.addSpacing(20)
        
        # Track actions
        add_video_btn = QPushButton("🎬 Add Video Track")
        add_video_btn.setToolTip("Add a new video track")
        add_video_btn.clicked.connect(self.on_add_video_track)
        layout.addWidget(add_video_btn)
        
        add_audio_btn = QPushButton("🔊 Add Audio Track")
        add_audio_btn.setToolTip("Add a new audio track")
        add_audio_btn.clicked.connect(self.on_add_audio_track)
        layout.addWidget(add_audio_btn)
        
        layout.addSpacing(20)
        
        # Source actions
        add_source_btn = QPushButton("📁 Add Source")
        add_source_btn.setToolTip("Add source video file")
        add_source_btn.clicked.connect(self.on_add_source)
        layout.addWidget(add_source_btn)
        
        layout.addStretch()
        
        # Render action
        render_btn = QPushButton("▶️ Render")
        render_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        render_btn.setToolTip("Render project to file")
        render_btn.clicked.connect(self.on_render)
        layout.addWidget(render_btn)
        
        return toolbar
    
    def _create_timeline_section(self) -> QWidget:
        """Create the timeline section with controls and track area"""
        timeline_widget = QFrame()
        timeline_widget.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
            }
        """)
        
        layout = QVBoxLayout(timeline_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Timeline header with zoom controls
        header = QFrame()
        header.setStyleSheet("background-color: transparent;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Time display
        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setStyleSheet("color: #aaa; font-family: monospace; font-size: 12px;")
        header_layout.addWidget(self.time_label)
        
        header_layout.addStretch()
        
        # Zoom controls
        zoom_out_btn = QPushButton("➖")
        zoom_out_btn.setFixedSize(30, 24)
        zoom_out_btn.setToolTip("Zoom Out")
        zoom_out_btn.clicked.connect(self.on_zoom_out)
        header_layout.addWidget(zoom_out_btn)
        
        self.zoom_label = QLabel("100%")
        self.zoom_label.setStyleSheet("color: #aaa; font-size: 11px; min-width: 50px;")
        self.zoom_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.zoom_label)
        
        zoom_in_btn = QPushButton("➕")
        zoom_in_btn.setFixedSize(30, 24)
        zoom_in_btn.setToolTip("Zoom In")
        zoom_in_btn.clicked.connect(self.on_zoom_in)
        header_layout.addWidget(zoom_in_btn)
        
        layout.addWidget(header)
        
        # Timeline widget (actual NLE timeline)
        from nle.nle_timeline import NLETimeline
        self.timeline = NLETimeline()
        self.timeline.playhead_moved.connect(self._on_playhead_moved)
        self.timeline.zoom_changed.connect(self._on_zoom_changed)
        self.timeline.setMinimumHeight(150)
        layout.addWidget(self.timeline)
        
        return timeline_widget
    
    def connect_signals(self):
        """Connect internal signals"""
        self.project_changed.connect(self.on_project_changed)
        
        # Connect source bin signals
        self.source_bin.preview_requested.connect(self._on_preview_source)
        self.source_bin.clip_create_requested.connect(self._on_create_clip_from_source)
        
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        from PySide6.QtCore import Qt
        
        if event.key() == Qt.Key_Delete:
            # Delete selected clips
            self.timeline.delete_selected_clips()
            self.project_changed.emit()
            self.app_state.log("Deleted selected clips", "INFO")
            
        elif event.key() == Qt.Key_S and event.modifiers() == Qt.ControlModifier:
            # Save project
            self.on_save_project()
            
        elif event.key() == Qt.Key_Space:
            # Toggle play/pause (future implementation)
            self.app_state.log("Play/Pause not yet implemented", "INFO")
            
        elif event.key() == Qt.Key_S and event.modifiers() == Qt.NoModifier:
            # Split at playhead
            if self.timeline.split_clip_at_playhead():
                self.project_changed.emit()
                self.app_state.log("Split clip at playhead", "INFO")
                
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
            # Zoom in
            self.timeline.zoom_in()
            
        elif event.key() == Qt.Key_Minus:
            # Zoom out
            self.timeline.zoom_out()
            
        else:
            super().keyPressEvent(event)
    
    # === Toolbar Actions ===
    
    def on_new_project(self):
        """Create new project"""
        self.project.clear()
        self.project_changed.emit()
        self.app_state.log("Created new NLE project", "INFO")
    
    def on_open_project(self):
        """Open existing project"""
        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open NLE Project",
            "",
            "NLE Project (*.nle.json);;All Files (*)"
        )
        if file_path:
            import json
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                self.project = NLEProject.from_dict(data)
                self.project_changed.emit()
                self.app_state.log(f"Opened project: {file_path}", "INFO")
            except Exception as e:
                self.app_state.log(f"Failed to open project: {e}", "ERROR")
    
    def on_save_project(self):
        """Save current project"""
        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save NLE Project",
            f"{self.project.name}.nle.json",
            "NLE Project (*.nle.json);;All Files (*)"
        )
        if file_path:
            import json
            try:
                with open(file_path, 'w') as f:
                    json.dump(self.project.to_dict(), f, indent=2)
                self.app_state.log(f"Saved project: {file_path}", "INFO")
            except Exception as e:
                self.app_state.log(f"Failed to save project: {e}", "ERROR")
    
    def on_add_video_track(self):
        """Add a new video track"""
        track = self.project.add_track(TrackType.VIDEO)
        self.project_changed.emit()
        self.app_state.log(f"Added video track: {track.name}", "INFO")
    
    def on_add_audio_track(self):
        """Add a new audio track"""
        track = self.project.add_track(TrackType.AUDIO)
        self.project_changed.emit()
        self.app_state.log(f"Added audio track: {track.name}", "INFO")
    
    def on_add_source(self):
        """Add source file to bin"""
        from PySide6.QtWidgets import QFileDialog
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Source Files",
            "",
            "Video Files (*.mp4 *.mkv *.avi *.mov *.webm *.flv);;All Files (*)"
        )
        if file_paths:
            for path in file_paths:
                self.source_bin.add_source(path)
                self.app_state.log(f"Added source: {path}", "INFO")
                
    def _on_preview_source(self, source_path: str):
        """Handle preview request for source"""
        self.app_state.log(f"Preview requested for: {source_path}", "INFO")
        # TODO: Implement preview in preview panel
        
    def _on_create_clip_from_source(self, source_path: str, timeline_position: float):
        """Handle creating a clip from source"""
        # Get source metadata
        metadata = self.source_bin.get_source(source_path)
        if not metadata or not metadata.valid:
            self.app_state.log(f"Cannot create clip: source not valid", "WARN")
            return
            
        # Find or create appropriate track
        video_tracks = self.project.get_video_tracks()
        if not video_tracks:
            track = self.project.add_track(TrackType.VIDEO)
        else:
            track = video_tracks[0]
            
        # Create clip
        clip = NLEClip(
            source_path=source_path,
            source_start=0.0,
            source_end=metadata.duration,
            timeline_start=timeline_position
        )
        
        # Add to track
        track.add_clip(clip)
        self.project_changed.emit()
        self.app_state.log(f"Created clip from {metadata.filename}", "INFO")
    
    def on_render(self):
        """Render the project"""
        self.app_state.log("Render not yet implemented", "WARN")
        
    def on_split_at_playhead(self):
        """Split clip at playhead position"""
        if self.timeline.split_clip_at_playhead():
            self.project_changed.emit()
            self.app_state.log("Split clip at playhead", "INFO")
        else:
            self.app_state.log("No clip under playhead to split", "WARN")
    
    def on_zoom_in(self):
        """Zoom in timeline"""
        self.timeline.zoom_in()
    
    def on_zoom_out(self):
        """Zoom out timeline"""
        self.timeline.zoom_out()
    
    def _on_playhead_moved(self, position: float):
        """Handle playhead position change"""
        self._update_time_display(position)
    
    def _on_zoom_changed(self, pixels_per_second: float):
        """Handle zoom change"""
        percentage = int((pixels_per_second / 20.0) * 100)
        self.zoom_label.setText(f"{percentage}%")
    
    def _update_time_display(self, current_time: float = 0.0):
        """Update the time display label"""
        current_str = self._format_time(current_time)
        duration_str = self._format_time(self.project.duration)
        self.time_label.setText(f"{current_str} / {duration_str}")
    
    def on_project_changed(self):
        """Handle project changes"""
        # Update timeline with project
        self.timeline.set_project(self.project)
        
        # Update time display
        self._update_time_display()
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
