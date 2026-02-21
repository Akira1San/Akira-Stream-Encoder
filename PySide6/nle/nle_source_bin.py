"""
NLE Source Bin - Source file management panel
"""
import os
import subprocess
import json
from typing import Dict, Any, Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QFileDialog, QProgressBar, QMenu
)
from PySide6.QtCore import Qt, Signal, QThread, QMimeData
from PySide6.QtGui import QDrag

from nle.nle_models import NLEClip, TrackType


class SourceMetadata:
    """Metadata for a source file"""
    
    def __init__(self, path: str):
        self.path = path
        self.filename = os.path.basename(path)
        self.duration: float = 0.0
        self.width: int = 0
        self.height: int = 0
        self.fps: float = 0.0
        self.has_audio: bool = False
        self.audio_codec: str = ""
        self.video_codec: str = ""
        self.valid: bool = False
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'path': self.path,
            'filename': self.filename,
            'duration': self.duration,
            'width': self.width,
            'height': self.height,
            'fps': self.fps,
            'has_audio': self.has_audio,
            'audio_codec': self.audio_codec,
            'video_codec': self.video_codec,
            'valid': self.valid
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SourceMetadata':
        """Create from dictionary"""
        meta = cls(data['path'])
        meta.filename = data.get('filename', meta.filename)
        meta.duration = data.get('duration', 0.0)
        meta.width = data.get('width', 0)
        meta.height = data.get('height', 0)
        meta.fps = data.get('fps', 0.0)
        meta.has_audio = data.get('has_audio', False)
        meta.audio_codec = data.get('audio_codec', '')
        meta.video_codec = data.get('video_codec', '')
        meta.valid = data.get('valid', False)
        return meta


class FFProbeWorker(QThread):
    """Worker thread to extract metadata using ffprobe"""
    
    finished = Signal(str, dict)  # path, metadata
    error = Signal(str, str)  # path, error_message
    
    def __init__(self, source_path: str, ffprobe_path: str = "ffprobe"):
        super().__init__()
        self.source_path = source_path
        self.ffprobe_path = ffprobe_path
        
    def run(self):
        """Run ffprobe to extract metadata"""
        try:
            cmd = [
                self.ffprobe_path,
                "-v", "error",
                "-show_entries", "format=duration:stream=width,height,r_frame_rate,codec_type,codec_name",
                "-of", "json",
                self.source_path
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                self.error.emit(self.source_path, result.stderr)
                return
                
            data = json.loads(result.stdout)
            
            metadata = {
                'path': self.source_path,
                'duration': 0.0,
                'width': 0,
                'height': 0,
                'fps': 0.0,
                'has_audio': False,
                'video_codec': '',
                'audio_codec': ''
            }
            
            # Get duration from format
            if 'format' in data:
                metadata['duration'] = float(data['format'].get('duration', 0))
            
            # Get stream info
            for stream in data.get('streams', []):
                codec_type = stream.get('codec_type', '')
                
                if codec_type == 'video':
                    metadata['width'] = stream.get('width', 0)
                    metadata['height'] = stream.get('height', 0)
                    metadata['video_codec'] = stream.get('codec_name', '')
                    
                    # Parse frame rate
                    fps_str = stream.get('r_frame_rate', '0/1')
                    if '/' in fps_str:
                        num, den = fps_str.split('/')
                        if float(den) > 0:
                            metadata['fps'] = float(num) / float(den)
                            
                elif codec_type == 'audio':
                    metadata['has_audio'] = True
                    metadata['audio_codec'] = stream.get('codec_name', '')
            
            metadata['valid'] = True
            self.finished.emit(self.source_path, metadata)
            
        except subprocess.TimeoutExpired:
            self.error.emit(self.source_path, "FFprobe timed out")
        except json.JSONDecodeError:
            self.error.emit(self.source_path, "Failed to parse ffprobe output")
        except Exception as e:
            self.error.emit(self.source_path, str(e))


class SourceBinItem(QListWidgetItem):
    """Custom list item for source files"""
    
    def __init__(self, metadata: SourceMetadata, parent=None):
        super().__init__(parent)
        self.metadata = metadata
        
        # Set display text
        self.setText(self._format_display())
        self.setToolTip(self._format_tooltip())
        
    def _format_display(self) -> str:
        """Format display text"""
        duration_str = self._format_duration(self.metadata.duration)
        return f"{self.metadata.filename}\n{duration_str}"
    
    def _format_tooltip(self) -> str:
        """Format tooltip with full info"""
        return (
            f"Path: {self.metadata.path}\n"
            f"Duration: {self._format_duration(self.metadata.duration)}\n"
            f"Resolution: {self.metadata.width}x{self.metadata.height}\n"
            f"Frame Rate: {self.metadata.fps:.2f} fps\n"
            f"Video: {self.metadata.video_codec}\n"
            f"Audio: {self.metadata.audio_codec if self.metadata.has_audio else 'None'}"
        )
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration as HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class SourceBinPanel(QWidget):
    """
    Source Bin Panel - manages source video files.
    
    Features:
    - Add source files via button or drag & drop
    - Display filename and duration
    - Double-click to preview
    - Drag to timeline to create clips
    """
    
    source_added = Signal(str)  # source_path
    source_removed = Signal(str)  # source_path
    preview_requested = Signal(str)  # source_path
    clip_create_requested = Signal(str, float)  # source_path, timeline_position
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._sources: Dict[str, SourceMetadata] = {}
        self._workers: List[FFProbeWorker] = []
        self._ffprobe_path = "ffprobe"
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the UI"""
        self.setStyleSheet("""
            SourceBinPanel {
                background-color: #252525;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
            }
            QListWidget {
                background-color: #1e1e1e;
                border: none;
                color: #ddd;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #2a2a2a;
            }
            QListWidget::item:selected {
                background-color: #3498db;
            }
            QListWidget::item:hover {
                background-color: #2a2a2a;
            }
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Header
        header = QLabel("Source Bin")
        header.setStyleSheet("color: #aaa; font-weight: bold; font-size: 12px;")
        layout.addWidget(header)
        
        # Source list
        self.source_list = QListWidget()
        self.source_list.setSelectionMode(QListWidget.SingleSelection)
        self.source_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.source_list.setDragEnabled(True)
        self.source_list.setAcceptDrops(True)
        self.source_list.startDrag = self._start_drag
        layout.addWidget(self.source_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("📁 Add Source")
        self.add_btn.clicked.connect(self._on_add_source)
        btn_layout.addWidget(self.add_btn)
        
        self.remove_btn = QPushButton("🗑️ Remove")
        self.remove_btn.clicked.connect(self._on_remove_source)
        self.remove_btn.setEnabled(False)
        btn_layout.addWidget(self.remove_btn)
        
        layout.addLayout(btn_layout)
        
        # Add to Timeline button
        self.add_to_timeline_btn = QPushButton("➕ Add to Timeline")
        self.add_to_timeline_btn.setToolTip("Add selected source to timeline at playhead position")
        self.add_to_timeline_btn.clicked.connect(self._on_add_to_timeline)
        self.add_to_timeline_btn.setEnabled(False)
        layout.addWidget(self.add_to_timeline_btn)
        
        # Progress bar (hidden by default)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setMaximumHeight(3)
        layout.addWidget(self.progress)
        
        # Connect selection change
        self.source_list.itemSelectionChanged.connect(self._on_selection_changed)
        
    def set_ffprobe_path(self, path: str):
        """Set ffprobe path"""
        self._ffprobe_path = path
        
    def add_source(self, path: str):
        """Add a source file"""
        if path in self._sources:
            return
            
        # Create placeholder metadata
        metadata = SourceMetadata(path)
        self._sources[path] = metadata
        
        # Add item to list
        item = SourceBinItem(metadata, self.source_list)
        self.source_list.addItem(item)
        
        # Extract metadata in background
        self._extract_metadata(path)
        
        self.source_added.emit(path)
        
    def remove_source(self, path: str):
        """Remove a source file"""
        if path not in self._sources:
            return
            
        # Remove from list
        for i in range(self.source_list.count()):
            item = self.source_list.item(i)
            if isinstance(item, SourceBinItem) and item.metadata.path == path:
                self.source_list.takeItem(i)
                break
                
        # Remove from dict
        del self._sources[path]
        
        self.source_removed.emit(path)
        
    def get_source(self, path: str) -> Optional[SourceMetadata]:
        """Get source metadata by path"""
        return self._sources.get(path)
        
    def get_all_sources(self) -> List[SourceMetadata]:
        """Get all source metadata"""
        return list(self._sources.values())
        
    def _extract_metadata(self, path: str):
        """Extract metadata using ffprobe"""
        worker = FFProbeWorker(path, self._ffprobe_path)
        worker.finished.connect(self._on_metadata_extracted)
        worker.error.connect(self._on_metadata_error)
        self._workers.append(worker)
        worker.start()
        
    def _on_metadata_extracted(self, path: str, data: dict):
        """Handle metadata extraction completion"""
        if path in self._sources:
            metadata = self._sources[path]
            metadata.duration = data.get('duration', 0.0)
            metadata.width = data.get('width', 0)
            metadata.height = data.get('height', 0)
            metadata.fps = data.get('fps', 0.0)
            metadata.has_audio = data.get('has_audio', False)
            metadata.video_codec = data.get('video_codec', '')
            metadata.audio_codec = data.get('audio_codec', '')
            metadata.valid = data.get('valid', False)
            
            # Update list item
            for i in range(self.source_list.count()):
                item = self.source_list.item(i)
                if isinstance(item, SourceBinItem) and item.metadata.path == path:
                    item.setText(item._format_display())
                    item.setToolTip(item._format_tooltip())
                    break
                    
    def _on_metadata_error(self, path: str, error: str):
        """Handle metadata extraction error"""
        # Keep placeholder but mark as invalid
        if path in self._sources:
            self._sources[path].valid = False
            
    def _on_add_source(self):
        """Handle add source button"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Source Files",
            "",
            "Video Files (*.mp4 *.mkv *.avi *.mov *.webm *.flv *.vob);;All Files (*)"
        )
        
        for path in file_paths:
            self.add_source(path)
            
    def _on_remove_source(self):
        """Handle remove source button"""
        item = self.source_list.currentItem()
        if isinstance(item, SourceBinItem):
            self.remove_source(item.metadata.path)
            
    def _on_selection_changed(self):
        """Handle selection change"""
        has_selection = self.source_list.currentItem() is not None
        self.remove_btn.setEnabled(has_selection)
        self.add_to_timeline_btn.setEnabled(has_selection)
        
    def _on_item_double_clicked(self, item: QListWidgetItem):
        """Handle double-click on item"""
        if isinstance(item, SourceBinItem):
            self.preview_requested.emit(item.metadata.path)
    
    def _on_add_to_timeline(self):
        """Handle add to timeline button - emit signal with position 0"""
        item = self.source_list.currentItem()
        if isinstance(item, SourceBinItem):
            # Add at position 0 (beginning of timeline)
            # The parent tab can override this to use playhead position
            self.clip_create_requested.emit(item.metadata.path, 0.0)
            
    def _start_drag(self, supportedActions):
        """Start drag operation"""
        item = self.source_list.currentItem()
        if not isinstance(item, SourceBinItem):
            return
            
        # Create mime data with source path
        mime_data = QMimeData()
        mime_data.setText(item.metadata.path)
        mime_data.setData("application/x-nle-source", item.metadata.path.encode())
        
        # Create drag object
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec_(Qt.CopyAction)
        
    def clear(self):
        """Clear all sources"""
        self.source_list.clear()
        self._sources.clear()
        
    def to_dict(self) -> List[Dict[str, Any]]:
        """Serialize sources to list of dicts"""
        return [meta.to_dict() for meta in self._sources.values()]
        
    def from_dict(self, data: List[Dict[str, Any]]):
        """Load sources from list of dicts"""
        self.clear()
        for item_data in data:
            metadata = SourceMetadata.from_dict(item_data)
            self._sources[metadata.path] = metadata
            
            item = SourceBinItem(metadata, self.source_list)
            self.source_list.addItem(item)
