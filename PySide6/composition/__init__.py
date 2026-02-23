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
    create_layer,
)

from composition.layer_stack import LayerStackWidget, LayerItemWidget
from composition.properties_panel import PropertiesPanel
from composition.timeline import CompositionTimeline
from composition.preview import CompositionPreview
from composition.composition_tab import CompositionTab
from composition.renderer import (
    CompositionRenderer,
    RenderSettings,
    RenderQuality,
    RenderCodec,
    RenderDialog,
    FrameRenderer,
)

__all__ = [
    # Models
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
    'create_layer',
    # Widgets
    'LayerStackWidget',
    'LayerItemWidget',
    'PropertiesPanel',
    'CompositionTimeline',
    'CompositionPreview',
    'CompositionTab',
    # Rendering
    'CompositionRenderer',
    'RenderSettings',
    'RenderQuality',
    'RenderCodec',
    'RenderDialog',
    'FrameRenderer',
]
