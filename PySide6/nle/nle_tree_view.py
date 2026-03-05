"""
NLE Tree View - Tree-based composition view replacing the timeline
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QLabel, QPushButton, QFrame, QCheckBox, QStyle
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

from nle.nle_models import NLEProject, NLETrack, NLEClip, TrackType


class NLETreeView(QWidget):
    """
    Tree-based composition view.
    
    Shows tracks and clips in a hierarchical tree structure:
    - Project
      - Video Track 1 (checkbox to enable/disable)
        - Clip 1 (name, duration)
        - Clip 2
      - Audio Track 1
        - Clip 1
    """
    
    # Signals
    selection_changed = Signal(object)  # Emits selected track or clip
    project_changed = Signal()  # Emits when project structure changes
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._project = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the tree view UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header with controls
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-bottom: 1px solid #3d3d3d;
                padding: 5px;
            }
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 5, 10, 5)
        
        # Add track buttons
        add_video_btn = QPushButton("+ Video")
        add_video_btn.setToolTip("Add video track")
        add_video_btn.clicked.connect(self._on_add_video_track)
        header_layout.addWidget(add_video_btn)
        
        add_audio_btn = QPushButton("+ Audio")
        add_audio_btn.setToolTip("Add audio track")
        add_audio_btn.clicked.connect(self._on_add_audio_track)
        header_layout.addWidget(add_audio_btn)
        
        header_layout.addStretch()
        
        # Duration label
        self.duration_label = QLabel("Duration: 00:00")
        self.duration_label.setStyleSheet("color: #888; font-size: 11px;")
        header_layout.addWidget(self.duration_label)
        
        main_layout.addWidget(header)
        
        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Duration", "Type"])
        self.tree.setColumnWidth(0, 200)
        self.tree.setAlternatingRowColors(True)
        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1e1e1e;
                color: #cccccc;
                border: none;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 4px;
            }
            QTreeWidget::item:selected {
                background-color: #3d5a80;
                color: white;
            }
            QTreeWidget::item:hover {
                background-color: #2d2d2d;
            }
            QTreeWidget::branch {
                background-color: #1e1e1e;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #888;
                padding: 4px;
                border: none;
                font-size: 11px;
            }
        """)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemClicked.connect(self._on_item_clicked)
        
        main_layout.addWidget(self.tree)
    
    def set_project(self, project: NLEProject):
        """Set the NLE project"""
        self._project = project
        self._refresh_tree()
    
    def _refresh_tree(self):
        """Refresh the tree from project"""
        self.tree.blockSignals(True)
        self.tree.clear()
        
        if not self._project:
            self.tree.blockSignals(False)
            return
        
        # Add tracks
        for track in self._project.tracks:
            self._add_track_to_tree(track)
        
        # Update duration
        self._update_duration()
        
        self.tree.blockSignals(False)
    
    def _add_track_to_tree(self, track: NLETrack):
        """Add a track to the tree"""
        # Track item
        track_item = QTreeWidgetItem()
        track_item.setText(0, track.name)
        
        # Track type column
        track_type_str = "Video" if track.track_type == TrackType.VIDEO else "Audio"
        track_item.setText(2, track_type_str)
        
        # Store reference to track
        track_item.setData(0, Qt.UserRole, {"type": "track", "object": track})
        
        # Set checkbox for enabled/disabled
        track_item.setCheckState(0, Qt.Checked if track.visible else Qt.Unchecked)
        
        # Track icon (color indicator)
        if track.track_type == TrackType.VIDEO:
            track_item.setForeground(0, QCheckBox().palette().windowText())
        else:
            track_item.setForeground(0, QCheckBox().palette().windowText())
        
        self.tree.addTopLevelItem(track_item)
        track_item.setExpanded(True)
        
        # Add clips to track
        for clip in track.clips:
            self._add_clip_to_tree(clip, track_item)
    
    def _add_clip_to_tree(self, clip: NLEClip, parent_item: QTreeWidgetItem):
        """Add a clip to the tree"""
        clip_item = QTreeWidgetItem()
        clip_item.setText(0, clip.name)
        
        # Duration
        duration_str = self._format_duration(clip.duration)
        clip_item.setText(1, duration_str)
        
        # Source type
        clip_item.setText(2, "Clip")
        
        # Store reference to clip
        clip_item.setData(0, Qt.UserRole, {"type": "clip", "object": clip})
        
        parent_item.addChild(clip_item)
    
    def _on_item_changed(self, item: QTreeWidgetItem, column: int):
        """Handle checkbox state change"""
        data = item.data(0, Qt.UserRole)
        if not data or column != 0:
            return
        
        if data["type"] == "track":
            track = data["object"]
            checked = item.checkState(0) == Qt.Checked
            track.visible = checked
            self.project_changed.emit()
    
    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle item selection"""
        if item is None:
            return
        data = item.data(0, Qt.UserRole)
        if data:
            self.selection_changed.emit(data["object"])
    
    def _on_add_video_track(self):
        """Add a new video track"""
        if self._project:
            self._project.add_track(TrackType.VIDEO)
            self._refresh_tree()
            self.project_changed.emit()
    
    def _on_add_audio_track(self):
        """Add a new audio track"""
        if self._project:
            self._project.add_track(TrackType.AUDIO)
            self._refresh_tree()
            self.project_changed.emit()
    
    def _update_duration(self):
        """Update duration display"""
        if self._project:
            duration_str = self._format_duration(self._project.duration)
            self.duration_label.setText(f"Duration: {duration_str}")
        else:
            self.duration_label.setText("Duration: 00:00")
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration as HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
    
    def get_selected_item(self):
        """Get the currently selected track or clip"""
        current_item = self.tree.currentItem()
        if current_item:
            data = current_item.data(0, Qt.UserRole)
            if data:
                return data["object"]
        return None
    
    def add_clip_to_track(self, track_id: str, clip: NLEClip):
        """Add a clip to a track in the tree"""
        if not self._project:
            return
        
        track = self._project.get_track(track_id)
        if track:
            track.add_clip(clip)
            self._refresh_tree()
            self.project_changed.emit()
    
    def remove_selected(self):
        """Remove selected item (track or clip)"""
        current_item = self.tree.currentItem()
        if not current_item or not self._project:
            return
        
        data = current_item.data(0, Qt.UserRole)
        if not data:
            return
        
        if data["type"] == "track":
            # Remove track
            track = data["object"]
            self._project.remove_track(track.id)
        elif data["type"] == "clip":
            # Remove clip
            clip = data["object"]
            self._project.remove_clip(clip.id)
        
        self._refresh_tree()
        self.project_changed.emit()
