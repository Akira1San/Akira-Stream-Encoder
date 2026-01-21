# Design Document: H.265 Codec Support

## Overview

This design document outlines the implementation of comprehensive H.265 (HEVC) codec support for the existing Python-based video encoder application. The current application has partial H.265 support through GPU-accelerated NVENC encoding but lacks CPU-based H.265 encoding (libx265) and H.265-specific optimization features.

The design focuses on extending the existing encoder framework to include libx265 CPU encoding, improving H.265 parameter handling, enhancing container compatibility validation, and providing H.265-specific quality controls while maintaining backward compatibility with existing H.264 workflows.

## Architecture

The H.265 codec support will be integrated into the existing modular architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    VideoEncoderApp                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   ConfigTab     │  │    VideoTab     │  │ EncodingPanel│ │
│  │                 │  │                 │  │             │ │
│  │ - File Management│  │ - Preview       │  │ - Encoder   │ │
│  │ - Path Settings │  │ - Settings UI   │  │   Selection │ │
│  │                 │  │                 │  │ - Quality   │ │
│  └─────────────────┘  └─────────────────┘  │   Controls  │ │
│                                            └─────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              FFmpeg Command Builder                     │ │
│  │                                                         │ │
│  │ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │ │
│  │ │   H.264     │ │   H.265     │ │    Container        │ │ │
│  │ │  Encoder    │ │  Encoder    │ │   Compatibility     │ │ │
│  │ │  Handler    │ │  Handler    │ │    Validator        │ │ │
│  │ │             │ │             │ │                     │ │ │
│  │ │ - h264_nvenc│ │ - hevc_nvenc│ │ - MP4 validation    │ │ │
│  │ │ - libx264   │ │ - libx265   │ │ - MKV validation    │ │ │
│  │ │             │ │             │ │ - AVI warnings      │ │ │
│  │ └─────────────┘ └─────────────┘ └─────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

The design maintains the existing single-file architecture while extending functionality through:
- Enhanced encoder selection logic in `EncodingPanel`
- Extended FFmpeg command building in `build_ffmpeg_command()`
- Improved container compatibility validation in `validate_container_codec()`
- H.265-specific parameter handling throughout the encoding pipeline

## Components and Interfaces

### 1. Enhanced Encoder Selection Component

**Location**: `encoding_settings.py` - `EncodingPanel` class

**Current State**: 
```python
values=["h264_nvenc", "hevc_nvenc", "libx264"]
```

**Enhanced Interface**:
```python
values=["h264_nvenc", "hevc_nvenc", "libx264", "libx265"]
```

**Responsibilities**:
- Provide libx265 as a selectable encoder option
- Maintain existing encoder options for backward compatibility
- Trigger encoder-specific UI updates when selection changes

### 2. H.265 Parameter Handler Component

**Location**: `zve5.py` - `build_ffmpeg_command()` method

**Interface**:
```python
def apply_h265_parameters(self, cmd: List[str], encoder: str, use_gpu: bool) -> List[str]:
    """Apply H.265-specific encoding parameters based on encoder type"""
    pass

def get_h265_quality_range(self, encoder: str) -> Tuple[int, int]:
    """Get appropriate quality range for H.265 encoder (CRF/CQ)"""
    pass

def get_h265_preset(self, encoder: str) -> str:
    """Get optimal preset for H.265 encoder"""
    pass
```

**Responsibilities**:
- Apply encoder-specific parameters (libx265 vs hevc_nvenc)
- Handle quality settings (CRF for libx265, CQ for hevc_nvenc)
- Set appropriate presets and optimization flags
- Configure pixel format and profile settings

### 3. Enhanced Container Compatibility Validator

**Location**: `zve5.py` - `validate_container_codec()` method

**Current Interface**:
```python
compatibility = {
    "mp4": ["h264_nvenc", "h264_amf", "libx264", "hevc_nvenc", "hevc_amf", "libx265"],
    "mkv": ["h264_nvenc", "h264_amf", "libx264", "hevc_nvenc", "hevc_amf", "libx265", "vp9", "av1"],
    "avi": ["h264_nvenc", "h264_amf", "libx264"]
}
```

**Enhanced Interface**:
```python
def validate_h265_container_compatibility(self, container: str, encoder: str) -> ValidationResult:
    """Validate H.265 encoder compatibility with container format"""
    pass

class ValidationResult:
    is_compatible: bool
    warning_message: Optional[str]
    suggested_containers: List[str]
```

**Responsibilities**:
- Validate H.265 encoder compatibility with selected container
- Provide specific warnings for problematic combinations (H.265 + AVI)
- Suggest alternative containers when compatibility issues exist
- Handle edge cases for different H.265 profiles

### 4. H.265 Quality Control Component

**Location**: `encoding_settings.py` - Quality control widgets

**Interface**:
```python
def update_quality_range_for_encoder(self, encoder: str) -> None:
    """Update quality slider range based on selected encoder"""
    pass

def get_encoder_quality_mapping(self, encoder: str, quality_value: int) -> Dict[str, Any]:
    """Map UI quality value to encoder-specific parameters"""
    pass
```

**Responsibilities**:
- Adjust quality control ranges based on encoder (CRF 18-28 for libx265, CQ 18-30 for hevc_nvenc)
- Provide encoder-specific quality parameter mapping
- Display appropriate quality labels and tooltips

## Data Models

### Encoder Configuration Model

```python
@dataclass
class EncoderConfig:
    name: str                    # "libx265", "hevc_nvenc", etc.
    type: EncoderType           # CPU, GPU_NVENC, GPU_AMF
    codec: str                  # "hevc", "h264"
    quality_mode: str           # "crf", "cq", "cbr"
    quality_range: Tuple[int, int]  # (min, max) quality values
    default_preset: str         # "medium", "p4", etc.
    supported_containers: List[str]  # ["mp4", "mkv"]
    
class EncoderType(Enum):
    CPU = "cpu"
    GPU_NVENC = "gpu_nvenc" 
    GPU_AMF = "gpu_amf"
```

### FFmpeg Command Configuration Model

```python
@dataclass
class H265CommandConfig:
    encoder: str                # "libx265" or "hevc_nvenc"
    quality_value: int          # CRF/CQ value
    preset: str                # Encoder preset
    profile: str               # "main", "main10"
    pixel_format: str          # "yuv420p", "yuv420p10le"
    keyframe_interval: int     # GOP size
    bframes: int               # B-frame count
    additional_params: Dict[str, str]  # Encoder-specific parameters
```

### Container Compatibility Model

```python
@dataclass
class ContainerCompatibility:
    container: str              # "mp4", "mkv", "avi"
    encoder: str               # "libx265", "hevc_nvenc"
    is_compatible: bool        # Full compatibility
    has_warnings: bool         # Compatibility with issues
    warning_message: str       # User-facing warning text
    alternatives: List[str]    # Suggested alternatives
```

Now I need to use the prework tool to analyze the acceptance criteria before writing the correctness properties:

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Encoder Selection Logic
*For any* GPU acceleration setting (enabled/disabled) and H.265 encoding request, the system should select hevc_nvenc when GPU is enabled and libx265 when GPU is disabled
**Validates: Requirements 1.3, 2.2, 2.3**

### Property 2: Encoder-Specific Parameter Application
*For any* selected H.265 encoder (libx265 or hevc_nvenc), the generated FFmpeg command should contain the encoder-specific parameters appropriate for that encoder type
**Validates: Requirements 1.4, 5.1, 5.2**

### Property 3: Quality Mode Mapping
*For any* H.265 encoder selection, libx265 should use CRF mode with range 18-28 and hevc_nvenc should use CQ mode with NVENC-appropriate range
**Validates: Requirements 3.1, 3.2**

### Property 4: H.265 Encoding Parameters Consistency
*For any* H.265 encoder in use, the system should apply consistent pixel format (yuv420p), profile settings (main/main10), and GOP structure optimizations
**Validates: Requirements 5.3, 5.4**

### Property 5: Container Compatibility Validation
*For any* H.265 encoder and container combination, the system should provide appropriate validation results with warnings for incompatible combinations and suggestions for alternatives
**Validates: Requirements 4.4**

### Property 6: Bitrate Control Integration
*For any* H.265 encoding with bitrate controls enabled, the system should apply appropriate CBR parameters, enforce bitrate limits, and preserve original bitrate characteristics when requested
**Validates: Requirements 6.1, 6.2, 6.3**

### Property 7: Error Handling and Fallback
*For any* H.265 encoding failure scenario (missing encoder, hardware limitations, invalid parameters), the system should provide specific error messages and appropriate fallback suggestions
**Validates: Requirements 7.2, 7.3, 7.4**

### Property 8: Settings Persistence Completeness
*For any* H.265-related setting modification (encoder choice, quality settings, parameters), the system should persist all changes to the settings file and restore them correctly on application restart
**Validates: Requirements 8.1, 8.2, 8.3, 8.4**

### Property 9: FFmpeg Command Correctness
*For any* valid H.265 encoding configuration, the generated FFmpeg command should be syntactically correct and contain all required parameters for successful encoding
**Validates: Requirements 1.2**

### Property 10: Hardware Compatibility Validation
*For any* H.265 encoder selection, the system should validate hardware compatibility and display appropriate warnings when hardware requirements are not met
**Validates: Requirements 2.4**

## Error Handling

### H.265 Encoder Availability
- **Missing libx265**: When libx265 is not available in the FFmpeg installation, display clear error message: "libx265 encoder not found. Please install FFmpeg with libx265 support."
- **Missing hevc_nvenc**: When NVENC hardware is not available, gracefully fall back to libx265 with user notification
- **Encoder Detection**: Implement runtime detection of available H.265 encoders through FFmpeg capability queries

### Parameter Validation
- **Quality Range Validation**: Validate CRF/CQ values are within acceptable ranges for each encoder
- **Container Compatibility**: Validate encoder-container combinations and warn about potential issues
- **Hardware Requirements**: Check GPU memory and driver requirements for hevc_nvenc

### Encoding Failures
- **Memory Issues**: Detect memory-related encoding failures and suggest parameter adjustments (lower resolution, reduced B-frames)
- **Hardware Failures**: Implement automatic fallback from GPU to CPU encoding when hardware encoding fails
- **Parameter Conflicts**: Detect and resolve conflicting encoding parameters

### User Feedback
- **Progress Monitoring**: Provide real-time encoding progress for H.265 operations
- **Quality Estimation**: Display estimated file size and quality impact for H.265 settings
- **Performance Warnings**: Warn users about potentially slow CPU encoding with libx265

## Testing Strategy

### Dual Testing Approach
The testing strategy employs both unit tests and property-based tests to ensure comprehensive coverage:

**Unit Tests**: Focus on specific examples, edge cases, and integration points:
- Specific encoder dropdown content validation
- Container compatibility matrix verification  
- Settings file format validation
- Error message content verification
- UI component integration testing

**Property Tests**: Verify universal properties across all inputs:
- Encoder selection logic across all GPU/encoder combinations
- Parameter application correctness for all encoder types
- Settings persistence for all configuration variations
- FFmpeg command generation for all valid input combinations
- Error handling behavior across all failure scenarios

### Property-Based Testing Configuration
- **Testing Library**: Use `hypothesis` for Python property-based testing
- **Test Iterations**: Minimum 100 iterations per property test
- **Test Tagging**: Each property test references its design document property
- **Tag Format**: `# Feature: h265-codec-support, Property {number}: {property_text}`

### Test Coverage Areas
1. **Encoder Selection Logic**: Test all combinations of GPU settings and encoder preferences
2. **FFmpeg Command Generation**: Verify command correctness across all parameter combinations
3. **Container Compatibility**: Test all encoder-container combinations
4. **Settings Persistence**: Verify all H.265 settings are saved and restored correctly
5. **Error Scenarios**: Test all identified error conditions and fallback behaviors
6. **Integration Testing**: Verify H.265 support integrates correctly with existing features (subtitles, filters, etc.)

The combination of unit and property tests ensures both concrete behavior verification and comprehensive input space coverage, providing confidence in the H.265 implementation's correctness and robustness.