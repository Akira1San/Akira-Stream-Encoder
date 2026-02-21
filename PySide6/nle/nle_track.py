"""
NLE Track Widget - Track row with header and clip container
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QPainter, QColor, QPen

from nle.nle_models import NLETrack, NLEClip, TrackType


class TrackHeader(QFrame):
    """
    Track header widget showing track name and controls.
    
    Displays: Name | Mute button | Lock button
    """
    
    mute_toggled = Signal(str, bool)  # track_id, muted
    lock_toggled = Signal(str, bool)  # track_id, locked
    clicked = Signal(str)  # track_id
    
    def __init__(self, track: NLETrack, parent=None):
        super().__init__(parent)
        self.track = track
        self.setMinimumWidth(120)
        self.setMaximumWidth(180)
        self.setFixedHeight(50)
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the header layout"""
        self.setStyleSheet("""
            TrackHeader {
                background-color: #2a2a2a;
                border: 1px solid #3d3d3d;
                border-radius: 3px;
            }
            QLabel {
                color: #ddd;
                font-size: 11px;
            }
            QPushButton {
                background-color: #3a3a3a;
                color: #aaa;
                border: none;
                border-radius: 3px;
                padding: 3px 6px;
                font-size: 10px;
                min-width: 40px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:checked {
                background-color: #e74c3c;
                color: white;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)
        
        # Track name
        self.name_label = QLabel(self.track.name)
        self.name_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.name_label)
        
        layout.addStretch()
        
        # Mute button
        self.mute_btn = QPushButton("M")
        self.mute_btn.setToolTip("Mute track")
        self.mute_btn.setCheckable(True)
        self.mute_btn.setChecked(self.track.muted)
        self.mute_btn.clicked.connect(self._on_mute_clicked)
        layout.addWidget(self.mute_btn)
        
        # Lock button
        self.lock_btn = QPushButton("L")
        self.lock_btn.setToolTip("Lock track")
        self.lock_btn.setCheckable(True)
        self.lock_btn.setChecked(self.track.locked)
        self.lock_btn.clicked.connect(self._on_lock_clicked)
        layout.addWidget(self.lock_btn)
        
    def _on_mute_clicked(self, checked: bool):
        """Handle mute button click"""
        self.track.muted = checked
        self.mute_toggled.emit(self.track.id, checked)
        
    def _on_lock_clicked(self, checked: bool):
        """Handle lock button click"""
        self.track.locked = checked
        self.lock_toggled.emit(self.track.id, checked)
        
    def mousePressEvent(self, event):
        """Handle mouse click on header"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.track.id)
        super().mousePressEvent(event)
        
    def update_from_track(self):
        """Update UI from track state"""
        self.name_label.setText(self.track.name)
        self.mute_btn.setChecked(self.track.muted)
        self.lock_btn.setChecked(self.track.locked)


class ClipContainer(QWidget):
    """
    Container widget for clips on a track.
    
    This is where clip widgets are placed and moved.
    """
    
    clip_clicked = Signal(str)  # clip_id
    clip_moved = Signal(str, float)  # clip_id, new_start
    clip_trimmed = Signal(str, float, float)  # clip_id, new_start, new_end
    
    def __init__(self, track: NLETrack, parent=None):
        super().__init__(parent)
        self.track = track
        self._clips_widgets = {}  # clip_id -> NLEClipWidget
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the container"""
        self.setMinimumHeight(50)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # Use absolute positioning for clips
        self.setStyleSheet("background-color: transparent;")
        
    def add_clip_widget(self, clip: NLEClip):
        """Add a clip widget to the container"""
        from nle.nle_clip import NLEClipWidget
        
        if clip.id in self._clips_widgets:
            return
            
        widget = NLEClipWidget(clip, self)
        widget.clicked.connect(self._on_clip_clicked)
        widget.moved.connect(self._on_clip_moved)
        widget.trimmed.connect(self._on_clip_trimmed)
        
        self._clips_widgets[clip.id] = widget
        widget.show()  # Make sure widget is visible
        self._update_clip_positions()
        
    def remove_clip_widget(self, clip_id: str):
        """Remove a clip widget"""
        if clip_id in self._clips_widgets:
            widget = self._clips_widgets.pop(clip_id)
            widget.deleteLater()
            
    def _on_clip_clicked(self, clip_id: str):
        """Handle clip click"""
        self.clip_clicked.emit(clip_id)
        
    def _on_clip_moved(self, clip_id: str, new_start: float):
        """Handle clip move"""
        self.clip_moved.emit(clip_id, new_start)
        
    def _on_clip_trimmed(self, clip_id: str, new_start: float, new_end: float):
        """Handle clip trim"""
        self.clip_trimmed.emit(clip_id, new_start, new_end)
        
    def _update_clip_positions(self):
        """Update all clip widget positions based on zoom and scroll"""
        # This will be called when zoom or scroll changes
        for clip_id, widget in self._clips_widgets.items():
            widget.update_position()
            
    def set_zoom(self, pixels_per_second: float):
        """Set zoom level for clip positioning"""
        for clip_id, widget in self._clips_widgets.items():
            widget.set_zoom(pixels_per_second)
            
    def set_scroll_offset(self, offset: float):
        """Set scroll offset for clip positioning"""
        for clip_id, widget in self._clips_widgets.items():
            widget.set_scroll_offset(offset)


class NLETrackWidget(QFrame):
    """
    Complete track row widget combining header and clip container.
    
    Layout: [TrackHeader] | [ClipContainer]
    """
    
    clip_clicked = Signal(str)  # clip_id
    clip_moved = Signal(str, float)  # clip_id, new_start
    clip_trimmed = Signal(str, float, float)  # clip_id, new_start, new_end
    track_clicked = Signal(str)  # track_id
    
    def __init__(self, track: NLETrack, parent=None):
        super().__init__(parent)
        self.track = track
        self._pixels_per_second = 20.0
        self._scroll_offset = 0.0
        
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """Setup the track row layout"""
        self.setStyleSheet("""
            NLETrackWidget {
                background-color: #1e1e1e;
                border: none;
                border-bottom: 1px solid #2a2a2a;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Track header
        self.header = TrackHeader(self.track, self)
        layout.addWidget(self.header)
        
        # Clip container
        self.clip_container = ClipContainer(self.track, self)
        layout.addWidget(self.clip_container, 1)
        
    def _connect_signals(self):
        """Connect internal signals"""
        self.header.clicked.connect(self._on_track_clicked)
        self.clip_container.clip_clicked.connect(self.clip_clicked)
        self.clip_container.clip_moved.connect(self.clip_moved)
        self.clip_container.clip_trimmed.connect(self.clip_trimmed)
        
    def _on_track_clicked(self, track_id: str):
        """Handle track header click"""
        self.track_clicked.emit(track_id)
        
    def add_clip(self, clip: NLEClip):
        """Add a clip to this track"""
        self.clip_container.add_clip_widget(clip)
        
    def remove_clip(self, clip_id: str):
        """Remove a clip from this track"""
        self.clip_container.remove_clip_widget(clip_id)
        
    def set_zoom(self, pixels_per_second: float):
        """Set zoom level"""
        self._pixels_per_second = pixels_per_second
        self.clip_container.set_zoom(pixels_per_second)
        
    def set_scroll_offset(self, offset: float):
        """Set scroll offset"""
        self._scroll_offset = offset
        self.clip_container.set_scroll_offset(offset)
        
    def update_from_track(self):
        """Update UI from track state"""
        self.header.update_from_track()
