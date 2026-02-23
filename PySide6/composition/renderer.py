"""
Composition Renderer - FFmpeg-based rendering for compositions

This module provides rendering capabilities for compositions, compositing
layers from bottom to top with effects and exporting to video files.
"""
import os
import subprocess
import tempfile
import json
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import QObject, Signal, QThread, QMutex
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPixmap, QImage,
    QLinearGradient, QPainterPath, QTransform
)
from PySide6.QtWidgets import QApplication

from composition.models import (
    Composition, Layer, ColorLayer, VideoLayer, ImageLayer,
    TextLayer, ShapeLayer, Effect
)


class RenderQuality(Enum):
    """Render quality presets"""
    LOW = "low"           # 720p, lower bitrate
    MEDIUM = "medium"     # 1080p, medium bitrate
    HIGH = "high"         # 1080p, high bitrate
    ULTRA = "ultra"       # 4K, very high bitrate


class RenderCodec(Enum):
    """Available video codecs"""
    H264 = "h264"
    H265 = "h265"
    PRORES = "prores"
    VP9 = "vp9"


@dataclass
class RenderSettings:
    """Settings for composition rendering"""
    output_path: str = ""
    quality: RenderQuality = RenderQuality.HIGH
    codec: RenderCodec = RenderCodec.H264
    custom_width: Optional[int] = None   # Override composition width
    custom_height: Optional[int] = None  # Override composition height
    custom_fps: Optional[float] = None   # Override composition fps
    custom_bitrate: Optional[str] = None # Override auto bitrate (e.g., "10M")
    audio_sample_rate: int = 48000
    audio_bitrate: str = "192k"
    
    def get_resolution(self, composition: Composition) -> tuple:
        """Get output resolution"""
        width = self.custom_width or composition.width
        height = self.custom_height or composition.height
        return width, height
    
    def get_fps(self, composition: Composition) -> float:
        """Get output frame rate"""
        return self.custom_fps or composition.fps
    
    def get_bitrate(self, composition: Composition) -> str:
        """Get video bitrate based on quality and resolution"""
        if self.custom_bitrate:
            return self.custom_bitrate
        
        width, height = self.get_resolution(composition)
        pixels = width * height
        
        # Base bitrates by quality (in Mbps)
        bitrate_multipliers = {
            RenderQuality.LOW: 0.5,
            RenderQuality.MEDIUM: 1.0,
            RenderQuality.HIGH: 1.5,
            RenderQuality.ULTRA: 2.5,
        }
        
        # Calculate bitrate based on 1080p baseline
        base_bitrate = 8.0  # 8 Mbps for 1080p at medium quality
        pixel_ratio = pixels / (1920 * 1080)
        multiplier = bitrate_multipliers.get(self.quality, 1.0)
        
        bitrate_mbps = base_bitrate * pixel_ratio * multiplier
        return f"{int(bitrate_mbps)}M"


class FrameRenderer:
    """
    Renders individual frames of a composition.
    
    Uses QPainter to composite layers with effects applied.
    """
    
    def __init__(self, composition: Composition):
        self.composition = composition
        self._video_frames: Dict[str, Any] = {}  # Cached video frame readers
        
    def render_frame(self, time: float) -> QImage:
        """
        Render a single frame at the given time.
        
        Args:
            time: Time in seconds
            
        Returns:
            Rendered QImage
        """
        width = self.composition.width
        height = self.composition.height
        
        # Create image with background
        image = QImage(width, height, QImage.Format_ARGB32)
        image.fill(QColor(self.composition.background_color))
        
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Render each visible layer (bottom to top)
        for layer in self.composition.layers:
            if not layer.enabled:
                continue
            if not (layer.start_time <= time < layer.end_time):
                continue
            
            self._render_layer(painter, layer, time)
        
        painter.end()
        return image
    
    def _render_layer(self, painter: QPainter, layer: Layer, time: float):
        """Render a single layer with effects"""
        painter.save()
        
        # Calculate layer-local time
        layer_time = time - layer.start_time
        
        # Apply fade effect first (affects opacity)
        fade_effect = layer.get_effect("fade")
        opacity = layer.opacity
        if fade_effect and fade_effect.enabled:
            opacity *= self._calculate_fade_opacity(fade_effect, layer, layer_time)
        
        painter.setOpacity(opacity)
        
        # Apply transform
        transform = QTransform()
        transform.translate(
            layer.transform.position_x + layer.transform.anchor_x * self.composition.width,
            layer.transform.position_y + layer.transform.anchor_y * self.composition.height
        )
        transform.rotate(layer.transform.rotation)
        transform.scale(layer.transform.scale_x, layer.transform.scale_y)
        transform.translate(
            -layer.transform.anchor_x * self.composition.width,
            -layer.transform.anchor_y * self.composition.height
        )
        painter.setTransform(transform, True)
        
        # Render layer content
        if isinstance(layer, ColorLayer):
            self._render_color_layer(painter, layer)
        elif isinstance(layer, VideoLayer):
            self._render_video_layer(painter, layer, layer_time)
        elif isinstance(layer, ImageLayer):
            self._render_image_layer(painter, layer)
        elif isinstance(layer, TextLayer):
            self._render_text_layer(painter, layer)
        elif isinstance(layer, ShapeLayer):
            self._render_shape_layer(painter, layer)
        
        painter.restore()
    
    def _calculate_fade_opacity(self, effect: Effect, layer: Layer, layer_time: float) -> float:
        """Calculate opacity multiplier from fade effect"""
        params = effect.parameters
        in_duration = params.get("in_duration", 0.5)
        out_duration = params.get("out_duration", 0.5)
        in_enabled = params.get("in_enabled", True)
        out_enabled = params.get("out_enabled", True)
        
        layer_duration = layer.duration
        opacity = 1.0
        
        # Fade in
        if in_enabled and layer_time < in_duration:
            opacity *= layer_time / in_duration
        
        # Fade out
        if out_enabled and layer_time > layer_duration - out_duration:
            opacity *= (layer_duration - layer_time) / out_duration
        
        return max(0.0, min(1.0, opacity))
    
    def _render_color_layer(self, painter: QPainter, layer: ColorLayer):
        """Render a color/gradient layer"""
        from PySide6.QtCore import QRect
        
        rect = QRect(0, 0, self.composition.width, self.composition.height)
        
        if layer.gradient_enabled:
            gradient = QLinearGradient()
            gradient.setColorAt(0, QColor(layer.color))
            gradient.setColorAt(1, QColor(layer.gradient_color))
            
            angle = layer.gradient_direction
            import math
            rad = angle * math.pi / 180
            w = self.composition.width
            h = self.composition.height
            gradient.setStart(w/2 - h/2 * math.sin(rad), h/2 - w/2 * math.cos(rad))
            gradient.setFinalStop(w/2 + h/2 * math.sin(rad), h/2 + w/2 * math.cos(rad))
            
            painter.fillRect(rect, gradient)
        else:
            painter.fillRect(rect, QColor(layer.color))
    
    def _render_video_layer(self, painter: QPainter, layer: VideoLayer, layer_time: float):
        """Render a video layer frame"""
        from PySide6.QtCore import QRect
        
        rect = QRect(0, 0, self.composition.width, self.composition.height)
        
        if layer.source_path and os.path.exists(layer.source_path):
            # Get frame at current time
            source_time = layer.source_start + layer_time
            if layer.loop and layer.source_end > layer.source_start:
                source_duration = layer.source_end - layer.source_start
                source_time = layer.source_start + (layer_time % source_duration)
            
            # Try to extract frame using FFmpeg
            frame = self._get_video_frame(layer.source_path, source_time)
            if frame:
                painter.drawImage(rect, frame)
                return
            
            # Fallback: show placeholder
            painter.fillRect(rect, QColor(50, 50, 80))
            painter.setPen(QPen(QColor(100, 100, 150), 2))
            painter.drawRect(rect)
            painter.setPen(QColor(150, 150, 200))
            painter.setFont(QFont("Arial", 24))
            painter.drawText(rect, 0x84, f"Video: {layer.name}")  # Qt.AlignCenter
        else:
            painter.fillRect(rect, QColor(40, 40, 60))
            painter.setPen(QColor(80, 80, 100))
            painter.drawText(rect, 0x84, "No Video Source")  # Qt.AlignCenter
    
    def _get_video_frame(self, video_path: str, time: float) -> Optional[QImage]:
        """Extract a frame from video at specified time"""
        try:
            # Use FFmpeg to extract frame
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp_path = tmp.name
            
            cmd = [
                'ffmpeg', '-y',
                '-ss', str(time),
                '-i', video_path,
                '-vframes', '1',
                '-f', 'image2',
                tmp_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=10
            )
            
            if result.returncode == 0 and os.path.exists(tmp_path):
                image = QImage(tmp_path)
                os.unlink(tmp_path)
                return image
            
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
        except Exception:
            pass
        
        return None
    
    def _render_image_layer(self, painter: QPainter, layer: ImageLayer):
        """Render an image layer"""
        from PySide6.QtCore import QRect, Qt
        
        rect = QRect(0, 0, self.composition.width, self.composition.height)
        
        if layer.source_path and os.path.exists(layer.source_path):
            pixmap = QPixmap(layer.source_path)
            if not pixmap.isNull():
                # Apply fit mode
                if layer.fit_mode == "fill":
                    scaled = pixmap.scaled(rect.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                elif layer.fit_mode == "fit":
                    scaled = pixmap.scaled(rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                elif layer.fit_mode == "stretch":
                    scaled = pixmap.scaled(rect.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                else:
                    scaled = pixmap
                
                # Center the image
                x = (rect.width() - scaled.width()) // 2
                y = (rect.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
            else:
                painter.fillRect(rect, QColor(60, 40, 60))
                painter.setPen(QColor(150, 100, 150))
                painter.drawText(rect, 0x84, f"Image Error: {layer.source_path}")
        else:
            painter.fillRect(rect, QColor(50, 30, 50))
            painter.setPen(QColor(100, 60, 100))
            painter.drawText(rect, 0x84, "No Image Source")
    
    def _render_text_layer(self, painter: QPainter, layer: TextLayer):
        """Render a text layer"""
        from PySide6.QtCore import QRect, Qt
        
        # Set font
        weight = QFont.Bold if layer.font_weight == "bold" else QFont.Normal
        italic = layer.font_style == "italic"
        font = QFont(layer.font_family, layer.font_size, weight, italic)
        painter.setFont(font)
        
        # Set color
        painter.setPen(QColor(layer.color))
        
        # Apply effects (shadow, glow)
        shadow_effect = layer.get_effect("shadow")
        if shadow_effect and shadow_effect.enabled:
            self._apply_shadow(painter, layer, shadow_effect)
        
        # Draw text
        rect = QRect(0, 0, self.composition.width, self.composition.height)
        align_flags = {"left": Qt.AlignLeft, "center": Qt.AlignHCenter, "right": Qt.AlignRight}
        h_align = align_flags.get(layer.alignment, Qt.AlignHCenter)
        painter.drawText(rect, h_align | Qt.AlignVCenter, layer.text)
    
    def _apply_shadow(self, painter: QPainter, layer: TextLayer, effect: Effect):
        """Apply shadow effect to text"""
        params = effect.parameters
        color = QColor(params.get("color", "#000000"))
        color.setAlphaF(params.get("opacity", 0.5))
        offset_x = params.get("offset_x", 5.0)
        offset_y = params.get("offset_y", 5.0)
        
        painter.save()
        painter.setPen(color)
        
        from PySide6.QtCore import QRect, Qt
        rect = QRect(0, 0, self.composition.width, self.composition.height)
        shadow_rect = rect.translated(int(offset_x), int(offset_y))
        
        align_flags = {"left": Qt.AlignLeft, "center": Qt.AlignHCenter, "right": Qt.AlignRight}
        h_align = align_flags.get(layer.alignment, Qt.AlignHCenter)
        painter.drawText(shadow_rect, h_align | Qt.AlignVCenter, layer.text)
        
        painter.restore()
    
    def _render_shape_layer(self, painter: QPainter, layer: ShapeLayer):
        """Render a shape layer"""
        from PySide6.QtCore import QRectF, Qt
        
        # Center the shape
        x = (self.composition.width - layer.width) / 2
        y = (self.composition.height - layer.height) / 2
        rect = QRectF(x, y, layer.width, layer.height)
        
        # Create path based on shape type
        path = QPainterPath()
        
        if layer.shape_type == "rectangle":
            if layer.corner_radius > 0:
                path.addRoundedRect(rect, layer.corner_radius, layer.corner_radius)
            else:
                path.addRect(rect)
        elif layer.shape_type == "ellipse":
            path.addEllipse(rect)
        elif layer.shape_type == "line":
            path.moveTo(rect.left(), rect.top())
            path.lineTo(rect.right(), rect.bottom())
        elif layer.shape_type == "star":
            self._add_star_path(path, rect)
        else:
            path.addRect(rect)
        
        # Fill
        if layer.fill_enabled:
            painter.fillPath(path, QColor(layer.fill_color))
        
        # Stroke
        if layer.stroke_enabled and layer.stroke_width > 0:
            painter.setPen(QPen(QColor(layer.stroke_color), layer.stroke_width))
            painter.drawPath(path)
    
    def _add_star_path(self, path: QPainterPath, rect):
        """Add a star shape to the path"""
        import math
        
        cx = rect.center().x()
        cy = rect.center().y()
        outer_r = min(rect.width(), rect.height()) / 2
        inner_r = outer_r * 0.4
        points = 5
        
        for i in range(points * 2):
            angle = i * math.pi / points - math.pi / 2
            r = outer_r if i % 2 == 0 else inner_r
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()


class RenderWorker(QThread):
    """
    Background worker for rendering compositions.
    
    Runs the rendering process in a separate thread to keep UI responsive.
    """
    
    # Signals
    progress = Signal(int, int, float)  # current_frame, total_frames, current_time
    frame_rendered = Signal(QImage)      # Emitted for each rendered frame
    finished = Signal(bool, str)         # success, message
    error = Signal(str)                  # error_message
    
    def __init__(self, composition: Composition, settings: RenderSettings, parent=None):
        super().__init__(parent)
        self.composition = composition
        self.settings = settings
        self._is_cancelled = False
        self._mutex = QMutex()
        
    def cancel(self):
        """Cancel the rendering process"""
        self._mutex.lock()
        self._is_cancelled = True
        self._mutex.unlock()
        
    def is_cancelled(self) -> bool:
        """Check if rendering was cancelled"""
        self._mutex.lock()
        cancelled = self._is_cancelled
        self._mutex.unlock()
        return cancelled
    
    def run(self):
        """Execute the rendering process"""
        try:
            # Get render parameters
            width, height = self.settings.get_resolution(self.composition)
            fps = self.settings.get_fps(self.composition)
            duration = self.composition.duration
            total_frames = int(duration * fps)
            
            if total_frames <= 0:
                self.error.emit("Invalid composition duration")
                self.finished.emit(False, "Invalid composition duration")
                return
            
            # Create temporary directory for frames
            temp_dir = tempfile.mkdtemp(prefix="composition_render_")
            frames_pattern = os.path.join(temp_dir, "frame_%06d.png")
            
            # Initialize frame renderer
            renderer = FrameRenderer(self.composition)
            
            # Render frames
            for frame_num in range(total_frames):
                if self.is_cancelled():
                    self._cleanup(temp_dir)
                    self.finished.emit(False, "Rendering cancelled")
                    return
                
                time = frame_num / fps
                
                # Render frame
                image = renderer.render_frame(time)
                
                # Save frame
                frame_path = os.path.join(temp_dir, f"frame_{frame_num:06d}.png")
                image.save(frame_path)
                
                # Emit progress
                self.progress.emit(frame_num + 1, total_frames, time)
                
                # Process Qt events to keep UI responsive
                if QApplication.instance():
                    QApplication.instance().processEvents()
            
            # Encode video with FFmpeg
            output_path = self._encode_video(
                temp_dir, frames_pattern, width, height, fps
            )
            
            # Cleanup
            self._cleanup(temp_dir)
            
            if output_path and os.path.exists(output_path):
                self.finished.emit(True, f"Rendered to: {output_path}")
            else:
                self.finished.emit(False, "Failed to encode video")
                
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False, str(e))
    
    def _encode_video(self, temp_dir: str, frames_pattern: str, 
                      width: int, height: int, fps: float) -> Optional[str]:
        """Encode rendered frames to video using FFmpeg"""
        output_path = self.settings.output_path
        if not output_path:
            output_path = os.path.join(
                os.path.expanduser("~"),
                f"{self.composition.name}.mp4"
            )
        
        # Build FFmpeg command
        cmd = self._build_ffmpeg_command(frames_pattern, output_path, width, height, fps)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            if result.returncode != 0:
                print(f"FFmpeg error: {result.stderr}")
                return None
            
            return output_path
            
        except subprocess.TimeoutExpired:
            self.error.emit("Rendering timeout exceeded")
            return None
        except Exception as e:
            self.error.emit(f"FFmpeg error: {str(e)}")
            return None
    
    def _build_ffmpeg_command(self, input_pattern: str, output_path: str,
                               width: int, height: int, fps: float) -> List[str]:
        """Build FFmpeg command based on codec and quality settings"""
        cmd = [
            'ffmpeg', '-y',
            '-framerate', str(fps),
            '-i', input_pattern,
        ]
        
        # Add video encoding settings based on codec
        codec = self.settings.codec
        bitrate = self.settings.get_bitrate(self.composition)
        
        if codec == RenderCodec.H264:
            cmd.extend([
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-b:v', bitrate,
                '-pix_fmt', 'yuv420p',
            ])
        elif codec == RenderCodec.H265:
            cmd.extend([
                '-c:v', 'libx265',
                '-preset', 'medium',
                '-b:v', bitrate,
                '-pix_fmt', 'yuv420p',
            ])
        elif codec == RenderCodec.PRORES:
            cmd.extend([
                '-c:v', 'prores_ks',
                '-profile:v', '3',  # ProRes 422 HQ
            ])
        elif codec == RenderCodec.VP9:
            cmd.extend([
                '-c:v', 'libvpx-vp9',
                '-b:v', bitrate,
                '-pix_fmt', 'yuv420p',
            ])
        
        # Scale if needed
        target_width, target_height = self.settings.get_resolution(self.composition)
        if target_width != width or target_height != height:
            cmd.extend(['-vf', f'scale={target_width}:{target_height}'])
        
        # Add audio settings (silent audio for now)
        # TODO: Mix audio from video layers
        cmd.extend([
            '-f', 'lavfi',
            '-i', 'anullsrc=channel_layout=stereo:sample_rate=48000',
            '-shortest',
        ])
        
        cmd.append(output_path)
        return cmd
    
    def _cleanup(self, temp_dir: str):
        """Clean up temporary files"""
        import shutil
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except Exception:
            pass


class CompositionRenderer(QObject):
    """
    Main renderer class for compositions.
    
    Provides a high-level interface for rendering compositions with
    progress reporting and cancellation support.
    """
    
    # Signals
    render_started = Signal()
    render_progress = Signal(int, int, float)  # frame, total, time
    render_completed = Signal(bool, str)        # success, message
    render_error = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: Optional[RenderWorker] = None
        self._is_rendering = False
        
    def is_rendering(self) -> bool:
        """Check if rendering is in progress"""
        return self._is_rendering
    
    def render(self, composition: Composition, settings: RenderSettings):
        """
        Start rendering a composition.
        
        Args:
            composition: The composition to render
            settings: Render settings
        """
        if self._is_rendering:
            self.render_error.emit("Rendering already in progress")
            return
        
        self._is_rendering = True
        self.render_started.emit()
        
        # Create and configure worker
        self._worker = RenderWorker(composition, settings)
        self._worker.progress.connect(self.render_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self.render_error)
        
        # Start rendering
        self._worker.start()
    
    def cancel(self):
        """Cancel the current rendering operation"""
        if self._worker and self._is_rendering:
            self._worker.cancel()
    
    def _on_finished(self, success: bool, message: str):
        """Handle rendering completion"""
        self._is_rendering = False
        self._worker = None
        self.render_completed.emit(success, message)


class RenderDialog:
    """
    Dialog for configuring and starting renders.
    
    This is a helper class for showing render settings UI.
    """
    
    @staticmethod
    def get_render_settings(composition: Composition, parent=None) -> Optional[RenderSettings]:
        """
        Show a dialog to configure render settings.
        
        Returns:
            RenderSettings if user confirmed, None if cancelled
        """
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
            QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit,
            QPushButton, QFileDialog, QCheckBox, QGroupBox
        )
        
        dialog = QDialog(parent)
        dialog.setWindowTitle("Render Settings")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        
        # Output file
        output_group = QGroupBox("Output")
        output_layout = QFormLayout(output_group)
        
        output_edit = QLineEdit()
        output_edit.setPlaceholderText("Click Browse to select output file...")
        output_edit.setText(f"{composition.name}.mp4")
        output_layout.addRow("Output File:", output_edit)
        
        browse_btn = QPushButton("Browse...")
        output_layout.addRow("", browse_btn)
        layout.addWidget(output_group)
        
        def on_browse():
            path, _ = QFileDialog.getSaveFileName(
                dialog, "Select Output File",
                output_edit.text(),
                "MP4 Video (*.mp4);;All Files (*)"
            )
            if path:
                output_edit.setText(path)
        
        browse_btn.clicked.connect(on_browse)
        
        # Video settings
        video_group = QGroupBox("Video Settings")
        video_layout = QFormLayout(video_group)
        
        quality_combo = QComboBox()
        quality_combo.addItems(["Low (720p)", "Medium (1080p)", "High (1080p HQ)", "Ultra (4K)"])
        quality_combo.setCurrentIndex(2)  # High
        video_layout.addRow("Quality:", quality_combo)
        
        codec_combo = QComboBox()
        codec_combo.addItems(["H.264 (MP4)", "H.265/HEVC", "ProRes", "VP9 (WebM)"])
        codec_combo.setCurrentIndex(0)
        video_layout.addRow("Codec:", codec_combo)
        
        # Resolution override
        custom_res_check = QCheckBox("Override resolution")
        video_layout.addRow("", custom_res_check)
        
        width_spin = QSpinBox()
        width_spin.setRange(320, 7680)
        width_spin.setValue(composition.width)
        width_spin.setEnabled(False)
        video_layout.addRow("Width:", width_spin)
        
        height_spin = QSpinBox()
        height_spin.setRange(240, 4320)
        height_spin.setValue(composition.height)
        height_spin.setEnabled(False)
        video_layout.addRow("Height:", height_spin)
        
        def on_custom_res_changed(checked):
            width_spin.setEnabled(checked)
            height_spin.setEnabled(checked)
        
        custom_res_check.stateChanged.connect(on_custom_res_changed)
        
        # FPS override
        custom_fps_check = QCheckBox("Override frame rate")
        video_layout.addRow("", custom_fps_check)
        
        fps_spin = QDoubleSpinBox()
        fps_spin.setRange(1.0, 120.0)
        fps_spin.setValue(composition.fps)
        fps_spin.setEnabled(False)
        video_layout.addRow("Frame Rate:", fps_spin)
        
        def on_custom_fps_changed(checked):
            fps_spin.setEnabled(checked)
        
        custom_fps_check.stateChanged.connect(on_custom_fps_changed)
        
        layout.addWidget(video_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        render_btn = QPushButton("Render")
        render_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(render_btn)
        layout.addLayout(button_layout)
        
        # Connect buttons
        cancel_btn.clicked.connect(dialog.reject)
        
        result = [None]
        
        def on_render():
            quality_map = {
                0: RenderQuality.LOW,
                1: RenderQuality.MEDIUM,
                2: RenderQuality.HIGH,
                3: RenderQuality.ULTRA,
            }
            codec_map = {
                0: RenderCodec.H264,
                1: RenderCodec.H265,
                2: RenderCodec.PRORES,
                3: RenderCodec.VP9,
            }
            
            settings = RenderSettings(
                output_path=output_edit.text(),
                quality=quality_map[quality_combo.currentIndex()],
                codec=codec_map[codec_combo.currentIndex()],
                custom_width=width_spin.value() if custom_res_check.isChecked() else None,
                custom_height=height_spin.value() if custom_res_check.isChecked() else None,
                custom_fps=fps_spin.value() if custom_fps_check.isChecked() else None,
            )
            result[0] = settings
            dialog.accept()
        
        render_btn.clicked.connect(on_render)
        
        if dialog.exec() == QDialog.Accepted:
            return result[0]
        return None
