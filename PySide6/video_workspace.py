"""
Video Workspace - Main Video Tab layout and panel management (PySide6)
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QScrollArea, QFrame, QLabel, QPushButton
)
from PySide6.QtCore import Qt

from models import AppState
from ui_components import CollapsibleFrame
from encoding_settings import EncodingPanel
from geometry import GeometryPanel
from color_correction import ColorCorrectionPanel
from subtitles import SubtitlesPanel
from filters import FiltersPanel
from trim_panel import TrimPanel
from scan_panel import ScanPanel
from video_preview import VideoPreview


class VideoWorkspace(QWidget):
    """
    Main video workspace with settings panels on the left
    and preview with tabs on the right.
    """
    
    def __init__(self, app_state: AppState, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        
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
        
        # Video Preview
        self.preview = VideoPreview(self.app_state)
        right_layout.addWidget(self.preview)
        
        # Tabs for Trim/Cut and Scan
        self.tabs = QTabWidget()
        
        # Trim/Cut Tab
        self.trim_tab = QWidget()
        trim_layout = QVBoxLayout(self.trim_tab)
        self.trim_panel = TrimPanel(self.app_state, self.preview.get_current_timestamp)
        self.trim_panel.cut_point_set.connect(self.on_cut_point_set)
        self.trim_panel.execute_cut.connect(self.on_execute_cut)
        self.trim_panel.cut_removed.connect(self.on_cut_removed)
        self.trim_panel.clear_all_cuts.connect(self.on_clear_all_cuts)
        trim_layout.addWidget(self.trim_panel)
        
        # Connect timeline marker clicks to select cuts
        self.preview.timeline_slider.cut_marker_clicked.connect(self.on_cut_marker_clicked)
        trim_layout.addStretch()
        self.tabs.addTab(self.trim_tab, "Trim/Cut")
        
        # Scan/Repair Tab
        self.scan_tab = QWidget()
        scan_layout = QVBoxLayout(self.scan_tab)
        self.scan_panel = ScanPanel(self.app_state)
        scan_layout.addWidget(self.scan_panel)
        scan_layout.addStretch()
        self.tabs.addTab(self.scan_tab, "🔍 Scan/Repair")
        
        right_layout.addWidget(self.tabs)
        
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([400, 800])
        
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
        
    def on_settings_changed(self):
        """Handle settings change - refresh preview"""
        self.preview.refresh_preview()
        
    def on_video_changed(self, video_path: str):
        """Handle video selection change"""
        if video_path:
            self.preview.set_video(video_path)
            self.trim_panel.detect_tracks(video_path)
            
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
        segments = self.app_state.cut.get_segments(0)  # Duration will be updated when video is loaded
        self.trim_panel.update_segments_info(segments)
        
        self.app_state.log(f"Added cut point at {time_str}", "INFO")
    
    def on_cut_removed(self, cut_id: str):
        """Handle removing a cut point"""
        if self.app_state.cut.remove_point(cut_id):
            self.trim_panel.remove_cut_from_list(cut_id)
            self._update_timeline_markers()
            
            # Update segments info
            segments = self.app_state.cut.get_segments(0)
            self.trim_panel.update_segments_info(segments)
            
            self.app_state.log(f"Removed cut point", "INFO")
    
    def on_clear_all_cuts(self):
        """Handle clearing all cut points"""
        self.app_state.cut.clear_all()
        self.trim_panel.clear_all_cuts_from_list()
        self._update_timeline_markers()
        self.trim_panel.update_segments_info([])
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
        
    def on_execute_cut(self):
        """Handle execute cut - split video at all cut points"""
        if not self.app_state.input_files:
            self.app_state.log("No video file loaded", "ERROR")
            return
            
        cuts = self.app_state.cut.get_sorted_points()
        if not cuts:
            self.app_state.log("No cut points defined", "ERROR")
            return
            
        input_file = self.app_state.input_files[0]
        
        self.app_state.log(f"Executing {len(cuts)} cut(s)", "INFO")
        
        # Initialize controller
        from controller import VideoController
        controller = VideoController(self.app_state)
        
        # Get video duration
        duration = controller.get_video_duration(input_file)
        if duration == 0:
            self.app_state.log("Could not determine video duration", "ERROR")
            return
        
        # Validate all cut positions
        for i, cut in enumerate(cuts):
            if cut.position < 5 or cut.position > duration - 5:
                self.app_state.log(f"Cut {i+1} at {cut.time_display} is too close to start or end (minimum 5 seconds)", "ERROR")
                return
        
        # Check gaps between cuts (minimum 5 seconds between cuts)
        prev_pos = 0
        for i, cut in enumerate(cuts):
            if cut.position - prev_pos < 5:
                self.app_state.log(f"Cut {i+1} is too close to previous cut (minimum 5 seconds gap required)", "ERROR")
                return
            prev_pos = cut.position
        
        # Check final segment
        if duration - prev_pos < 5:
            self.app_state.log("Final segment is too short (minimum 5 seconds)", "ERROR")
            return
        
        # Check if we can do fast cut (stream copy) - only when resolution is "none"
        can_fast_cut = (
            self.app_state.encoding.resolution == "none" and
            not self.app_state.filters.deinterlace and
            not self.app_state.filters.denoise and
            not self.app_state.eq.enabled and
            not self.app_state.subtitles.burn_subs and
            not self.app_state.filters.volume_enabled
        )
        
        # Generate segments
        segments = self.app_state.cut.get_segments(duration)
        
        self.app_state.log(f"Will create {len(segments)} segments:", "INFO")
        for i, (start, end) in enumerate(segments, 1):
            start_str = self._format_time(start)
            end_str = self._format_time(end)
            self.app_state.log(f"  Segment {i}: {start_str} - {end_str}", "INFO")
        
        # Generate output paths for all segments
        import os
        from pathlib import Path
        base_name = Path(input_file).stem
        output_folder = self.app_state.output_folder or os.path.dirname(input_file)
        container = self.app_state.encoding.container
        
        # Encode each segment
        all_success = True
        for i, (seg_start, seg_end) in enumerate(segments, 1):
            # Generate output path with part number
            output_path = os.path.join(output_folder, f"{base_name}_part{i:02d}.{container}")
            
            # Check for existing file and append counter if needed
            counter = 1
            original_output = output_path
            while os.path.exists(output_path):
                output_path = os.path.join(output_folder, f"{base_name}_part{i:02d}_{counter}.{container}")
                counter += 1
            
            duration_sec = seg_end - seg_start
            
            self.app_state.log(f"Processing segment {i}/{len(segments)}: {self._format_time(seg_start)} - {self._format_time(seg_end)}", "INFO")
            
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
                self.app_state.log(f"Failed to process segment {i}", "ERROR")
                all_success = False
                break
        
        if all_success:
            self.app_state.log(f"Successfully created {len(segments)} segments!", "SUCCESS")
            # Clear cuts after successful execution
            self.on_clear_all_cuts()
        else:
            self.app_state.log("Cut execution failed", "ERROR")
    
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
        
    def set_video(self, video_path: str):
        """Set the current video"""
        self.preview.set_video(video_path)
        self.trim_panel.detect_tracks(video_path)
