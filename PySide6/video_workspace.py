"""
Video Workspace - Main Video Tab layout and panel management (PySide6)
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QScrollArea, QFrame, QLabel, QPushButton, QTextEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from models import AppState
from ui_components import CollapsibleFrame
from encoding_settings import EncodingPanel
from geometry import GeometryPanel
from color_correction import ColorCorrectionPanel
from subtitles import SubtitlesPanel
from filters import FiltersPanel
from trim_panel import TrimPanel
from video_preview import VideoPreview
from nle import NLETab


class LogWidget(QTextEdit):
    """Custom log display widget"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(1000)
        self.setFont(QFont("Consolas", 9))
        
    def log(self, message: str, level: str = "INFO"):
        """Add a log entry with color coding"""
        colors = {
            "INFO": "#000000",
            "WARN": "#FF8C00",
            "ERROR": "#FF0000",
            "SUCCESS": "#008000"
        }
        color = colors.get(level, "#000000")
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        html = f'<span style="color: #666666;">[{timestamp}]</span> '
        html += f'<span style="color: {color};">{message}</span>'
        
        self.append(html)
        
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


class VideoWorkspace(QWidget):
    """
    Main video workspace with settings panels on the left
    and preview with tabs on the right.
    """
    
    def __init__(self, app_state: AppState, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        
        # Create log widget
        self.log_widget = LogWidget()
        self.app_state.log_message.connect(self.on_log_message)
        
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """Setup the main layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Main horizontal splitter
        main_splitter = QSplitter(Qt.Horizontal)
        
        # === LEFT PANE: Settings Panels ===
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll area for settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(5)
        
        # Encoding Settings (Collapsible)
        enc_collapsible = CollapsibleFrame("Encoding Settings")
        self.enc_panel = EncodingPanel(self.app_state)
        self.enc_panel.settings_changed.connect(self.on_settings_changed)
        enc_collapsible.content_layout().addWidget(self.enc_panel)
        scroll_layout.addWidget(enc_collapsible)
        
        # Geometry Settings (Collapsible)
        geo_collapsible = CollapsibleFrame("Geometry")
        self.geo_panel = GeometryPanel(self.app_state)
        self.geo_panel.settings_changed.connect(self.on_settings_changed)
        geo_collapsible.content_layout().addWidget(self.geo_panel)
        scroll_layout.addWidget(geo_collapsible)
        
        # Color Correction (Collapsible)
        color_collapsible = CollapsibleFrame("Color Correction")
        self.color_panel = ColorCorrectionPanel(self.app_state)
        self.color_panel.settings_changed.connect(self.on_settings_changed)
        color_collapsible.content_layout().addWidget(self.color_panel)
        scroll_layout.addWidget(color_collapsible)
        
        # Subtitles (Collapsible)
        subs_collapsible = CollapsibleFrame("Subtitles")
        self.subs_panel = SubtitlesPanel(self.app_state)
        self.subs_panel.settings_changed.connect(self.on_settings_changed)
        self.subs_panel.refresh_subtitles.connect(self.on_refresh_subtitles)
        subs_collapsible.content_layout().addWidget(self.subs_panel)
        scroll_layout.addWidget(subs_collapsible)
        
        # Filters (Collapsible)
        filters_collapsible = CollapsibleFrame("Filters")
        self.filters_panel = FiltersPanel(self.app_state)
        self.filters_panel.settings_changed.connect(self.on_settings_changed)
        filters_collapsible.content_layout().addWidget(self.filters_panel)
        scroll_layout.addWidget(filters_collapsible)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        left_layout.addWidget(scroll)
        
        main_splitter.addWidget(left_widget)
        
        # === RIGHT PANE: Preview and Tabs ===
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Use splitter between preview and tabs for adjustable sizing
        right_splitter = QSplitter(Qt.Vertical)
        
        # Video Preview
        self.preview = VideoPreview(self.app_state)
        right_splitter.addWidget(self.preview)
        
        # Tabs for Trim/Cut, Log, and Scan
        self.tabs = QTabWidget()
        
        # Trim/Cut Tab
        self.trim_tab = QWidget()
        trim_layout = QVBoxLayout(self.trim_tab)
        self.trim_panel = TrimPanel(self.app_state, self.preview.get_current_timestamp)
        self.trim_panel.cut_point_set.connect(self.on_cut_point_set)
        self.trim_panel.execute_cuts.connect(self.on_execute_cuts)
        self.trim_panel.cut_removed.connect(self.on_cut_removed)
        self.trim_panel.clear_all_cuts.connect(self.on_clear_all_cuts)
        trim_layout.addWidget(self.trim_panel)
        
        # Connect timeline marker clicks to select cuts
        self.preview.timeline_slider.cut_marker_clicked.connect(self.on_cut_marker_clicked)
        trim_layout.addStretch()
        self.tabs.addTab(self.trim_tab, "Trim/Cut")
        
        # Log Tab
        self.log_tab = QWidget()
        log_layout = QVBoxLayout(self.log_tab)
        
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("<b>Log Output</b>"))
        log_header.addStretch()
        
        clear_btn = QPushButton("Clear")
        clear_btn.setMaximumWidth(80)
        clear_btn.clicked.connect(self.clear_log)
        log_header.addWidget(clear_btn)
        
        log_layout.addLayout(log_header)
        log_layout.addWidget(self.log_widget)
        
        self.tabs.addTab(self.log_tab, "📋 Log")
        
        # NLE Tab (Non-Linear Editor)
        self.nle_tab = NLETab(self.app_state)
        self.tabs.addTab(self.nle_tab, "NLE Editor")
        
        right_splitter.addWidget(self.tabs)
        right_splitter.setSizes([500, 250])
        
        right_layout.addWidget(right_splitter)
        
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([350, 900])
        
        layout.addWidget(main_splitter)
        
        # Bottom: Encode and Cancel buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        # Cancel button (hidden by default)
        self.cancel_btn = QPushButton("❌ Cancel")
        self.cancel_btn.setMinimumWidth(120)
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.cancel_btn.clicked.connect(self.on_cancel_clicked)
        self.cancel_btn.setVisible(False)
        btn_layout.addWidget(self.cancel_btn)
        
        # Encode button
        self.encode_btn = QPushButton("🎬 Start Encoding")
        self.encode_btn.setMinimumWidth(150)
        self.encode_btn.setMinimumHeight(40)
        self.encode_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.encode_btn.clicked.connect(self.on_encode_clicked)
        btn_layout.addWidget(self.encode_btn)
        
        layout.addLayout(btn_layout)
        
    def connect_signals(self):
        """Connect signals"""
        self.app_state.current_video_changed.connect(self.on_video_changed)
        
    def on_log_message(self, message: str, level: str):
        """Handle log messages from app state"""
        self.log_widget.log(message, level)
        
    def clear_log(self):
        """Clear the log widget"""
        self.log_widget.clear()
        
    def on_settings_changed(self):
        """Handle settings change - refresh preview"""
        self.preview.refresh_preview()
        
    def on_video_changed(self, video_path: str):
        """Handle video selection change"""
        if video_path:
            self.preview.set_video(video_path)
            self.trim_panel.detect_tracks(video_path)
            
            # Detect audio tracks and populate encoding panel
            from controller import VideoController
            controller = VideoController(self.app_state)
            audio_tracks = controller.get_audio_tracks(video_path)
            
            if audio_tracks:
                # Convert to AudioTrackInfo objects
                from models import AudioTrackInfo
                track_infos = []
                for track in audio_tracks:
                    track_info = AudioTrackInfo(
                        index=track['index'],
                        codec=track['codec'],
                        channels=track['channels'],
                        sample_rate=track['sample_rate'],
                        language=track['language'],
                        title=track['title']
                    )
                    track_infos.append(track_info)
                
                self.app_state.tracks.available_audio_tracks = track_infos
                self.enc_panel.populate_audio_tracks(track_infos)
                self.app_state.log(f"Detected {len(track_infos)} audio track(s)", "INFO")
            else:
                self.app_state.tracks.available_audio_tracks = []
                self.enc_panel.populate_audio_tracks([])
            
    def on_cut_point_set(self, position: float):
        """Handle adding a new cut point"""
        # Format time display from position
        mins, secs = divmod(int(position), 60)
        hours = mins // 60
        mins = mins % 60
        if hours > 0:
            time_str = f"{hours}:{mins:02d}:{secs:02d}"
        else:
            time_str = f"{mins}:{secs:02d}"
        
        # Add the cut point to the list
        cut_point = self.app_state.cut.add_point(position, time_str)
        
        # Get segment info for display
        sorted_cuts = self.app_state.cut.get_sorted_points()
        segment_info = self._get_segment_info_for_cut(cut_point, sorted_cuts)
        
        # Add to UI list
        self.trim_panel.add_cut_to_list(cut_point, segment_info)
        
        # Update timeline markers
        self._update_timeline_markers()
        
        # Update segments info
        self.trim_panel._update_segments_list()
        
        self.app_state.log(f"Added cut point at {time_str}", "INFO")
    
    def on_cut_removed(self, cut_id: str):
        """Handle removing a cut point"""
        if self.app_state.cut.remove_point(cut_id):
            self.trim_panel.remove_cut_from_list(cut_id)
            self._update_timeline_markers()
            
            # Update segments info
            self.trim_panel._update_segments_list()
            
            self.app_state.log(f"Removed cut point", "INFO")
    
    def on_clear_all_cuts(self):
        """Handle clearing all cut points"""
        self.app_state.cut.clear_all()
        self.trim_panel.clear_all_cuts_from_list()
        self._update_timeline_markers()
        self.trim_panel._update_segments_list()
        self.app_state.log("Cleared all cut points", "INFO")
    
    def _get_segment_info_for_cut(self, cut_point, sorted_cuts):
        """Get segment duration info for a cut point"""
        # Find the index of this cut
        for i, cut in enumerate(sorted_cuts):
            if cut.cut_id == cut_point.cut_id:
                # Calculate segment duration
                if i == 0:
                    # First cut - segment is from 0 to this cut
                    return f"0:00 - {cut_point.time_display}"
                else:
                    # Subsequent cut - segment is from previous cut to this cut
                    return f"{sorted_cuts[i-1].time_display} - {cut_point.time_display}"
        return ""
    
    def _update_timeline_markers(self):
        """Update the timeline with current cut markers"""
        cut_points = [(cut.position, cut.cut_id) for cut in self.app_state.cut.points]
        self.preview.update_cut_markers(cut_points)
        
    def on_execute_cuts(self, segments_data):
        """Handle execute cuts - encode selected segments only (runs in background thread)"""
        if not self.app_state.input_files:
            self.app_state.log("No video file loaded", "ERROR")
            return
            
        if not segments_data:
            self.app_state.log("No segments selected", "ERROR")
            return
        
        # Show cancel button, hide encode button
        self.encode_btn.setVisible(False)
        self.cancel_btn.setVisible(True)
        
        self.app_state.log(f"Encoding {len(segments_data)} selected segment(s)", "INFO")
        
        # Start encoding in a separate thread to keep UI responsive
        import threading
        def cut_worker():
            try:
                self._execute_cuts_worker(segments_data)
            finally:
                # Re-enable encode button when done
                self.encode_btn.setVisible(True)
                self.cancel_btn.setVisible(False)
        
        self.cut_thread = threading.Thread(target=cut_worker, daemon=True)
        self.cut_thread.start()
    
    def _execute_cuts_worker(self, segments_data):
        """Worker method that does the actual encoding (runs in background thread)"""
        input_file = self.app_state.input_files[0]
        
        # segments_data is list of (start_time, end_time, segment_name) tuples
        # end_time = -1 means "end of video"
        
        # Initialize controller
        from controller import VideoController
        controller = VideoController(self.app_state)
        
        # Get video duration
        duration = controller.get_video_duration(input_file)
        if duration == 0:
            self.app_state.log("Could not determine video duration", "ERROR")
            return
        
        self.app_state.log(f"Video duration: {duration:.2f} seconds ({duration/60:.2f} minutes)", "INFO")
        
        # Check if we can do fast cut (stream copy) - only when no filters or re-encoding needed
        can_fast_cut = (
            self.app_state.encoding.resolution == "none" and
            not self.app_state.filters.deinterlace and
            not self.app_state.filters.denoise and
            not getattr(self.app_state.filters, 'delogo_enabled', False) and
            not self.app_state.eq.enabled and
            not self.app_state.subtitles.burn_subs and
            not self.app_state.filters.volume_enabled and
            not getattr(self.app_state.filters, 'audio_denoise', False) and
            not getattr(self.app_state.filters, 'audio_dynnorm', False) and
            not getattr(self.app_state.filters, 'audio_compressor', False)
        )
        
        # Generate output paths
        import os
        from pathlib import Path
        base_name = Path(input_file).stem
        output_folder = self.app_state.output_folder or os.path.dirname(input_file)
        container = self.app_state.encoding.container
        
        # Encode each selected segment
        all_success = True
        for i, (seg_start, seg_end, seg_name) in enumerate(segments_data, 1):
            # Handle end = -1 (end of video)
            if seg_end == -1:
                seg_end = duration
            
            # Validate segment
            if seg_start < 0 or seg_end <= seg_start:
                self.app_state.log(f"Invalid segment: {seg_name} (start: {seg_start}, end: {seg_end})", "ERROR")
                continue
            
            duration_sec = seg_end - seg_start
            
            # Skip very short segments
            if duration_sec < 1:
                self.app_state.log(f"Skipping {seg_name}: too short ({duration_sec:.1f}s)", "WARN")
                continue
            
            # Generate output path
            output_path = os.path.join(output_folder, f"{base_name}_{seg_name}.{container}")
            
            # Check for existing file and append counter if needed
            counter = 1
            while os.path.exists(output_path):
                output_path = os.path.join(output_folder, f"{base_name}_{seg_name}_{counter}.{container}")
                counter += 1
            
            self.app_state.log(f"Processing {seg_name}: {self._format_time(seg_start)} - {self._format_time(seg_end)} ({duration_sec:.1f}s)", "INFO")
            
            if can_fast_cut:
                success = controller.fast_cut_file(
                    input_file,
                    output_path,
                    start_time=str(seg_start),
                    duration=str(duration_sec)
                )
            else:
                success = controller.encode_file(
                    input_file,
                    output_path,
                    start_time=str(seg_start),
                    duration=str(duration_sec)
                )
            
            if not success:
                self.app_state.log(f"Failed to encode {seg_name}", "ERROR")
                all_success = False
                break
        
        if all_success:
            self.app_state.log(f"Successfully encoded {len(segments_data)} segment(s)!", "SUCCESS")
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds as time string"""
        mins, secs = divmod(int(seconds), 60)
        hours = mins // 60
        mins = mins % 60
        if hours > 0:
            return f"{hours}:{mins:02d}:{secs:02d}"
        else:
            return f"{mins:02d}:{secs:02d}"
    
    def on_cut_marker_clicked(self, position: float, cut_id: str):
        """Handle click on timeline cut marker - select in list"""
        # Find and select the cut in the list
        self.trim_panel.select_cut_by_id(cut_id)
        self.app_state.log(f"Selected cut at {self._format_time(position)}", "INFO")
        
    def on_encode_clicked(self):
        """Handle encode button click"""
        if not self.app_state.input_files:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No Files", "Please add video files first.")
            return
            
        # Initialize controller and start encoding
        from controller import VideoController
        self.controller = VideoController(self.app_state)
        
        # Show cancel button, hide encode button
        self.encode_btn.setVisible(False)
        self.cancel_btn.setVisible(True)
        
        # Start encoding in a separate thread to keep UI responsive
        import threading
        def encode_worker():
            for input_file in self.app_state.input_files:
                output_path = self.controller.generate_output_path(input_file)
                success = self.controller.encode_file(input_file, output_path)
                if not success:
                    self.app_state.log(f"Failed to encode: {input_file}", "ERROR")
            
            # Re-enable encode button when done
            self.encode_btn.setVisible(True)
            self.cancel_btn.setVisible(False)
                    
        self.encode_thread = threading.Thread(target=encode_worker, daemon=True)
        self.encode_thread.start()
        self.app_state.log(f"Started encoding {len(self.app_state.input_files)} file(s)...", "INFO")
        
    def on_cancel_clicked(self):
        """Handle cancel button click"""
        if self.controller and self.controller.is_encoding:
            self.controller.cancel_encode()
            self.app_state.log("Encoding cancelled by user", "INFO")
        
        # Reset buttons
        self.encode_btn.setVisible(True)
        self.cancel_btn.setVisible(False)
        
    def on_refresh_subtitles(self):
        """Handle refresh subtitle files button click"""
        self._scan_and_update_subtitles()
        
    def _scan_and_update_subtitles(self):
        """Scan video folder for subtitle files and update combobox"""
        import os
        
        if not self.app_state.input_files:
            self.subs_panel.set_subtitle_files([])
            return
        
        video_path = self.app_state.input_files[0]
        video_dir = os.path.dirname(video_path)
        
        if not video_dir:
            self.subs_panel.set_subtitle_files([])
            return
        
        # Scan for subtitle files
        sub_files = []
        for f in os.listdir(video_dir):
            if f.lower().endswith(('.srt', '.ass', '.ssa', '.sub')):
                sub_files.append(os.path.join(video_dir, f))
        
        # Sort: .srt first, then alphabetically
        sub_files.sort(key=lambda x: (0 if x.lower().endswith('.srt') else 1, os.path.basename(x).lower()))
        
        self.subs_panel.set_subtitle_files(sub_files)
        
    def set_video(self, video_path: str):
        """Set the current video"""
        self.preview.set_video(video_path)
        self.trim_panel.detect_tracks(video_path)
        
        # Scan for subtitle files in video folder
        self._scan_and_update_subtitles()
        
        # Update DVD subtitle selector (will hide if not a DVD source)
        self.subs_panel.update_dvd_subtitles()
