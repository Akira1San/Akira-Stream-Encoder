import os
import subprocess
import tkinter as tk
from tkinter import ttk


class TrackSelectionPanel(ttk.LabelFrame):
    """Track selection UI for trim operations"""
    
    def __init__(self, parent, app_vars, log_callback, refresh_callback):
        super().__init__(parent, text="Track Selection", padding=10)
        self.vars = app_vars
        self.log = log_callback
        self.refresh_callback = refresh_callback
        self.current_video_path = None
        self.create_widgets()
    
    def create_widgets(self):
        """Create track selection checkboxes"""
        # Video Track
        self.video_frame = ttk.Frame(self)
        self.video_frame.pack(fill="x", pady=2)
        
        self.video_var = getattr(self.vars, 'track_video_selected')
        self.video_check = ttk.Checkbutton(
            self.video_frame,
            text="🎥 Video Track",
            variable=self.video_var,
            command=self.refresh_callback
        )
        self.video_check.pack(side="left", padx=5)
        
        self.video_info_label = ttk.Label(
            self.video_frame,
            text=getattr(self.vars, 'track_video_info').get(),
            foreground="gray"
        )
        self.video_info_label.pack(side="left", padx=5)
        
        # Audio Track
        self.audio_frame = ttk.Frame(self)
        self.audio_frame.pack(fill="x", pady=2)
        
        self.audio_var = getattr(self.vars, 'track_audio_selected')
        self.audio_check = ttk.Checkbutton(
            self.audio_frame,
            text="🔊 Audio Track",
            variable=self.audio_var,
            command=self.refresh_callback
        )
        self.audio_check.pack(side="left", padx=5)
        
        self.audio_info_label = ttk.Label(
            self.audio_frame,
            text=getattr(self.vars, 'track_audio_info').get(),
            foreground="gray"
        )
        self.audio_info_label.pack(side="left", padx=5)
        
        # Subtitle Track (conditional)
        self.subtitle_var = getattr(self.vars, 'track_subtitle_selected')
        
        if getattr(self.vars, 'track_subtitle_available').get():
            self.sub_frame = ttk.Frame(self)
            self.sub_frame.pack(fill="x", pady=2)
            
            self.sub_check = ttk.Checkbutton(
                self.sub_frame,
                text="📝 Subtitle Track",
                variable=self.subtitle_var,
                command=self.refresh_callback
            )
            self.sub_check.pack(side="left", padx=5)
            
            self.sub_info_label = ttk.Label(
                self.sub_frame,
                text=getattr(self.vars, 'track_subtitle_info').get(),
                foreground="gray"
            )
            self.sub_info_label.pack(side="left", padx=5)
    
    def detect_tracks(self, video_path):
        """
        Detect available tracks in video file
        
        Args:
            video_path: Path to video file
        """
        self.current_video_path = video_path
        ffprobe_path = "ffprobe"
        ffmpeg_path = getattr(self.vars, 'ffmpeg_path').get()
        
        # Try to find ffprobe
        if ffmpeg_path != "ffmpeg" and os.path.exists(ffmpeg_path):
            base_dir = os.path.dirname(ffmpeg_path)
            candidate = os.path.join(base_dir, "ffprobe.exe" if os.name == 'nt' else "ffprobe")
            if os.path.exists(candidate):
                ffprobe_path = candidate
        
        try:
            # Detect video stream
            video_info = self._detect_stream_info(ffprobe_path, video_path, "v", "0")
            audio_info = self._detect_stream_info(ffprobe_path, video_path, "a", "0")
            subtitle_info = self._detect_stream_info(ffprobe_path, video_path, "s", "0")
            
            # Update state variables
            if video_info:
                getattr(self.vars, 'track_video_info').set(video_info)
                self.video_check.state(['!disabled'])
            else:
                getattr(self.vars, 'track_video_info').set("No video stream found")
                self.video_check.state(['disabled'])
            
            if audio_info:
                getattr(self.vars, 'track_audio_info').set(audio_info)
                self.audio_check.state(['!disabled'])
            else:
                getattr(self.vars, 'track_audio_info').set("No audio stream found")
                self.audio_check.state(['disabled'])
            
            if subtitle_info:
                getattr(self.vars, 'track_subtitle_info').set(subtitle_info)
                getattr(self.vars, 'track_subtitle_available').set(True)
                getattr(self.vars, 'track_subtitle_selected').set(False)
            else:
                getattr(self.vars, 'track_subtitle_info').set("No subtitle stream")
                getattr(self.vars, 'track_subtitle_available').set(False)
                getattr(self.vars, 'track_subtitle_selected').set(False)
            
            # Refresh UI labels
            self.video_info_label.config(text=getattr(self.vars, 'track_video_info').get())
            self.audio_info_label.config(text=getattr(self.vars, 'track_audio_info').get())
            
            if hasattr(self, 'sub_info_label'):
                self.sub_info_label.config(text=getattr(self.vars, 'track_subtitle_info').get())
            
            self.log(f"Tracks detected: Video={bool(video_info)}, Audio={bool(audio_info)}, Subs={bool(subtitle_info)}")
            
        except Exception as e:
            self.log(f"Track detection failed: {e}")
    
    def _detect_stream_info(self, ffprobe_path, video_path, stream_type, stream_index):
        """
        Detect information about a specific stream
        
        Args:
            ffprobe_path: Path to ffprobe executable
            video_path: Path to video file
            stream_type: Stream type (v, a, s)
            stream_index: Stream index (0, 1, etc.)
            
        Returns:
            String describing the stream (codec, resolution, etc.)
        """
        try:
            cmd = [
                ffprobe_path,
                "-v", "error",
                "-select_streams", f"{stream_type}:{stream_index}",
                "-show_entries", "stream=codec_name,width,height,r_frame_rate,channels",
                "-of", "default=noprint_wrappers=1",
                video_path
            ]
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                info_parts = result.stdout.strip().split('|')
                codec = info_parts[0].strip()
                
                # Format based on stream type
                if stream_type == "v":
                    if len(info_parts) >= 4:
                        width = info_parts[1].strip()
                        height = info_parts[2].strip()
                        fps = info_parts[3].strip()
                        return f"{codec}, {width}x{height}, {fps}fps"
                    return codec
                elif stream_type == "a":
                    if len(info_parts) >= 3:
                        channels = info_parts[2].strip()
                        return f"{codec}, {channels}ch"
                    return codec
                else:
                    return codec
            
        except Exception as e:
            return f"Error: {str(e)}"
    
    def get_selected_tracks(self):
        """
        Get list of selected track types
        
        Returns:
            list of track types: ["video", "audio", "subtitle"]
        """
        selected = []
        
        if getattr(self.vars, 'track_video_selected').get():
            selected.append("video")
        
        if getattr(self.vars, 'track_audio_selected').get():
            selected.append("audio")
        
        if getattr(self.vars, 'track_subtitle_available').get() and \
           getattr(self.vars, 'track_subtitle_selected').get():
            selected.append("subtitle")
        
        return selected
    
    def reset_tracks(self):
        """Reset track selection to default state"""
        getattr(self.vars, 'track_video_selected').set(True)
        getattr(self.vars, 'track_audio_selected').set(True)
        getattr(self.vars, 'track_subtitle_selected').set(False)
        getattr(self.vars, 'track_subtitle_available').set(False)
        getattr(self.vars, 'track_video_info').set("")
        getattr(self.vars, 'track_audio_info').set("")
        getattr(self.vars, 'track_subtitle_info').set("")