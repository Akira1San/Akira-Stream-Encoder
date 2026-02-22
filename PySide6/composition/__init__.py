"""
Composition-based video editor module.

This module provides a stack-based composition system for creating
video content from layers (color, video, image, text, shapes) with
effects applied to each layer.
"""

from composition.models import (
    Composition,
    Layer,
    ColorLayer,
    VideoLayer,
    ImageLayer,
    TextLayer,
    ShapeLayer,
    Effect,
    Transform,
    BlendMode,
    ShapeType,
    LayerType,
)

__all__ = [
    'Composition',
    'Layer',
    'ColorLayer',
    'VideoLayer',
    'ImageLayer',
    'TextLayer',
    'ShapeLayer',
    'Effect',
    'Transform',
    'BlendMode',
    'ShapeType',
    'LayerType',
]
