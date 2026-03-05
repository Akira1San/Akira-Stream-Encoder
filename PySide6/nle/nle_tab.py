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
from nle.nle_tree_view import NLETreeView


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


class PropertiesPanel(PlaceholderPanel):
    """Properties Panel - for clip/track properties and effects"""
    
    def __init__(self, parent=None):
        super().__init__("Properties\n\nSelect a track or clip", "#252525", parent)
        self.setMinimumWidth(200)
        self.current_item = None
    
    def set_item(self, item):
        """Set the currently selected item (track or clip)"""
        self.current_item = item
        self._update_display()
    
    def _update_display(self):
        """Update the properties display based on selected item"""
        from nle.nle_models import NLETrack, NLEClip
        
        if self.current_item is None:
            self.label.setText("Properties\n\nSelect a track or clip")
            return
        
        if isinstance(self.current_item, NLETrack):
            track = self.current_item
            track_type = "Video" if track.track_type.value == "video" else "Audio"
            self.label.setText(
                f"Properties\n\n"
                f"Name: {track.name}\n"
                f"Type: {track_type}\n"
                f"Clips: {len(track.clips)}"
            )
        elif isinstance(self.current_item, NLEClip):
            clip = self.current_item
            self.label.setText(
                f"Properties\n\n"
                f"Name: {clip.name}\n"
                f"Duration: {self._format_time(clip.duration)}\n"
                f"Source: {clip.source_path}"
            )
        else:
            self.label.setText("Properties\n\nUnknown item type")
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"


class NLETab(QWidget):
    """
    Non-Linear Editor Tab
    
    Layout structure:
    ┌─────────────────────────────────────────────────────────────┐
    │  Toolbar                                                     │
    ├──────────────┬──────────────────────────────────────────────┤
    │              │                                               │
    │  Source Bin  │              Properties                       │
    │              │                                               │
    ├──────────────┴──────────────────────────────────────────────┤
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
        
        # === Main Content Area ===
        # Vertical splitter for top panels and timeline
        main_splitter = QSplitter(Qt.Vertical)
        
        # Top section: Horizontal splitter for Source Bin | Properties
        top_splitter = QSplitter(Qt.Horizontal)
        
        # Source Bin Panel
        self.source_bin = SourceBinPanel()
        top_splitter.addWidget(self.source_bin)
        
        # Properties Panel
        self.properties = PropertiesPanel()
        top_splitter.addWidget(self.properties)
        
        # Set initial sizes for top splitter (Source:Properties = 1:1)
        top_splitter.setSizes([250, 250])
        
        main_splitter.addWidget(top_splitter)
        
        # === Composition Section (Tree View) ===
        composition_widget = self._create_composition_section()
        main_splitter.addWidget(composition_widget)
        
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
    
    def _create_composition_section(self) -> QWidget:
        """Create the composition section with tree view"""
        # Use tree view instead of timeline
        self.tree_view = NLETreeView()
        self.tree_view.selection_changed.connect(self._on_selection_changed)
        self.tree_view.project_changed.connect(self._on_project_tree_changed)
        
        # Set project immediately so buttons work
        self.tree_view.set_project(self.project)
        
        return self.tree_view
    
    def _on_selection_changed(self, item):
        """Handle selection change in tree view"""
        self.properties.set_item(item)
    
    def _on_project_tree_changed(self):
        """Handle project change from tree view"""
        self.project_changed.emit()
    
    def connect_signals(self):
        """Connect internal signals"""
        self.project_changed.connect(self.on_project_changed)
        
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        from PySide6.QtCore import Qt
        
        if event.key() == Qt.Key_Delete:
            # Delete selected item in tree view
            self.tree_view.remove_selected()
            self.project_changed.emit()
            self.app_state.log("Deleted selected item", "INFO")
        
        elif event.key() == Qt.Key_S and event.modifiers() == Qt.ControlModifier:
            # Save project
            self.on_save_project()
        
        elif event.key() == Qt.Key_S and event.modifiers() == Qt.NoModifier:
            # (was split at playhead - not applicable in tree view)
            pass
        
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
            # (was zoom in - not applicable in tree view)
            pass
        
        elif event.key() == Qt.Key_Minus:
            # (was zoom out - not applicable in tree view)
            pass
        
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
        """Update the time display label"""
        current_str = self._format_time(current_time)
        duration_str = self._format_time(self.project.duration)
        self.time_label.setText(f"{current_str} / {duration_str}")
    
    def on_project_changed(self):
        """Handle project changes"""
        # Update tree view with project
        self.tree_view.set_project(self.project)
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
