"""
NLE Data Models - Dataclasses for Non-Linear Editor
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid


class TrackType(Enum):
    """Track type enumeration"""
    VIDEO = "video"
    AUDIO = "audio"


class EffectType(Enum):
    """Available effect types"""
    BRIGHTNESS = "brightness"
    CONTRAST = "contrast"
    SATURATION = "saturation"
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    SPEED = "speed"
    OPACITY = "opacity"
    VOLUME = "volume"


@dataclass
class Effect:
    """Effect applied to clip or track"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    effect_type: str = ""  # Effect type string
    params: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    
    def __post_init__(self):
        # Set default params based on effect type
        if not self.params:
            self.params = self._get_default_params()
    
    def _get_default_params(self) -> Dict[str, Any]:
        """Get default parameters for effect type"""
        defaults = {
            "brightness": {"value": 0.0},
            "contrast": {"value": 1.0},
            "saturation": {"value": 1.0},
            "fade_in": {"duration": 1.0},
            "fade_out": {"duration": 1.0},
            "speed": {"factor": 1.0},
            "opacity": {"value": 1.0},
            "volume": {"value": 1.0},
        }
        return defaults.get(self.effect_type, {})


@dataclass
class NLEClip:
    """
    NLE Clip - represents a segment of source media on the timeline.
    
    Attributes:
        id: Unique identifier
        source_path: Path to source media file
        source_start: Start time in source (seconds)
        source_end: End time in source (seconds)
        timeline_start: Start position on timeline (seconds)
        track_id: ID of track this clip belongs to
        name: Display name (defaults to source filename)
        effects: List of effects applied to this clip
        selected: Whether clip is currently selected
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    source_path: str = ""
    source_start: float = 0.0
    source_end: float = 0.0
    timeline_start: float = 0.0
    track_id: str = ""
    name: str = ""
    effects: List[Effect] = field(default_factory=list)
    selected: bool = False
    
    def __post_init__(self):
        if not self.name and self.source_path:
            import os
            self.name = os.path.basename(self.source_path)
    
    @property
    def duration(self) -> float:
        """Get clip duration in seconds"""
        return self.source_end - self.source_start
    
    @property
    def timeline_end(self) -> float:
        """Get end position on timeline"""
        return self.timeline_start + self.duration
    
    def get_effect(self, effect_type: str) -> Optional[Effect]:
        """Get effect by type if exists"""
        for effect in self.effects:
            if effect.effect_type == effect_type:
                return effect
        return None
    
    def add_effect(self, effect_type: str, params: Dict[str, Any] = None) -> Effect:
        """Add or update an effect"""
        existing = self.get_effect(effect_type)
        if existing:
            if params:
                existing.params.update(params)
            return existing
        
        effect = Effect(effect_type=effect_type, params=params or {})
        self.effects.append(effect)
        return effect
    
    def remove_effect(self, effect_type: str) -> bool:
        """Remove effect by type"""
        for i, effect in enumerate(self.effects):
            if effect.effect_type == effect_type:
                self.effects.pop(i)
                return True
        return False


@dataclass
class NLETrack:
    """
    NLE Track - represents a video or audio track on the timeline.
    
    Attributes:
        id: Unique identifier
        name: Display name
        track_type: VIDEO or AUDIO
        clips: List of clips on this track
        effects: Track-level effects
        muted: Whether track is muted
        locked: Whether track is locked for editing
        visible: Whether track is visible (for video)
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    track_type: TrackType = TrackType.VIDEO
    clips: List[NLEClip] = field(default_factory=list)
    effects: List[Effect] = field(default_factory=list)
    muted: bool = False
    locked: bool = False
    visible: bool = True
    
    def __post_init__(self):
        if not self.name:
            type_name = "Video" if self.track_type == TrackType.VIDEO else "Audio"
            self.name = f"{type_name} Track"
    
    def get_clip(self, clip_id: str) -> Optional[NLEClip]:
        """Get clip by ID"""
        for clip in self.clips:
            if clip.id == clip_id:
                return clip
        return None
    
    def get_clip_at_time(self, time: float) -> Optional[NLEClip]:
        """Get clip at specific timeline time"""
        for clip in self.clips:
            if clip.timeline_start <= time < clip.timeline_end:
                return clip
        return None
    
    def add_clip(self, clip: NLEClip) -> NLEClip:
        """Add clip to track"""
        clip.track_id = self.id
        self.clips.append(clip)
        self._sort_clips()
        return clip
    
    def remove_clip(self, clip_id: str) -> bool:
        """Remove clip by ID"""
        for i, clip in enumerate(self.clips):
            if clip.id == clip_id:
                self.clips.pop(i)
                return True
        return False
    
    def _sort_clips(self):
        """Sort clips by timeline start position"""
        self.clips.sort(key=lambda c: c.timeline_start)


@dataclass
class NLEProject:
    """
    NLE Project - represents the complete timeline project.
    
    Attributes:
        name: Project name
        tracks: List of tracks
        duration: Total project duration in seconds
        fps: Frames per second
        resolution: Tuple of (width, height)
        sample_rate: Audio sample rate
    """
    name: str = "Untitled Project"
    tracks: List[NLETrack] = field(default_factory=list)
    duration: float = 0.0
    fps: float = 24.0
    resolution: tuple = (1920, 1080)
    sample_rate: int = 48000
    
    # Counters for naming tracks
    _video_track_counter: int = field(default=0, repr=False)
    _audio_track_counter: int = field(default=0, repr=False)
    
    def add_track(self, track_type: TrackType, name: str = None) -> NLETrack:
        """
        Add a new track to the project.
        
        Args:
            track_type: VIDEO or AUDIO
            name: Optional custom name
            
        Returns:
            The created track
        """
        if track_type == TrackType.VIDEO:
            self._video_track_counter += 1
            default_name = f"Video {self._video_track_counter}"
        else:
            self._audio_track_counter += 1
            default_name = f"Audio {self._audio_track_counter}"
        
        track = NLETrack(
            name=name or default_name,
            track_type=track_type
        )
        self.tracks.append(track)
        return track
    
    def remove_track(self, track_id: str) -> bool:
        """Remove track by ID"""
        for i, track in enumerate(self.tracks):
            if track.id == track_id:
                self.tracks.pop(i)
                return True
        return False
    
    def get_track(self, track_id: str) -> Optional[NLETrack]:
        """Get track by ID"""
        for track in self.tracks:
            if track.id == track_id:
                return track
        return None
    
    def get_video_tracks(self) -> List[NLETrack]:
        """Get all video tracks"""
        return [t for t in self.tracks if t.track_type == TrackType.VIDEO]
    
    def get_audio_tracks(self) -> List[NLETrack]:
        """Get all audio tracks"""
        return [t for t in self.tracks if t.track_type == TrackType.AUDIO]
    
    def add_clip(self, track_id: str, clip: NLEClip) -> Optional[NLEClip]:
        """
        Add clip to a specific track.
        
        Args:
            track_id: ID of target track
            clip: Clip to add
            
        Returns:
            The added clip or None if track not found
        """
        track = self.get_track(track_id)
        if track:
            track.add_clip(clip)
            self._update_duration()
            return clip
        return None
    
    def remove_clip(self, clip_id: str) -> bool:
        """
        Remove clip from any track.
        
        Args:
            clip_id: ID of clip to remove
            
        Returns:
            True if clip was found and removed
        """
        for track in self.tracks:
            if track.remove_clip(clip_id):
                self._update_duration()
                return True
        return False
    
    def move_clip(self, clip_id: str, new_timeline_start: float, 
                  new_track_id: str = None) -> bool:
        """
        Move clip to new position and optionally new track.
        
        Args:
            clip_id: ID of clip to move
            new_timeline_start: New start position on timeline
            new_track_id: Optional new track ID
            
        Returns:
            True if move was successful
        """
        clip = self.get_clip(clip_id)
        if not clip:
            return False
        
        # If moving to different track
        if new_track_id and new_track_id != clip.track_id:
            old_track = self.get_track(clip.track_id)
            new_track = self.get_track(new_track_id)
            
            if not new_track:
                return False
            
            # Remove from old track
            if old_track:
                old_track.clips.remove(clip)
            
            # Add to new track
            clip.track_id = new_track_id
            new_track.clips.append(clip)
            new_track._sort_clips()
        
        # Update position
        clip.timeline_start = max(0, new_timeline_start)
        
        # Re-sort track
        track = self.get_track(clip.track_id)
        if track:
            track._sort_clips()
        
        self._update_duration()
        return True
    
    def split_clip(self, clip_id: str, split_time: float) -> Optional[tuple]:
        """
        Split a clip at the given timeline time.
        
        Args:
            clip_id: ID of clip to split
            split_time: Timeline time to split at
            
        Returns:
            Tuple of (left_clip, right_clip) or None if split not possible
        """
        clip = self.get_clip(clip_id)
        if not clip:
            return None
        
        # Check if split time is within clip
        if split_time <= clip.timeline_start or split_time >= clip.timeline_end:
            return None
        
        # Calculate source time for split
        time_in_clip = split_time - clip.timeline_start
        source_split_time = clip.source_start + time_in_clip
        
        # Create left clip (original becomes left)
        left_clip = NLEClip(
            source_path=clip.source_path,
            source_start=clip.source_start,
            source_end=source_split_time,
            timeline_start=clip.timeline_start,
            track_id=clip.track_id,
            name=clip.name,
            effects=[Effect(effect_type=e.effect_type, params=e.params.copy()) 
                    for e in clip.effects]
        )
        
        # Create right clip
        right_clip = NLEClip(
            source_path=clip.source_path,
            source_start=source_split_time,
            source_end=clip.source_end,
            timeline_start=split_time,
            track_id=clip.track_id,
            name=clip.name,
            effects=[Effect(effect_type=e.effect_type, params=e.params.copy()) 
                    for e in clip.effects]
        )
        
        # Replace original clip with two new clips
        track = self.get_track(clip.track_id)
        if track:
            # Find index of original clip
            idx = track.clips.index(clip)
            track.clips.pop(idx)
            track.clips.insert(idx, left_clip)
            track.clips.insert(idx + 1, right_clip)
            track._sort_clips()
        
        self._update_duration()
        return (left_clip, right_clip)
    
    def get_clip(self, clip_id: str) -> Optional[NLEClip]:
        """Get clip by ID from any track"""
        for track in self.tracks:
            clip = track.get_clip(clip_id)
            if clip:
                return clip
        return None
    
    def get_clip_at_time(self, time: float, track_type: TrackType = None) -> Optional[NLEClip]:
        """Get clip at specific timeline time"""
        for track in self.tracks:
            if track_type and track.track_type != track_type:
                continue
            clip = track.get_clip_at_time(time)
            if clip:
                return clip
        return None
    
    def _update_duration(self):
        """Update total project duration based on clips"""
        max_end = 0.0
        for track in self.tracks:
            for clip in track.clips:
                max_end = max(max_end, clip.timeline_end)
        self.duration = max_end
    
    def clear(self):
        """Clear all tracks and reset project"""
        self.tracks.clear()
        self.duration = 0.0
        self._video_track_counter = 0
        self._audio_track_counter = 0
    
    def to_dict(self) -> dict:
        """Serialize project to dictionary"""
        return {
            "name": self.name,
            "duration": self.duration,
            "fps": self.fps,
            "resolution": list(self.resolution),
            "sample_rate": self.sample_rate,
            "tracks": [
                {
                    "id": t.id,
                    "name": t.name,
                    "type": t.track_type.value,
                    "muted": t.muted,
                    "locked": t.locked,
                    "visible": t.visible,
                    "clips": [
                        {
                            "id": c.id,
                            "source_path": c.source_path,
                            "source_start": c.source_start,
                            "source_end": c.source_end,
                            "timeline_start": c.timeline_start,
                            "name": c.name,
                            "effects": [
                                {"type": e.effect_type, "params": e.params, "enabled": e.enabled}
                                for e in c.effects
                            ]
                        }
                        for c in t.clips
                    ],
                    "effects": [
                        {"type": e.effect_type, "params": e.params, "enabled": e.enabled}
                        for e in t.effects
                    ]
                }
                for t in self.tracks
            ]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'NLEProject':
        """Deserialize project from dictionary"""
        project = cls(
            name=data.get("name", "Untitled Project"),
            duration=data.get("duration", 0.0),
            fps=data.get("fps", 24.0),
            resolution=tuple(data.get("resolution", [1920, 1080])),
            sample_rate=data.get("sample_rate", 48000)
        )
        
        for track_data in data.get("tracks", []):
            track_type = TrackType(track_data.get("type", "video"))
            track = NLETrack(
                id=track_data.get("id"),
                name=track_data.get("name"),
                track_type=track_type,
                muted=track_data.get("muted", False),
                locked=track_data.get("locked", False),
                visible=track_data.get("visible", True)
            )
            
            for clip_data in track_data.get("clips", []):
                clip = NLEClip(
                    id=clip_data.get("id"),
                    source_path=clip_data.get("source_path", ""),
                    source_start=clip_data.get("source_start", 0.0),
                    source_end=clip_data.get("source_end", 0.0),
                    timeline_start=clip_data.get("timeline_start", 0.0),
                    name=clip_data.get("name", ""),
                    track_id=track.id
                )
                
                for effect_data in clip_data.get("effects", []):
                    effect = Effect(
                        effect_type=effect_data.get("type"),
                        params=effect_data.get("params", {}),
                        enabled=effect_data.get("enabled", True)
                    )
                    clip.effects.append(effect)
                
                track.clips.append(clip)
            
            for effect_data in track_data.get("effects", []):
                effect = Effect(
                    effect_type=effect_data.get("type"),
                    params=effect_data.get("params", {}),
                    enabled=effect_data.get("enabled", True)
                )
                track.effects.append(effect)
            
            project.tracks.append(track)
            
            # Update counters based on track names
            if track_type == TrackType.VIDEO:
                project._video_track_counter += 1
            else:
                project._audio_track_counter += 1
        
        return project
