"""
Composition Preview - Real-time preview widget for compositions

This widget renders the composition using QPainter, compositing layers
from bottom to top with blend modes and opacity support.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QToolButton, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer, QRect, QRectF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPixmap, QImage,
    QLinearGradient, QPainterPath, QTransform
)

from composition.models import (
    Composition, Layer, ColorLayer, VideoLayer, ImageLayer,
    TextLayer, ShapeLayer
)


class CompositionPreview(QFrame):
    """
    Preview widget for composition.
    
    Renders the composition at the current time using QPainter.
    Supports playback with timer-based updates.
    """
    
    # Signals
    time_changed = Signal(float)  # Current time changed
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._composition = None
        self._current_time = 0.0
        self._is_playing = False
        self._fps = 30
        
        # Playback timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        
        # Cached rendered frame
        self._cached_frame = None
        self._needs_redraw = True
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the preview UI"""
        self.setMinimumSize(320, 180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Preview area (will be drawn via paintEvent)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.preview_label, 1)
        
        # Playback controls
        controls = QFrame()
        controls.setStyleSheet("QFrame { background-color: transparent; }")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(5)
        
        # Time display
        self.time_label = QLabel("00:00:00:00")
        self.time_label.setStyleSheet("color: #ddd; font-family: monospace;")
        controls_layout.addWidget(self.time_label)
        
        controls_layout.addStretch()
        
        # Playback buttons
        self.stop_btn = QToolButton()
        self.stop_btn.setText("⏹")
        self.stop_btn.setFixedSize(32, 32)
        self.stop_btn.setToolTip("Stop")
        self.stop_btn.clicked.connect(self._on_stop)
        controls_layout.addWidget(self.stop_btn)
        
        self.play_btn = QToolButton()
        self.play_btn.setText("▶")
        self.play_btn.setFixedSize(32, 32)
        self.play_btn.setToolTip("Play/Pause")
        self.play_btn.clicked.connect(self._on_play_pause)
        controls_layout.addWidget(self.play_btn)
        
        controls_layout.addStretch()
        
        # Duration display
        self.duration_label = QLabel("/ 00:00:30:00")
        self.duration_label.setStyleSheet("color: #888; font-family: monospace;")
        controls_layout.addWidget(self.duration_label)
        
        layout.addWidget(controls)
        
    def set_composition(self, composition: Composition):
        """Set the composition to preview"""
        self._composition = composition
        self._current_time = 0.0
        self._needs_redraw = True
        
        if composition:
            self._fps = composition.fps
            self._update_duration_label()
            
        self._render_frame()
        self.update()
        
    def set_time(self, time: float):
        """Set current time"""
        if self._composition:
            self._current_time = max(0, min(time, self._composition.duration))
            self._needs_redraw = True
            self._update_time_label()
            self._render_frame()
            self.update()
            
    def get_time(self) -> float:
        """Get current time"""
        return self._current_time
        
    def play(self):
        """Start playback"""
        if not self._composition:
            return
        self._is_playing = True
        self.play_btn.setText("⏸")
        interval = int(1000 / self._fps)
        self._timer.start(interval)
        
    def pause(self):
        """Pause playback"""
        self._is_playing = False
        self.play_btn.setText("▶")
        self._timer.stop()
        
    def stop(self):
        """Stop playback and reset to beginning"""
        self.pause()
        self.set_time(0)
        
    def _on_play_pause(self):
        """Toggle play/pause"""
        if self._is_playing:
            self.pause()
        else:
            self.play()
            
    def _on_stop(self):
        """Stop playback"""
        self.stop()
        
    def _on_timer(self):
        """Handle playback timer"""
        if not self._composition:
            self.pause()
            return
            
        # Advance time
        self._current_time += 1.0 / self._fps
        
        # Loop or stop at end
        if self._current_time >= self._composition.duration:
            self._current_time = 0.0  # Loop
            
        self._needs_redraw = True
        self._update_time_label()
        self._render_frame()
        self.update()
        self.time_changed.emit(self._current_time)
        
    def _update_time_label(self):
        """Update time display"""
        self.time_label.setText(self._format_time(self._current_time))
        
    def _update_duration_label(self):
        """Update duration display"""
        if self._composition:
            self.duration_label.setText(f"/ {self._format_time(self._composition.duration)}")
            
    def _format_time(self, seconds: float) -> str:
        """Format time as HH:MM:SS:FF"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        frames = int((seconds % 1) * self._fps)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"
        
    def _render_frame(self):
        """Render the current frame"""
        if not self._composition or not self._needs_redraw:
            return
            
        # Create image at composition size
        width = self._composition.width
        height = self._composition.height
        
        # Scale to fit preview area while maintaining aspect ratio
        preview_size = self.preview_label.size()
        scale = min(preview_size.width() / width, preview_size.height() / height)
        scaled_width = int(width * scale)
        scaled_height = int(height * scale)
        
        # Render at composition size, then scale
        image = QImage(width, height, QImage.Format_ARGB32)
        image.fill(QColor(self._composition.background_color))
        
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        
        # Render each visible layer
        for layer in self._composition.layers:
            if not layer.enabled:
                continue
            if not (layer.start_time <= self._current_time < layer.end_time):
                continue
            self._render_layer(painter, layer)
            
        painter.end()
        
        # Scale and cache
        self._cached_frame = QPixmap.fromImage(image).scaled(
            scaled_width, scaled_height,
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._needs_redraw = False
        
        # Update preview label
        self.preview_label.setPixmap(self._cached_frame)
        
    def _render_layer(self, painter: QPainter, layer: Layer):
        """Render a single layer"""
        painter.save()
        
        # Apply opacity
        painter.setOpacity(layer.opacity)
        
        # Apply transform
        transform = QTransform()
        transform.translate(
            layer.transform.position_x + layer.transform.anchor_x * self._composition.width,
            layer.transform.position_y + layer.transform.anchor_y * self._composition.height
        )
        transform.rotate(layer.transform.rotation)
        transform.scale(layer.transform.scale_x, layer.transform.scale_y)
        transform.translate(
            -layer.transform.anchor_x * self._composition.width,
            -layer.transform.anchor_y * self._composition.height
        )
        painter.setTransform(transform)
        
        # Render based on layer type
        if isinstance(layer, ColorLayer):
            self._render_color_layer(painter, layer)
        elif isinstance(layer, VideoLayer):
            self._render_video_layer(painter, layer)
        elif isinstance(layer, ImageLayer):
            self._render_image_layer(painter, layer)
        elif isinstance(layer, TextLayer):
            self._render_text_layer(painter, layer)
        elif isinstance(layer, ShapeLayer):
            self._render_shape_layer(painter, layer)
            
        painter.restore()
        
    def _render_color_layer(self, painter: QPainter, layer: ColorLayer):
        """Render a color layer"""
        rect = QRect(0, 0, self._composition.width, self._composition.height)
        
        if layer.gradient_enabled:
            # Draw gradient
            gradient = QLinearGradient()
            gradient.setColorAt(0, QColor(layer.color))
            gradient.setColorAt(1, QColor(layer.gradient_color))
            
            # Set gradient direction
            angle = layer.gradient_direction
            rad = angle * 3.14159 / 180
            w = self._composition.width
            h = self._composition.height
            gradient.setStart(w/2 - h/2 * rad, h/2 - w/2 * rad)
            gradient.setFinalStop(w/2 + h/2 * rad, h/2 + w/2 * rad)
            
            painter.fillRect(rect, gradient)
        else:
            # Solid color
            painter.fillRect(rect, QColor(layer.color))
            
    def _render_video_layer(self, painter: QPainter, layer: VideoLayer):
        """Render a video layer (placeholder - shows frame)"""
        # For now, show a placeholder rectangle
        rect = QRect(0, 0, self._composition.width, self._composition.height)
        
        if layer.source_path:
            # Try to load a frame from the video (simplified - just show placeholder)
            painter.fillRect(rect, QColor(50, 50, 80))
            painter.setPen(QPen(QColor(100, 100, 150), 2))
            painter.drawRect(rect)
            
            # Draw video icon
            painter.setPen(QColor(150, 150, 200))
            painter.setFont(QFont("Arial", 24))
            painter.drawText(rect, Qt.AlignCenter, f"🎬\n{layer.name}")
        else:
            painter.fillRect(rect, QColor(40, 40, 60))
            painter.setPen(QColor(80, 80, 100))
            painter.drawText(rect, Qt.AlignCenter, "No Video Source")
            
    def _render_image_layer(self, painter: QPainter, layer: ImageLayer):
        """Render an image layer"""
        rect = QRect(0, 0, self._composition.width, self._composition.height)
        
        if layer.source_path:
            try:
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
                    raise Exception("Failed to load image")
            except Exception:
                painter.fillRect(rect, QColor(60, 40, 60))
                painter.setPen(QColor(150, 100, 150))
                painter.drawText(rect, Qt.AlignCenter, f"Image Error\n{layer.source_path}")
        else:
            painter.fillRect(rect, QColor(50, 30, 50))
            painter.setPen(QColor(100, 60, 100))
            painter.drawText(rect, Qt.AlignCenter, "No Image Source")
            
    def _render_text_layer(self, painter: QPainter, layer: TextLayer):
        """Render a text layer"""
        # Set font
        weight = QFont.Bold if layer.font_weight == "bold" else QFont.Normal
        italic = layer.font_style == "italic"
        font = QFont(layer.font_family, layer.font_size, weight, italic)
        painter.setFont(font)
        
        # Set color
        painter.setPen(QColor(layer.color))
        
        # Calculate text position based on alignment
        rect = QRect(0, 0, self._composition.width, self._composition.height)
        
        # Alignment flags
        align_flags = {
            "left": Qt.AlignLeft,
            "center": Qt.AlignHCenter,
            "right": Qt.AlignRight
        }
        h_align = align_flags.get(layer.alignment, Qt.AlignHCenter)
        
        painter.drawText(rect, h_align | Qt.AlignVCenter, layer.text)
        
    def _render_shape_layer(self, painter: QPainter, layer: ShapeLayer):
        """Render a shape layer"""
        # Center the shape
        x = (self._composition.width - layer.width) / 2
        y = (self._composition.height - layer.height) / 2
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
        else:
            # Default to rectangle
            path.addRect(rect)
            
        # Fill
        if layer.fill_enabled:
            painter.fillPath(path, QColor(layer.fill_color))
            
        # Stroke
        if layer.stroke_enabled:
            painter.setPen(QPen(QColor(layer.stroke_color), layer.stroke_width))
            painter.drawPath(path)
            
    def paintEvent(self, event):
        """Handle paint event"""
        super().paintEvent(event)
        
        if self._needs_redraw:
            self._render_frame()
            
    def resizeEvent(self, event):
        """Handle resize - need to re-render"""
        self._needs_redraw = True
        self._render_frame()
        super().resizeEvent(event)
        
    def request_update(self):
        """Request a redraw of the preview"""
        self._needs_redraw = True
        self._render_frame()
        self.update()
