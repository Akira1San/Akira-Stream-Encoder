"""
Extra Panel - Text overlays, image overlays, and video generation (PySide6)
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QLineEdit, QGroupBox, QFrame, QSpinBox, QComboBox, QSlider,
    QPushButton, QFileDialog, QColorDialog
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor

from models import AppState, TextOverlay, ImageOverlay


class TextOverlayWidget(QFrame):
    """Widget for a single text overlay item"""

    changed = Signal()
    remove_requested = Signal(object)

    def __init__(self, overlay: TextOverlay, index: int, parent=None):
        super().__init__(parent)
        self.overlay = overlay
        self.index = index

        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setStyleSheet("TextOverlayWidget { border: 1px solid #ccc; border-radius: 4px; padding: 4px; }")

        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(6, 6, 6, 6)

        header = QHBoxLayout()
        self.title_label = QLabel(f"<b>Text {index + 1}</b>")
        header.addWidget(self.title_label)
        header.addStretch()
        self.remove_btn = QPushButton("✕")
        self.remove_btn.setFixedSize(24, 24)
        self.remove_btn.setToolTip("Remove this text overlay")
        self.remove_btn.setStyleSheet("QPushButton { color: red; font-weight: bold; border: none; } QPushButton:hover { background: #ffcccc; border-radius: 3px; }")
        self.remove_btn.clicked.connect(self._on_remove)
        header.addWidget(self.remove_btn)
        layout.addLayout(header)

        self.enable_check = QCheckBox("Enable")
        self.enable_check.setChecked(overlay.enabled)
        layout.addWidget(self.enable_check)

        text_row = QHBoxLayout()
        text_row.addWidget(QLabel("Text:"))
        self.text_edit = QLineEdit(overlay.text)
        text_row.addWidget(self.text_edit)
        layout.addLayout(text_row)

        opt_row = QHBoxLayout()
        opt_row.addWidget(QLabel("Size:"))
        self.size_spin = QSpinBox()
        self.size_spin.setRange(8, 500)
        self.size_spin.setValue(overlay.font_size)
        self.size_spin.setMaximumWidth(60)
        opt_row.addWidget(self.size_spin)

        opt_row.addWidget(QLabel("Color:"))
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(30, 24)
        self.color_btn.setToolTip("Choose font color")
        self.color_btn.clicked.connect(self._pick_color)
        self._update_color_btn(overlay.font_color)
        opt_row.addWidget(self.color_btn)
        opt_row.addStretch()
        layout.addLayout(opt_row)

        pos_row = QHBoxLayout()
        pos_row.addWidget(QLabel("X:"))
        self.x_spin = QSpinBox()
        self.x_spin.setRange(-9999, 9999)
        self.x_spin.setValue(overlay.x)
        self.x_spin.setMaximumWidth(70)
        pos_row.addWidget(self.x_spin)
        pos_row.addWidget(QLabel("Y:"))
        self.y_spin = QSpinBox()
        self.y_spin.setRange(-9999, 9999)
        self.y_spin.setValue(overlay.y)
        self.y_spin.setMaximumWidth(70)
        pos_row.addWidget(self.y_spin)
        pos_row.addStretch()
        layout.addLayout(pos_row)

        anim_row = QHBoxLayout()
        anim_row.addWidget(QLabel("Animation:"))
        self.anim_combo = QComboBox()
        self.anim_combo.addItems([
            "none", "Fade In", "Fade Out", "Slide In Left",
            "Slide In Right", "Slide In Top", "Slide In Bottom",
            "Bounce", "Pulse", "Typewriter"
        ])
        idx = self.anim_combo.findText(overlay.animation)
        self.anim_combo.setCurrentIndex(idx if idx >= 0 else 0)
        anim_row.addWidget(self.anim_combo)
        anim_row.addStretch()
        layout.addLayout(anim_row)

        self._connect_signals()

    def _connect_signals(self):
        self.enable_check.toggled.connect(self._on_changed)
        self.text_edit.textChanged.connect(self._on_changed)
        self.size_spin.valueChanged.connect(self._on_changed)
        self.x_spin.valueChanged.connect(self._on_changed)
        self.y_spin.valueChanged.connect(self._on_changed)
        self.anim_combo.currentTextChanged.connect(self._on_changed)

    def _on_changed(self):
        self.overlay.enabled = self.enable_check.isChecked()
        self.overlay.text = self.text_edit.text()
        self.overlay.font_size = self.size_spin.value()
        self.overlay.x = self.x_spin.value()
        self.overlay.y = self.y_spin.value()
        self.overlay.animation = self.anim_combo.currentText()
        self.changed.emit()

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self.overlay.font_color))
        if color.isValid():
            self.overlay.font_color = color.name()
            self._update_color_btn(color.name())
            self.changed.emit()

    def _update_color_btn(self, color: str):
        self.color_btn.setStyleSheet(
            f"background-color: {color}; border: 1px solid gray; border-radius: 3px;"
        )

    def _on_remove(self):
        self.remove_requested.emit(self)


class ImageOverlayWidget(QFrame):
    """Widget for a single image overlay item"""

    changed = Signal()
    remove_requested = Signal(object)

    def __init__(self, overlay: ImageOverlay, index: int, parent=None):
        super().__init__(parent)
        self.overlay = overlay
        self.index = index

        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setStyleSheet("ImageOverlayWidget { border: 1px solid #ccc; border-radius: 4px; padding: 4px; }")

        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(6, 6, 6, 6)

        header = QHBoxLayout()
        self.title_label = QLabel(f"<b>Image {index + 1}</b>")
        header.addWidget(self.title_label)
        header.addStretch()
        self.remove_btn = QPushButton("✕")
        self.remove_btn.setFixedSize(24, 24)
        self.remove_btn.setToolTip("Remove this image overlay")
        self.remove_btn.setStyleSheet("QPushButton { color: red; font-weight: bold; border: none; } QPushButton:hover { background: #ffcccc; border-radius: 3px; }")
        self.remove_btn.clicked.connect(self._on_remove)
        header.addWidget(self.remove_btn)
        layout.addLayout(header)

        self.enable_check = QCheckBox("Enable")
        self.enable_check.setChecked(overlay.enabled)
        layout.addWidget(self.enable_check)

        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("File:"))
        self.path_label = QLabel(overlay.image_path if overlay.image_path else "No file selected")
        self.path_label.setStyleSheet("color: gray; font-size: 11px;")
        self.path_label.setWordWrap(True)
        file_row.addWidget(self.path_label, 1)
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(self.browse_btn)
        layout.addLayout(file_row)

        pos_row = QHBoxLayout()
        pos_row.addWidget(QLabel("X:"))
        self.x_spin = QSpinBox()
        self.x_spin.setRange(-9999, 9999)
        self.x_spin.setValue(overlay.x)
        self.x_spin.setMaximumWidth(70)
        pos_row.addWidget(self.x_spin)
        pos_row.addWidget(QLabel("Y:"))
        self.y_spin = QSpinBox()
        self.y_spin.setRange(-9999, 9999)
        self.y_spin.setValue(overlay.y)
        self.y_spin.setMaximumWidth(70)
        pos_row.addWidget(self.y_spin)
        pos_row.addStretch()
        layout.addLayout(pos_row)

        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel("Scale:"))
        self.scale_spin = QSpinBox()
        self.scale_spin.setRange(1, 500)
        self.scale_spin.setValue(int(overlay.scale * 100))
        self.scale_spin.setSuffix("%")
        self.scale_spin.setMaximumWidth(80)
        self.scale_spin.setToolTip("Scale as percentage (100% = original size)")
        scale_row.addWidget(self.scale_spin)
        scale_row.addWidget(QLabel("  Opacity:"))
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(int(overlay.opacity * 100))
        self.opacity_slider.setMaximumWidth(120)
        self.opacity_slider.setToolTip("Image opacity (0 = transparent, 100 = opaque)")
        scale_row.addWidget(self.opacity_slider)
        self.opacity_label = QLabel(f"{overlay.opacity:.1f}")
        self.opacity_label.setFixedWidth(30)
        scale_row.addWidget(self.opacity_label)
        scale_row.addStretch()
        layout.addLayout(scale_row)

        anim_row = QHBoxLayout()
        anim_row.addWidget(QLabel("Animation:"))
        self.anim_combo = QComboBox()
        self.anim_combo.addItems([
            "none", "Fade In", "Fade Out", "Slide In Left",
            "Slide In Right", "Slide In Top", "Slide In Bottom",
            "Bounce", "Pulse"
        ])
        idx = self.anim_combo.findText(overlay.animation)
        self.anim_combo.setCurrentIndex(idx if idx >= 0 else 0)
        anim_row.addWidget(self.anim_combo)
        anim_row.addStretch()
        layout.addLayout(anim_row)

        self._connect_signals()

    def _connect_signals(self):
        self.enable_check.toggled.connect(self._on_changed)
        self.x_spin.valueChanged.connect(self._on_changed)
        self.y_spin.valueChanged.connect(self._on_changed)
        self.scale_spin.valueChanged.connect(self._on_changed)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        self.anim_combo.currentTextChanged.connect(self._on_changed)

    def _on_changed(self):
        self.overlay.enabled = self.enable_check.isChecked()
        self.overlay.x = self.x_spin.value()
        self.overlay.y = self.y_spin.value()
        self.overlay.scale = self.scale_spin.value() / 100.0
        self.overlay.animation = self.anim_combo.currentText()
        self.changed.emit()

    def _on_opacity_changed(self, value):
        opacity = value / 100.0
        self.overlay.opacity = opacity
        self.opacity_label.setText(f"{opacity:.1f}")
        self.changed.emit()

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image",
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.tiff *.webp)"
        )
        if path:
            self.overlay.image_path = path
            self.path_label.setText(path)
            self.path_label.setStyleSheet("color: black; font-size: 11px;")
            self.changed.emit()

    def _on_remove(self):
        self.remove_requested.emit(self)


class ExtraPanel(QWidget):
    """Panel for extra overlays and video generation"""

    settings_changed = Signal()

    def __init__(self, app_state: AppState, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self._text_widgets: list[TextOverlayWidget] = []
        self._image_widgets: list[ImageOverlayWidget] = []

        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # === Add Text Section ===
        text_group = QGroupBox("Add Text")
        text_layout = QVBoxLayout(text_group)

        self.text_items_layout = QVBoxLayout()
        self.text_items_layout.setSpacing(6)
        text_layout.addLayout(self.text_items_layout)

        self.add_text_btn = QPushButton("+ Add Text")
        self.add_text_btn.setToolTip("Add a text overlay to the video")
        self.add_text_btn.clicked.connect(self._add_text_item)
        text_layout.addWidget(self.add_text_btn)

        layout.addWidget(text_group)

        # === Add Image Section ===
        image_group = QGroupBox("Add Image")
        image_layout = QVBoxLayout(image_group)

        self.image_items_layout = QVBoxLayout()
        self.image_items_layout.setSpacing(6)
        image_layout.addLayout(self.image_items_layout)

        self.add_image_btn = QPushButton("+ Add Image")
        self.add_image_btn.setToolTip("Add an image overlay (logo/icon) to the video")
        self.add_image_btn.clicked.connect(self._add_image_item)
        image_layout.addWidget(self.add_image_btn)

        layout.addWidget(image_group)

        # === Generate Video/Audio Section ===
        gen_group = QGroupBox("Generate Video / Add Audio Track")
        gen_layout = QVBoxLayout(gen_group)

        self.gen_enable_check = QCheckBox("Enable Generation")
        self.gen_enable_check.setChecked(self.app_state.extra.generate_video)
        self.gen_enable_check.toggled.connect(self._on_gen_enable_changed)
        gen_layout.addWidget(self.gen_enable_check)

        # Mode
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self.gen_mode_combo = QComboBox()
        self.gen_mode_combo.addItems(["Standby Video (color)", "Add Audio Track"])
        self.gen_mode_combo.currentTextChanged.connect(self._on_gen_mode_changed)
        mode_row.addWidget(self.gen_mode_combo)
        mode_row.addStretch()
        gen_layout.addLayout(mode_row)

        # Standby video controls
        self.standby_widget = QWidget()
        standby_layout = QVBoxLayout(self.standby_widget)
        standby_layout.setContentsMargins(0, 0, 0, 0)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Color:"))
        self.gen_color_btn = QPushButton()
        self.gen_color_btn.setFixedSize(40, 24)
        self.gen_color_btn.clicked.connect(self._pick_gen_color)
        self._update_gen_color_btn(self.app_state.extra.gen_color)
        color_row.addWidget(self.gen_color_btn)
        self.gen_color_label = QLabel(self.app_state.extra.gen_color)
        color_row.addWidget(self.gen_color_label)
        color_row.addStretch()
        standby_layout.addLayout(color_row)

        res_row = QHBoxLayout()
        res_row.addWidget(QLabel("Resolution:"))
        self.gen_res_combo = QComboBox()
        self.gen_res_combo.addItems([
            "640x480", "800x600", "1280x720", "1920x1080",
            "2560x1440", "3840x2160", "Custom"
        ])
        res_idx = self.gen_res_combo.findText(self.app_state.extra.gen_resolution)
        if res_idx < 0:
            self.gen_res_combo.setCurrentText("Custom")
        else:
            self.gen_res_combo.setCurrentIndex(res_idx)
        self.gen_res_combo.currentTextChanged.connect(self._on_gen_res_changed)
        res_row.addWidget(self.gen_res_combo)
        self.gen_w_spin = QSpinBox()
        self.gen_w_spin.setRange(16, 7680)
        self.gen_w_spin.setValue(1920)
        self.gen_w_spin.setMaximumWidth(70)
        self.gen_w_spin.setVisible(False)
        res_row.addWidget(self.gen_w_spin)
        self.gen_h_spin = QSpinBox()
        self.gen_h_spin.setRange(16, 4320)
        self.gen_h_spin.setValue(1080)
        self.gen_h_spin.setMaximumWidth(70)
        self.gen_h_spin.setVisible(False)
        res_row.addWidget(self.gen_h_spin)
        res_row.addWidget(QLabel("px"))
        res_row.addStretch()
        standby_layout.addLayout(res_row)

        dur_row = QHBoxLayout()
        dur_row.addWidget(QLabel("Duration:"))
        self.gen_dur_spin = QSpinBox()
        self.gen_dur_spin.setRange(1, 36000)
        self.gen_dur_spin.setValue(self.app_state.extra.gen_duration_sec)
        self.gen_dur_spin.setSuffix(" sec")
        self.gen_dur_spin.setMaximumWidth(120)
        dur_row.addWidget(self.gen_dur_spin)
        dur_row.addStretch()
        standby_layout.addLayout(dur_row)

        fps_row = QHBoxLayout()
        fps_row.addWidget(QLabel("Framerate:"))
        self.gen_fps_combo = QComboBox()
        self.gen_fps_combo.addItems(["24", "25", "30", "48", "50", "60", "120"])
        fps_idx = self.gen_fps_combo.findText(self.app_state.extra.gen_framerate)
        self.gen_fps_combo.setCurrentIndex(fps_idx if fps_idx >= 0 else 2)
        fps_row.addWidget(self.gen_fps_combo)
        fps_row.addStretch()
        standby_layout.addLayout(fps_row)

        self.gen_audio_check = QCheckBox("Include silent audio track")
        self.gen_audio_check.setChecked(self.app_state.extra.gen_include_audio)
        standby_layout.addWidget(self.gen_audio_check)

        gen_layout.addWidget(self.standby_widget)

        # Add Audio Track controls
        self.audio_track_widget = QWidget()
        audio_track_layout = QVBoxLayout(self.audio_track_widget)
        audio_track_layout.setContentsMargins(0, 0, 0, 0)

        audio_file_row = QHBoxLayout()
        audio_file_row.addWidget(QLabel("Audio File:"))
        self.audio_path_label = QLabel("No file selected")
        self.audio_path_label.setStyleSheet("color: gray; font-size: 11px;")
        self.audio_path_label.setWordWrap(True)
        audio_file_row.addWidget(self.audio_path_label, 1)
        self.audio_browse_btn = QPushButton("Browse...")
        self.audio_browse_btn.clicked.connect(self._browse_audio_file)
        audio_file_row.addWidget(self.audio_browse_btn)
        audio_track_layout.addLayout(audio_file_row)

        mix_row = QHBoxLayout()
        mix_row.addWidget(QLabel("Mix mode:"))
        self.audio_mix_combo = QComboBox()
        self.audio_mix_combo.addItems(["Replace existing audio", "Mix with existing audio", "Add as extra track"])
        self.audio_mix_combo.currentTextChanged.connect(self._on_audio_mix_changed)
        mix_row.addWidget(self.audio_mix_combo)
        mix_row.addStretch()
        audio_track_layout.addLayout(mix_row)

        audio_note = QLabel("Tip: Use 'Add Audio Track' to add background music or narration")
        audio_note.setStyleSheet("color: gray; font-size: 10px;")
        audio_note.setWordWrap(True)
        audio_track_layout.addWidget(audio_note)

        self.audio_track_widget.setVisible(False)
        gen_layout.addWidget(self.audio_track_widget)

        self._update_mode_visibility()

        layout.addWidget(gen_group)

        layout.addStretch()

    def connect_signals(self):
        """Connect UI signals to handlers"""
        self.gen_res_combo.currentTextChanged.connect(self._on_gen_res_changed)
        self.gen_w_spin.valueChanged.connect(self._on_gen_custom_res_changed)
        self.gen_h_spin.valueChanged.connect(self._on_gen_custom_res_changed)
        self.gen_dur_spin.valueChanged.connect(self._on_gen_dur_changed)
        self.gen_fps_combo.currentTextChanged.connect(self._on_gen_fps_changed)
        self.gen_audio_check.toggled.connect(self._on_gen_audio_changed)

    def _add_text_item(self):
        """Add a new text overlay item"""
        overlay = TextOverlay(
            text=f"Text {len(self.app_state.extra.text_overlays) + 1}",
            font_size=36,
            font_color="#FFFFFF",
            x=10,
            y=10,
            animation="none"
        )
        self.app_state.extra.text_overlays.append(overlay)
        widget = TextOverlayWidget(overlay, len(self.app_state.extra.text_overlays) - 1)
        widget.changed.connect(self._on_item_changed)
        widget.remove_requested.connect(self._remove_text_widget)
        self._text_widgets.append(widget)
        self.text_items_layout.addWidget(widget)
        self._renumber_text_widgets()
        self.settings_changed.emit()

    def _remove_text_widget(self, widget: TextOverlayWidget):
        """Remove a text overlay widget and its data"""
        if widget in self._text_widgets:
            idx = self._text_widgets.index(widget)
            self._text_widgets.remove(widget)
            if idx < len(self.app_state.extra.text_overlays):
                self.app_state.extra.text_overlays.pop(idx)
            self.text_items_layout.removeWidget(widget)
            widget.deleteLater()
            self._renumber_text_widgets()
            self.settings_changed.emit()

    def _renumber_text_widgets(self):
        """Update title labels for text widgets"""
        for i, w in enumerate(self._text_widgets):
            w.index = i
            w.title_label.setText(f"<b>Text {i + 1}</b>")

    def _add_image_item(self):
        """Add a new image overlay item"""
        overlay = ImageOverlay(
            image_path="",
            x=10,
            y=10,
            scale=1.0,
            opacity=1.0,
            animation="none"
        )
        self.app_state.extra.image_overlays.append(overlay)
        widget = ImageOverlayWidget(overlay, len(self.app_state.extra.image_overlays) - 1)
        widget.changed.connect(self._on_item_changed)
        widget.remove_requested.connect(self._remove_image_widget)
        self._image_widgets.append(widget)
        self.image_items_layout.addWidget(widget)
        self._renumber_image_widgets()
        self.settings_changed.emit()

    def _remove_image_widget(self, widget: ImageOverlayWidget):
        """Remove an image overlay widget and its data"""
        if widget in self._image_widgets:
            idx = self._image_widgets.index(widget)
            self._image_widgets.remove(widget)
            if idx < len(self.app_state.extra.image_overlays):
                self.app_state.extra.image_overlays.pop(idx)
            self.image_items_layout.removeWidget(widget)
            widget.deleteLater()
            self._renumber_image_widgets()
            self.settings_changed.emit()

    def _renumber_image_widgets(self):
        """Update title labels for image widgets"""
        for i, w in enumerate(self._image_widgets):
            w.index = i
            w.title_label.setText(f"<b>Image {i + 1}</b>")

    def _on_item_changed(self):
        """Handle any text/image overlay change"""
        self.settings_changed.emit()

    # --- Generate Video / Audio handlers ---

    def _on_gen_enable_changed(self, checked):
        self.app_state.extra.generate_video = checked
        self.settings_changed.emit()

    def _on_gen_mode_changed(self, text):
        self._update_mode_visibility()
        self.settings_changed.emit()

    def _update_mode_visibility(self):
        is_standby = self.gen_mode_combo.currentText() == "Standby Video (color)"
        self.standby_widget.setVisible(is_standby)
        self.audio_track_widget.setVisible(not is_standby)

    def _pick_gen_color(self):
        color = QColorDialog.getColor(QColor(self.app_state.extra.gen_color))
        if color.isValid():
            self.app_state.extra.gen_color = color.name()
            self._update_gen_color_btn(color.name())
            self.gen_color_label.setText(color.name())
            self.settings_changed.emit()

    def _update_gen_color_btn(self, color: str):
        self.gen_color_btn.setStyleSheet(
            f"background-color: {color}; border: 1px solid gray; border-radius: 3px;"
        )

    def _on_gen_res_changed(self, text):
        if text == "Custom":
            self.gen_w_spin.setVisible(True)
            self.gen_h_spin.setVisible(True)
            self.app_state.extra.gen_resolution = f"{self.gen_w_spin.value()}x{self.gen_h_spin.value()}"
        else:
            self.gen_w_spin.setVisible(False)
            self.gen_h_spin.setVisible(False)
            self.app_state.extra.gen_resolution = text
        self.settings_changed.emit()

    def _on_gen_custom_res_changed(self):
        if self.gen_res_combo.currentText() == "Custom":
            self.app_state.extra.gen_resolution = f"{self.gen_w_spin.value()}x{self.gen_h_spin.value()}"
            self.settings_changed.emit()

    def _on_gen_dur_changed(self, value):
        self.app_state.extra.gen_duration_sec = value
        self.settings_changed.emit()

    def _on_gen_fps_changed(self, text):
        self.app_state.extra.gen_framerate = text
        self.settings_changed.emit()

    def _on_gen_audio_changed(self, checked):
        self.app_state.extra.gen_include_audio = checked
        self.settings_changed.emit()

    def _browse_audio_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Audio File",
            "",
            "Audio Files (*.mp3 *.aac *.wav *.flac *.ogg *.m4a *.ac3)"
        )
        if path:
            self.app_state.extra.audio_track_path = path
            self.app_state.extra.add_audio_track = True
            self.audio_path_label.setText(path)
            self.audio_path_label.setStyleSheet("color: black; font-size: 11px;")
            self.settings_changed.emit()

    def _on_audio_mix_changed(self, text):
        mapping = {
            "Replace existing audio": "replace",
            "Mix with existing audio": "mix",
            "Add as extra track": "add_track"
        }
        self.app_state.extra.audio_mix_mode = mapping.get(text, "replace")
        self.settings_changed.emit()
