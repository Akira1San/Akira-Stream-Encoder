"""
Video Information Panel - Displays comprehensive video file metadata
"""
import os
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QGridLayout, QLabel, QWidget
)
from PySide6.QtCore import Qt
from ui_components import HorizontalLine


class VideoInfoPanel(QGroupBox):
    """Panel displaying comprehensive video file information"""

    def __init__(self, app_state, parent=None):
        super().__init__("Video Information", parent)
        self.app_state = app_state
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        grid = QGridLayout()
        grid.setVerticalSpacing(4)
        grid.setHorizontalSpacing(15)

        fields = [
            ("File:", "filename"),
            ("Size:", "size"),
            ("Container:", "container"),
            ("Duration:", "duration"),
            ("Resolution:", "resolution"),
            ("Video Codec:", "video_codec"),
            ("Video Bitrate:", "video_bitrate"),
            ("Overall Bitrate:", "overall_bitrate"),
            ("Frame Rate:", "framerate"),
        ]

        for row, (label_text, attr) in enumerate(fields):
            lbl = QLabel(label_text)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lbl.setStyleSheet("font-weight: normal; font-size: 11px;")
            val = QLabel("")
            val.setStyleSheet("font-weight: normal; font-size: 11px; color: #333;")
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(lbl, row, 0)
            grid.addWidget(val, row, 1)
            setattr(self, f"{attr}_label", val)

        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        layout.addWidget(HorizontalLine())

        self.audio_group = QGroupBox("Audio Tracks")
        self.audio_group.setStyleSheet("""
            QGroupBox { font-weight: bold; border: none; margin-top: 5px; }
            QGroupBox::title { subcontrol-origin: margin; left: 0px; padding: 0; }
        """)
        audio_layout = QVBoxLayout(self.audio_group)
        audio_layout.setContentsMargins(0, 15, 0, 0)
        audio_layout.setSpacing(2)
        self.audio_container = QWidget()
        self.audio_container_layout = QVBoxLayout(self.audio_container)
        self.audio_container_layout.setContentsMargins(0, 0, 0, 0)
        self.audio_container_layout.setSpacing(2)
        audio_layout.addWidget(self.audio_container)
        layout.addWidget(self.audio_group)

        self.sub_group = QGroupBox("Subtitle Tracks")
        self.sub_group.setStyleSheet("""
            QGroupBox { font-weight: bold; border: none; margin-top: 5px; }
            QGroupBox::title { subcontrol-origin: margin; left: 0px; padding: 0; }
        """)
        sub_layout = QVBoxLayout(self.sub_group)
        sub_layout.setContentsMargins(0, 15, 0, 0)
        self.subtitle_label = QLabel("")
        self.subtitle_label.setStyleSheet("font-weight: normal; font-size: 11px; color: #333;")
        self.subtitle_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        sub_layout.addWidget(self.subtitle_label)
        layout.addWidget(self.sub_group)

        self.hide()

    def clear_info(self):
        for attr in ['filename', 'size', 'container', 'duration',
                      'resolution', 'video_codec', 'video_bitrate',
                      'overall_bitrate', 'framerate']:
            getattr(self, f"{attr}_label").setText("")
        self._clear_audio_tracks()
        self.subtitle_label.setText("")
        self.hide()

    def _clear_audio_tracks(self):
        while self.audio_container_layout.count():
            item = self.audio_container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_audio_track(self, index, codec, channels, sample_rate, language, title=""):
        lang = language if language else "Unknown"
        lang_str = f" ({lang})" if language else ""
        title_str = f' "{title}"' if title else ""

        ch_map = {1: "Mono", 2: "Stereo", 6: "5.1", 8: "7.1"}
        ch_str = ch_map.get(channels, f"{channels}ch") if channels else "?"
        sr_val = float(sample_rate) if sample_rate else 0
        sr = f" {sr_val / 1000:.1f} kHz" if sr_val > 0 else ""

        text = f"Track {index}: {codec.upper()} - {ch_str}{sr}{lang_str}{title_str}"
        label = QLabel(text)
        label.setStyleSheet("font-weight: normal; font-size: 11px; color: #333; padding-left: 5px;")
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.audio_container_layout.addWidget(label)

    def _add_no_audio(self):
        label = QLabel("No audio tracks")
        label.setStyleSheet("font-weight: normal; font-size: 11px; color: #999; padding-left: 5px;")
        self.audio_container_layout.addWidget(label)

    def set_info(self, file_path):
        if not file_path or not os.path.exists(file_path):
            self.clear_info()
            return

        try:
            data = self.app_state.backend.get_full_info(file_path)
            streams = data.get('streams', []) if data else []
            fmt = data.get('format', {}) if data else {}

            self.filename_label.setText(os.path.basename(file_path))

            size_bytes = os.path.getsize(file_path)
            if size_bytes > 1024 * 1024 * 1024:
                self.size_label.setText(f"{size_bytes / (1024*1024*1024):.2f} GB")
            else:
                self.size_label.setText(f"{size_bytes / (1024*1024):.2f} MB")

            container = fmt.get('format_name', '')
            self.container_label.setText(container if container else "Unknown")

            duration_str = fmt.get('duration', '0')
            duration_sec = float(duration_str) if duration_str else 0
            if duration_sec > 0:
                mins, secs = divmod(int(duration_sec), 60)
                hours, mins = divmod(mins, 60)
                if hours > 0:
                    self.duration_label.setText(f"{hours}h {mins:02d}m {secs:02d}s")
                else:
                    self.duration_label.setText(f"{mins}m {secs:02d}s")
            else:
                self.duration_label.setText("Unknown")

            overall_br = fmt.get('bit_rate', '')
            if overall_br:
                self.overall_bitrate_label.setText(f"{int(overall_br) // 1000} kbps")
            else:
                self.overall_bitrate_label.setText("Unknown")

            video_stream = None
            for s in streams:
                if s.get('codec_type') == 'video':
                    video_stream = s
                    break

            if video_stream:
                w = video_stream.get('width', '?')
                h = video_stream.get('height', '?')
                aspect = ""
                sar = video_stream.get('display_aspect_ratio', '')
                if sar:
                    aspect = f" ({sar})"
                self.resolution_label.setText(f"{w}x{h}{aspect}")
                codec = video_stream.get('codec_name', 'Unknown').upper()
                profile = video_stream.get('profile', '')
                if profile:
                    codec = f"{codec} ({profile})"
                self.video_codec_label.setText(codec)
                vbr = video_stream.get('bit_rate', '')
                if vbr:
                    self.video_bitrate_label.setText(f"{int(vbr) // 1000} kbps")
                else:
                    self.video_bitrate_label.setText("Unknown (VBR)")
            else:
                self.resolution_label.setText("N/A")
                self.video_codec_label.setText("N/A")
                self.video_bitrate_label.setText("N/A")

            fps_info = self.app_state.backend.get_frame_rate(file_path)
            if fps_info and fps_info.get('fps'):
                fps = fps_info['fps']
                vfr = " (VFR)" if fps_info.get('is_vfr', False) else " (CFR)"
                self.framerate_label.setText(f"{fps:.3f} fps{vfr}")
            else:
                self.framerate_label.setText("Unknown")

            audio_tracks = [s for s in streams if s.get('codec_type') == 'audio']
            self._clear_audio_tracks()
            if audio_tracks:
                for i, s in enumerate(audio_tracks, 1):
                    tags = s.get('tags', {})
                    codec = s.get('codec_name', '?')
                    channels = s.get('channels', 0)
                    sample_rate = s.get('sample_rate', '')
                    language = tags.get('language', '')
                    title = tags.get('title', '')
                    self._add_audio_track(i, codec, channels, sample_rate, language, title)
            else:
                self._add_no_audio()

            subtitle_tracks = [s for s in streams if s.get('codec_type') == 'subtitle']
            if subtitle_tracks:
                sub_info = []
                for s in subtitle_tracks:
                    tags = s.get('tags', {})
                    lang = tags.get('language', '?')
                    codec = s.get('codec_name', '?')
                    sub_info.append(f"{codec.upper()} ({lang})")
                self.subtitle_label.setText(f"{len(subtitle_tracks)} track(s): {', '.join(sub_info)}")
            else:
                self.subtitle_label.setText("None")

            self.show()

        except Exception as e:
            self.app_state.log(f"Failed to get file info: {e}", "ERROR")
            self.clear_info()
