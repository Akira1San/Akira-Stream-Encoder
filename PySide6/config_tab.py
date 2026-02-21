"""
Configuration Tab - System Paths and Input File Management (PySide6)
"""
import os
import re
import subprocess
import threading
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QFileDialog,
    QGroupBox, QCheckBox, QMessageBox, QAbstractItemView,
    QDialog, QDialogButtonBox, QScrollArea, QFrame
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


class ConfigTab(QWidget):
    """Configuration tab for system paths and file management"""
    
    file_selected = Signal(str)  # Emitted when a file is selected
    
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
        
        # FFmpeg Path
        ffmpeg_layout = QHBoxLayout()
        ffmpeg_layout.addWidget(QLabel("FFmpeg Path:"))
        
        self.ffmpeg_edit = QLineEdit(self.app_state.ffmpeg_path)
        ffmpeg_layout.addWidget(self.ffmpeg_edit)
        
        browse_ffmpeg_btn = QPushButton("Browse...")
        browse_ffmpeg_btn.clicked.connect(self.browse_ffmpeg)
        ffmpeg_layout.addWidget(browse_ffmpeg_btn)
        
        auto_ffmpeg_btn = QPushButton("Auto Detect")
        auto_ffmpeg_btn.clicked.connect(self.auto_detect_ffmpeg)
        ffmpeg_layout.addWidget(auto_ffmpeg_btn)
        
        paths_layout.addLayout(ffmpeg_layout)
        
        # FFprobe Path
        ffprobe_layout = QHBoxLayout()
        ffprobe_layout.addWidget(QLabel("FFprobe Path:"))
        
        self.ffprobe_edit = QLineEdit(self.app_state.ffprobe_path)
        ffprobe_layout.addWidget(self.ffprobe_edit)
        
        browse_ffprobe_btn = QPushButton("Browse...")
        browse_ffprobe_btn.clicked.connect(self.browse_ffprobe)
        ffprobe_layout.addWidget(browse_ffprobe_btn)
        
        paths_layout.addLayout(ffprobe_layout)
        
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
        self.ffmpeg_edit.textChanged.connect(self.on_ffmpeg_changed)
        self.ffprobe_edit.textChanged.connect(self.on_ffprobe_changed)
        self.output_edit.textChanged.connect(self.on_output_changed)
        self.custom_name_check.toggled.connect(self.on_custom_name_toggled)
        self.custom_name_edit.textChanged.connect(self.on_custom_name_changed)
        
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
        
    def run_validation(self, filepath):
        """Run video validation and show results"""
        from video_validator import VideoValidator
        
        validator = VideoValidator(self.app_state.ffmpeg_path, self.app_state.log)
        
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
