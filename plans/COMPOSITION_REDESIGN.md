# Composition-Based Editor Redesign

## Overview

Redesign the NLE from a track-based system to a **stack-based composition system**. This approach is better suited for creating video content from scratch (like After Effects, Motion, or CapCut) rather than editing existing footage.

## Current vs Proposed Architecture

### Current (Track-Based)
```
Timeline
├── Video Track 1 → [Clip A] [Clip B]
├── Audio Track 1 → [Clip C]
```

### Proposed (Stack-Based)
```
Composition (duration: 30s)
├── Layer 1: Background (color/gradient)
│   └── Effect: Blur
├── Layer 2: Video Source
│   └── Effect: Color Correction
├── Layer 3: Text
│   ├── Effect: Drop Shadow
│   └── Effect: Fade In/Out
├── Layer 4: Image Overlay (logo)
```

## Data Models

### Composition
- `id`: Unique identifier
- `name`: Composition name
- `duration`: Total duration in seconds
- `width`: Output width (1920)
- `height`: Output height (1080)
- `fps`: Frame rate (30)
- `layers`: Ordered list of layers (bottom to top)
- `background_color`: Default background

### Layer (Base Class)
- `id`: Unique identifier
- `name`: Display name
- `type`: Layer type (color, video, image, text, shape)
- `enabled`: Visibility toggle
- `locked`: Lock toggle
- `start_time`: When layer appears (default 0)
- `end_time`: When layer ends (default composition duration)
- `opacity`: 0.0 - 1.0
- `blend_mode`: Normal, Multiply, Screen, Overlay, etc.
- `effects`: List of applied effects
- `transform`: Position, scale, rotation, anchor point

### Layer Types

#### ColorLayer extends Layer
- `color`: Fill color (hex or RGBA)
- `gradient`: Optional gradient settings

#### VideoLayer extends Layer
- `source_path`: Path to video file
- `source_start`: Start point in source (for trimming)
- `source_end`: End point in source
- `loop`: Loop video to fit layer duration
- `mute`: Mute audio

#### ImageLayer extends Layer
- `source_path`: Path to image file
- `fit_mode`: Fill, Fit, Stretch, None

#### TextLayer extends Layer
- `text`: Text content
- `font_family`: Font name
- `font_size`: Size in points
- `font_weight`: Normal, Bold, etc.
- `color`: Text color
- `alignment`: Left, Center, Right
- `line_spacing`: Line height multiplier

#### ShapeLayer extends Layer
- `shape_type`: Rectangle, Ellipse, Line, Polygon
- `fill_color`: Fill color
- `stroke_color`: Border color
- `stroke_width`: Border width
- `corner_radius`: For rectangles

### Effect (Base Class)
- `id`: Unique identifier
- `type`: Effect type
- `enabled`: On/off toggle
- `parameters`: Dict of effect-specific parameters

#### Effect Types
1. **Color Correction**: brightness, contrast, saturation, hue
2. **Blur**: radius
3. **Shadow**: color, offset_x, offset_y, blur_radius
4. **Glow**: color, radius, intensity
5. **Fade**: in_duration, out_duration
6. **Transform Animation**: keyframes for position, scale, rotation
7. **Crop**: left, top, right, bottom
8. **Mask**: shape, feather, invert

## UI Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  Toolbar: [New] [Open] [Save] | [Add Layer ▼] | [Render]           │
├──────────────┬──────────────────────────────────┬───────────────────┤
│              │                                  │                   │
│  Layer Stack │         Preview                  │   Properties      │
│              │                                  │                   │
│  ┌─────────┐ │   ┌────────────────────────┐    │   Layer: Text     │
│  │ ☰ Text  │ │   │                        │    │   ─────────────   │
│  ├─────────┤ │   │    Preview Content     │    │   Text: "Title"   │
│  │ ☰ Video │ │   │                        │    │   Font: Arial     │
│  ├─────────┤ │   │                        │    │   Size: 48        │
│  │ ☰ Color │ │   └────────────────────────┘    │   Color: #FFFFFF  │
│  └─────────┘ │                                  │                   │
│              │   [▶ Play] [⏹ Stop] [-1s] [+1s] │   Effects:        │
│  [+] [-]     │   00:00:05 / 00:00:30           │   ☑ Shadow        │
│              │                                  │   ☑ Fade          │
├──────────────┴──────────────────────────────────┴───────────────────┤
│  Timeline                                                            │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ [00:00═══════════════════════════════════════════════════00:30] ││
│  │     ▼ Playhead                                                  ││
│  ├─────────────────────────────────────────────────────────────────┤│
│  │ Text    │███████████████████████████████████████████████████████││
│  │ Video   │░░░░░░░░░░░░███████████████████████████████████████████││
│  │ Color   │███████████████████████████████████████████████████████││
│  └─────────────────────────────────────────────────────────────────┘│
│  [➖] [100%] [➕]                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Implementation Plan

### Phase 1: Data Models
1. Create `Composition` dataclass
2. Create `Layer` base class and subclasses
3. Create `Effect` base class and subclasses
4. Add serialization (to_dict/from_dict)

### Phase 2: Layer Stack UI
1. Create `LayerStackWidget` (left panel)
2. Implement layer list with drag-to-reorder
3. Add layer visibility/lock toggles
4. Add layer type icons

### Phase 3: Properties Panel
1. Create `PropertiesPanel` (right panel)
2. Implement layer-specific property editors
3. Add effect list with add/remove
4. Implement effect parameter controls

### Phase 4: Timeline Redesign
1. Simplify timeline to show layer bars
2. Implement layer duration editing
3. Add keyframe markers (for animations)
4. Connect to preview

### Phase 5: Preview Integration
1. Update preview to render composition
2. Implement layer compositing
3. Add real-time preview updates

### Phase 6: Rendering
1. Implement FFmpeg composition rendering
2. Layer compositing pipeline
3. Effect application
4. Progress reporting

## File Structure

```
PySide6/
├── composition/
│   ├── __init__.py
│   ├── models.py          # Composition, Layer, Effect classes
│   ├── composition_tab.py # Main composition tab widget
│   ├── layer_stack.py     # Layer list panel
│   ├── properties_panel.py # Properties editor panel
│   ├── timeline.py        # Simplified timeline
│   ├── preview.py         # Composition preview
│   ├── effects.py         # Effect implementations
│   └── renderer.py        # FFmpeg rendering
```

## Key Features

### Layer Management
- Add layers: Color, Video, Image, Text, Shape
- Reorder by drag-and-drop
- Duplicate, Delete layers
- Group layers (future)

### Properties Editing
- Transform: Position, Scale, Rotation
- Timing: Start time, End time, Duration
- Type-specific properties
- Real-time preview updates

### Effects System
- Add multiple effects per layer
- Reorder effects
- Enable/disable individual effects
- Effect presets

### Rendering
- Export to MP4 (H.264/H.265)
- Configurable quality
- Resolution scaling
- Frame rate selection

## Migration Path

The existing NLE code can be kept for users who want traditional video editing. The composition editor will be a separate tab:

1. **NLE Tab** - Track-based video editing (current implementation)
2. **Composition Tab** - Stack-based content creation (new)

Both can coexist in the application.
