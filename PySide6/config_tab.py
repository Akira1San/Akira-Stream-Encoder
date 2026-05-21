"""
Configuration Tab - System Paths and Input File Management (PySide6)
"""
import os
import re
import subprocess
import threading
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QFileDialog,
    QGroupBox, QCheckBox, QMessageBox, QAbstractItemView,
    QDialog, QDialogButtonBox, QScrollArea, QFrame, QComboBox,
    QSpinBox, QGridLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from models import AppState


class DragDropListWidget(QListWidget):
    """List widget that accepts file drops"""
    
    files_dropped = Signal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setAlternatingRowColors(True)
        
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            
    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            
    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            files = []
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if os.path.isfile(file_path):
                    # Check if it's a video file
                    ext = Path(file_path).suffix.lower()
                    if ext in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg']:
                        files.append(file_path)
                        
            if files:
                self.files_dropped.emit(files)
            event.acceptProposedAction()


class CleanNamesDialog(QDialog):
    """Dialog for previewing and applying filename cleaning"""
    
    def __init__(self, files, parent=None):
        super().__init__(parent)
        self.files = files
        self.cleaned = []
        self.applied = False
        
        self.setWindowTitle("Clean Filenames - Preview")
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("<b>Before -> After</b>"))
        
        # List widget showing changes
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        layout.addWidget(self.list_widget)
        
        # Generate cleaned names
        for f in files:
            base = os.path.basename(f)
            cleaned_base = self._clean_filename(base)
            self.cleaned.append((f, cleaned_base))
            self.list_widget.addItem(f"{base} -> {cleaned_base}")
        
        # Buttons
        btn_box = QDialogButtonBox()
        self.apply_btn = btn_box.addButton("Apply", QDialogButtonBox.AcceptRole)
        btn_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)
        
    def _clean_filename(self, filename):
        """Clean a filename by removing clutter and normalizing spaces."""
        base, ext = os.path.splitext(filename)
        # Preserve year (4 digits)
        year_match = re.search(r'\b(19|20)\d{2}\b', base)
        year = year_match.group(0) if year_match else None

        # Remove all dots (except the one before the file extension)
        base = base.replace('.', ' ')
        # Remove all underscores
        base = base.replace('_', ' ')
        # Remove all special characters
        base = re.sub(r'[\-_&]', ' ', base)
        # Normalize spaces
        base = re.sub(r'\s+', ' ', base).strip()

        # Remove common clutter patterns
        patterns = [
            r'\bBDRip\b', r'\bx265\b', r'\bx264\b', r'\bAC3\b', r'\bAAC\b',
            r'\bbgaudio\b', r'\bDUAL\b', r'\bAUDiO\b', r'\bBluRay\b', r'\bDVDRip\b',
            r'\bH\b', r'\b265\b', r'\bWAR\b', r'\bSiSO\b', r'\bfmp4\b', r'\btv\b',
            r'\bgpu\b', r'\bpart01\b', r'\bjoined\b', r'\bencoded\b', r'\bmucker\b',
            r'\bAtany\b', r'\bStezarai\b', r'\bBG\b', r'\bAudio\b', r'\bBGAUDiO\b',
            r'\b10\b', r'\bbit\b', r'\b1080p\b', r'\b720x404\b',
            r'\b576p\b', r'\bWEBRip\b', r'\bHUD\b', r'\bAtany Stezarai\b', r'\bVHS\b',
            r'\b720p\b', r'\bBluRay\b', r'\bAC3\b', r'\bAVS\b', r'\bDD5\.1\b'
        ]
        for pat in patterns:
            base = re.sub(pat, '', base, flags=re.IGNORECASE)

        # Reinsert year if found
        if year:
            base = re.sub(r'\b(19|20)\d{2}\b', year, base)

        # Remove any remaining numbers that are not part of the year
        base = re.sub(r'\b\d{1,3}\b', '', base)

        # Remove any remaining words that are not part of the title
        base = re.sub(r'\b\w{1,2}\b', '', base)

        # Remove any remaining extra spaces
        base = re.sub(r'\s+', ' ', base).strip()

        return f"{base}{ext}"


class DVDTitleDialog(QDialog):
    """Dialog for selecting DVD title to import"""
    
    def __init__(self, titles, dvd_folder, parent=None):
        super().__init__(parent)
        self.titles = titles
        self.dvd_folder = dvd_folder
        self.selected_title = None
        
        self.setWindowTitle("Select DVD Title")
        self.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # Info label
        layout.addWidget(QLabel(f"<b>DVD Folder:</b> {dvd_folder}"))
        layout.addWidget(QLabel(f"<b>Titles Found:</b> {len(titles)}"))
        layout.addWidget(QLabel(""))
        
        # Title list
        layout.addWidget(QLabel("<b>Select a title to import:</b>"))
        
        self.title_list = QListWidget()
        self.title_list.setAlternatingRowColors(True)
        self.title_list.itemDoubleClicked.connect(self.accept)
        
        for title in titles:
            main_marker = " [MAIN]" if title.is_main else ""
            item_text = f"Title {title.title_number}{main_marker} - {title.duration_display} ({title.size_display})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, title)
            if title.is_main:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.title_list.addItem(item)
        
        # Select main title by default
        for i in range(self.title_list.count()):
            item = self.title_list.item(i)
            title = item.data(Qt.UserRole)
            if title.is_main:
                self.title_list.setCurrentItem(item)
                break
        
        layout.addWidget(self.title_list)
        
        # Track info
        self.track_info_label = QLabel("")
        self.track_info_label.setStyleSheet("color: gray; font-size: 9pt;")
        self.track_info_label.setWordWrap(True)
        layout.addWidget(self.track_info_label)
        
        self.title_list.currentItemChanged.connect(self.on_title_changed)
        
        # Update info for initial selection
        if self.title_list.currentItem():
            self.on_title_changed(self.title_list.currentItem())
        
        # Buttons
        btn_box = QDialogButtonBox()
        btn_box.addButton("Import Title", QDialogButtonBox.AcceptRole)
        btn_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)
    
    def on_title_changed(self, current):
        """Update track info when selection changes"""
        if current:
            title = current.data(Qt.UserRole)
            
            info_parts = []
            
            # Audio info
            if title.audio_tracks:
                audio_info = [f"{t['codec'].upper()} {t['channels']}ch" for t in title.audio_tracks[:3]]
                if len(title.audio_tracks) > 3:
                    audio_info.append(f"+{len(title.audio_tracks) - 3} more")
                info_parts.append(f"Audio: {', '.join(audio_info)}")
            else:
                info_parts.append("Audio: No track info")
            
            # Subtitle info
            if title.subtitles:
                sub_langs = [sub.get('language', '?') for sub in title.subtitles]
                info_parts.append(f"Subtitles: {len(title.subtitles)} track(s) - {', '.join(sub_langs[:5])}")
            else:
                info_parts.append("Subtitles: None detected")
            
            self.track_info_label.setText(" | ".join(info_parts))
    
    def get_selected_title(self):
        """Return the selected DVDTitle object"""
        current = self.title_list.currentItem()
        if current:
            return current.data(Qt.UserRole)
        return None


class TrackSelectionDialog(QDialog):
    """Dialog for selecting a video or audio track to extract"""
    
    def __init__(self, video_tracks, audio_tracks, parent=None):
        super().__init__(parent)
        self.video_tracks = video_tracks
        self.audio_tracks = audio_tracks
        self.selected_track = None  # {'type': 'video'|'audio', 'index': int, 'info': str}
        
        self.setWindowTitle("Select Track to Extract")
        self.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # Video tracks section
        if video_tracks:
            layout.addWidget(QLabel("<b>Video Tracks:</b>"))
            self.video_list = QListWidget()
            self.video_list.setAlternatingRowColors(True)
            self.video_list.setSelectionMode(QAbstractItemView.SingleSelection)
            
            for track in video_tracks:
                item_text = f"Track {track['index']}: {track['codec']} {track.get('resolution', '')}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, {'type': 'video', 'index': track['index'], 'video_index': track['video_index'], 'info': item_text})
                self.video_list.addItem(item)
            
            layout.addWidget(self.video_list)
        else:
            layout.addWidget(QLabel("<b>Video Tracks:</b> None found"))
            self.video_list = None
        
        layout.addSpacing(10)
        
        # Audio tracks section
        if audio_tracks:
            layout.addWidget(QLabel("<b>Audio Tracks:</b>"))
            self.audio_list = QListWidget()
            self.audio_list.setAlternatingRowColors(True)
            self.audio_list.setSelectionMode(QAbstractItemView.SingleSelection)
            
            for track in audio_tracks:
                lang = track.get('language', 'unknown')
                item_text = f"Track {track['index']}: {track['codec']} - {track['channels']}ch ({lang})"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, {'type': 'audio', 'index': track['index'], 'audio_index': track['audio_index'], 'info': item_text})
                self.audio_list.addItem(item)
            
            layout.addWidget(self.audio_list)
        else:
            layout.addWidget(QLabel("<b>Audio Tracks:</b> None found"))
            self.audio_list = None
        
        layout.addSpacing(10)
        
        # Buttons
        btn_box = QDialogButtonBox()
        self.extract_btn = btn_box.addButton("Extract", QDialogButtonBox.AcceptRole)
        self.extract_btn.setEnabled(False)
        btn_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)
        
        # Connect selection signals
        if self.video_list:
            self.video_list.itemSelectionChanged.connect(self._on_selection_changed)
        if self.audio_list:
            self.audio_list.itemSelectionChanged.connect(self._on_selection_changed)
    
    def _on_selection_changed(self):
        """Handle selection change"""
        self.selected_track = None
        
        if self.video_list and self.video_list.selectedItems():
            item = self.video_list.selectedItems()[0]
            self.selected_track = item.data(Qt.UserRole)
            if self.audio_list:
                self.audio_list.clearSelection()
        elif self.audio_list and self.audio_list.selectedItems():
            item = self.audio_list.selectedItems()[0]
            self.selected_track = item.data(Qt.UserRole)
            if self.video_list:
                self.video_list.clearSelection()
        
        self.extract_btn.setEnabled(self.selected_track is not None)
    
    def get_selected_track(self):
        """Return the selected track info"""
        return self.selected_track


class ConfigTab(QWidget):
    """Configuration tab for system paths and file management"""
    
    file_selected = Signal(str)  # Emitted when a file is selected
    dvd_imported = Signal()  # Emitted when a DVD is imported
    
    def __init__(self, app_state: AppState, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # === System Paths Group ===
        paths_group = QGroupBox("System Paths")
        paths_layout = QVBoxLayout(paths_group)

        # Media Engine Selection
        engine_group = QGroupBox("Media Engine")
        engine_layout = QVBoxLayout(engine_group)

        engine_selector = QHBoxLayout()
        engine_selector.addWidget(QLabel("Engine:"))
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["FFmpeg", "GStreamer"])
        self.engine_combo.setCurrentText("FFmpeg" if self.app_state.media_engine == "ffmpeg" else "GStreamer")
        engine_selector.addWidget(self.engine_combo)

        self.engine_status_label = QLabel("")
        engine_selector.addWidget(self.engine_status_label)
        engine_selector.addStretch()
        engine_layout.addLayout(engine_selector)

        # Engine-specific path
        engine_path_layout = QHBoxLayout()
        self.engine_path_label = QLabel("FFmpeg Path:")
        engine_path_layout.addWidget(self.engine_path_label)

        self.engine_path_edit = QLineEdit(self.app_state.ffmpeg_path)
        engine_path_layout.addWidget(self.engine_path_edit)

        self.engine_browse_btn = QPushButton("Browse...")
        self.engine_browse_btn.clicked.connect(self._browse_engine_path)
        engine_path_layout.addWidget(self.engine_browse_btn)

        self.engine_auto_btn = QPushButton("Auto Detect")
        self.engine_auto_btn.clicked.connect(self._auto_detect_engine)
        engine_path_layout.addWidget(self.engine_auto_btn)

        self.engine_version_btn = QPushButton("Check Version")
        self.engine_version_btn.clicked.connect(self._check_engine_version)
        engine_path_layout.addWidget(self.engine_version_btn)

        engine_layout.addLayout(engine_path_layout)
        paths_layout.addWidget(engine_group)

        # FFmpeg Path
        ffmpeg_layout = QHBoxLayout()
        ffmpeg_layout.addWidget(QLabel("FFprobe Path:"))
        self.ffprobe_edit = QLineEdit(self.app_state.ffprobe_path)
        ffmpeg_layout.addWidget(self.ffprobe_edit)
        browse_ffprobe_btn = QPushButton("Browse...")
        browse_ffprobe_btn.clicked.connect(self.browse_ffprobe)
        ffmpeg_layout.addWidget(browse_ffprobe_btn)
        paths_layout.addLayout(ffmpeg_layout)

        # HandBrake Path
        hb_layout = QHBoxLayout()
        hb_layout.addWidget(QLabel("HandBrake Path:"))
        self.handbrake_edit = QLineEdit(self.app_state.handbrake_path)
        hb_layout.addWidget(self.handbrake_edit)
        browse_hb_btn = QPushButton("Browse...")
        browse_hb_btn.clicked.connect(self.browse_handbrake)
        hb_layout.addWidget(browse_hb_btn)
        auto_hb_btn = QPushButton("Auto Detect")
        auto_hb_btn.clicked.connect(self.auto_detect_handbrake)
        hb_layout.addWidget(auto_hb_btn)
        self.hb_status_label = QLabel("")
        hb_layout.addWidget(self.hb_status_label)
        paths_layout.addLayout(hb_layout)

        layout.addWidget(paths_group)
        
        # === Output Settings Group ===
        output_group = QGroupBox("Output Settings")
        output_layout = QVBoxLayout(output_group)
        
        # Output Folder
        folder_layout = QHBoxLayout()
        folder_layout.addWidget(QLabel("Output Folder:"))
        
        self.output_edit = QLineEdit(self.app_state.output_folder)
        folder_layout.addWidget(self.output_edit)
        
        browse_output_btn = QPushButton("Browse...")
        browse_output_btn.clicked.connect(self.browse_output_folder)
        folder_layout.addWidget(browse_output_btn)
        
        output_layout.addLayout(folder_layout)
        
        # Custom Filename
        custom_layout = QHBoxLayout()
        
        self.custom_name_check = QCheckBox("Use Custom Filename:")
        self.custom_name_check.setChecked(self.app_state.use_custom_filename)
        custom_layout.addWidget(self.custom_name_check)
        
        self.custom_name_edit = QLineEdit(self.app_state.custom_filename)
        self.custom_name_edit.setEnabled(self.app_state.use_custom_filename)
        custom_layout.addWidget(self.custom_name_edit)
        
        output_layout.addLayout(custom_layout)
        
        layout.addWidget(output_group)
        
        # === Input Files Group ===
        files_group = QGroupBox("Input Files Queue")
        files_layout = QVBoxLayout(files_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        # Left side: Action buttons
        self.details_btn = QPushButton("📋 Show Details")
        self.details_btn.clicked.connect(self.show_file_details)
        btn_layout.addWidget(self.details_btn)
        
        self.validate_btn = QPushButton("✓ Validate Video")
        self.validate_btn.clicked.connect(self.validate_video_file)
        btn_layout.addWidget(self.validate_btn)
        
        btn_layout.addStretch()
        
        # Right side: File management buttons
        self.join_btn = QPushButton("🔗 Join")
        self.join_btn.clicked.connect(self.join_files)
        btn_layout.addWidget(self.join_btn)
        
        self.clean_btn = QPushButton("🧹 Clean Names")
        self.clean_btn.clicked.connect(self.clean_filenames)
        btn_layout.addWidget(self.clean_btn)
        
        btn_layout.addSpacing(20)
        
        add_files_btn = QPushButton("➕ Add Files")
        add_files_btn.clicked.connect(self.add_files)
        btn_layout.addWidget(add_files_btn)
        
        add_folder_btn = QPushButton("📁 Add Folder")
        add_folder_btn.clicked.connect(self.add_folder)
        btn_layout.addWidget(add_folder_btn)
        
        add_dvd_btn = QPushButton("📀 Open DVD")
        add_dvd_btn.clicked.connect(self.add_dvd_folder)
        btn_layout.addWidget(add_dvd_btn)
        
        extract_subs_btn = QPushButton("📝 Extract Subs")
        extract_subs_btn.setToolTip("Extract all subtitles from video or DVD folder")
        extract_subs_btn.clicked.connect(self.extract_subtitles)
        btn_layout.addWidget(extract_subs_btn)
        
        extract_track_btn = QPushButton("📦 Extract Track")
        extract_track_btn.setToolTip("Extract video or audio track from video file")
        extract_track_btn.clicked.connect(self.extract_track)
        btn_layout.addWidget(extract_track_btn)
        
        clear_btn = QPushButton("🗑️ Clear All")
        clear_btn.clicked.connect(self.clear_files)
        btn_layout.addWidget(clear_btn)
        
        files_layout.addLayout(btn_layout)
        
        # File list with drag-drop support
        self.files_list = DragDropListWidget()
        self.files_list.setMinimumHeight(200)
        self.files_list.files_dropped.connect(self.on_files_dropped)
        self.files_list.itemSelectionChanged.connect(self.on_selection_changed)
        files_layout.addWidget(self.files_list)
        
        # Info label for showing file details
        self.info_label = QLabel("Select a file and click 'Show Details'...")
        self.info_label.setStyleSheet("color: blue; font-size: 9pt;")
        files_layout.addWidget(self.info_label)
        
        # File count label
        self.count_label = QLabel("0 files selected")
        files_layout.addWidget(self.count_label)
        
        layout.addWidget(files_group)
        
        # Add stretch at the bottom
        layout.addStretch()
        
    def connect_signals(self):
        """Connect UI signals to handlers"""
        self.engine_combo.currentTextChanged.connect(self.on_engine_changed)
        self.engine_path_edit.textChanged.connect(self.on_engine_path_changed)
        self.ffprobe_edit.textChanged.connect(self.on_ffprobe_changed)
        self.output_edit.textChanged.connect(self.on_output_changed)
        self.custom_name_check.toggled.connect(self.on_custom_name_toggled)
        self.custom_name_edit.textChanged.connect(self.on_custom_name_changed)
        self.handbrake_edit.textChanged.connect(self.on_handbrake_changed)
        self.app_state.handbrake_available_changed.connect(self.on_handbrake_available_changed)
        
    def on_engine_changed(self, text):
        engine = "gstreamer" if text == "GStreamer" else "ffmpeg"
        self.app_state.media_engine = engine
        is_gst = engine == "gstreamer"
        self.engine_path_label.setText("GStreamer Path:" if is_gst else "FFmpeg Path:")
        self.engine_path_edit.setText(
            self.app_state.gstreamer_path if is_gst else self.app_state.ffmpeg_path
        )

    def on_engine_path_changed(self, text):
        if self.engine_combo.currentText() == "GStreamer":
            self.app_state.gstreamer_path = text
        else:
            self.app_state.ffmpeg_path = text

    def _browse_engine_path(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Executable", "",
            "Executables (*);;All Files (*)"
        )
        if file_path:
            self.engine_path_edit.setText(file_path)

    def _auto_detect_engine(self):
        import shutil
        if self.engine_combo.currentText() == "GStreamer":
            path = shutil.which("gst-launch-1.0")
            if path:
                self.engine_path_edit.setText(path)
                self.app_state.log(f"Auto-detected GStreamer: {path}", "INFO")
            else:
                QMessageBox.warning(self, "Not Found", "gst-launch-1.0 not found on PATH.")
        else:
            path = shutil.which("ffmpeg")
            if path:
                self.engine_path_edit.setText(path)
            else:
                QMessageBox.warning(self, "Not Found", "ffmpeg not found on PATH.")

    def _check_engine_version(self):
        path = self.engine_path_edit.text()
        if not path:
            QMessageBox.warning(self, "No Path", "Please set the executable path first.")
            return
        try:
            result = subprocess.run([path, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            output = result.stdout.strip() or result.stderr.strip()
            self.app_state.log(f"Version: {output[:200]}", "INFO")
            QMessageBox.information(self, "Version Info", output[:500])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to check version: {e}")

    def on_ffmpeg_changed(self, text):
        """Handle FFmpeg path change"""
        self.app_state.ffmpeg_path = text
        
    def on_ffprobe_changed(self, text):
        """Handle FFprobe path change"""
        self.app_state.ffprobe_path = text
        
    def on_output_changed(self, text):
        """Handle output folder change"""
        self.app_state.output_folder = text
        
    def on_custom_name_toggled(self, checked):
        """Handle custom filename checkbox"""
        self.app_state.use_custom_filename = checked
        self.custom_name_edit.setEnabled(checked)
        
    def on_custom_name_changed(self, text):
        """Handle custom filename change"""
        self.app_state.custom_filename = text
        
    def browse_ffmpeg(self):
        """Browse for FFmpeg executable"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select FFmpeg Executable", "",
            "Executables (*.exe);;All Files (*)"
        )
        if file_path:
            self.ffmpeg_edit.setText(file_path)
            
    def browse_ffprobe(self):
        """Browse for FFprobe executable"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select FFprobe Executable", "",
            "Executables (*.exe);;All Files (*)"
        )
        if file_path:
            self.ffprobe_edit.setText(file_path)
            
    def auto_detect_ffmpeg(self):
        """Auto-detect FFmpeg in common locations"""
        import shutil
        
        # Check PATH first
        ffmpeg_path = shutil.which("ffmpeg")
        ffprobe_path = shutil.which("ffprobe")
        
        if ffmpeg_path:
            self.ffmpeg_edit.setText(ffmpeg_path)
        if ffprobe_path:
            self.ffprobe_edit.setText(ffprobe_path)
            
        # Check common Windows locations
        if os.name == 'nt':
            common_paths = [
                r"C:\ffmpeg\bin\ffmpeg.exe",
                r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
                r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
            ]
            for path in common_paths:
                if os.path.exists(path):
                    self.ffmpeg_edit.setText(path)
                    # Try to find ffprobe in same directory
                    ffprobe = os.path.join(os.path.dirname(path), "ffprobe.exe")
                    if os.path.exists(ffprobe):
                        self.ffprobe_edit.setText(ffprobe)
                    break
                    
        if not ffmpeg_path and not self.ffmpeg_edit.text():
            QMessageBox.warning(self, "Not Found", "Could not auto-detect FFmpeg. Please browse manually.")
            
    def browse_handbrake(self):
        """Browse for HandBrakeCLI executable"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select HandBrakeCLI Executable", "",
            "Executables (*);;All Files (*)"
        )
        if file_path:
            self.handbrake_edit.setText(file_path)
            
    def auto_detect_handbrake(self):
        """Auto-detect HandBrakeCLI in common locations"""
        import shutil
        path = shutil.which("HandBrakeCLI")
        if path:
            self.handbrake_edit.setText(path)
        else:
            QMessageBox.warning(self, "Not Found", "HandBrakeCLI not found on PATH.")
            
    def on_handbrake_changed(self, text):
        """Handle HandBrake path change"""
        self.app_state.handbrake_path = text
        
    def on_handbrake_available_changed(self, available):
        """Update HandBrake status label"""
        if available:
            self.hb_status_label.setText("✓ Available")
            self.hb_status_label.setStyleSheet("color: green; font-size: 10px;")
        else:
            self.hb_status_label.setText("✗ Not Found")
            self.hb_status_label.setStyleSheet("color: red; font-size: 10px;")
            
    def browse_output_folder(self):
        """Browse for output folder"""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Output Folder", self.app_state.output_folder or ""
        )
        if folder:
            self.output_edit.setText(folder)
            
    def add_files(self):
        """Add video files to the queue"""
        import config
        last_folder = config.load_last_folder()
        
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Video Files", last_folder,
            "Video Files (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.mpg *.mpeg *.vob);;All Files (*)"
        )
        if files:
            # Remember the folder of the first file
            first_file_dir = os.path.dirname(files[0])
            config.save_last_folder(first_file_dir)
            
            self.add_files_to_list(files)
            
    def add_folder(self):
        """Add all video files from a folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.vob'}
            files = []
            for f in os.listdir(folder):
                if Path(f).suffix.lower() in video_extensions:
                    files.append(os.path.join(folder, f))
            if files:
                self.add_files_to_list(files)
                
    def add_dvd_folder(self):
        """Open a DVD folder (VIDEO_TS) and select title to import"""
        from dvd_handler import DVDHandler
        
        folder = QFileDialog.getExistingDirectory(self, "Select DVD Folder (VIDEO_TS parent folder)")
        if not folder:
            return
            
        # Initialize DVD handler
        handler = DVDHandler(
            self.app_state.ffmpeg_path,
            self.app_state.ffprobe_path,
            self.app_state.log
        )
        
        # Check if it's a valid DVD folder
        video_ts_path = handler.find_video_ts_folder(folder)
        if not video_ts_path:
            QMessageBox.warning(
                self, "Invalid DVD Folder",
                f"No VIDEO_TS folder found in:\n{folder}\n\nPlease select a DVD-Video folder containing VIDEO_TS directory."
            )
            return
        
        # Scan for titles
        self.app_state.log(f"Scanning DVD: {video_ts_path}", "INFO")
        titles = handler.get_dvd_titles(video_ts_path)
        
        if not titles:
            QMessageBox.warning(
                self, "No Titles Found",
                "No DVD titles found in the selected folder."
            )
            return
        
        # Show title selection dialog
        dialog = DVDTitleDialog(titles, video_ts_path, self)
        if dialog.exec() == QDialog.Accepted:
            selected_title = dialog.get_selected_title()
            if selected_title:
                self._import_dvd_title(handler, selected_title, video_ts_path)
    
    def _import_dvd_title(self, handler, title, video_ts_path):
        """Import a DVD title into the encoding queue"""
        import tempfile
        import os
        
        # Create concat file for the selected title
        concat_file = handler.create_concat_file(title.vob_files)
        
        # Store DVD info in app state
        self.app_state.dvd.is_dvd_source = True
        self.app_state.dvd.dvd_folder_path = video_ts_path
        self.app_state.dvd.available_titles = handler.get_dvd_titles(video_ts_path)
        self.app_state.dvd.selected_title_number = title.title_number
        self.app_state.dvd.concat_file_path = concat_file
        self.app_state.dvd.selected_subtitle_index = -1  # Reset - will be set in subtitles panel
        self.app_state.dvd.subtitle_tracks = title.subtitles  # Store for subtitles panel
        self.app_state.dvd.extracted_subtitle_path = ""  # Reset (not used for DVD subtitles)
        
        # Add to file list as a special DVD entry
        # Clear existing files first (DVD replaces queue)
        self.clear_files()
        
        # Add the concat file as the input
        # We use a special display name for DVD sources
        display_name = f"[DVD] Title {title.title_number} - {title.duration_display}"
        
        item = QListWidgetItem(display_name)
        item.setData(Qt.UserRole, concat_file)  # Actual path is concat file
        item.setData(Qt.UserRole + 1, "dvd")  # Mark as DVD source
        
        # Build tooltip with track info
        tooltip = f"DVD Title {title.title_number}\nDuration: {title.duration_display}\nSize: {title.size_display}\nSource: {video_ts_path}"
        if title.subtitles:
            tooltip += f"\nSubtitles: {len(title.subtitles)} track(s) available"
        item.setToolTip(tooltip)
        
        # Set a special icon/color for DVD entries
        item.setForeground(Qt.darkMagenta)
        
        self.files_list.addItem(item)
        self.app_state.add_input_file(concat_file)
        
        # Update the current video path
        self.app_state.current_video_path = concat_file
        
        self.update_count_label()
        
        sub_info = f", {len(title.subtitles)} subtitle tracks" if title.subtitles else ""
        self.app_state.log(
            f"Imported DVD Title {title.title_number}: {title.duration_display}, {len(title.vob_files)} VOB files{sub_info}",
            "SUCCESS"
        )
        
        # Emit signals
        self.file_selected.emit(concat_file)
        self.dvd_imported.emit()  # Notify subtitles panel to update DVD subtitle selector
                
    def add_files_to_list(self, files):
        """Add files to the list widget and app state"""
        for file_path in files:
            if file_path not in self.app_state.input_files:
                self.app_state.add_input_file(file_path)
                item = QListWidgetItem(os.path.basename(file_path))
                item.setData(Qt.UserRole, file_path)
                item.setToolTip(file_path)
                self.files_list.addItem(item)
                
        self.update_count_label()
        
    def on_files_dropped(self, files):
        """Handle files dropped onto the list"""
        self.add_files_to_list(files)
        self.app_state.log(f"Added {len(files)} file(s) via drag & drop", "INFO")
        
    def remove_selected(self):
        """Remove selected files from the list"""
        selected = self.files_list.selectedItems()
        for item in selected:
            file_path = item.data(Qt.UserRole)
            self.app_state.input_files.remove(file_path)
            self.files_list.takeItem(self.files_list.row(item))
        self.update_count_label()
        
    def clear_files(self):
        """Clear all files from the list"""
        self.app_state.clear_input_files()
        self.files_list.clear()
        self.update_count_label()
        self.info_label.setText("Select a file and click 'Show Details'...")
        
    def update_count_label(self):
        """Update the file count label"""
        count = self.files_list.count()
        self.count_label.setText(f"{count} file{'s' if count != 1 else ''} selected")
        
    def on_selection_changed(self):
        """Handle file selection change"""
        selected = self.files_list.selectedItems()
        if selected:
            file_path = selected[0].data(Qt.UserRole)
            self.app_state.current_video_path = file_path
            self.file_selected.emit(file_path)
            
    def show_file_details(self):
        """Show details for the selected file"""
        selected = self.files_list.selectedItems()
        if not selected:
            QMessageBox.information(self, "Show Details", "Please select a file first.")
            return
            
        file_path = selected[0].data(Qt.UserRole)
        self.detect_and_show_info(file_path)
        
    def detect_and_show_info(self, filepath):
        """Detect and display file information"""
        self.app_state.log(f"Getting info for {os.path.basename(filepath)}...", "INFO")
        
        cmd = [
            self.app_state.ffmpeg_path, "-i", filepath,
            "-f", "null", "-"
        ]
        
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            stderr = result.stderr
            
            # Parse info lines
            info_text = []
            
            # Resolution
            match = re.search(r"\d{3,4}x\d{3,4}", stderr)
            if match:
                info_text.append(f"Resolution: {match.group()}")

            # Codec
            match = re.search(r"Stream #0:0.*Video: (\w+)", stderr)
            if match:
                info_text.append(f"Codec: {match.group(1)}")

            # Bitrate
            match = re.search(r"bitrate: (\d+) kb/s", stderr)
            if match:
                info_text.append(f"Bitrate: {match.group(1)} kbps")
            
            # Duration
            match = re.search(r"Duration: (\d{2}:\d{2}:\d{2})", stderr)
            if match:
                info_text.append(f"Duration: {match.group(1)}")

            # Construct display string
            display_msg = " | ".join(info_text) if info_text else "Could not parse video info."
            
            # Show in Label AND Log
            self.info_label.setText(display_msg)
            self.app_state.log(f"File Info: {display_msg}", "INFO")
            
        except Exception as e:
            err_msg = f"Failed to get info: {e}"
            self.info_label.setText(err_msg)
            self.app_state.log(err_msg, "ERROR")
            
    def validate_video_file(self):
        """Validate selected video file for health and DTS issues"""
        selected = self.files_list.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Validation", "Please select a file first.")
            return
        
        file_path = selected[0].data(Qt.UserRole)
        self.run_validation(file_path)
        
    def extract_subtitles(self):
        """Extract all subtitles from video or DVD folder"""
        selected = self.files_list.selectedItems()
        
        if selected:
            file_path = selected[0].data(Qt.UserRole)
            source_type = selected[0].data(Qt.UserRole + 1)
            
            if source_type == "dvd":
                self._extract_subs_from_dvd(self.app_state.dvd.dvd_folder_path)
            else:
                self._extract_subs_from_video(file_path)
            return
        
        # Let user choose between video file or DVD folder
        msg = QMessageBox(self)
        msg.setWindowTitle("Extract Subtitles")
        msg.setText("Choose source type:")
        msg.setInformativeText("Select a video file or DVD folder to extract subtitles from.")
        
        btn_video = msg.addButton("Video File", QMessageBox.AcceptRole)
        btn_dvd = msg.addButton("DVD Folder", QMessageBox.ActionRole)
        btn_cancel = msg.addButton("Cancel", QMessageBox.RejectRole)
        
        msg.exec()
        
        if msg.clickedButton() == btn_video:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Video File",
                "",
                "Video Files (*.mp4 *.mkv *.avi *.mov *.mpg *.mpeg);;All Files (*)"
            )
            if file_path:
                self._extract_subs_from_video(file_path)
        elif msg.clickedButton() == btn_dvd:
            folder_path = QFileDialog.getExistingDirectoryUrl(
                self, "Select DVD Folder (VIDEO_TS)"
            )
            if folder_path:
                self._extract_subs_from_dvd(folder_path.toLocalFile())
    
    def _extract_subs_from_video(self, video_path):
        """Extract subtitles from a video file"""
        import tempfile
        
        self.app_state.log(f"Extracting subtitles from: {os.path.basename(video_path)}", "INFO")
        
        # Get subtitle streams using ffprobe
        cmd = [
            self.app_state.ffprobe_path,
            "-v", "error",
            "-show_entries", "stream=index,codec_type,codec_name:stream_tags=language",
            "-of", "json",
            video_path
        ]
        
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            import json
            data = json.loads(result.stdout)
            
            subtitle_streams = [s for s in data.get('streams', []) if s.get('codec_type') == 'subtitle']
            
            if not subtitle_streams:
                self.app_state.log("No subtitle streams found in video file", "WARN")
                QMessageBox.information(self, "Extract Subtitles", "No subtitle streams found in the video file.")
                return
            
            self.app_state.log(f"Found {len(subtitle_streams)} subtitle stream(s)", "INFO")
            
            # Use video file's directory for output
            video_dir = os.path.dirname(video_path)
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            output_dir = os.path.join(video_dir, f"{video_name}_subs")
            os.makedirs(output_dir, exist_ok=True)
            
            extracted_files = []
            
            for i, stream in enumerate(subtitle_streams):
                stream_idx = stream.get('index', i)
                lang = stream.get('tags', {}).get('language', f'track{i}')
                codec = stream.get('codec_name', 'unknown')
                
                output_file = os.path.join(output_dir, f"sub_{i}_{lang}.srt")
                
                # Extract subtitle
                cmd = [
                    self.app_state.ffmpeg_path,
                    "-y", "-i", video_path,
                    "-map", f"0:s:{i}",
                    "-c:s", "srt",
                    output_file
                ]
                
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
                
                if result.returncode == 0 and os.path.exists(output_file):
                    extracted_files.append(output_file)
                    self.app_state.log(f"Extracted: {os.path.basename(output_file)}", "SUCCESS")
            
            if extracted_files:
                msg = f"Extracted {len(extracted_files)} subtitle(s) to:\n{output_dir}"
                self.app_state.log(msg, "SUCCESS")
                QMessageBox.information(self, "Extract Subtitles", msg)
            else:
                self.app_state.log("Failed to extract subtitles", "WARN")
                QMessageBox.warning(self, "Extract Subtitles", "Failed to extract subtitles from video file.")
                
        except Exception as e:
            self.app_state.log(f"Error extracting subtitles: {e}", "ERROR")
            QMessageBox.warning(self, "Extract Subtitles", f"Error: {e}")
    
    def _extract_subs_from_dvd(self, folder_path):
        """Extract subtitles from DVD folder - shows info about DVD subtitles"""
        from dvd_handler import DVDHandler
        import tempfile
        
        self.app_state.log(f"Scanning DVD folder: {folder_path}", "INFO")
        
        handler = DVDHandler(
            ffmpeg_path=self.app_state.ffmpeg_path,
            ffprobe_path=self.app_state.ffprobe_path,
            log_callback=self.app_state.log
        )
        
        # Check if it's a VIDEO_TS folder
        if not handler.is_video_ts_folder(folder_path):
            # Try VIDEO_TS subfolder
            video_ts = os.path.join(folder_path, 'VIDEO_TS')
            if os.path.isdir(video_ts):
                folder_path = video_ts
            else:
                self.app_state.log("Not a valid VIDEO_TS folder", "WARN")
                QMessageBox.warning(self, "Extract Subtitles", "Selected folder is not a valid VIDEO_TS folder.")
                return
        
        # Get DVD titles
        titles = handler.get_dvd_titles(folder_path)
        
        if not titles:
            self.app_state.log("No DVD titles found", "WARN")
            QMessageBox.warning(self, "Extract Subtitles", "No DVD titles found in the folder.")
            return
        
        # Find main title (longest)
        main_title = max(titles, key=lambda t: t.duration)
        
        self.app_state.log(f"Found {len(titles)} title(s), main title is Title {main_title.title_number}", "INFO")
        
        # Get subtitles for main title
        if not main_title.subtitles:
            self.app_state.log("No subtitles found in main title", "WARN")
            QMessageBox.warning(self, "Extract Subtitles", "No subtitles found in the main DVD title.")
            return
        
        self.app_state.log(f"Found {len(main_title.subtitles)} subtitle track(s)", "INFO")
        
        # Show subtitle info
        msg = f"Found {len(main_title.subtitles)} subtitle track(s) in DVD Title {main_title.title_number}:\n\n"
        for i, sub in enumerate(main_title.subtitles):
            lang = sub.get('language', 'unknown')
            msg += f"  Track {i}: {lang}\n"
        
        msg += "\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "NOTE: DVD subtitles are bitmap-based (VobSub format).\n\n"
        msg += "They cannot be extracted to text files like .srt.\n"
        msg += "Instead, they are burned directly into the video\n"
        msg += "during encoding using FFmpeg's overlay filter.\n\n"
        msg += "To use DVD subtitles:\n"
        msg += "1. Click '📀 Open DVD' to import the DVD\n"
        msg += "2. Select a subtitle track in the dialog\n"
        msg += "3. Enable 'Burn Subtitles' in Subtitles panel\n"
        msg += "4. Start encoding - subtitles will be burned in"
        
        self.app_state.log(msg, "INFO")
        QMessageBox.information(self, "DVD Subtitles", msg)
    
    def extract_track(self):
        """Extract video or audio track from video file"""
        selected = self.files_list.selectedItems()
        
        if selected:
            file_path = selected[0].data(Qt.UserRole)
            self._extract_track_from_video(file_path)
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File",
            "",
            "Video Files (*.mp4 *.mkv *.avi *.mov *.mpg *.mpeg *.vob);;All Files (*)"
        )
        if not file_path:
            return
        
        self._extract_track_from_video(file_path)
    
    def _extract_track_from_video(self, video_path):
        """Extract a track from a video file"""
        self.app_state.log(f"Analyzing tracks in: {os.path.basename(video_path)}", "INFO")
        
        # Get all streams using ffprobe
        cmd = [
            self.app_state.ffprobe_path,
            "-v", "error",
            "-show_entries", "stream=index,codec_type,codec_name,width,height:stream_tags=language",
            "-of", "json",
            video_path
        ]
        
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            
            if result.returncode != 0:
                self.app_state.log(f"ffprobe error: {result.stderr}", "ERROR")
                QMessageBox.warning(self, "Extract Track", f"Error analyzing file: {result.stderr}")
                return
            
            data = json.loads(result.stdout)
            streams = data.get('streams', [])
            
            # Separate video and audio tracks
            video_tracks = []
            audio_tracks = []
            
            for stream in streams:
                codec_type = stream.get('codec_type')
                
                if codec_type == 'video':
                    width = stream.get('width', 0)
                    height = stream.get('height', 0)
                    resolution = f"{width}x{height}" if width and height else ""
                    video_tracks.append({
                        'index': stream.get('index'),
                        'video_index': len(video_tracks),  # 0-based position among video streams
                        'codec': stream.get('codec_name', 'unknown').upper(),
                        'resolution': resolution
                    })
                elif codec_type == 'audio':
                    audio_tracks.append({
                        'index': stream.get('index'),
                        'audio_index': len(audio_tracks),  # 0-based position among audio streams
                        'codec': stream.get('codec_name', 'unknown').upper(),
                        'channels': 'Stereo',
                        'language': stream.get('tags', {}).get('language', 'unknown')
                    })
            
            # Get more detailed audio info
            if audio_tracks:
                cmd_audio = [
                    self.app_state.ffprobe_path,
                    "-v", "error",
                    "-select_streams", "a",
                    "-show_entries", "stream=index,codec_name,channels:stream_tags=language",
                    "-of", "json",
                    video_path
                ]
                try:
                    result_audio = subprocess.run(cmd_audio, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
                    if result_audio.returncode == 0:
                        audio_data = json.loads(result_audio.stdout)
                        for i, stream in enumerate(audio_data.get('streams', [])):
                            if i < len(audio_tracks):
                                channels = stream.get('channels', 0)
                                ch_str = f"{channels}ch" if channels else "Stereo"
                                audio_tracks[i]['channels'] = ch_str
                except Exception:
                    pass
            
            if not video_tracks and not audio_tracks:
                self.app_state.log("No video or audio tracks found", "WARN")
                QMessageBox.information(self, "Extract Track", "No video or audio tracks found in the file.")
                return
            
            # Show selection dialog
            dialog = TrackSelectionDialog(video_tracks, audio_tracks, self)
            if dialog.exec() == QDialog.Accepted:
                selected = dialog.get_selected_track()
                if selected:
                    self._do_extract_track(video_path, selected)
            
        except json.JSONDecodeError as e:
            self.app_state.log(f"Failed to parse ffprobe output: {e}", "ERROR")
            QMessageBox.warning(self, "Extract Track", f"Failed to analyze file: {e}")
        except Exception as e:
            self.app_state.log(f"Error extracting track: {e}", "ERROR")
            QMessageBox.warning(self, "Extract Track", f"Error: {e}")
    
    def _do_extract_track(self, video_path, track_info):
        """Perform the actual track extraction"""
        # Get output folder
        output_folder = self.app_state.output_folder if self.app_state.output_folder else os.path.dirname(video_path)
        
        # Generate output filename
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        track_type = track_info['type']
        track_idx = track_info['index']
        
        if track_type == 'video':
            output_ext = '.mkv'
            output_filename = f"{base_name}_video_track{track_idx}{output_ext}"
            
            cmd = [
                self.app_state.ffmpeg_path,
                "-y",
                "-i", video_path,
                "-map", f"0:v:{track_info['video_index']}",
                "-c", "copy",
                os.path.join(output_folder, output_filename)
            ]
        else:
            # Get audio codec
            cmd_probe = [
                self.app_state.ffprobe_path,
                "-v", "error",
                "-select_streams", f"a:{track_info['audio_index']}",
                "-show_entries", "stream=codec_name",
                "-of", "json",
                video_path
            ]
            
            codec = 'aac'
            try:
                result = subprocess.run(cmd_probe, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    streams = data.get('streams', [])
                    if streams:
                        codec = streams[0].get('codec_name', 'aac').lower()
            except Exception:
                pass
            
            codec_ext = {
                'aac': '.aac', 'mp3': '.mp3', 'ac3': '.ac3', 'dts': '.dts',
                'flac': '.flac', 'ogg': '.ogg', 'opus': '.opus',
                'wav': '.wav', 'pcm_s16le': '.wav'
            }
            output_ext = codec_ext.get(codec, '.aac')
            output_filename = f"{base_name}_audio_track{track_idx}{output_ext}"
            
            cmd = [
                self.app_state.ffmpeg_path,
                "-y",
                "-i", video_path,
                "-map", f"0:a:{track_info['audio_index']}",
                "-c", "copy",
                os.path.join(output_folder, output_filename)
            ]
        
        self.app_state.log(f"Extracting {track_type} track to: {output_filename}", "INFO")
        
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
            
            if result.returncode == 0:
                output_path = os.path.join(output_folder, output_filename)
                if os.path.exists(output_path):
                    size_mb = os.path.getsize(output_path) / (1024 * 1024)
                    msg = f"Successfully extracted {track_type} track!\n\nOutput: {output_filename}\nSize: {size_mb:.2f} MB"
                    self.app_state.log(msg, "SUCCESS")
                    QMessageBox.information(self, "Extract Track", msg)
                else:
                    self.app_state.log("Output file not found", "ERROR")
                    QMessageBox.warning(self, "Extract Track", "Extraction completed but output file not found.")
            else:
                error_msg = result.stderr if result.stderr else "Unknown error"
                self.app_state.log(f"Extraction failed: {error_msg}", "ERROR")
                QMessageBox.warning(self, "Extract Track", f"Extraction failed: {error_msg}")
                
        except subprocess.TimeoutExpired:
            self.app_state.log("Extraction timed out", "ERROR")
            QMessageBox.warning(self, "Extract Track", "Extraction timed out.")
        except Exception as e:
            self.app_state.log(f"Error during extraction: {e}", "ERROR")
            QMessageBox.warning(self, "Extract Track", f"Error: {e}")
        
    def run_validation(self, filepath):
        """Run video validation and show results"""
        from video_validator import VideoValidator
        
        validator = VideoValidator(self.app_state.backend, self.app_state.log)
        
        # Quick health check
        if not validator.quick_health_check(filepath):
            self.app_state.log("Quick health check failed", "WARN")
            QMessageBox.warning(self, "Video Validation", "❌ Quick health check failed. File may be corrupted.")
            return
        
        # DTS check
        dts_result = validator.check_dts_issues(filepath)
        
        # Frame rate analysis
        fps_info = validator.analyze_frame_rate(filepath)
        
        # Build results message
        warnings = []
        
        if dts_result['has_issues']:
            warnings.extend(dts_result['issues'])
        
        if fps_info.get('is_vfr', True):
            warnings.append(f"Variable frame rate: {fps_info.get('fps_str', 'unknown')}")
        
        if fps_info.get('is_problematic', True):
            warnings.append(f"Unusual frame rate: {fps_info.get('fps_str', 'unknown')}")
        
        # Show results
        if not warnings:
            QMessageBox.information(self, "Video Validation", "✅ Video appears healthy\n\nNo DTS or frame rate issues detected.")
        else:
            QMessageBox.warning(self, "Video Validation", f"⚠️ Issues found:\n\n" + "\n".join(warnings))
        
        self.app_state.log(f"Validation completed for {os.path.basename(filepath)}", "INFO")
        
    def join_files(self):
        """Join queued input files into a single video if identical codecs/params."""
        import tempfile
        
        files = [f for f in self.app_state.input_files if os.path.exists(f)]
        if len(files) < 2:
            QMessageBox.information(self, "Join", "Need at least 2 input files to join.")
            return
            
        if not self._files_identical(files):
            QMessageBox.information(self, "Join", "Files cannot be joined without re-encoding. Please re-encode to a common format first.")
            return

        # Create concat list file
        with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt', encoding='utf-8') as tf:
            list_path = tf.name
            for p in files:
                # Escape single quotes in path
                safe = p.replace("'", "'\"'\"'")
                tf.write(f"file '{safe}'\n")

        first_ext = os.path.splitext(files[0])[1] or ".mp4"
        default_name = os.path.splitext(os.path.basename(files[0]))[0] + "_joined" + first_ext
        
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save joined video as", default_name,
            f"Video (*{first_ext});;All Files (*)"
        )
        
        if not out_path:
            try:
                os.remove(list_path)
            except Exception:
                pass
            return

        cmd = [self.app_state.ffmpeg_path, "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", out_path]

        def do_join():
            try:
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
                ok = res.returncode == 0
                err = res.stderr
            except Exception as e:
                ok = False
                err = str(e)

            # Cleanup and show result in main thread
            try:
                os.remove(list_path)
            except Exception:
                pass
                
            if ok:
                self.app_state.log(f"Joined file created: {out_path}", "SUCCESS")
            else:
                self.app_state.log(f"Failed to join files: {err}", "ERROR")

        thread = threading.Thread(target=do_join, daemon=True)
        thread.start()
        self.app_state.log("Starting file join operation...", "INFO")

    def _files_identical(self, paths):
        """Return True if all inputs have identical video/audio params."""
        base = self._get_media_params(paths[0])
        for p in paths[1:]:
            if self._get_media_params(p) != base:
                return False
        return True

    def _get_media_params(self, path):
        """Return a simple dict of media params using ffprobe."""
        params = {}
        try:
            cmd_v = ["ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=codec_name,width,height,avg_frame_rate",
                     "-of", "default=noprint_wrappers=1:nokey=1", path]
            res = subprocess.run(cmd_v, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            lines = res.stdout.strip().splitlines()
            if len(lines) >= 4:
                params["vcodec"] = lines[0]
                params["width"] = lines[1]
                params["height"] = lines[2]
                params["fps"] = lines[3]
        except Exception:
            pass
        try:
            cmd_a = ["ffprobe", "-v", "error", "-select_streams", "a:0",
                     "-show_entries", "stream=codec_name",
                     "-of", "default=noprint_wrappers=1:nokey=1", path]
            res = subprocess.run(cmd_a, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            a = res.stdout.strip()
            if a:
                params["acodec"] = a
        except Exception:
            pass
        return params
        
    def clean_filenames(self):
        """Clean filenames in the Input Files Queue."""
        files = [f for f in self.app_state.input_files if os.path.exists(f)]
        if not files:
            QMessageBox.information(self, "Clean Names", "No files to clean.")
            return

        # Show preview dialog
        dialog = CleanNamesDialog(files, self)
        if dialog.exec() == QDialog.Accepted:
            # Apply changes
            errors = []
            for orig_path, new_base in dialog.cleaned:
                dirname = os.path.dirname(orig_path)
                new_path = os.path.join(dirname, new_base)
                if os.path.exists(new_path):
                    errors.append(f"Destination exists: {new_base}")
                    continue
                try:
                    os.rename(orig_path, new_path)
                except Exception as e:
                    errors.append(f"Failed to rename {orig_path}: {e}")
                    break

            if errors:
                QMessageBox.critical(self, "Clean Names", "\n".join(errors))
                return

            # Update queue
            new_files = []
            for f in files:
                dirname = os.path.dirname(f)
                new_base = dialog._clean_filename(os.path.basename(f))
                new_files.append(os.path.join(dirname, new_base))
            
            self.app_state.input_files = new_files
            self.files_list.clear()
            for f in new_files:
                item = QListWidgetItem(os.path.basename(f))
                item.setData(Qt.UserRole, f)
                item.setToolTip(f)
                self.files_list.addItem(item)

            QMessageBox.information(self, "Clean Names", "Filenames cleaned successfully.")
            self.app_state.log("Filenames cleaned successfully", "SUCCESS")
