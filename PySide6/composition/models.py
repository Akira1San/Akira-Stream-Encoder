"""
Composition Data Models - Dataclasses for stack-based video composition

This module provides the data models for a composition-based video editor
where content is built from layers (color, video, image, text, shapes) with
effects applied to each layer.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import uuid
import copy


class BlendMode(Enum):
    """Layer blend modes"""
    NORMAL = "normal"
    MULTIPLY = "multiply"
    SCREEN = "screen"
    OVERLAY = "overlay"
    DARKEN = "darken"
    LIGHTEN = "lighten"
    COLOR_DODGE = "color_dodge"
    COLOR_BURN = "color_burn"
    HARD_LIGHT = "hard_light"
    SOFT_LIGHT = "soft_light"
    DIFFERENCE = "difference"
    EXCLUSION = "exclusion"


class LayerType(Enum):
    """Layer type enumeration"""
    COLOR = "color"
    VIDEO = "video"
    IMAGE = "image"
    TEXT = "text"
    SHAPE = "shape"
    AUDIO = "audio"


class ShapeType(Enum):
    """Shape types for ShapeLayer"""
    RECTANGLE = "rectangle"
    ELLIPSE = "ellipse"
    LINE = "line"
    POLYGON = "polygon"
    STAR = "star"


class EffectType(Enum):
    """Available effect types"""
    COLOR_CORRECTION = "color_correction"
    BLUR = "blur"
    SHADOW = "shadow"
    GLOW = "glow"
    FADE = "fade"
    CROP = "crop"
    MASK = "mask"
    TRANSFORM_ANIMATION = "transform_animation"


@dataclass
class Transform:
    """
    Transform properties for a layer.
    
    Defines position, scale, rotation, and anchor point.
    """
    position_x: float = 0.0  # X position in pixels
    position_y: float = 0.0  # Y position in pixels
    scale_x: float = 1.0     # Horizontal scale (1.0 = 100%)
    scale_y: float = 1.0     # Vertical scale (1.0 = 100%)
    rotation: float = 0.0    # Rotation in degrees
    anchor_x: float = 0.5    # Anchor point X (0-1, relative to size)
    anchor_y: float = 0.5    # Anchor point Y (0-1, relative to size)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            'position_x': self.position_x,
            'position_y': self.position_y,
            'scale_x': self.scale_x,
            'scale_y': self.scale_y,
            'rotation': self.rotation,
            'anchor_x': self.anchor_x,
            'anchor_y': self.anchor_y,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Transform':
        """Deserialize from dictionary"""
        return cls(
            position_x=data.get('position_x', 0.0),
            position_y=data.get('position_y', 0.0),
            scale_x=data.get('scale_x', 1.0),
            scale_y=data.get('scale_y', 1.0),
            rotation=data.get('rotation', 0.0),
            anchor_x=data.get('anchor_x', 0.5),
            anchor_y=data.get('anchor_y', 0.5),
        )
    
    def copy(self) -> 'Transform':
        """Create a copy of this transform"""
        return Transform(**self.__dict__)


@dataclass
class Effect:
    """
    Effect applied to a layer.
    
    Effects are applied in order and can be enabled/disabled individually.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    effect_type: str = ""  # Effect type string
    name: str = ""  # Display name
    enabled: bool = True
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # Set name from type if not provided
        if not self.name:
            self.name = self.effect_type.replace('_', ' ').title()
        # Set default parameters based on effect type
        if not self.parameters:
            self.parameters = self._get_default_params()
    
    def _get_default_params(self) -> Dict[str, Any]:
        """Get default parameters for effect type"""
        defaults = {
            "color_correction": {
                "brightness": 0.0,      # -1.0 to 1.0
                "contrast": 1.0,        # 0.0 to 2.0
                "saturation": 1.0,      # 0.0 to 2.0
                "hue": 0.0,             # 0 to 360
            },
            "blur": {
                "radius": 5.0,          # 0 to 100
            },
            "shadow": {
                "color": "#000000",
                "offset_x": 5.0,
                "offset_y": 5.0,
                "blur_radius": 10.0,
                "opacity": 0.5,
            },
            "glow": {
                "color": "#FFFFFF",
                "radius": 10.0,
                "intensity": 1.0,
            },
            "fade": {
                "in_duration": 0.5,     # Fade in duration in seconds
                "out_duration": 0.5,    # Fade out duration in seconds
                "in_enabled": True,
                "out_enabled": True,
            },
            "crop": {
                "left": 0.0,
                "top": 0.0,
                "right": 0.0,
                "bottom": 0.0,
            },
            "mask": {
                "shape": "rectangle",
                "feather": 0.0,
                "invert": False,
            },
            "transform_animation": {
                "keyframes": [],  # List of keyframe data
            },
        }
        return defaults.get(self.effect_type, {})
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            'id': self.id,
            'effect_type': self.effect_type,
            'name': self.name,
            'enabled': self.enabled,
            'parameters': self.parameters,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Effect':
        """Deserialize from dictionary"""
        return cls(
            id=data.get('id', str(uuid.uuid4())[:8]),
            effect_type=data.get('effect_type', ''),
            name=data.get('name', ''),
            enabled=data.get('enabled', True),
            parameters=data.get('parameters', {}),
        )


@dataclass
class Layer:
    """
    Base layer class for composition.
    
    Layers are stacked bottom-to-top and can have effects applied.
    Each layer has a start time and end time within the composition.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Layer"
    layer_type: str = "base"
    enabled: bool = True
    locked: bool = False
    start_time: float = 0.0      # When layer appears (seconds)
    end_time: float = 30.0       # When layer ends (seconds)
    opacity: float = 1.0         # 0.0 to 1.0
    blend_mode: str = "normal"
    transform: Transform = field(default_factory=Transform)
    effects: List[Effect] = field(default_factory=list)
    
    @property
    def duration(self) -> float:
        """Get layer duration"""
        return self.end_time - self.start_time
    
    def add_effect(self, effect_type: str, params: Dict[str, Any] = None) -> Effect:
        """Add an effect to this layer"""
        effect = Effect(
            effect_type=effect_type,
            parameters=params or {}
        )
        self.effects.append(effect)
        return effect
    
    def remove_effect(self, effect_id: str) -> bool:
        """Remove an effect by ID"""
        for i, effect in enumerate(self.effects):
            if effect.id == effect_id:
                self.effects.pop(i)
                return True
        return False
    
    def get_effect(self, effect_type: str) -> Optional[Effect]:
        """Get effect by type if exists"""
        for effect in self.effects:
            if effect.effect_type == effect_type:
                return effect
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'layer_type': self.layer_type,
            'enabled': self.enabled,
            'locked': self.locked,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'opacity': self.opacity,
            'blend_mode': self.blend_mode,
            'transform': self.transform.to_dict(),
            'effects': [e.to_dict() for e in self.effects],
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Layer':
        """Deserialize from dictionary"""
        layer = cls(
            id=data.get('id', str(uuid.uuid4())[:8]),
            name=data.get('name', 'Layer'),
            enabled=data.get('enabled', True),
            locked=data.get('locked', False),
            start_time=data.get('start_time', 0.0),
            end_time=data.get('end_time', 30.0),
            opacity=data.get('opacity', 1.0),
            blend_mode=data.get('blend_mode', 'normal'),
            transform=Transform.from_dict(data.get('transform', {})),
        )
        for effect_data in data.get('effects', []):
            layer.effects.append(Effect.from_dict(effect_data))
        return layer


@dataclass
class ColorLayer(Layer):
    """
    Solid color or gradient background layer.
    """
    layer_type: str = "color"
    name: str = "Background"
    color: str = "#000000"       # Primary color (hex)
    gradient_enabled: bool = False
    gradient_color: str = "#FFFFFF"  # Secondary color for gradient
    gradient_direction: float = 0.0  # Angle in degrees (0 = horizontal)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        data = super().to_dict()
        data.update({
            'color': self.color,
            'gradient_enabled': self.gradient_enabled,
            'gradient_color': self.gradient_color,
            'gradient_direction': self.gradient_direction,
        })
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ColorLayer':
        """Deserialize from dictionary"""
        layer = super().from_dict(data)
        layer.color = data.get('color', '#000000')
        layer.gradient_enabled = data.get('gradient_enabled', False)
        layer.gradient_color = data.get('gradient_color', '#FFFFFF')
        layer.gradient_direction = data.get('gradient_direction', 0.0)
        return layer


@dataclass
class VideoLayer(Layer):
    """
    Video file layer.
    """
    layer_type: str = "video"
    name: str = "Video"
    source_path: str = ""
    source_start: float = 0.0    # Start point in source video
    source_end: float = 0.0      # End point in source video (0 = use all)
    loop: bool = False           # Loop video to fit layer duration
    mute: bool = False           # Mute audio
    volume: float = 1.0          # Audio volume (0.0 to 2.0)
    
    @property
    def source_duration(self) -> float:
        """Get source video duration (if source_end is set)"""
        if self.source_end > 0:
            return self.source_end - self.source_start
        return 0.0  # Unknown until metadata is loaded
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        data = super().to_dict()
        data.update({
            'source_path': self.source_path,
            'source_start': self.source_start,
            'source_end': self.source_end,
            'loop': self.loop,
            'mute': self.mute,
            'volume': self.volume,
        })
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VideoLayer':
        """Deserialize from dictionary"""
        layer = super().from_dict(data)
        layer.source_path = data.get('source_path', '')
        layer.source_start = data.get('source_start', 0.0)
        layer.source_end = data.get('source_end', 0.0)
        layer.loop = data.get('loop', False)
        layer.mute = data.get('mute', False)
        layer.volume = data.get('volume', 1.0)
        return layer


@dataclass
class ImageLayer(Layer):
    """
    Static image layer.
    """
    layer_type: str = "image"
    name: str = "Image"
    source_path: str = ""
    fit_mode: str = "fit"  # fill, fit, stretch, none
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        data = super().to_dict()
        data.update({
            'source_path': self.source_path,
            'fit_mode': self.fit_mode,
        })
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImageLayer':
        """Deserialize from dictionary"""
        layer = super().from_dict(data)
        layer.source_path = data.get('source_path', '')
        layer.fit_mode = data.get('fit_mode', 'fit')
        return layer


@dataclass
class TextLayer(Layer):
    """
    Text layer with font styling.
    """
    layer_type: str = "text"
    name: str = "Text"
    text: str = "Text"
    font_family: str = "Arial"
    font_size: int = 48
    font_weight: str = "normal"  # normal, bold
    font_style: str = "normal"   # normal, italic
    color: str = "#FFFFFF"
    alignment: str = "center"    # left, center, right
    line_spacing: float = 1.2
    letter_spacing: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        data = super().to_dict()
        data.update({
            'text': self.text,
            'font_family': self.font_family,
            'font_size': self.font_size,
            'font_weight': self.font_weight,
            'font_style': self.font_style,
            'color': self.color,
            'alignment': self.alignment,
            'line_spacing': self.line_spacing,
            'letter_spacing': self.letter_spacing,
        })
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TextLayer':
        """Deserialize from dictionary"""
        layer = super().from_dict(data)
        layer.text = data.get('text', 'Text')
        layer.font_family = data.get('font_family', 'Arial')
        layer.font_size = data.get('font_size', 48)
        layer.font_weight = data.get('font_weight', 'normal')
        layer.font_style = data.get('font_style', 'normal')
        layer.color = data.get('color', '#FFFFFF')
        layer.alignment = data.get('alignment', 'center')
        layer.line_spacing = data.get('line_spacing', 1.2)
        layer.letter_spacing = data.get('letter_spacing', 0.0)
        return layer


@dataclass
class ShapeLayer(Layer):
    """
    Shape layer (rectangle, ellipse, line, etc.).
    """
    layer_type: str = "shape"
    name: str = "Shape"
    shape_type: str = "rectangle"
    fill_color: str = "#FFFFFF"
    fill_enabled: bool = True
    stroke_color: str = "#000000"
    stroke_width: float = 2.0
    stroke_enabled: bool = True
    corner_radius: float = 0.0  # For rectangles
    width: float = 200.0        # Shape width in pixels
    height: float = 100.0       # Shape height in pixels
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        data = super().to_dict()
        data.update({
            'shape_type': self.shape_type,
            'fill_color': self.fill_color,
            'fill_enabled': self.fill_enabled,
            'stroke_color': self.stroke_color,
            'stroke_width': self.stroke_width,
            'stroke_enabled': self.stroke_enabled,
            'corner_radius': self.corner_radius,
            'width': self.width,
            'height': self.height,
        })
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ShapeLayer':
        """Deserialize from dictionary"""
        layer = super().from_dict(data)
        layer.shape_type = data.get('shape_type', 'rectangle')
        layer.fill_color = data.get('fill_color', '#FFFFFF')
        layer.fill_enabled = data.get('fill_enabled', True)
        layer.stroke_color = data.get('stroke_color', '#000000')
        layer.stroke_width = data.get('stroke_width', 2.0)
        layer.stroke_enabled = data.get('stroke_enabled', True)
        layer.corner_radius = data.get('corner_radius', 0.0)
        layer.width = data.get('width', 200.0)
        layer.height = data.get('height', 100.0)
        return layer


@dataclass
class Composition:
    """
    Main composition container.
    
    A composition contains layers stacked bottom-to-top, with a defined
    duration, resolution, and frame rate. The composition can be rendered
    to a video file.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Untitled Composition"
    duration: float = 30.0       # Total duration in seconds
    width: int = 1920            # Output width
    height: int = 1080           # Output height
    fps: float = 30.0            # Frame rate
    background_color: str = "#000000"
    layers: List[Layer] = field(default_factory=list)
    
    def add_layer(self, layer: Layer, index: int = None):
        """Add a layer to the composition"""
        if index is not None:
            self.layers.insert(index, layer)
        else:
            self.layers.append(layer)
        # Ensure layer times are within composition bounds
        layer.end_time = min(layer.end_time, self.duration)
    
    def remove_layer(self, layer_id: str) -> bool:
        """Remove a layer by ID"""
        for i, layer in enumerate(self.layers):
            if layer.id == layer_id:
                self.layers.pop(i)
                return True
        return False
    
    def get_layer(self, layer_id: str) -> Optional[Layer]:
        """Get layer by ID"""
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        return None
    
    def move_layer(self, layer_id: str, new_index: int):
        """Move a layer to a new position in the stack"""
        layer = self.get_layer(layer_id)
        if layer:
            self.layers.remove(layer)
            self.layers.insert(new_index, layer)
    
    def get_layers_at_time(self, time: float) -> List[Layer]:
        """Get all layers visible at a given time"""
        visible = []
        for layer in self.layers:
            if layer.enabled and layer.start_time <= time < layer.end_time:
                visible.append(layer)
        return visible
    
    def set_duration(self, duration: float):
        """Set composition duration and adjust layers"""
        self.duration = max(1.0, duration)
        # Adjust layer end times
        for layer in self.layers:
            if layer.end_time > self.duration:
                layer.end_time = self.duration
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'duration': self.duration,
            'width': self.width,
            'height': self.height,
            'fps': self.fps,
            'background_color': self.background_color,
            'layers': [layer.to_dict() for layer in self.layers],
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Composition':
        """Deserialize from dictionary"""
        composition = cls(
            id=data.get('id', str(uuid.uuid4())[:8]),
            name=data.get('name', 'Untitled Composition'),
            duration=data.get('duration', 30.0),
            width=data.get('width', 1920),
            height=data.get('height', 1080),
            fps=data.get('fps', 30.0),
            background_color=data.get('background_color', '#000000'),
        )
        
        # Deserialize layers based on type
        for layer_data in data.get('layers', []):
            layer_type = layer_data.get('layer_type', 'base')
            layer_class = {
                'color': ColorLayer,
                'video': VideoLayer,
                'image': ImageLayer,
                'text': TextLayer,
                'shape': ShapeLayer,
            }.get(layer_type, Layer)
            layer = layer_class.from_dict(layer_data)
            composition.layers.append(layer)
        
        return composition
    
    def copy(self) -> 'Composition':
        """Create a deep copy of this composition"""
        return Composition.from_dict(self.to_dict())


# Layer factory function
def create_layer(layer_type: str, **kwargs) -> Layer:
    """Create a layer of the specified type"""
    layer_classes = {
        'color': ColorLayer,
        'video': VideoLayer,
        'image': ImageLayer,
        'text': TextLayer,
        'shape': ShapeLayer,
    }
    layer_class = layer_classes.get(layer_type, Layer)
    return layer_class(**kwargs)
