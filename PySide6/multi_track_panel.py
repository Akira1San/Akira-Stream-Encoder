"""
Multi Track Panel — consolidated audio & subtitle multi-track controls (PySide6)
"""
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QGroupBox, QListWidget, QAbstractItemView, QPushButton,
    QFileDialog, QListWidgetItem, QRadioButton, QComboBox
)
from PySide6.QtCore import Signal

from models import (
    AppState, AudioTrackInfo, AudioTrackAssignment, ExternalAudioTrack,
    SubtitleTrackAssignment, ExternalSubtitleTrack
)


class MultiTrackPanel(QGroupBox):
    """Dedicated panel for multi-track audio and subtitle management"""

    settings_changed = Signal()

    def __init__(self, app_state: AppState, parent=None):
        super().__init__("Multi Track", parent)
        self.app_state = app_state
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Audio Section ──
        audio_group = QGroupBox("Audio Tracks")
        audio_layout = QVBoxLayout(audio_group)

        self.multi_audio_check = QCheckBox("Enable Multi-Track Audio")
        self.multi_audio_check.setChecked(self.app_state.tracks.multi_track_audio_enabled)
        self.multi_audio_check.setToolTip(
            "Select multiple audio tracks to include in the output.\n"
            "Each track can be independently copied or re-encoded."
        )
        audio_layout.addWidget(self.multi_audio_check)

        self.audio_track_list = QListWidget()
        self.audio_track_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.audio_track_list.setMaximumHeight(100)
        self.audio_track_list.setToolTip("Select audio tracks. Ctrl+click for multiple.")
        self.audio_track_list.setEnabled(self.app_state.tracks.multi_track_audio_enabled)
        audio_layout.addWidget(self.audio_track_list)

        audio_btn_layout = QHBoxLayout()
        self.load_audio_btn = QPushButton("Load External Audio...")
        self.load_audio_btn.setToolTip("Load an external audio file as an additional track")
        self.load_audio_btn.setEnabled(self.app_state.tracks.multi_track_audio_enabled)
        audio_btn_layout.addWidget(self.load_audio_btn)
        self.remove_audio_btn = QPushButton("Remove Selected")
        self.remove_audio_btn.setToolTip("Remove selected external audio tracks")
        self.remove_audio_btn.setEnabled(self.app_state.tracks.multi_track_audio_enabled)
        audio_btn_layout.addWidget(self.remove_audio_btn)
        audio_btn_layout.addStretch()
        audio_layout.addLayout(audio_btn_layout)

        self.audio_copy_check = QCheckBox("Copy Audio (no re-encode)")
        self.audio_copy_check.setChecked(self.app_state.tracks.audio_copy_mode)
        self.audio_copy_check.setEnabled(self.app_state.tracks.multi_track_audio_enabled)
        audio_layout.addWidget(self.audio_copy_check)

        layout.addWidget(audio_group)

        # ── Subtitle Section ──
        sub_group = QGroupBox("Subtitle Tracks")
        sub_layout = QVBoxLayout(sub_group)

        self.multi_sub_check = QCheckBox("Enable Multi-Track Subtitles")
        self.multi_sub_check.setChecked(self.app_state.tracks.multi_track_subtitle_enabled)
        self.multi_sub_check.setToolTip(
            "Select multiple subtitle tracks to passthrough.\n"
            "Both embedded and external subtitle files can be included."
        )
        sub_layout.addWidget(self.multi_sub_check)

        self.subtitle_track_list = QListWidget()
        self.subtitle_track_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.subtitle_track_list.setMaximumHeight(100)
        self.subtitle_track_list.setToolTip("Select subtitle tracks. Ctrl+click for multiple.")
        self.subtitle_track_list.setEnabled(self.app_state.tracks.multi_track_subtitle_enabled)
        sub_layout.addWidget(self.subtitle_track_list)

        sub_btn_layout = QHBoxLayout()
        self.load_sub_btn = QPushButton("Load External Subtitle...")
        self.load_sub_btn.setToolTip("Load an external subtitle file as an additional track")
        self.load_sub_btn.setEnabled(self.app_state.tracks.multi_track_subtitle_enabled)
        sub_btn_layout.addWidget(self.load_sub_btn)
        self.remove_sub_btn = QPushButton("Remove Selected")
        self.remove_sub_btn.setToolTip("Remove selected external subtitle tracks")
        self.remove_sub_btn.setEnabled(self.app_state.tracks.multi_track_subtitle_enabled)
        sub_btn_layout.addWidget(self.remove_sub_btn)
        sub_btn_layout.addStretch()
        sub_layout.addLayout(sub_btn_layout)

        # Subtitle passthrough
        self.passthrough_check = QCheckBox("Passthrough subtitle tracks (no burn-in)")
        self.passthrough_check.setChecked(self.app_state.tracks.subtitle_passthrough)
        self.passthrough_check.setEnabled(self.app_state.tracks.multi_track_subtitle_enabled)
        sub_layout.addWidget(self.passthrough_check)

        # Burn from embedded
        burn_layout = QHBoxLayout()
        self.burn_radio = QRadioButton("Burn embedded track:")
        self.burn_radio.setEnabled(self.app_state.tracks.multi_track_subtitle_enabled)
        burn_layout.addWidget(self.burn_radio)
        self.burn_combo = QComboBox()
        self.burn_combo.setMinimumWidth(150)
        self.burn_combo.setEnabled(self.app_state.tracks.multi_track_subtitle_enabled)
        burn_layout.addWidget(self.burn_combo)
        burn_layout.addStretch()
        sub_layout.addLayout(burn_layout)

        layout.addWidget(sub_group)

    def connect_signals(self):
        """Connect UI signals to handlers"""
        self.multi_audio_check.toggled.connect(self.on_multi_audio_toggled)
        self.audio_track_list.itemSelectionChanged.connect(self.on_audio_list_changed)
        self.load_audio_btn.clicked.connect(self.on_load_external_audio)
        self.remove_audio_btn.clicked.connect(self.on_remove_external_audio)
        self.audio_copy_check.toggled.connect(self.on_audio_copy_changed)

        self.multi_sub_check.toggled.connect(self.on_multi_sub_toggled)
        self.subtitle_track_list.itemSelectionChanged.connect(self.on_sub_list_changed)
        self.load_sub_btn.clicked.connect(self.on_load_external_subtitle)
        self.remove_sub_btn.clicked.connect(self.on_remove_external_subtitle)
        self.passthrough_check.toggled.connect(self.on_passthrough_changed)
        self.burn_radio.toggled.connect(self.on_burn_radio_toggled)
        self.burn_combo.currentIndexChanged.connect(self.on_burn_combo_changed)

    # ── Audio handlers ──

    def on_multi_audio_toggled(self, checked):
        self.app_state.tracks.multi_track_audio_enabled = checked
        self.audio_track_list.setEnabled(checked)
        self.load_audio_btn.setEnabled(checked)
        self.remove_audio_btn.setEnabled(checked)
        self.audio_copy_check.setEnabled(checked)
        if checked:
            self._rebuild_audio_track_list()
        self.settings_changed.emit()

    def on_audio_list_changed(self):
        selected_items = self.audio_track_list.selectedItems()
        selected_indices = []
        assignments = []
        for item in selected_items:
            data = item.data(256)
            if data is None:
                continue
            track_type, track_idx = data
            selected_indices.append(len(assignments))
            assignments.append(AudioTrackAssignment(
                stream_index=track_idx,
                mode="copy" if self.app_state.tracks.audio_copy_mode else "encode",
                is_external=(track_type == 1)
            ))
        self.app_state.tracks.selected_audio_indices = selected_indices
        self.app_state.tracks.audio_track_assignments = assignments
        self.settings_changed.emit()

    def on_load_external_audio(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select External Audio File", "",
            "Audio Files (*.mp3 *.aac *.wav *.flac *.ogg *.m4a *.ac3 *.wma);;All Files (*)"
        )
        if not file_path:
            return
        try:
            info = self.app_state.backend.get_external_audio_info(file_path)
            ext_track = ExternalAudioTrack(
                file_path=file_path,
                codec=info.get('codec', 'unknown') if info else 'unknown',
                channels=info.get('channels', 2) if info else 2,
                sample_rate=info.get('sample_rate', '') if info else '',
                title=os.path.basename(file_path)
            )
        except Exception:
            ext_track = ExternalAudioTrack(file_path=file_path, title=os.path.basename(file_path))
        self.app_state.tracks.external_audio_tracks.append(ext_track)
        self._rebuild_audio_track_list()
        total = len(self.app_state.tracks.available_audio_tracks) + len(self.app_state.tracks.external_audio_tracks)
        self.audio_track_list.item(total - 1).setSelected(True)
        self.settings_changed.emit()

    def on_remove_external_audio(self):
        indices_to_remove = []
        for item in self.audio_track_list.selectedItems():
            data = item.data(256)
            if data is not None and data[0] == 1:
                indices_to_remove.append(data[1])
        for idx in sorted(indices_to_remove, reverse=True):
            if 0 <= idx < len(self.app_state.tracks.external_audio_tracks):
                del self.app_state.tracks.external_audio_tracks[idx]
        self.app_state.tracks.selected_audio_indices = []
        self.app_state.tracks.audio_track_assignments = []
        self._rebuild_audio_track_list()
        self.settings_changed.emit()

    def on_audio_copy_changed(self, checked):
        self.app_state.tracks.audio_copy_mode = checked
        for assignment in self.app_state.tracks.audio_track_assignments:
            assignment.mode = "copy" if checked else "encode"
        self.settings_changed.emit()

    # ── Subtitle handlers ──

    def on_multi_sub_toggled(self, checked):
        self.app_state.tracks.multi_track_subtitle_enabled = checked
        self.subtitle_track_list.setEnabled(checked)
        self.load_sub_btn.setEnabled(checked)
        self.remove_sub_btn.setEnabled(checked)
        self.passthrough_check.setEnabled(checked)
        self.burn_radio.setEnabled(checked)
        self.burn_combo.setEnabled(checked)
        if checked:
            self._rebuild_subtitle_track_list()
            self._rebuild_burn_combo()
        self.settings_changed.emit()

    def on_sub_list_changed(self):
        selected_items = self.subtitle_track_list.selectedItems()
        selected_indices = []
        assignments = []
        for item in selected_items:
            data = item.data(256)
            if data is None:
                continue
            track_type, track_idx = data
            selected_indices.append(len(assignments))
            assignments.append(SubtitleTrackAssignment(
                stream_index=track_idx,
                is_external=(track_type == 1),
                mode="copy"
            ))
        self.app_state.tracks.selected_subtitle_indices = selected_indices
        self.app_state.tracks.subtitle_track_assignments = assignments
        self.settings_changed.emit()

    def on_load_external_subtitle(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select External Subtitle File", "",
            "Subtitle Files (*.srt *.ass *.ssa *.sub);;All Files (*)"
        )
        if not file_path:
            return
        ext_track = ExternalSubtitleTrack(
            file_path=file_path,
            codec="subrip" if file_path.endswith('.srt') else "ass" if file_path.endswith(('.ass', '.ssa')) else "subrip",
            title=os.path.basename(file_path)
        )
        self.app_state.tracks.external_subtitle_tracks.append(ext_track)
        self._rebuild_subtitle_track_list()
        total = len(self.app_state.tracks.available_subtitle_tracks) + len(self.app_state.tracks.external_subtitle_tracks)
        self.subtitle_track_list.item(total - 1).setSelected(True)
        self.settings_changed.emit()

    def on_remove_external_subtitle(self):
        indices_to_remove = []
        for item in self.subtitle_track_list.selectedItems():
            data = item.data(256)
            if data is not None and data[0] == 1:
                indices_to_remove.append(data[1])
        for idx in sorted(indices_to_remove, reverse=True):
            if 0 <= idx < len(self.app_state.tracks.external_subtitle_tracks):
                del self.app_state.tracks.external_subtitle_tracks[idx]
        self.app_state.tracks.selected_subtitle_indices = []
        self.app_state.tracks.subtitle_track_assignments = []
        self._rebuild_subtitle_track_list()
        self.settings_changed.emit()

    def on_passthrough_changed(self, checked):
        self.app_state.tracks.subtitle_passthrough = checked
        self.settings_changed.emit()

    def on_burn_radio_toggled(self, checked):
        if checked:
            idx = self.burn_combo.currentData()
            if idx is not None and idx >= 0:
                self.app_state.tracks.subtitle_burn_index = idx
                self.settings_changed.emit()

    def on_burn_combo_changed(self, index):
        if index >= 0:
            data = self.burn_combo.itemData(index)
            if data is not None:
                self.app_state.tracks.subtitle_burn_index = data
                if data >= 0:
                    self.burn_radio.setChecked(True)
                self.settings_changed.emit()

    # ── Rebuild helpers ──

    def _rebuild_audio_track_list(self):
        self.audio_track_list.clear()
        for i, track in enumerate(self.app_state.tracks.available_audio_tracks):
            display = f"[Embedded] Track {i+1}"
            if track.language:
                display += f" [{track.language}]"
            if track.title:
                display += f" - {track.title}"
            display += f" ({track.codec}, {track.channels}ch)"
            if track.sample_rate:
                display += f", {track.sample_rate}Hz"
            item = QListWidgetItem(display)
            item.setData(256, (0, i))
            self.audio_track_list.addItem(item)
        for i, track in enumerate(self.app_state.tracks.external_audio_tracks):
            display = f"[External] {track.title}"
            if track.codec:
                display += f" ({track.codec}, {track.channels}ch)"
                if track.sample_rate:
                    display += f", {track.sample_rate}Hz"
            item = QListWidgetItem(display)
            item.setData(256, (1, i))
            self.audio_track_list.addItem(item)
        self._sync_audio_selection()

    def _sync_audio_selection(self):
        assignments = self.app_state.tracks.audio_track_assignments
        selected_embedded = {a.stream_index for a in assignments if not a.is_external}
        selected_external = {a.stream_index for a in assignments if a.is_external}
        for i in range(self.audio_track_list.count()):
            item = self.audio_track_list.item(i)
            data = item.data(256)
            if data is not None:
                tt, ti = data
                item.setSelected(ti in (selected_embedded if tt == 0 else selected_external))

    def _rebuild_subtitle_track_list(self):
        self.subtitle_track_list.clear()
        for i, track in enumerate(self.app_state.tracks.available_subtitle_tracks):
            display = f"[Embedded] Track {i+1}"
            if track.language:
                display += f" [{track.language}]"
            if track.title:
                display += f" - {track.title}"
            display += f" ({track.codec})"
            item = QListWidgetItem(display)
            item.setData(256, (0, i))
            self.subtitle_track_list.addItem(item)
        for i, track in enumerate(self.app_state.tracks.external_subtitle_tracks):
            display = f"[External] {track.title} ({track.codec})"
            item = QListWidgetItem(display)
            item.setData(256, (1, i))
            self.subtitle_track_list.addItem(item)
        self._sync_sub_selection()

    def _sync_sub_selection(self):
        assignments = self.app_state.tracks.subtitle_track_assignments
        selected_embedded = {a.stream_index for a in assignments if not a.is_external}
        selected_external = {a.stream_index for a in assignments if a.is_external}
        for i in range(self.subtitle_track_list.count()):
            item = self.subtitle_track_list.item(i)
            data = item.data(256)
            if data is not None:
                tt, ti = data
                item.setSelected(ti in (selected_embedded if tt == 0 else selected_external))

    def _rebuild_burn_combo(self):
        self.burn_combo.blockSignals(True)
        self.burn_combo.clear()
        self.burn_combo.addItem("None (use external file)", -1)
        for i, track in enumerate(self.app_state.tracks.available_subtitle_tracks):
            display = f"Track {i+1}"
            if track.language:
                display += f" [{track.language}]"
            display += f" ({track.codec})"
            self.burn_combo.addItem(display, i)
        burn_idx = self.app_state.tracks.subtitle_burn_index
        for i in range(self.burn_combo.count()):
            if self.burn_combo.itemData(i) == burn_idx:
                self.burn_combo.setCurrentIndex(i)
                break
        self.burn_combo.blockSignals(False)

    # ── External sync helpers (called from video_workspace) ──

    def populate_audio_tracks(self, tracks: list):
        """Populate audio track lists (called when video loads)"""
        self._rebuild_audio_track_list()
        self._sync_audio_selection()

    def populate_subtitle_tracks(self, tracks: list):
        """Populate subtitle track lists (called when video loads)"""
        self._rebuild_subtitle_track_list()
        self._sync_sub_selection()
        self._rebuild_burn_combo()
