"""
Track Selection Panel (PySide6)
"""
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QGroupBox, QComboBox, QFrame, QListWidget, QAbstractItemView,
    QPushButton, QFileDialog
)
from PySide6.QtCore import Signal

from models import AppState, AudioTrackInfo, AudioTrackAssignment, ExternalAudioTrack, SubtitleTrackAssignment, ExternalSubtitleTrack


class TrackSelectionPanel(QGroupBox):
    """Panel for selecting video/audio/subtitle tracks"""

    tracks_changed = Signal()

    def __init__(self, app_state: AppState, parent=None):
        super().__init__("Track Selection", parent)
        self.app_state = app_state
        self.current_video_path = None

        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)

        # Video Track
        video_layout = QHBoxLayout()
        self.video_check = QCheckBox("Video Track")
        self.video_check.setChecked(self.app_state.tracks.video_selected)
        video_layout.addWidget(self.video_check)

        self.video_info_label = QLabel(self.app_state.tracks.video_info)
        self.video_info_label.setStyleSheet("color: gray;")
        video_layout.addWidget(self.video_info_label)
        video_layout.addStretch()
        layout.addLayout(video_layout)

        # Separator line
        line1 = QFrame()
        line1.setFrameShape(QFrame.HLine)
        line1.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line1)

        # Audio Track Section
        audio_section_layout = QVBoxLayout()

        # Audio enable checkbox
        audio_enable_layout = QHBoxLayout()
        self.audio_check = QCheckBox("Audio Track")
        self.audio_check.setChecked(self.app_state.tracks.audio_selected)
        audio_enable_layout.addWidget(self.audio_check)

        self.audio_info_label = QLabel(self.app_state.tracks.audio_info)
        self.audio_info_label.setStyleSheet("color: gray;")
        audio_enable_layout.addWidget(self.audio_info_label)
        audio_enable_layout.addStretch()
        audio_section_layout.addLayout(audio_enable_layout)

        # Multi-track audio toggle
        multi_track_layout = QHBoxLayout()
        multi_track_layout.addSpacing(25)
        self.multi_track_check = QCheckBox("Enable Multi-Track Audio")
        self.multi_track_check.setChecked(self.app_state.tracks.multi_track_audio_enabled)
        self.multi_track_check.setToolTip(
            "When enabled, you can select multiple audio tracks to include in the output.\n"
            "Each track can be independently copied or re-encoded."
        )
        multi_track_layout.addWidget(self.multi_track_check)
        multi_track_layout.addStretch()
        audio_section_layout.addLayout(multi_track_layout)

        # Audio track selection (single dropdown for default mode)
        audio_track_layout = QHBoxLayout()
        audio_track_layout.addSpacing(25)  # Indent
        audio_track_layout.addWidget(QLabel("Select Track:"))

        self.audio_track_combo = QComboBox()
        self.audio_track_combo.setMinimumWidth(250)
        self.audio_track_combo.setEnabled(False)
        self.audio_track_combo.setToolTip("Select which audio track to use from the source video")
        audio_track_layout.addWidget(self.audio_track_combo)
        audio_track_layout.addStretch()
        audio_section_layout.addLayout(audio_track_layout)

        # Audio track multi-select list (for multi-track mode)
        self.audio_track_list = QListWidget()
        self.audio_track_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.audio_track_list.setMaximumHeight(120)
        self.audio_track_list.setMinimumWidth(300)
        self.audio_track_list.setToolTip("Select audio tracks to include. Ctrl+click to select multiple.")
        self.audio_track_list.setVisible(False)
        audio_section_layout.addWidget(self.audio_track_list)

        # Load external audio button (multi-track mode)
        load_ext_layout = QHBoxLayout()
        load_ext_layout.addSpacing(25)
        self.load_audio_btn = QPushButton("Load External Audio...")
        self.load_audio_btn.setToolTip("Load an external audio file as an additional track")
        self.load_audio_btn.setVisible(False)
        load_ext_layout.addWidget(self.load_audio_btn)
        load_ext_layout.addStretch()
        audio_section_layout.addLayout(load_ext_layout)

        # Audio copy mode checkbox
        audio_copy_layout = QHBoxLayout()
        audio_copy_layout.addSpacing(25)  # Indent
        self.audio_copy_check = QCheckBox("Copy Original Audio (no re-encode)")
        self.audio_copy_check.setChecked(self.app_state.tracks.audio_copy_mode)
        self.audio_copy_check.setEnabled(False)
        self.audio_copy_check.setToolTip("Copy the original audio stream without re-encoding.\nFaster processing and preserves original quality.")
        audio_copy_layout.addWidget(self.audio_copy_check)
        audio_copy_layout.addStretch()
        audio_section_layout.addLayout(audio_copy_layout)

        layout.addLayout(audio_section_layout)

        # Separator line
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line2)

        # Subtitle Track (hidden if not available)
        subtitle_section_layout = QVBoxLayout()

        subtitle_enable_layout = QHBoxLayout()
        self.subtitle_check = QCheckBox("Subtitle Track")
        self.subtitle_check.setChecked(self.app_state.tracks.subtitle_selected)
        subtitle_enable_layout.addWidget(self.subtitle_check)

        self.subtitle_info_label = QLabel(self.app_state.tracks.subtitle_info)
        self.subtitle_info_label.setStyleSheet("color: gray;")
        subtitle_enable_layout.addWidget(self.subtitle_info_label)
        subtitle_enable_layout.addStretch()
        subtitle_section_layout.addLayout(subtitle_enable_layout)

        # Subtitle multi-track toggle
        multi_sub_layout = QHBoxLayout()
        multi_sub_layout.addSpacing(25)
        self.multi_sub_check = QCheckBox("Enable Multi-Track Subtitles")
        self.multi_sub_check.setChecked(self.app_state.tracks.multi_track_subtitle_enabled)
        self.multi_sub_check.setToolTip(
            "When enabled, you can select multiple subtitle tracks to passthrough.\n"
            "Both embedded and external subtitle files can be included."
        )
        multi_sub_layout.addWidget(self.multi_sub_check)
        multi_sub_layout.addStretch()
        subtitle_section_layout.addLayout(multi_sub_layout)

        # Subtitle multi-select list
        self.subtitle_track_list = QListWidget()
        self.subtitle_track_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.subtitle_track_list.setMaximumHeight(100)
        self.subtitle_track_list.setMinimumWidth(300)
        self.subtitle_track_list.setToolTip("Select subtitle tracks to passthrough. Ctrl+click to select multiple.")
        self.subtitle_track_list.setVisible(False)
        subtitle_section_layout.addWidget(self.subtitle_track_list)

        # Load external subtitle button
        load_ext_sub_layout = QHBoxLayout()
        load_ext_sub_layout.addSpacing(25)
        self.load_sub_btn = QPushButton("Load External Subtitle...")
        self.load_sub_btn.setToolTip("Load an external subtitle file as an additional track")
        self.load_sub_btn.setVisible(False)
        load_ext_sub_layout.addWidget(self.load_sub_btn)
        load_ext_sub_layout.addStretch()
        subtitle_section_layout.addLayout(load_ext_sub_layout)

        self.subtitle_widget = QWidget()
        self.subtitle_widget.setLayout(subtitle_section_layout)
        layout.addWidget(self.subtitle_widget)
        self.subtitle_widget.setVisible(self.app_state.tracks.subtitle_available)

    def connect_signals(self):
        """Connect UI signals to handlers"""
        self.video_check.toggled.connect(self.on_video_changed)
        self.audio_check.toggled.connect(self.on_audio_changed)
        self.multi_track_check.toggled.connect(self.on_multi_track_toggled)
        self.audio_track_combo.currentIndexChanged.connect(self.on_audio_track_changed)
        self.audio_track_list.itemSelectionChanged.connect(self.on_audio_track_list_changed)
        self.audio_copy_check.toggled.connect(self.on_audio_copy_changed)
        self.load_audio_btn.clicked.connect(self.on_load_external_audio)
        self.subtitle_check.toggled.connect(self.on_subtitle_changed)
        self.multi_sub_check.toggled.connect(self.on_multi_sub_toggled)
        self.subtitle_track_list.itemSelectionChanged.connect(self.on_subtitle_track_list_changed)
        self.load_sub_btn.clicked.connect(self.on_load_external_subtitle)

    def on_video_changed(self, checked):
        """Handle video track checkbox change"""
        self.app_state.tracks.video_selected = checked
        self.tracks_changed.emit()

    def on_audio_changed(self, checked):
        """Handle audio track checkbox change"""
        self.app_state.tracks.audio_selected = checked
        has_tracks = self.audio_track_combo.count() > 0
        self.audio_track_combo.setEnabled(checked and has_tracks and not self.app_state.tracks.multi_track_audio_enabled)
        self.audio_track_list.setEnabled(checked and self.app_state.tracks.multi_track_audio_enabled)
        self.audio_copy_check.setEnabled(checked)
        self.tracks_changed.emit()

    def on_multi_track_toggled(self, checked):
        """Handle multi-track audio toggle"""
        self.app_state.tracks.multi_track_audio_enabled = checked
        self.audio_track_combo.setVisible(not checked)
        self.audio_track_list.setVisible(checked)
        self.load_audio_btn.setVisible(checked)
        has_tracks = self.audio_track_combo.count() > 0
        self.audio_track_combo.setEnabled(not checked and self.audio_check.isChecked() and has_tracks)
        self.audio_track_list.setEnabled(checked and self.audio_check.isChecked())

        if checked:
            # Sync list selection from selected_audio_indices
            self._sync_list_from_indices()
        else:
            # Sync combo from audio_stream_index
            if self.audio_track_combo.count() > 0:
                idx = self.app_state.tracks.audio_stream_index
                if 0 <= idx < self.audio_track_combo.count():
                    self.audio_track_combo.setCurrentIndex(idx)
        self.tracks_changed.emit()

    def on_audio_track_changed(self, index):
        """Handle audio track selection change (single mode)"""
        if index >= 0 and index < len(self.app_state.tracks.available_audio_tracks):
            track_info = self.app_state.tracks.available_audio_tracks[index]
            self.app_state.tracks.audio_stream_index = index
            self.audio_info_label.setText(f"{track_info.codec} ({track_info.channels}ch)")
            self.tracks_changed.emit()

    def on_audio_track_list_changed(self):
        """Handle multi-track audio list selection change"""
        selected_items = self.audio_track_list.selectedItems()
        selected_indices = []
        assignments = []
        for item in selected_items:
            data = item.data(256)
            if data is None:
                continue
            track_type, track_idx = data
            selected_indices.append(len(assignments))
            if track_type == 0:  # Embedded
                assignments.append(AudioTrackAssignment(
                    stream_index=track_idx,
                    mode="copy" if self.app_state.tracks.audio_copy_mode else "encode",
                    is_external=False
                ))
            else:  # External
                assignments.append(AudioTrackAssignment(
                    stream_index=track_idx,
                    mode="copy" if self.app_state.tracks.audio_copy_mode else "encode",
                    is_external=True
                ))

        self.app_state.tracks.selected_audio_indices = selected_indices
        self.app_state.tracks.audio_track_assignments = assignments

        if selected_items:
            names = ", ".join([item.text().split(" (")[0] for item in selected_items])
            self.audio_info_label.setText(names)
        else:
            self.audio_info_label.setText("")
        self.tracks_changed.emit()

    def on_load_external_audio(self):
        """Handle Load External Audio button click"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select External Audio File",
            "",
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
            ext_track = ExternalAudioTrack(
                file_path=file_path,
                title=os.path.basename(file_path)
            )

        self.app_state.tracks.external_audio_tracks.append(ext_track)
        self._rebuild_audio_track_list()
        # Auto-select the new track
        total_count = len(self.app_state.tracks.available_audio_tracks) + len(self.app_state.tracks.external_audio_tracks)
        self.audio_track_list.item(total_count - 1).setSelected(True)
        self.tracks_changed.emit()

    def on_audio_copy_changed(self, checked):
        """Handle audio copy mode checkbox change"""
        self.app_state.tracks.audio_copy_mode = checked
        # Update assignment modes
        for assignment in self.app_state.tracks.audio_track_assignments:
            assignment.mode = "copy" if checked else "encode"
        self.tracks_changed.emit()

    def on_multi_sub_toggled(self, checked):
        """Handle multi-track subtitle toggle"""
        self.app_state.tracks.multi_track_subtitle_enabled = checked
        self.subtitle_track_list.setVisible(checked)
        self.load_sub_btn.setVisible(checked)
        self.subtitle_track_list.setEnabled(checked and self.subtitle_check.isChecked())
        if checked:
            self._rebuild_subtitle_track_list()
            self._sync_sub_list_from_assignments()
        self.tracks_changed.emit()

    def on_subtitle_track_list_changed(self):
        """Handle multi-track subtitle list selection change"""
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

        if selected_items:
            names = ", ".join([item.text().split(" (")[0] for item in selected_items])
            self.subtitle_info_label.setText(names)
        else:
            self.subtitle_info_label.setText("")
        self.tracks_changed.emit()

    def on_load_external_subtitle(self):
        """Handle Load External Subtitle button click"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select External Subtitle File",
            "",
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
        total_count = len(self.app_state.tracks.available_subtitle_tracks) + len(self.app_state.tracks.external_subtitle_tracks)
        self.subtitle_track_list.item(total_count - 1).setSelected(True)
        self.tracks_changed.emit()

    def _rebuild_subtitle_track_list(self):
        """Rebuild the subtitle multi-select list with embedded + external tracks"""
        self.subtitle_track_list.clear()
        embedded_tracks = self.app_state.tracks.available_subtitle_tracks
        external_tracks = self.app_state.tracks.external_subtitle_tracks

        for i, track in enumerate(embedded_tracks):
            display_text = f"[Embedded] Track {i+1}"
            if track.language:
                display_text += f" [{track.language}]"
            if track.title:
                display_text += f" - {track.title}"
            display_text += f" ({track.codec})"
            item = QListWidgetItem(display_text)
            item.setData(256, (0, i))
            self.subtitle_track_list.addItem(item)

        for i, track in enumerate(external_tracks):
            display_text = f"[External] {track.title}"
            display_text += f" ({track.codec})"
            item = QListWidgetItem(display_text)
            item.setData(256, (1, i))
            self.subtitle_track_list.addItem(item)

    def _sync_sub_list_from_assignments(self):
        """Sync QListWidget selection from subtitle_track_assignments"""
        assignments = self.app_state.tracks.subtitle_track_assignments
        selected_embedded = {a.stream_index for a in assignments if not a.is_external}
        selected_external = {a.stream_index for a in assignments if a.is_external}
        for i in range(self.subtitle_track_list.count()):
            item = self.subtitle_track_list.item(i)
            data = item.data(256)
            if data is not None:
                track_type, track_idx = data
                if track_type == 0:
                    item.setSelected(track_idx in selected_embedded)
                else:
                    item.setSelected(track_idx in selected_external)

    def on_subtitle_changed(self, checked):
        """Handle subtitle track checkbox change"""
        self.app_state.tracks.subtitle_selected = checked
        self.subtitle_track_list.setEnabled(checked and self.app_state.tracks.multi_track_subtitle_enabled)
        self.tracks_changed.emit()

    def _rebuild_audio_track_list(self):
        """Rebuild the multi-select list with embedded + external tracks"""
        self.audio_track_list.clear()
        embedded_tracks = self.app_state.tracks.available_audio_tracks
        external_tracks = self.app_state.tracks.external_audio_tracks

        for i, track in enumerate(embedded_tracks):
            display_text = f"[Embedded] Track {i+1}"
            if track.language:
                display_text += f" [{track.language}]"
            if track.title:
                display_text += f" - {track.title}"
            display_text += f" ({track.codec}, {track.channels}ch)"
            if track.sample_rate:
                display_text += f", {track.sample_rate}Hz"
            from PySide6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(display_text)
            item.setData(256, (0, i))  # (type=embedded, index)
            self.audio_track_list.addItem(item)

        for i, track in enumerate(external_tracks):
            display_text = f"[External] {track.title}"
            if track.codec:
                display_text += f" ({track.codec}, {track.channels}ch)"
                if track.sample_rate:
                    display_text += f", {track.sample_rate}Hz"
            from PySide6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(display_text)
            item.setData(256, (1, i))  # (type=external, index)
            self.audio_track_list.addItem(item)

    def _sync_list_from_indices(self):
        """Sync QListWidget selection from audio_track_assignments"""
        assignments = self.app_state.tracks.audio_track_assignments
        selected_embedded = {a.stream_index for a in assignments if not a.is_external}
        selected_external = {a.stream_index for a in assignments if a.is_external}
        for i in range(self.audio_track_list.count()):
            item = self.audio_track_list.item(i)
            data = item.data(256)
            if data is not None:
                track_type, track_idx = data
                if track_type == 0:
                    item.setSelected(track_idx in selected_embedded)
                else:
                    item.setSelected(track_idx in selected_external)

    def detect_tracks(self, video_path: str):
        """Detect available tracks in video file via backend"""
        self.current_video_path = video_path

        try:
            data = self.app_state.backend.get_streams(video_path)
            if not data or not data.get('streams'):
                self.app_state.log("No stream information available from backend", "WARN")
                return

            has_video = False
            has_audio = False
            has_subtitle = False
            audio_tracks = []
            video_info = ""
            subtitle_info = ""
            subtitle_streams = []

            for stream in data.get('streams', []):
                codec_type = stream.get('codec_type', '')
                codec_name = stream.get('codec_name', 'unknown')
                stream_index = stream.get('index', 0)
                tags = stream.get('tags', {})

                if codec_type == 'video':
                    has_video = True
                    width = stream.get('width', 0)
                    height = stream.get('height', 0)
                    dar = stream.get('display_aspect_ratio', 'N/A')
                    video_info = f"{codec_name}, {width}x{height}, {dar}"
                    self.app_state.tracks.video_width = width
                    self.app_state.tracks.video_height = height
                    self.app_state.tracks.video_dar = dar
                elif codec_type == 'audio':
                    has_audio = True
                    channels = stream.get('channels', 2)
                    sample_rate = stream.get('sample_rate', '')
                    language = tags.get('language', '')
                    title = tags.get('title', '')

                    track_info = AudioTrackInfo(
                        index=stream_index,
                        codec=codec_name,
                        channels=channels,
                        sample_rate=sample_rate,
                        language=language,
                        title=title
                    )
                    audio_tracks.append(track_info)
                elif codec_type == 'subtitle':
                    has_subtitle = True
                    subtitle_info = codec_name
                    from models import SubtitleTrackInfo
                    subtitle_streams.append(SubtitleTrackInfo(
                        index=stream_index,
                        codec=codec_name,
                        language=tags.get('language', ''),
                        title=tags.get('title', '')
                    ))

            self.app_state.tracks.available_audio_tracks = audio_tracks
            self.app_state.tracks.available_subtitle_tracks = subtitle_streams

            # Populate single-selection combo
            self.audio_track_combo.clear()
            for i, track in enumerate(audio_tracks):
                display_text = f"Track {i+1}"
                if track.language:
                    display_text += f" [{track.language}]"
                if track.title:
                    display_text += f" - {track.title}"
                display_text += f" ({track.codec}, {track.channels}ch"
                if track.sample_rate:
                    display_text += f", {track.sample_rate}Hz"
                display_text += ")"
                self.audio_track_combo.addItem(display_text)

            # Populate multi-select list (embedded + external)
            self._rebuild_audio_track_list()

            self.video_info_label.setText(video_info)

            if audio_tracks:
                default_index = 0
                self.audio_track_combo.setCurrentIndex(default_index)
                self.app_state.tracks.audio_stream_index = default_index
                self.audio_info_label.setText(f"{audio_tracks[default_index].codec} ({audio_tracks[default_index].channels}ch)")

                # Set default audio track assignment
                self.app_state.tracks.selected_audio_indices = [0]
                self.app_state.tracks.audio_track_assignments = [
                    AudioTrackAssignment(stream_index=0, mode="copy" if self.app_state.tracks.audio_copy_mode else "encode")
                ]
            else:
                self.audio_info_label.setText("")

            is_multi = self.app_state.tracks.multi_track_audio_enabled
            self.audio_track_combo.setVisible(not is_multi)
            self.audio_track_list.setVisible(is_multi)
            self.audio_track_combo.setEnabled(not is_multi and has_audio and self.audio_check.isChecked())
            self.audio_track_list.setEnabled(is_multi and has_audio and self.audio_check.isChecked())
            self.audio_copy_check.setEnabled(has_audio and self.audio_check.isChecked())

            self.app_state.tracks.video_info = video_info
            self.app_state.tracks.subtitle_info = subtitle_info
            self.app_state.tracks.subtitle_available = has_subtitle

            if has_subtitle:
                self.subtitle_info_label.setText(subtitle_info)
                self.subtitle_widget.setVisible(True)
            else:
                self.subtitle_widget.setVisible(False)

            # Build subtitle multi-select list
            self._rebuild_subtitle_track_list()
            is_multi_sub = self.app_state.tracks.multi_track_subtitle_enabled
            self.subtitle_track_list.setVisible(is_multi_sub)
            self.load_sub_btn.setVisible(is_multi_sub)
            self.subtitle_track_list.setEnabled(is_multi_sub and self.subtitle_check.isChecked())

            self.video_check.setChecked(has_video)
            self.audio_check.setChecked(has_audio)
            self.subtitle_check.setChecked(False)

            self.app_state.tracks.video_selected = has_video
            self.app_state.tracks.audio_selected = has_audio
            self.app_state.tracks.subtitle_selected = False

            self.app_state.log(f"Detected {len(audio_tracks)} audio track(s)", "INFO")
            for track in audio_tracks:
                track_desc = f"  Track {track.index}: {track.codec}, {track.channels} channels"
                if track.language:
                    track_desc += f", lang={track.language}"
                self.app_state.log(track_desc, "INFO")

        except Exception as e:
            self.app_state.log(f"Track detection failed: {e}", "WARN")

    def get_selected_tracks_filter(self):
        """Get FFmpeg filter string for selected tracks"""
        filters = []

        if self.app_state.tracks.video_selected:
            filters.append("v:0")
        if self.app_state.tracks.audio_selected:
            if self.app_state.tracks.multi_track_audio_enabled and self.app_state.tracks.selected_audio_indices:
                for idx in self.app_state.tracks.selected_audio_indices:
                    filters.append(f"a:{idx}")
            else:
                filters.append("a:0")
        if self.app_state.tracks.subtitle_selected and self.app_state.tracks.subtitle_available:
            filters.append("s:0")

        return filters
