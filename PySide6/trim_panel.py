"""
Trim/Cut Panel (PySide6)
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QMessageBox
)
from PySide6.QtCore import Signal

from models import AppState
from tracks_panel import TrackSelectionPanel


class TrimPanel(QGroupBox):
    """Panel for trim/cut operations"""
    
    cut_point_set = Signal(float)
    execute_cut = Signal()
    
    def __init__(self, app_state: AppState, get_timeline_position_callback=None, parent=None):
        super().__init__("Trim/Cut Video", parent)
        self.app_state = app_state
        self.get_timeline_position = get_timeline_position_callback
        
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)
        
        # Track Selection Panel
        self.tracks_panel = TrackSelectionPanel(self.app_state)
        self.tracks_panel.tracks_changed.connect(self.on_tracks_changed)
        layout.addWidget(self.tracks_panel)
        
        # Cut Point Status
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Status:"))
        
        self.status_label = QLabel("Not Set")
        self.status_label.setStyleSheet("color: gray;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.set_cut_btn = QPushButton("📍 Set Cut Point (Current Timeline Position)")
        self.set_cut_btn.clicked.connect(self.on_set_cut_clicked)
        btn_layout.addWidget(self.set_cut_btn)
        
        self.execute_btn = QPushButton("✂️ Execute Cut")
        self.execute_btn.setEnabled(False)
        self.execute_btn.clicked.connect(self.on_execute_clicked)
        btn_layout.addWidget(self.execute_btn)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
        
    def connect_signals(self):
        """Connect UI signals"""
        pass
        
    def on_tracks_changed(self):
        """Handle track selection changes"""
        pass
        
    def on_set_cut_clicked(self):
        """Handle set cut point button click"""
        # Get current timeline position from callback
        if self.get_timeline_position:
            position = self.get_timeline_position()
            if position is not None:
                self.cut_point_set.emit(position)
        else:
            # Fallback to app_state if no callback provided
            position = self.app_state.cut.position
            self.cut_point_set.emit(position)
        
    def on_execute_clicked(self):
        """Handle execute cut button click"""
        if not self.app_state.cut.point_set:
            QMessageBox.warning(self, "No Cut Point", "Please set a cut point first.")
            return
        self.execute_cut.emit()
        
    def update_cut_status(self, time_str: str, valid: bool = True):
        """Update the cut status display"""
        if valid:
            self.status_label.setText(f"Cut at {time_str}")
            self.status_label.setStyleSheet("color: green;")
            self.execute_btn.setEnabled(True)
        else:
            self.status_label.setText(time_str)
            self.status_label.setStyleSheet("color: red;")
            self.execute_btn.setEnabled(False)
            
    def reset_cut_status(self):
        """Reset cut status to default"""
        self.status_label.setText("Not Set")
        self.status_label.setStyleSheet("color: gray;")
        self.execute_btn.setEnabled(False)
        self.app_state.cut.point_set = False
        
    def detect_tracks(self, video_path: str):
        """Detect tracks for the current video"""
        self.tracks_panel.detect_tracks(video_path)
