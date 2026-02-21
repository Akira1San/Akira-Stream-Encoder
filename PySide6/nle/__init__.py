"""
NLE (Non-Linear Editor) Package

A Blender-inspired video editing module with multi-track timeline,
clip management, effects, and rendering capabilities.
"""

from nle.nle_models import (
    NLEProject,
    NLETrack,
    NLEClip,
    Effect,
    TrackType,
    EffectType
)

from nle.nle_tab import NLETab
from nle.nle_timeline import NLETimeline

__all__ = [
    # Models
    'NLEProject',
    'NLETrack', 
    'NLEClip',
    'Effect',
    'TrackType',
    'EffectType',
    # Widgets
    'NLETab',
    'NLETimeline',
]
