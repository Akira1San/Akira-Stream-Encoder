"""
Geometry and Aspect Ratio Panel (PySide6)
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QSlider, QSpinBox, QGroupBox, QFrame, QComboBox, QPushButton
)
from PySide6.QtCore import Qt, Signal

from models import AppState


class GeometryPanel(QWidget):
    """Panel for geometry and aspect ratio settings"""
    
    settings_changed = Signal()
    extract_frames_requested = Signal(int, str)  # count, format
    
    def __init__(self, app_state: AppState, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # === Split Video Section ===
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        split_group = QGroupBox("Split Video")
        split_layout = QVBoxLayout(split_group)
        
        # Enable split
        self.split_check = QCheckBox("Split by Duration")
        self.split_check.setChecked(self.app_state.split.enabled)
        split_layout.addWidget(self.split_check)
        
        # Chunk length
        chunk_layout = QHBoxLayout()
        chunk_layout.addWidget(QLabel("Chunk Length (Minutes):"))
        
        self.chunk_spin = QSpinBox()
        self.chunk_spin.setRange(10, 120)
        self.chunk_spin.setValue(self.app_state.split.split_duration_min)
        self.chunk_spin.setSingleStep(10)
        self.chunk_spin.setEnabled(self.app_state.split.enabled)
        chunk_layout.addWidget(self.chunk_spin)
        
        chunk_layout.addStretch()
        split_layout.addLayout(chunk_layout)
        
        # Include subtitles
        self.split_subs_check = QCheckBox("Include Subtitles")
        self.split_subs_check.setChecked(self.app_state.split.split_subs)
        self.split_subs_check.setToolTip("Split subtitle file alongside video segments")
        self.split_subs_check.setEnabled(self.app_state.split.enabled)
        split_layout.addWidget(self.split_subs_check)
        
        layout.addWidget(split_group)
        
        # === Fast Split Section (for comparison) ===
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line2)
        
        fast_split_group = QGroupBox("Fast Split (for Comparison)")
        fast_split_layout = QVBoxLayout(fast_split_group)
        
        # Enable fast split
        self.fast_split_check = QCheckBox("Enable Single Split")
        self.fast_split_check.setChecked(self.app_state.split.fast_split_enabled)
        self.fast_split_check.setToolTip("Split video at a specific time point for quick comparison")
        fast_split_layout.addWidget(self.fast_split_check)
        
        # Split time selection
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Split at minute:"))
        
        self.fast_split_combo = QComboBox()
        self.fast_split_combo.addItems(["1 min", "2 min", "5 min", "10 min"])
        self.fast_split_combo.setCurrentIndex(2)  # Default to 5 min
        self.fast_split_combo.setEnabled(self.app_state.split.fast_split_enabled)
        time_layout.addWidget(self.fast_split_combo)
        
        time_layout.addStretch()
        fast_split_layout.addLayout(time_layout)
        
        layout.addWidget(fast_split_group)
        
        # === Extract Clip Section ===
        line3 = QFrame()
        line3.setFrameShape(QFrame.HLine)
        line3.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line3)
        
        extract_group = QGroupBox("Extract Clip (Cut Segment)")
        extract_layout = QVBoxLayout(extract_group)
        
        # Enable extract
        self.extract_check = QCheckBox("Enable Clip Extraction")
        self.extract_check.setChecked(self.app_state.split.extract_clip_enabled)
        self.extract_check.setToolTip("Extract a specific segment from the video")
        extract_layout.addWidget(self.extract_check)
        
        # Start time
        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("Start at minute:"))
        
        self.extract_start_spin = QSpinBox()
        self.extract_start_spin.setRange(0, 300)  # Up to 5 hours
        self.extract_start_spin.setValue(self.app_state.split.extract_start_min)
        self.extract_start_spin.setSuffix(" min")
        self.extract_start_spin.setEnabled(self.app_state.split.extract_clip_enabled)
        start_layout.addWidget(self.extract_start_spin)
        
        start_layout.addStretch()
        extract_layout.addLayout(start_layout)
        
        # Duration
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel("Duration:"))
        
        self.extract_duration_spin = QSpinBox()
        self.extract_duration_spin.setRange(1, 60)  # 1 to 60 minutes
        self.extract_duration_spin.setValue(self.app_state.split.extract_duration_min)
        self.extract_duration_spin.setSuffix(" min")
        self.extract_duration_spin.setEnabled(self.app_state.split.extract_clip_enabled)
        duration_layout.addWidget(self.extract_duration_spin)
        
        duration_layout.addStretch()
        extract_layout.addLayout(duration_layout)
        
        # Example label
        self.extract_example_label = QLabel("Example: Start at 20 min, duration 1 min = 20:00 to 21:00")
        self.extract_example_label.setStyleSheet("color: #888; font-size: 10px;")
        extract_layout.addWidget(self.extract_example_label)
        
        layout.addWidget(extract_group)
        
        # === Frame Extraction Section ===
        line4 = QFrame()
        line4.setFrameShape(QFrame.HLine)
        line4.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line4)
        
        frame_group = QGroupBox("Frame Extraction")
        frame_layout = QVBoxLayout(frame_group)
        
        # Number of frames
        count_layout = QHBoxLayout()
        count_layout.addWidget(QLabel("Frames to capture:"))
        
        self.frame_count_spin = QSpinBox()
        self.frame_count_spin.setRange(1, 100)
        self.frame_count_spin.setValue(self.app_state.frame_extraction.count)
        self.frame_count_spin.setToolTip("Number of consecutive frames to extract from the timeline position")
        count_layout.addWidget(self.frame_count_spin)
        
        count_layout.addStretch()
        frame_layout.addLayout(count_layout)
        
        # Output format
        fmt_layout = QHBoxLayout()
        fmt_layout.addWidget(QLabel("Output format:"))
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPEG"])
        self.format_combo.setCurrentText(self.app_state.frame_extraction.output_format.upper())
        fmt_layout.addWidget(self.format_combo)
        
        fmt_layout.addStretch()
        frame_layout.addLayout(fmt_layout)
        
        # Extract button
        self.extract_frames_btn = QPushButton("📷 Extract Frames")
        self.extract_frames_btn.setToolTip("Extract frames starting from the current timeline position")
        frame_layout.addWidget(self.extract_frames_btn)
        
        layout.addWidget(frame_group)
        
        layout.addStretch()
        
    def connect_signals(self):
        """Connect UI signals to handlers"""
        self.split_check.toggled.connect(self.on_split_toggled)
        self.chunk_spin.valueChanged.connect(self.on_chunk_changed)
        self.split_subs_check.toggled.connect(self.on_split_subs_toggled)
        self.fast_split_check.toggled.connect(self.on_fast_split_toggled)
        self.fast_split_combo.currentIndexChanged.connect(self.on_fast_split_time_changed)
        self.extract_check.toggled.connect(self.on_extract_toggled)
        self.extract_start_spin.valueChanged.connect(self.on_extract_start_changed)
        self.extract_duration_spin.valueChanged.connect(self.on_extract_duration_changed)
        self.frame_count_spin.valueChanged.connect(self.on_frame_count_changed)
        self.format_combo.currentTextChanged.connect(self.on_format_changed)
        self.extract_frames_btn.clicked.connect(self.on_extract_frames_clicked)
        
    def on_split_toggled(self, checked):
        """Handle split checkbox toggle"""
        self.app_state.split.enabled = checked
        self.chunk_spin.setEnabled(checked)
        self.split_subs_check.setEnabled(checked)
        self.settings_changed.emit()
        
    def on_chunk_changed(self, value):
        """Handle chunk length change"""
        self.app_state.split.split_duration_min = value
        self.settings_changed.emit()
        
    def on_split_subs_toggled(self, checked):
        """Handle split subtitles toggle"""
        self.app_state.split.split_subs = checked
        self.settings_changed.emit()
        
    def on_fast_split_toggled(self, checked):
        """Handle fast split checkbox toggle"""
        self.app_state.split.fast_split_enabled = checked
        self.fast_split_combo.setEnabled(checked)
        self.settings_changed.emit()
        
    def on_fast_split_time_changed(self, index):
        """Handle fast split time selection change"""
        time_values = [1, 2, 5, 10]
        self.app_state.split.fast_split_minutes = time_values[index]
        self.settings_changed.emit()
        
    def on_extract_toggled(self, checked):
        """Handle extract clip checkbox toggle"""
        self.app_state.split.extract_clip_enabled = checked
        self.extract_start_spin.setEnabled(checked)
        self.extract_duration_spin.setEnabled(checked)
        self.settings_changed.emit()
        
    def on_extract_start_changed(self, value):
        """Handle extract start time change"""
        self.app_state.split.extract_start_min = value
        # Update example label
        duration = self.app_state.split.extract_duration_min
        self.extract_example_label.setText(
            f"Example: Start at {value} min, duration {duration} min = "
            f"{value}:00 to {value + duration}:00"
        )
        self.settings_changed.emit()
        
    def on_extract_duration_changed(self, value):
        """Handle extract duration change"""
        self.app_state.split.extract_duration_min = value
        # Update example label
        start = self.app_state.split.extract_start_min
        self.extract_example_label.setText(
            f"Example: Start at {start} min, duration {value} min = "
            f"{start}:00 to {start + value}:00"
        )
        self.settings_changed.emit()

    def on_frame_count_changed(self, value):
        """Handle frame count change"""
        self.app_state.frame_extraction.count = value

    def on_format_changed(self, text):
        """Handle format combo change"""
        fmt = text.lower()
        self.app_state.frame_extraction.output_format = fmt

    def on_extract_frames_clicked(self):
        """Emit signal for video workspace to handle extraction"""
        count = self.frame_count_spin.value()
        fmt = self.format_combo.currentText().lower()
        self.extract_frames_requested.emit(count, fmt)
