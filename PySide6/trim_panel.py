"""
Trim/Cut Panel (PySide6)
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QMessageBox, QCheckBox, QListWidget, QListWidgetItem, QFrame
)
from PySide6.QtCore import Signal, Qt

from models import AppState, CutPoint


class TrimPanel(QGroupBox):
    """Panel for trim/cut operations"""
    
    cut_point_set = Signal(float)
    execute_cuts = Signal(list)  # List of (start, end, segment_name) tuples to encode
    cut_removed = Signal(str)  # cut_id
    clear_all_cuts = Signal()
    
    def __init__(self, app_state: AppState, get_timeline_position_callback=None, parent=None):
        super().__init__("Trim/Cut Video", parent)
        self.app_state = app_state
        self.get_timeline_position = get_timeline_position_callback
        self.segment_checkboxes = []  # Store checkbox references
        
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)
        
        # === Cuts Section ===
        cuts_header = QHBoxLayout()
        self.cuts_count_label = QLabel("Cuts: 0")
        self.cuts_count_label.setStyleSheet("font-weight: bold;")
        cuts_header.addWidget(self.cuts_count_label)
        cuts_header.addStretch()
        layout.addLayout(cuts_header)
        
        # Cut Points List
        self.cuts_list = QListWidget()
        self.cuts_list.setMaximumHeight(100)
        self.cuts_list.setToolTip("Click on a cut to jump to that position")
        layout.addWidget(self.cuts_list)
        
        # Cut Buttons
        cut_btn_layout = QHBoxLayout()
        self.set_cut_btn = QPushButton("Add Cut Point")
        self.set_cut_btn.setToolTip("Add cut at current timeline position")
        self.set_cut_btn.clicked.connect(self.on_set_cut_clicked)
        cut_btn_layout.addWidget(self.set_cut_btn)
        
        self.delete_cut_btn = QPushButton("Delete")
        self.delete_cut_btn.setToolTip("Delete the selected cut point")
        self.delete_cut_btn.setEnabled(False)
        self.delete_cut_btn.clicked.connect(self.on_delete_cut_clicked)
        cut_btn_layout.addWidget(self.delete_cut_btn)
        
        self.clear_all_btn = QPushButton("Clear All")
        self.clear_all_btn.setToolTip("Remove all cut points")
        self.clear_all_btn.setEnabled(False)
        self.clear_all_btn.clicked.connect(self.on_clear_all_clicked)
        cut_btn_layout.addWidget(self.clear_all_btn)
        
        layout.addLayout(cut_btn_layout)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # === Segments Section ===
        segments_header = QHBoxLayout()
        self.segments_count_label = QLabel("Parts to Export: 0")
        self.segments_count_label.setStyleSheet("font-weight: bold;")
        segments_header.addWidget(self.segments_count_label)
        segments_header.addStretch()
        layout.addLayout(segments_header)
        
        # Segment List with Checkboxes
        self.segments_list = QListWidget()
        self.segments_list.setMaximumHeight(150)
        self.segments_list.setToolTip("Check/uncheck which parts to export")
        layout.addWidget(self.segments_list)
        
        # Segment Buttons
        segment_btn_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setToolTip("Select all parts for export")
        self.select_all_btn.setEnabled(False)
        self.select_all_btn.clicked.connect(self.on_select_all_clicked)
        segment_btn_layout.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.setToolTip("Deselect all parts")
        self.deselect_all_btn.setEnabled(False)
        self.deselect_all_btn.clicked.connect(self.on_deselect_all_clicked)
        segment_btn_layout.addWidget(self.deselect_all_btn)
        
        segment_btn_layout.addStretch()
        layout.addLayout(segment_btn_layout)
        
        # Export Button
        self.execute_btn = QPushButton("Export Cut Parts")
        self.execute_btn.setToolTip("Export selected parts as separate files")
        self.execute_btn.setEnabled(False)
        self.execute_btn.clicked.connect(self.on_execute_clicked)
        layout.addWidget(self.execute_btn)
        
        layout.addStretch()
        
    def connect_signals(self):
        """Connect UI signals"""
        self.cuts_list.itemClicked.connect(self.on_cut_selected)
        self.cuts_list.itemSelectionChanged.connect(self.on_selection_changed)
        
    def on_set_cut_clicked(self):
        """Handle add cut point button click"""
        if self.get_timeline_position:
            position = self.get_timeline_position()
            if position is not None and position > 0:
                self.cut_point_set.emit(position)
        else:
            position = 0
            if hasattr(self.app_state, 'cut') and self.app_state.cut.points:
                pass
            self.cut_point_set.emit(position)
    
    def on_delete_cut_clicked(self):
        """Handle delete selected cut button"""
        current_item = self.cuts_list.currentItem()
        if current_item:
            cut_id = current_item.data(256)  # Qt.UserRole = 256
            self.cut_removed.emit(cut_id)
    
    def on_clear_all_clicked(self):
        """Handle clear all cuts button with confirmation"""
        if self.app_state.cut.points:
            reply = QMessageBox.question(
                self, 
                "Clear All Cuts",
                f"Are you sure you want to remove all {len(self.app_state.cut.points)} cut points?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.clear_all_cuts.emit()
    
    def on_select_all_clicked(self):
        """Select all segments for export"""
        for i in range(self.segments_list.count()):
            item = self.segments_list.item(i)
            checkbox = self.segments_list.itemWidget(item)
            if checkbox:
                checkbox.setChecked(True)
        self._update_segments_count()
    
    def on_deselect_all_clicked(self):
        """Deselect all segments"""
        for i in range(self.segments_list.count()):
            item = self.segments_list.item(i)
            checkbox = self.segments_list.itemWidget(item)
            if checkbox:
                checkbox.setChecked(False)
        self._update_segments_count()
    
    def on_execute_clicked(self):
        """Handle start encoding button click"""
        # Build list of selected segments
        segments_to_encode = []
        
        for i in range(self.segments_list.count()):
            item = self.segments_list.item(i)
            checkbox = self.segments_list.itemWidget(item)
            if checkbox and checkbox.isChecked():
                segment_data = item.data(256)  # Qt.UserRole = 256
                if segment_data:
                    segments_to_encode.append(segment_data)
        
        if not segments_to_encode:
            QMessageBox.warning(self, "No Parts Selected", "Please select at least one part to encode.")
            return
        
        self.execute_cuts.emit(segments_to_encode)
    
    def on_cut_selected(self, item):
        """Handle cut selection in list"""
        pass
    
    def on_selection_changed(self):
        """Handle selection change in list"""
        has_selection = self.cuts_list.currentItem() is not None
        self.delete_cut_btn.setEnabled(has_selection)
    
    def add_cut_to_list(self, cut_point: CutPoint, segment_info: str = ""):
        """Add a cut point to the visual list"""
        display_text = f"Cut: {cut_point.time_display}"
        
        item = QListWidgetItem(display_text)
        item.setData(256, cut_point.cut_id)  # Qt.UserRole = 256
        self.cuts_list.addItem(item)
        
        self.update_ui_state()
        self._update_segments_list()
    
    def remove_cut_from_list(self, cut_id: str):
        """Remove a cut point from the visual list"""
        for i in range(self.cuts_list.count()):
            item = self.cuts_list.item(i)
            if item and item.data(256) == cut_id:
                self.cuts_list.takeItem(i)
                break
        
        self._renumber_cuts()
        self.update_ui_state()
        self._update_segments_list()
    
    def clear_all_cuts_from_list(self):
        """Clear all cuts from the visual list"""
        self.cuts_list.clear()
        self._update_segments_list()
        self.update_ui_state()
    
    def _renumber_cuts(self):
        """Renumber cut items after deletion"""
        for i in range(self.cuts_list.count()):
            item = self.cuts_list.item(i)
            if item:
                text = item.text()
                import re
                new_text = re.sub(r'Cut \d+:', f'Cut {i+1}:', text)
                item.setText(new_text)
    
    def _update_segments_list(self):
        """Update the segments list with checkboxes"""
        self.segments_list.clear()
        self.segment_checkboxes = []
        
        if not self.app_state.cut.points:
            self.segments_list.addItem("Add cuts to see parts")
            self.select_all_btn.setEnabled(False)
            self.deselect_all_btn.setEnabled(False)
            self.execute_btn.setEnabled(False)
            self.segments_count_label.setText("Parts to Export: 0")
            return
        
        # Get segments from cut points
        sorted_cuts = self.app_state.cut.get_sorted_points()
        
        # Generate segments (start, end) pairs
        segments = []
        start = 0.0
        
        for cut in sorted_cuts:
            segments.append((start, cut.position))
            start = cut.position
        
        # Final segment to end (use placeholder duration, will be updated when encoding)
        segments.append((start, -1))  # -1 means "end of video"
        
        # Add segments to list with checkboxes
        for i, (seg_start, seg_end) in enumerate(segments, 1):
            start_str = self._format_time(seg_start)
            if seg_end == -1:
                end_str = "End"
                duration_str = "?"
            else:
                end_str = self._format_time(seg_end)
                duration = seg_end - seg_start
                duration_str = self._format_time(duration)
            
            display_text = f"Part {i:02d}: {start_str} - {end_str} ({duration_str})"
            
            item = QListWidgetItem()
            checkbox = QCheckBox(display_text)
            checkbox.setChecked(True)  # Default: all selected
            checkbox.stateChanged.connect(self._on_segment_checkbox_changed)
            
            self.segments_list.addItem(item)
            self.segments_list.setItemWidget(item, checkbox)
            self.segment_checkboxes.append(checkbox)
            
            # Store segment data
            item.setData(256, (seg_start, seg_end, f"Part {i:02d}"))  # Qt.UserRole = 256
        
        self.select_all_btn.setEnabled(True)
        self.deselect_all_btn.setEnabled(True)
        self.execute_btn.setEnabled(True)
        
        self._update_segments_count()
    
    def _on_segment_checkbox_changed(self, state):
        """Handle segment checkbox state change"""
        self._update_segments_count()
    
    def _update_segments_count(self):
        """Update the segments count label"""
        checked_count = sum(1 for cb in self.segment_checkboxes if cb.isChecked())
        total = len(self.segment_checkboxes)
        self.segments_count_label.setText(f"Parts to Export: {checked_count}/{total}")
    
    def _format_time(self, seconds: float, show_hours: bool = True) -> str:
        """Format seconds as time string"""
        if seconds < 0:
            return "End"
        
        secs = int(seconds)
        mins, secs = divmod(secs, 60)
        hours = mins // 60
        mins = mins % 60
        
        if hours > 0 and show_hours:
            return f"{hours}:{mins:02d}:{secs:02d}"
        else:
            return f"{mins:02d}:{secs:02d}"
    
    def update_ui_state(self):
        """Update UI elements based on current state"""
        cut_count = len(self.app_state.cut.points)
        
        # Update cuts count label
        self.cuts_count_label.setText(f"Cuts: {cut_count}")
        
        # Enable/disable buttons
        self.clear_all_btn.setEnabled(cut_count > 0)
    
    def select_cut_by_id(self, cut_id: str):
        """Select a cut in the list by its ID"""
        for i in range(self.cuts_list.count()):
            item = self.cuts_list.item(i)
            if item and item.data(256) == cut_id:
                self.cuts_list.setCurrentItem(item)
                self.cuts_list.scrollToItem(item)
                break
        
    def detect_tracks(self, video_path: str):
        """Detect tracks for the current video"""
        pass
