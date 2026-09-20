"""
DVD Handler - VIDEO_TS folder detection and title parsing (PySide6)

Handles DVD-Video structure (VIDEO_TS folder) detection, title parsing,
and VOB file concatenation for encoding.
"""
import os
import re
import subprocess
import tempfile
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class DVDTitle:
    """Represents a single DVD title (movie/episode)"""
    title_number: int
    vob_files: List[str]
    duration: float = 0.0  # in seconds
    size_bytes: int = 0
    is_main: bool = False
    audio_tracks: List[Dict] = field(default_factory=list)
    subtitles: List[Dict] = field(default_factory=list)
    
    @property
    def duration_display(self) -> str:
        """Human-readable duration"""
        if self.duration <= 0:
            return "Unknown"
        hours, remainder = divmod(int(self.duration), 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"
    
    @property
    def size_display(self) -> str:
        """Human-readable size"""
        if self.size_bytes < 1024:
            return f"{self.size_bytes} B"
        elif self.size_bytes < 1024 * 1024:
            return f"{self.size_bytes / 1024:.1f} KB"
        elif self.size_bytes < 1024 * 1024 * 1024:
            return f"{self.size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{self.size_bytes / (1024 * 1024 * 1024):.2f} GB"


class DVDHandler:
    """
    Handles DVD-Video (VIDEO_TS) folder detection and processing.
    
    DVD Structure:
    VIDEO_TS/
    ├── VIDEO_TS.IFO  - First Play PGC (menu)
    ├── VIDEO_TS.VOB  - Menu video
    ├── VTS_01_0.IFO  - Title 1 info
    ├── VTS_01_0.VOB  - Title 1 menu
    ├── VTS_01_1.VOB  - Title 1 content (1GB chunks)
    ├── VTS_01_2.VOB
    └── ...
    """
    
    # VOB file pattern: VTS_XX_Y.VOB where XX is title (01-99), Y is part (0-9)
    VOB_PATTERN = re.compile(r'^VTS_(\d{2})_(\d)\.VOB$', re.IGNORECASE)
    IFO_PATTERN = re.compile(r'^VTS_(\d{2})_0\.IFO$', re.IGNORECASE)
    
    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe",
                 log_callback=None, backend=None):
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        self.log = log_callback or (lambda msg, level="INFO": None)
        self.backend = backend
        self._concat_file: Optional[str] = None
        
    def is_video_ts_folder(self, folder_path: str) -> bool:
        """
        Check if a folder is a valid VIDEO_TS DVD structure.
        
        Args:
            folder_path: Path to check
            
        Returns:
            True if folder contains VIDEO_TS structure
        """
        if not os.path.isdir(folder_path):
            return False
            
        # Check for VIDEO_TS folder (either the folder itself or parent)
        video_ts_path = folder_path
        if not folder_path.upper().endswith('VIDEO_TS'):
            # Check if VIDEO_TS subfolder exists
            candidate = os.path.join(folder_path, 'VIDEO_TS')
            if os.path.isdir(candidate):
                video_ts_path = candidate
            else:
                return False
        
        # Must have at least one IFO file
        ifo_files = [f for f in os.listdir(video_ts_path) 
                     if f.upper().endswith('.IFO')]
        
        if not ifo_files:
            return False
            
        # Must have at least one VOB file
        vob_files = [f for f in os.listdir(video_ts_path) 
                     if f.upper().endswith('.VOB')]
        
        return len(vob_files) > 0
    
    def find_video_ts_folder(self, path: str) -> Optional[str]:
        """
        Find VIDEO_TS folder from a given path.
        
        Args:
            path: Starting path (could be VIDEO_TS, DVD root, or any subfolder)
            
        Returns:
            Path to VIDEO_TS folder or None if not found
        """
        if not os.path.exists(path):
            return None
            
        # If path is VIDEO_TS folder
        if path.upper().endswith('VIDEO_TS') and os.path.isdir(path):
            return path
            
        # Check for VIDEO_TS subfolder
        video_ts = os.path.join(path, 'VIDEO_TS')
        if os.path.isdir(video_ts):
            return video_ts
            
        # Check parent directory
        parent = os.path.dirname(path)
        if parent:
            video_ts = os.path.join(parent, 'VIDEO_TS')
            if os.path.isdir(video_ts):
                return video_ts
                
        return None
    
    def get_dvd_titles(self, folder_path: str) -> List[DVDTitle]:
        """
        Parse DVD structure and return list of titles.
        
        Args:
            folder_path: Path to VIDEO_TS folder or DVD root
            
        Returns:
            List of DVDTitle objects sorted by title number
        """
        video_ts_path = self.find_video_ts_folder(folder_path)
        if not video_ts_path:
            self.log(f"Not a valid VIDEO_TS folder: {folder_path}", "ERROR")
            return []
        
        self.log(f"Scanning VIDEO_TS folder: {video_ts_path}", "INFO")
        
        # Group VOB files by title
        titles_vobs: Dict[int, List[str]] = {}
        
        for filename in os.listdir(video_ts_path):
            match = self.VOB_PATTERN.match(filename)
            if match:
                title_num = int(match.group(1))
                part_num = int(match.group(2))
                
                # Skip menu VOBs (part 0)
                if part_num == 0:
                    continue
                    
                if title_num not in titles_vobs:
                    titles_vobs[title_num] = []
                    
                vob_path = os.path.join(video_ts_path, filename)
                titles_vobs[title_num].append(vob_path)
        
        if not titles_vobs:
            self.log("No title VOB files found", "WARN")
            return []
        
        # Create DVDTitle objects
        titles = []
        for title_num, vob_files in sorted(titles_vobs.items()):
            # Sort VOB files by part number
            vob_files.sort(key=lambda p: int(self.VOB_PATTERN.match(os.path.basename(p)).group(2)))
            
            title = DVDTitle(
                title_number=title_num,
                vob_files=vob_files,
                size_bytes=sum(os.path.getsize(f) for f in vob_files if os.path.exists(f))
            )
            
            # Get duration using ffprobe
            title.duration = self._get_title_duration(vob_files)
            
            # Get audio track info
            title.audio_tracks = self._get_title_audio_tracks(vob_files[0])
            
            # Get subtitle track info - pass IFO file path
            ifo_file = os.path.join(video_ts_path, f"VTS_{title_num:02d}_0.IFO")
            if not os.path.exists(ifo_file):
                ifo_file = None
            title.subtitles = self._get_title_subtitle_tracks(vob_files[0], ifo_file)
            
            titles.append(title)
        
        # Mark the longest title as main
        if titles:
            main_title = max(titles, key=lambda t: t.duration)
            main_title.is_main = True
            self.log(f"Main title detected: Title {main_title.title_number} ({main_title.duration_display})", "INFO")
        
        self.log(f"Found {len(titles)} title(s)", "INFO")
        return titles
    
    def _get_title_duration(self, vob_files: List[str]) -> float:
        """
        Get total duration of a title by summing VOB durations.
        
        Args:
            vob_files: List of VOB file paths for the title
            
        Returns:
            Duration in seconds
        """
        total_duration = 0.0
        
        for vob_file in vob_files:
            duration = self._get_video_duration(vob_file)
            if duration > 0:
                total_duration += duration
        
        return total_duration
    
    def _get_video_duration(self, video_path: str) -> float:
        """Get duration of a single video file"""
        if self.backend:
            try:
                d = self.backend.get_duration(video_path)
                if d and d > 0:
                    return d
            except Exception:
                pass
        return self._ffprobe_duration(video_path)

    def _ffprobe_duration(self, video_path: str) -> float:
        """Fallback: get duration via ffprobe"""
        cmd = [
            self.ffprobe_path, "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception as e:
            self.log(f"Duration detection failed for {os.path.basename(video_path)}: {e}", "WARN")
        return 0.0
    
    def _get_title_audio_tracks(self, vob_file: str) -> List[Dict]:
        """Get audio track information from a VOB file"""
        if self.backend:
            try:
                backend_tracks = self.backend.get_audio_tracks(vob_file)
                if backend_tracks:
                    return [{
                        'index': t.get('index', i),
                        'codec': t.get('codec', 'unknown'),
                        'channels': t.get('channels', 2),
                        'language': t.get('language', '')
                    } for i, t in enumerate(backend_tracks)]
            except Exception:
                pass
        return self._ffprobe_audio_tracks(vob_file)

    def _ffprobe_audio_tracks(self, vob_file: str) -> List[Dict]:
        """Fallback: get audio tracks via ffprobe"""
        import json
        cmd = [
            self.ffprobe_path, "-v", "error",
            "-show_entries", "stream=index,codec_type,codec_name,channels:stream_tags=language",
            "-of", "json", vob_file
        ]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return [{
                    'index': s.get('index', 0),
                    'codec': s.get('codec_name', 'unknown'),
                    'channels': s.get('channels', 2),
                    'language': s.get('tags', {}).get('language', '')
                } for s in data.get('streams', []) if s.get('codec_type') == 'audio']
        except Exception as e:
            self.log(f"Audio track detection failed: {e}", "WARN")
        return []
    
    def _get_title_subtitle_tracks(self, vob_file: str, ifo_file: str = None) -> List[Dict]:
        """
        Get subtitle track information from a VOB file or IFO file.
        
        DVD subtitles are stored as subpictures in the MPEG-2 stream.
        The subtitle track information is in the IFO file, not the VOB.
        """
        import json
        
        self.log(f"Scanning for subtitles in: {os.path.basename(vob_file)}", "INFO")
        
        subtitle_tracks = []
        ifo_languages = {}  # Map of stream_id -> language from IFO
        
        # First, get language info from IFO file
        vob_dir = os.path.dirname(vob_file)
        vob_name = os.path.basename(vob_file)
        
        # Find IFO file
        ifo_path = ifo_file
        if not ifo_path or not os.path.exists(ifo_path):
            # VTS_XX_Y.VOB -> VTS_XX_0.IFO
            match = self.VOB_PATTERN.match(vob_name)
            if match:
                title_num = match.group(1)
                ifo_name = f"VTS_{title_num}_0.IFO"
                ifo_path = os.path.join(vob_dir, ifo_name)
        
        if ifo_path and os.path.exists(ifo_path):
            self.log(f"Reading IFO file for languages: {os.path.basename(ifo_path)}", "DEBUG")
            ifo_subs = self._parse_ifo_subtitles(ifo_path)
            if ifo_subs:
                for sub in ifo_subs:
                    # Map stream_id to language
                    stream_id = sub.get('stream_id', 0x20 + sub.get('index', 0))
                    ifo_languages[stream_id] = sub.get('language', 'unknown')
        
        # Method 1: Use FFmpeg with extended analysis to detect DVD subtitles
        # DVD subtitles need larger probe size to be detected
        self.log("Trying FFmpeg with extended analysis...", "DEBUG")
        
        cmd = [
            self.ffmpeg_path,
            "-analyzeduration", "100M",
            "-probesize", "100M",
            "-i", vob_file
        ]
        
        try:
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=60
            )
            
            # ffmpeg outputs to stderr when no output file is specified
            ffmpeg_output = result.stderr
            
            # Look for subtitle streams in the output
            # Pattern: Stream #0:3[0x20]: Subtitle: dvd_subtitle
            import re
            
            sub_pattern = re.compile(
                r'Stream\s+#(\d+):(\d+)\[0x([0-9a-fA-F]+)\]\s*:\s*Subtitle:\s*(\w+)',
                re.IGNORECASE
            )
            
            for match in sub_pattern.finditer(ffmpeg_output):
                file_idx = int(match.group(1))
                stream_idx = int(match.group(2))
                stream_id = int(match.group(3), 16)  # Hex stream ID
                codec = match.group(4)
                
                # Stream ID 0x20-0x3F are subtitle streams
                # The subtitle index can be derived from stream_id
                sub_index = len(subtitle_tracks)
                
                # Get language from IFO if available
                language = ifo_languages.get(stream_id, f"Track {sub_index}")
                
                subtitle_tracks.append({
                    'index': stream_idx,
                    'sub_index': sub_index,
                    'stream_id': stream_id,
                    'codec': codec,
                    'language': language,
                    'title': ''
                })
                self.log(f"Found subtitle via FFmpeg: stream {stream_idx}, id 0x{stream_id:02X}, lang={language}", "DEBUG")
            
        except Exception as e:
            self.log(f"FFmpeg subtitle detection failed: {e}", "WARN")
        
        # If FFmpeg found subtitles, return them
        if subtitle_tracks:
            self.log(f"Found {len(subtitle_tracks)} subtitle(s) via FFmpeg", "INFO")
            return subtitle_tracks
        
        # Method 2: Fall back to IFO-only detection
        if ifo_path and os.path.exists(ifo_path):
            self.log(f"Reading IFO file: {os.path.basename(ifo_path)}", "DEBUG")
            ifo_subs = self._parse_ifo_subtitles(ifo_path)
            if ifo_subs:
                subtitle_tracks = ifo_subs
                self.log(f"Found {len(subtitle_tracks)} subtitle(s) from IFO file", "INFO")
                return subtitle_tracks
        
        self.log(f"Found {len(subtitle_tracks)} subtitle track(s) in {os.path.basename(vob_file)}", "INFO")
        return subtitle_tracks
    
    def _parse_ifo_subtitles(self, ifo_path: str) -> List[Dict]:
        """
        Parse subtitle information from an IFO file.
        
        IFO files contain the PGCI (Program Chain Information) which includes
        subtitle (subpicture) stream information.
        """
        subtitle_tracks = []
        
        try:
            with open(ifo_path, 'rb') as f:
                data = f.read()
            
            self.log(f"IFO file size: {len(data)} bytes", "DEBUG")
            
            # Check for valid IFO header
            if len(data) < 12:
                return []
            
            # DVD IFO files start with "DVDVIDEO-VTS" or "DVDVIDEO-VMG"
            header = data[0:12]
            if not (header.startswith(b'DVDVIDEO-VTS') or header.startswith(b'DVDVIDEO-VMG')):
                self.log(f"Not a valid IFO file header: {header}", "DEBUG")
                return []
            
            # VTSI_MAT (Video Title Set Information Management Area Table)
            # Subpicture stream attributes are at offset 0x254-0x2B3 (32 streams max, 6 bytes each)
            # Each entry: 1 byte coding mode, 1 byte reserved, 2 bytes language code, 2 bytes reserved
            
            # First, get number of subpicture streams from offset 0x255
            num_subpic = 0
            if 0x255 < len(data):
                num_subpic = data[0x255]
                self.log(f"Number of subpicture streams at 0x255: {num_subpic}", "DEBUG")
            
            # Subpicture attribute table starts at 0x254
            # But the actual language codes are at different positions within each entry
            # Based on the log analysis:
            # - 0x258: bg (offset 0x254 + 4 = 0x258, so language is at bytes 4-5 of entry 0)
            # - 0x25E: en (0x258 + 6 = 0x25E)
            # etc.
            # So the table starts at 0x254, and language is at bytes 4-5 of each 6-byte entry
            
            subpic_attr_offset = 0x254
            
            # Dump the subpicture attribute area for debugging
            if len(data) >= 0x2B4:
                debug_bytes = ' '.join(f'{data[0x254+i]:02X}' for i in range(96))
                self.log(f"Bytes at 0x254-0x2B4: {debug_bytes}", "DEBUG")
            
            # Scan subpicture streams
            # Use num_subpic if valid, otherwise scan all 32 possible
            max_streams = num_subpic if 0 < num_subpic <= 32 else 32
            
            for i in range(max_streams):
                entry_offset = subpic_attr_offset + (i * 6)
                
                if entry_offset + 6 > len(data):
                    break
                
                entry = data[entry_offset:entry_offset + 6]
                
                # Log raw bytes for debugging
                self.log(f"Subpic {i} at 0x{entry_offset:X}: {' '.join(f'{b:02X}' for b in entry)}", "DEBUG")
                
                # Check if this entry is valid (non-zero bytes)
                if all(b == 0 for b in entry):
                    self.log(f"Subpic {i}: empty entry, skipping", "DEBUG")
                    continue
                
                # Language code is at bytes 4-5 of each entry (based on log analysis)
                # But also try other positions as fallback
                lang_positions = [(4, 5), (2, 3), (0, 1)]
                language = None
                
                for pos1, pos2 in lang_positions:
                    if pos1 < len(entry) and pos2 < len(entry):
                        b1, b2 = entry[pos1], entry[pos2]
                        # Check for ASCII lowercase letters (a-z = 97-122)
                        if 97 <= b1 <= 122 and 97 <= b2 <= 122:
                            lang = chr(b1) + chr(b2)
                            if lang.isalpha():
                                language = lang
                                self.log(f"Subpic {i}: found lang '{lang}' at bytes {pos1}-{pos2}", "DEBUG")
                                break
                
                if not language:
                    language = f"Track {i}"
                
                # Stream ID for DVD subtitles is 0x20 + index
                stream_id = 0x20 + i
                
                subtitle_tracks.append({
                    'index': i,
                    'sub_index': len(subtitle_tracks),
                    'stream_id': stream_id,
                    'codec': 'dvd_subtitle',
                    'language': language,
                    'title': ''
                })
                self.log(f"IFO subtitle {i}: language={language}, stream_id=0x{stream_id:02X}", "DEBUG")
            
            self.log(f"Found {len(subtitle_tracks)} subtitle track(s) from IFO", "INFO")
            
        except Exception as e:
            self.log(f"IFO parsing failed: {e}", "WARN")
        
        return subtitle_tracks
    
    def _detect_subtitles_mplayer(self, vob_file: str) -> List[Dict]:
        """Use mplayer or mpv to detect subtitle streams (if available)"""
        subtitle_tracks = []
        
        # Try mpv first (more common on modern systems)
        for player in ['mpv', 'mplayer']:
            try:
                cmd = [player, '-identify', '-frames', '0', '-vo', 'null', '-ao', 'null', vob_file]
                result = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, timeout=30
                )
                
                output = result.stdout + result.stderr
                
                # mpv/mplayer identify output includes lines like:
                # ID_SUBTITLE_ID=0
                # ID_SID_0_LANG=en
                import re
                
                sub_ids = re.findall(r'ID_SUBTITLE_ID=(\d+)', output)
                
                for sub_id in sub_ids:
                    lang_match = re.search(rf'ID_SID_{sub_id}_LANG=(\w+)', output)
                    language = lang_match.group(1) if lang_match else f"Track {sub_id}"
                    
                    subtitle_tracks.append({
                        'index': int(sub_id),
                        'sub_index': int(sub_id),
                        'codec': 'dvd_subtitle',
                        'language': language,
                        'title': ''
                    })
                
                if subtitle_tracks:
                    self.log(f"Found {len(subtitle_tracks)} subtitle(s) via {player}", "INFO")
                    return subtitle_tracks
                    
            except FileNotFoundError:
                continue
            except Exception as e:
                self.log(f"{player} subtitle detection failed: {e}", "DEBUG")
                continue
        
        return []
    
    def extract_subtitle(self, vob_file: str, subtitle_index: int, output_path: str, 
                         concat_file: str = None) -> Optional[str]:
        """
        Extract a DVD subtitle track to an external .sub file.
        
        Args:
            vob_file: Path to the source VOB file
            subtitle_index: Subtitle stream index (e.g., 0 for 0:s:0)
            output_path: Base path for output (without extension)
            concat_file: Optional path to concat file for full title extraction
            
        Returns:
            Path to extracted .sub file, or None on failure
        """
        # DVD subtitles are typically in VobSub format
        # FFmpeg can extract them to .sub + .idx pair
        sub_file = f"{output_path}.sub"
        idx_file = f"{output_path}.idx"
        
        self.log(f"Extracting subtitle track {subtitle_index}...", "INFO")
        
        # Method 0: Try MKV intermediate format (most reliable for FFmpeg)
        # The concat demuxer doesn't expose subtitle streams, so we need to remux to MKV first
        mkv_result = self._extract_subtitle_via_mkv(vob_file, subtitle_index, output_path, concat_file)
        if mkv_result and os.path.exists(mkv_result) and os.path.getsize(mkv_result) > 0:
            return mkv_result
        
        # Method 1: Try mplayer for VobSub extraction (most reliable for DVD)
        # mplayer can extract DVD subtitles as VobSub format
        mplayer_result = self._extract_subtitle_mplayer(vob_file, subtitle_index, output_path, concat_file)
        if mplayer_result and os.path.exists(mplayer_result) and os.path.getsize(mplayer_result) > 0:
            return mplayer_result
        
        # Method 2: Try FFmpeg extraction
        # First, let's check what streams are actually available
        probe_cmd = [
            self.ffprobe_path,
            "-v", "error",
            "-show_streams",
            "-select_streams", "s",
            "-of", "json",
            vob_file
        ]
        
        try:
            probe_result = subprocess.run(
                probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=30
            )
            
            if probe_result.returncode == 0:
                import json
                probe_data = json.loads(probe_result.stdout)
                available_subs = probe_data.get('streams', [])
                self.log(f"FFprobe found {len(available_subs)} subtitle stream(s) in VOB", "DEBUG")
                
                for i, stream in enumerate(available_subs):
                    self.log(f"  Stream {i}: index={stream.get('index')}, codec={stream.get('codec_name')}", "DEBUG")
        except Exception as e:
            self.log(f"FFprobe check failed: {e}", "DEBUG")
        
        # Try extraction from concat file first (full title)
        if concat_file and os.path.exists(concat_file):
            self.log(f"Trying subtitle extraction from concat file...", "DEBUG")
            
            # Try different stream indices - DVD subtitles might be at different positions
            for try_idx in range(subtitle_index, min(subtitle_index + 10, 32)):
                cmd = [
                    self.ffmpeg_path,
                    "-y",  # Overwrite
                    "-analyzeduration", "100M",  # Extended analysis for DVD subtitles
                    "-probesize", "100M",
                    "-f", "concat", "-safe", "0",
                    "-i", concat_file,
                    "-map", f"0:s:{try_idx}",
                    "-c:s", "copy",  # Copy without re-encoding
                    sub_file
                ]
                
                try:
                    result = subprocess.run(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        text=True, timeout=300  # 5 minute timeout for full title
                    )
                    
                    if result.returncode == 0 and os.path.exists(sub_file) and os.path.getsize(sub_file) > 0:
                        self.log(f"Subtitle extracted from concat (stream {try_idx}) to: {sub_file}", "SUCCESS")
                        return sub_file
                        
                except Exception as e:
                    pass
            
            # If specific indices failed, try without specifying stream
            self.log("Trying auto subtitle selection...", "DEBUG")
            cmd = [
                self.ffmpeg_path,
                "-y",
                "-analyzeduration", "100M",
                "-probesize", "100M",
                "-f", "concat", "-safe", "0",
                "-i", concat_file,
                "-map", "0:s",  # Map all subtitle streams
                "-c:s", "copy",
                sub_file
            ]
            
            try:
                result = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, timeout=300
                )
                
                if result.returncode == 0 and os.path.exists(sub_file) and os.path.getsize(sub_file) > 0:
                    self.log(f"Subtitle extracted (auto) to: {sub_file}", "SUCCESS")
                    return sub_file
                else:
                    # Log full error for debugging
                    self.log(f"Auto extraction failed: {result.stderr}", "DEBUG")
            except Exception as e:
                self.log(f"Auto extraction error: {e}", "DEBUG")
        
        # Try extraction from single VOB file
        self.log(f"Trying extraction from single VOB: {os.path.basename(vob_file)}...", "DEBUG")
        
        for try_idx in range(min(10, 32)):
            cmd = [
                self.ffmpeg_path,
                "-y",  # Overwrite
                "-analyzeduration", "100M",  # Extended analysis for DVD subtitles
                "-probesize", "100M",
                "-i", vob_file,
                "-map", f"0:s:{try_idx}",
                "-c:s", "copy",  # Copy without re-encoding
                sub_file
            ]
            
            try:
                result = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, timeout=120
                )
                
                if result.returncode == 0 and os.path.exists(sub_file) and os.path.getsize(sub_file) > 0:
                    self.log(f"Subtitle extracted (stream {try_idx}) to: {sub_file}", "SUCCESS")
                    return sub_file
                    
            except Exception as e:
                pass
        
        # Log the last error
        self.log(f"Subtitle extraction failed for all stream indices", "WARN")
        self.log(f"Last FFmpeg error: {result.stderr[:500] if 'result' in locals() else 'N/A'}", "DEBUG")
        
        return None
    
    def _extract_subtitle_mplayer(self, vob_file: str, subtitle_index: int, output_path: str,
                                   concat_file: str = None) -> Optional[str]:
        """
        Extract DVD subtitle using mplayer (most reliable for VobSub extraction).
        
        MPlayer can extract DVD subtitles as VobSub format (.sub + .idx files).
        This is the same method SMPlayer uses.
        
        Args:
            vob_file: Path to the source VOB file
            subtitle_index: Subtitle stream index (0-based)
            output_path: Base path for output (without extension)
            concat_file: Optional concat file (not used by mplayer)
            
        Returns:
            Path to extracted .sub file, or None on failure
        """
        sub_file = f"{output_path}.sub"
        idx_file = f"{output_path}.idx"
        
        # Common mplayer paths to try
        mplayer_paths = [
            'mplayer',
            'mplayer2',
            r'C:\Program Files\SMPlayer\mplayer\mplayer.exe',
            r'C:\Program Files (x86)\SMPlayer\mplayer\mplayer.exe',
        ]
        
        for player_path in mplayer_paths:
            try:
                # Check if player is available
                if os.path.isabs(player_path):
                    if not os.path.exists(player_path):
                        continue
                else:
                    # Check if in PATH
                    check_result = subprocess.run(
                        [player_path, '-version'],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        timeout=5
                    )
                    if check_result.returncode != 0:
                        continue
                
                self.log(f"Using mplayer: {player_path}", "INFO")
                
                # MPlayer VobSub extraction command
                # -vobsuboutindex: subtitle index to extract
                # -vobsubout: output base name (without extension)
                # -sid: subtitle ID to extract
                cmd = [
                    player_path,
                    '-nosound',
                    '-novideo',
                    '-vobsuboutindex', str(subtitle_index),
                    '-vobsubout', output_path,
                    '-sid', str(subtitle_index),
                    vob_file
                ]
                
                self.log(f"Running: {' '.join(cmd)}", "DEBUG")
                
                result = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, timeout=300  # 5 minute timeout
                )
                
                # Log output for debugging
                if result.stdout:
                    self.log(f"mplayer stdout: {result.stdout[:500]}", "DEBUG")
                if result.stderr:
                    self.log(f"mplayer stderr: {result.stderr[:500]}", "DEBUG")
                
                # Check if extraction succeeded
                if os.path.exists(sub_file) and os.path.exists(idx_file):
                    if os.path.getsize(sub_file) > 0:
                        self.log(f"Subtitle extracted via mplayer: {sub_file}", "SUCCESS")
                        return sub_file
                    else:
                        self.log(f"mplayer created empty .sub file", "DEBUG")
                
            except FileNotFoundError:
                continue
            except subprocess.TimeoutExpired:
                self.log(f"mplayer extraction timed out", "WARN")
                continue
            except Exception as e:
                self.log(f"mplayer extraction failed: {e}", "DEBUG")
                continue
        
        # Try mpv as alternative (modern fork of mplayer)
        mpv_paths = [
            'mpv',
            r'C:\Program Files\SMPlayer\mpv\mpv.exe',
        ]
        
        for mpv_path in mpv_paths:
            try:
                if os.path.isabs(mpv_path):
                    if not os.path.exists(mpv_path):
                        continue
                
                self.log(f"Trying mpv: {mpv_path}", "INFO")
                
                # mpv doesn't have direct VobSub extraction like mplayer
                # But we can try using it to convert subtitles
                # For now, skip mpv
                self.log("mpv doesn't support direct VobSub extraction", "DEBUG")
                break
                
            except Exception as e:
                self.log(f"mpv check failed: {e}", "DEBUG")
        
        return None
    
    def _extract_subtitle_via_mkv(self, vob_file: str, subtitle_index: int, output_path: str,
                                   concat_file: str = None) -> Optional[str]:
        """
        Extract DVD subtitle by first remuxing to MKV (which preserves subtitle streams).
        
        The concat demuxer doesn't expose DVD subtitle streams, but MKV does.
        This method:
        1. Remuxes the VOB to MKV (stream copy, very fast)
        2. Extracts the subtitle from the MKV file
        
        Args:
            vob_file: Path to the source VOB file
            subtitle_index: Subtitle stream index
            output_path: Base path for output (without extension)
            concat_file: Optional concat file for full title (NOT USED - concat doesn't expose subtitles)
            
        Returns:
            Path to extracted .sub file, or None on failure
        """
        sub_file = f"{output_path}.sub"
        
        # Create temporary MKV file
        mkv_file = f"{output_path}.mkv"
        
        self.log("Trying MKV intermediate format for subtitle extraction...", "INFO")
        
        # IMPORTANT: Always use VOB file directly, NOT concat file
        # The concat demuxer doesn't expose DVD subtitle streams!
        # We only extract from the first VOB (subtitles are repeated across VOBs)
        
        remux_cmd = [
            self.ffmpeg_path,
            "-y",
            "-analyzeduration", "100M",
            "-probesize", "100M",
            "-i", vob_file,  # Use VOB directly
            "-c", "copy",  # Stream copy (no re-encoding)
            "-map", "0:v?",  # Map video (optional)
            "-map", "0:a?",  # Map audio (optional)
            "-map", "0:s?",  # Map all subtitles (optional)
            mkv_file
        ]
        
        try:
            self.log(f"Remuxing VOB to MKV: {os.path.basename(vob_file)}", "DEBUG")
            result = subprocess.run(
                remux_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                self.log(f"MKV remux failed: {result.stderr[:500]}", "DEBUG")
                return None
            
            if not os.path.exists(mkv_file):
                self.log("MKV file not created", "DEBUG")
                return None
            
            self.log(f"MKV remux successful: {os.path.getsize(mkv_file) / 1024 / 1024:.1f} MB", "DEBUG")
            
        except Exception as e:
            self.log(f"MKV remux error: {e}", "DEBUG")
            return None
        
        # Step 2: Extract subtitle from MKV
        extract_cmd = [
            self.ffmpeg_path,
            "-y",
            "-i", mkv_file,
            "-map", f"0:s:{subtitle_index}",
            "-c:s", "copy",
            sub_file
        ]
        
        try:
            result = subprocess.run(
                extract_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=120
            )
            
            if result.returncode == 0 and os.path.exists(sub_file) and os.path.getsize(sub_file) > 0:
                self.log(f"Subtitle extracted from MKV: {sub_file}", "SUCCESS")
                # Clean up MKV file
                try:
                    os.remove(mkv_file)
                except:
                    pass
                return sub_file
            else:
                self.log(f"Subtitle extraction from MKV failed: {result.stderr[:300]}", "DEBUG")
        
        except Exception as e:
            self.log(f"MKV subtitle extraction error: {e}", "DEBUG")
        
        # Clean up MKV file on failure
        try:
            if os.path.exists(mkv_file):
                os.remove(mkv_file)
        except:
            pass
        
        return None
    
    def extract_all_subtitles(self, vob_file: str, output_dir: str, title_number: int) -> Dict[int, str]:
        """
        Extract all subtitle tracks from a VOB file.
        
        Args:
            vob_file: Path to the source VOB file
            output_dir: Directory for output files
            title_number: DVD title number for naming
            
        Returns:
            Dict mapping subtitle index to extracted file path
        """
        extracted = {}
        
        # First detect available subtitles
        subtitles = self._get_title_subtitle_tracks(vob_file)
        
        if not subtitles:
            self.log("No subtitles found to extract", "WARN")
            return extracted
        
        os.makedirs(output_dir, exist_ok=True)
        
        for sub in subtitles:
            sub_idx = sub.get('sub_index', sub.get('index', 0))
            lang = sub.get('language', 'unknown')
            
            output_base = os.path.join(output_dir, f"title{title_number}_sub{sub_idx}_{lang}")
            
            result = self.extract_subtitle(vob_file, sub_idx, output_base)
            if result:
                extracted[sub_idx] = result
        
        return extracted
    
    def create_concat_file(self, vob_files: List[str]) -> str:
        """
        Create an FFmpeg concat demuxer file.
        
        Args:
            vob_files: List of VOB file paths in order
            
        Returns:
            Path to the concat file (temporary file)
        """
        # Clean up previous concat file
        if self._concat_file and os.path.exists(self._concat_file):
            try:
                os.remove(self._concat_file)
            except:
                pass
        
        # Create new concat file
        fd, concat_path = tempfile.mkstemp(suffix='.txt', prefix='dvd_concat_')
        
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            for vob_path in vob_files:
                # Convert to absolute path and normalize
                abs_path = os.path.abspath(vob_path)
                # Convert backslashes to forward slashes for FFmpeg
                escaped = abs_path.replace('\\', '/')
                # Escape single quotes for FFmpeg concat format
                escaped = escaped.replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")
                self.log(f"Added to concat: {abs_path}", "DEBUG")
        
        self._concat_file = concat_path
        self.log(f"Created concat file: {concat_path} with {len(vob_files)} files", "INFO")
        return concat_path
    
    def cleanup(self):
        """Clean up temporary files"""
        if self._concat_file and os.path.exists(self._concat_file):
            try:
                os.remove(self._concat_file)
                self._concat_file = None
            except Exception as e:
                self.log(f"Failed to cleanup concat file: {e}", "WARN")
    
    def get_ffmpeg_input_args(self, concat_file: str) -> List[str]:
        """
        Get FFmpeg input arguments for concat demuxer.
        
        Args:
            concat_file: Path to concat file
            
        Returns:
            List of FFmpeg arguments for input
        """
        return [
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file
        ]
    
    def build_concat_command(self, concat_file: str, output_path: str,
                            ffmpeg_path: str = "ffmpeg",
                            video_codec: str = "h264_nvenc",
                            audio_codec: str = "aac",
                            additional_args: List[str] = None) -> List[str]:
        """
        Build a complete FFmpeg command for DVD to file conversion.
        
        Args:
            concat_file: Path to concat file
            output_path: Output file path
            ffmpeg_path: Path to ffmpeg executable
            video_codec: Video encoder
            audio_codec: Audio encoder
            additional_args: Additional FFmpeg arguments
            
        Returns:
            Complete FFmpeg command as list of strings
        """
        cmd = [ffmpeg_path]
        
        # Concat demuxer input
        cmd.extend(["-f", "concat", "-safe", "0"])
        cmd.extend(["-i", concat_file])
        
        # Video codec
        cmd.extend(["-c:v", video_codec])
        
        # Audio codec
        cmd.extend(["-c:a", audio_codec])
        
        # Additional arguments
        if additional_args:
            cmd.extend(additional_args)
        
        # Output
        cmd.extend(["-y", output_path])
        
        return cmd


def scan_for_dvd_titles(folder_path: str, ffmpeg_path: str = "ffmpeg",
                        ffprobe_path: str = "ffprobe",
                        log_callback=None) -> List[DVDTitle]:
    """
    Convenience function to scan a folder for DVD titles.
    
    Args:
        folder_path: Path to scan
        ffmpeg_path: Path to ffmpeg
        ffprobe_path: Path to ffprobe
        log_callback: Optional logging callback
        
    Returns:
        List of DVDTitle objects
    """
    handler = DVDHandler(ffmpeg_path, ffprobe_path, log_callback)
    return handler.get_dvd_titles(folder_path)
