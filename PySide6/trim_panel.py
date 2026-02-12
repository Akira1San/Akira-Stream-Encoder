"""
Trim/Cut Panel (PySide6)
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QMessageBox, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Signal, Qt

from models import AppState, CutPoint


class TrimPanel(QGroupBox):
    """Panel for trim/cut operations"""
    
    cut_point_set = Signal(float)
    execute_cut = Signal()
    cut_removed = Signal(str)  # cut_id
    clear_all_cuts = Signal()
    
    def __init__(self, app_state: AppState, get_timeline_position_callback=None, parent=None):
        super().__init__("Trim/Cut Video", parent)
        self.app_state = app_state
        self.get_timeline_position = get_timeline_position_callback
        
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)
        
        # Cut List Header
        header_layout = QHBoxLayout()
        self.cuts_count_label = QLabel("Cuts: 0")
        self.cuts_count_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(self.cuts_count_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Cut Points List
        self.cuts_list = QListWidget()
        self.cuts_list.setMaximumHeight(150)
        self.cuts_list.setToolTip("Click on a cut to jump to that position")
        layout.addWidget(self.cuts_list)
        
        # Segment Info Label
        self.segments_label = QLabel("No segments defined")
        self.segments_label.setStyleSheet("color: gray; font-size: 11px;")
        self.segments_label.setWordWrap(True)
        layout.addWidget(self.segments_label)
        
        # Buttons Layout
        btn_layout = QHBoxLayout()
        
        self.set_cut_btn = QPushButton("Add Cut Point")
        self.set_cut_btn.setToolTip("Add cut at current timeline position")
        self.set_cut_btn.clicked.connect(self.on_set_cut_clicked)
        btn_layout.addWidget(self.set_cut_btn)
        
        self.delete_cut_btn = QPushButton("Delete Selected")
        self.delete_cut_btn.setToolTip("Delete the selected cut point")
        self.delete_cut_btn.setEnabled(False)
        self.delete_cut_btn.clicked.connect(self.on_delete_cut_clicked)
        btn_layout.addWidget(self.delete_cut_btn)
        
        self.clear_all_btn = QPushButton("Clear All")
        self.clear_all_btn.setToolTip("Remove all cut points")
        self.clear_all_btn.setEnabled(False)
        self.clear_all_btn.clicked.connect(self.on_clear_all_clicked)
        btn_layout.addWidget(self.clear_all_btn)
        
        layout.addLayout(btn_layout)
        
        # Execute Button
        self.execute_btn = QPushButton("Execute Cuts")
        self.execute_btn.setToolTip("Split video at all cut points")
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
        # Get current timeline position from callback
        if self.get_timeline_position:
            position = self.get_timeline_position()
            if position is not None and position > 0:
                self.cut_point_set.emit(position)
        else:
            # Fallback to app_state if no callback provided
            position = 0
            if hasattr(self.app_state, 'cut') and self.app_state.cut.points:
                # This shouldn't happen, but just in case
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
        reply = QMessageBox.question(
            self, 
            "Clear All Cuts",
            f"Are you sure you want to remove all {len(self.app_state.cut.points)} cut points?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.clear_all_cuts.emit()
    
    def on_execute_clicked(self):
        """Handle execute cut button click"""
        if not self.app_state.cut.points:
            QMessageBox.warning(self, "No Cuts", "Please add at least one cut point first.")
            return
        self.execute_cut.emit()
    
    def on_cut_selected(self, item):
        """Handle cut selection in list"""
        # Could emit signal to jump to this position in timeline
        pass
    
    def on_selection_changed(self):
        """Handle selection change in list"""
        has_selection = self.cuts_list.currentItem() is not None
        self.delete_cut_btn.setEnabled(has_selection)
    
    def add_cut_to_list(self, cut_point: CutPoint, segment_info: str = ""):
        """Add a cut point to the visual list"""
        # Format display text
        if segment_info:
            display_text = f"Cut {len(self.app_state.cut.points)}: {cut_point.time_display} ({segment_info})"
        else:
            display_text = f"Cut {len(self.app_state.cut.points)}: {cut_point.time_display}"
        
        item = QListWidgetItem(display_text)
        item.setData(256, cut_point.cut_id)  # Qt.UserRole = 256
        self.cuts_list.addItem(item)
        
        # Update UI
        self.update_ui_state()
    
    def remove_cut_from_list(self, cut_id: str):
        """Remove a cut point from the visual list"""
        for i in range(self.cuts_list.count()):
            item = self.cuts_list.item(i)
            if item and item.data(256) == cut_id:  # Qt.UserRole = 256
                self.cuts_list.takeItem(i)
                break
        
        # Renumber remaining items
        self.renumber_cuts()
        self.update_ui_state()
    
    def clear_all_cuts_from_list(self):
        """Clear all cuts from the visual list"""
        self.cuts_list.clear()
        self.update_ui_state()
    
    def renumber_cuts(self):
        """Renumber cut items after deletion"""
        for i in range(self.cuts_list.count()):
            item = self.cuts_list.item(i)
            if item:
                text = item.text()
                # Replace "Cut N:" with new number
                import re
                new_text = re.sub(r'Cut \d+:', f'Cut {i+1}:', text)
                item.setText(new_text)
    
    def update_segments_info(self, segments: list):
        """Update the segments info label"""
        if not segments or len(segments) <= 1:
            self.segments_label.setText("No segments defined")
            return
        
        info_lines = [f"Will create {len(segments)} segments:"]
        for i, (start, end) in enumerate(segments, 1):
            # Format times
            start_str = self._format_time(start)
            end_str = self._format_time(end)
            duration = end - start
            duration_str = self._format_time(duration, show_hours=False)
            info_lines.append(f"  Part {i}: {start_str} - {end_str} (duration: {duration_str})")
        
        self.segments_label.setText("\n".join(info_lines))
    
    def _format_time(self, seconds: float, show_hours: bool = True) -> str:
        """Format seconds as time string"""
        mins, secs = divmod(int(seconds), 60)
        hours = mins // 60
        mins = mins % 60
        
        if hours > 0 and show_hours:
            return f"{hours}:{mins:02d}:{secs:02d}"
        else:
            return f"{mins:02d}:{secs:02d}"
    
    def update_ui_state(self):
        """Update UI elements based on current state"""
        cut_count = len(self.app_state.cut.points)
        
        # Update count label
        self.cuts_count_label.setText(f"Cuts: {cut_count}")
        
        # Enable/disable buttons
        self.clear_all_btn.setEnabled(cut_count > 0)
        self.execute_btn.setEnabled(cut_count > 0)
        
        # Delete button depends on selection
        has_selection = self.cuts_list.currentItem() is not None
        self.delete_cut_btn.setEnabled(has_selection and cut_count > 0)
    
    def select_cut_by_id(self, cut_id: str):
        """Select a cut in the list by its ID"""
        for i in range(self.cuts_list.count()):
            item = self.cuts_list.item(i)
            if item and item.data(256) == cut_id:  # Qt.UserRole = 256
                self.cuts_list.setCurrentItem(item)
                # Scroll to make it visible
                self.cuts_list.scrollToItem(item)
                break
        
    def detect_tracks(self, video_path: str):
        """Detect tracks for the current video"""
        pass  # Tracks are handled by TrackSelectionPanel
