import datetime
import json
import os
import tkinter as tk
from tkinter import messagebox, ttk

from controller import VideoController
from video_tab import ConfigTab, VideoTab
from trim_controller import TrimController


class SharedState:
    """Single source of truth for all UI variables and application state"""
    
    def __init__(self):
        # General / IO
        self.input_files = []
        self.output_folder = tk.StringVar(value=os.path.expanduser("~\\Desktop"))
        self.ffmpeg_path = tk.StringVar(value="ffmpeg")
        
        # Encoding
        self.use_gpu = tk.BooleanVar(value=True)
        self.encoder_var = tk.StringVar(value="h264_nvenc")
        self.resolution_var = tk.StringVar(value="none")
        self.framerate_var = tk.StringVar(value="24000/1001")
        self.cq_var = tk.IntVar(value=23)
        self.use_orig_br_var = tk.BooleanVar(value=False)
        self.max_br_var = tk.IntVar(value=4000)
        
        # Subtitle Variables
        self.burn_subs = tk.BooleanVar(value=False)
        self.sub_font = tk.StringVar(value="Arial")
        self.sub_size = tk.IntVar(value=24)
        self.sub_position = tk.StringVar(value="bottom")
        self.sub_color = tk.StringVar(value="#FFFFFF")
        self.sub_outline_color = tk.StringVar(value="#000000")
        self.sub_bg_color = tk.StringVar(value="#000000")
        self.sub_outline_width = tk.IntVar(value=2)
        self.sub_bg_opacity = tk.DoubleVar(value=0.5)
        
        # Trim/Cut Feature State
        self.track_video_selected = tk.BooleanVar(value=True)
        self.track_audio_selected = tk.BooleanVar(value=True)
        self.track_subtitle_available = tk.BooleanVar(value=False)
        self.track_subtitle_selected = tk.BooleanVar(value=False)
        self.cut_position = tk.DoubleVar(value=0.0)
        self.cut_time_display = tk.StringVar(value="Not Set")
        self.cut_point_set = tk.BooleanVar(value=False)
        self.track_video_info = tk.StringVar(value="")
        self.track_audio_info = tk.StringVar(value="")
        self.track_subtitle_info = tk.StringVar(value="")
        
        # EQ Settings
        self.eq_bypass = tk.BooleanVar(value=False)
        self.eq_brightness = tk.DoubleVar(value=0.0)
        self.eq_contrast = tk.DoubleVar(value=1.0)
        self.eq_saturation = tk.DoubleVar(value=1.0)
        self.eq_gamma = tk.DoubleVar(value=1.0)
        self.eq_gamma_r = tk.DoubleVar(value=1.0)
        self.eq_gamma_g = tk.DoubleVar(value=1.0)
        self.eq_gamma_b = tk.DoubleVar(value=1.0)
        
        # Filter Variables
        self.deint = tk.BooleanVar(value=False)
        self.denoise = tk.BooleanVar(value=False)
        self.libplacebo = tk.BooleanVar(value=False)
        self.vol_enable = tk.BooleanVar(value=False)
        self.vol_val = tk.DoubleVar(value=0.0)
        self.stretch_fill = tk.BooleanVar(value=False)
        
        # Geometry
        self.force_widescreen = tk.BooleanVar(value=False)
        self.geo_offset = tk.DoubleVar(value=0.0)
        
        # Cut Parts
        self.cut_parts = tk.StringVar(value="1")
        self.split_duration_min = tk.IntVar(value=30)
        
        # Additional variables created by modules
        self.split_mode = tk.BooleanVar(value=False)
        self.eq_enable = tk.BooleanVar(value=False)
        
        # Runtime state
        self.is_encoding = False
    
    def __getitem__(self, key):
        """Support dictionary-style access for backward compatibility"""
        return getattr(self, key)
    
    def __setitem__(self, key, value):
        """Support dictionary-style assignment for backward compatibility"""
        setattr(self, key, value)
    
    def __contains__(self, key):
        """Support 'in' operator for backward compatibility"""
        return hasattr(self, key)
    
    def get(self, key, default=None):
        """Support dictionary-style .get() method for backward compatibility"""
        return getattr(self, key, default)


class VideoEncoderApp(tk.Tk):
    """Main application orchestrator"""
    
    def __init__(self):
        super().__init__()
        self.title("Video Encoder - Unified Workspace")
        self.geometry("1024x1024")
        self.current_process = None
        
        # Initialize shared state and controller
        self.state = SharedState()
        self.controller = VideoController(self.state, self.log)
        
        # Initialize trim controller
        self.trim_controller = TrimController(self.state, self.log)
        
        # Setup UI
        self._setup_ui()
        
        # Load settings after UI is created
        self.load_settings()
    
    def _setup_ui(self):
        """Create the main user interface"""
        # Top Control Panel
        control_frame = ttk.Frame(self, padding=5)
        control_frame.pack(fill="x")
        
        ttk.Button(
            control_frame, text="Start Encoding", command=self.start_encoding
        ).pack(side="left", padx=5)
        ttk.Button(control_frame, text="Cancel", command=self.cancel_encoding).pack(
            side="left", padx=5
        )
        ttk.Button(
            control_frame, text="Save Settings", command=self.save_settings
        ).pack(side="right", padx=5)
        
        # Notebook (Config and Video tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Create tabs
        self.tab_config = ConfigTab(self.notebook, self.state, self.log)
        self.notebook.add(self.tab_config, text="Config")
        
        self.tab_video = VideoTab(self.notebook, self.state, self.trim_controller, self.log)
        self.notebook.add(self.tab_video, text="Video")
        
        # Set up cross-tab references
        self.tab_video.set_config_tab(self.tab_config)
        
        # Bind file selection to video tab
        self.tab_config.files_listbox.bind(
            "<<ListboxSelect>>", self.tab_video.on_file_select
        )
        
        # Bottom Log/Status
        bottom_frame = ttk.Frame(self, padding=5)
        bottom_frame.pack(fill="x", side="bottom")
        
        self.log_text = tk.Text(bottom_frame, height=6, state="disabled")
        self.log_text.pack(fill="x")
        
        self.progress = ttk.Progressbar(bottom_frame, mode="determinate")
        self.progress.pack(fill="x", pady=2)
        
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(bottom_frame, textvariable=self.status_var).pack(anchor="w")
    
    def log(self, msg):
        """Log a message to the UI"""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
    
    def start_encoding(self):
        """Start the encoding process"""
        if not self.state.input_files:
            messagebox.showwarning("No Files", "Please add video files first.")
            return
        
        if (
            not os.path.exists(self.state.ffmpeg_path.get())
            and self.state.ffmpeg_path.get() != "ffmpeg"
        ):
            messagebox.showerror("FFmpeg Error", "FFmpeg path is invalid.")
            return
        
        self.log("Starting batch encoding...")
        self.state.is_encoding = True
        
        import threading
        self.processing_thread = threading.Thread(
            target=self.controller.process_batch,
            args=(self.status_var,),
            daemon=True
        )
        self.processing_thread.start()
    
    def cancel_encoding(self):
        """Cancel the encoding process"""
        self.state.is_encoding = False
        self.status_var.set("Cancelled")
    
    def save_settings(self):
        """Save current settings to JSON file"""
        # Convert all tkinter variables to their values
        data = {
            name: var.get() if hasattr(var, "get") else var
            for name, var in vars(self.state).items()
            if hasattr(var, "get") and not name.startswith('_')
        }
        
        # Additional boolean variables from panels
        data.update({
            'deint': self.state.deint.get(),
            'denoise': self.state.denoise.get(),
            'libplacebo': self.state.libplacebo.get(),
            'vol_enable': self.state.vol_enable.get(),
            'vol_val': self.state.vol_val.get(),
            'stretch_fill': self.state.stretch_fill.get(),
            'eq_bypass': self.state.eq_bypass.get(),
            'eq_bright': self.state.eq_brightness.get(),
            'eq_contrast': self.state.eq_contrast.get(),
            'eq_sat': self.state.eq_saturation.get(),
            'eq_gamma': self.state.eq_gamma.get(),
            'eq_rg': self.state.eq_gamma_r.get(),
            'eq_gg': self.state.eq_gamma_g.get(),
            'eq_gb': self.state.eq_gamma_b.get(),
            'cut_parts': self.state.cut_parts.get()
        })
        
        try:
            with open("settings.json", "w") as f:
                json.dump(data, f)
            self.log("Settings saved.")
        except Exception as e:
            self.log(f"Error saving settings: {e}")
    
    def load_settings(self):
        """Load settings from JSON file"""
        if os.path.exists("settings.json"):
            try:
                with open("settings.json", "r") as f:
                    data = json.load(f)
                
                # Load all tkinter variables from SharedState
                for name, var in vars(self.state).items():
                    if name in data and hasattr(var, "set"):
                        var.set(data[name])
                        self.log(f"Loaded {name}: {data[name]}")
                
                # Handle legacy/alternative variable names for compatibility
                legacy_mappings = {
                    "deint": self.state.deint,
                    "denoise": self.state.denoise,
                    "libplacebo": self.state.libplacebo,
                    "vol_enable": self.state.vol_enable,
                    "vol_val": self.state.vol_val,
                    "stretch_fill": self.state.stretch_fill,
                    "eq_bypass": self.state.eq_bypass,
                    "eq_bright": self.state.eq_brightness,
                    "eq_contrast": self.state.eq_contrast,
                    "eq_sat": self.state.eq_saturation,
                    "eq_gamma": self.state.eq_gamma,
                    "eq_rg": self.state.eq_gamma_r,
                    "eq_gg": self.state.eq_gamma_g,
                    "eq_gb": self.state.eq_gamma_b,
                    "cut_parts": self.state.cut_parts
                }
                
                for legacy_name, var in legacy_mappings.items():
                    if legacy_name in data and hasattr(var, "set"):
                        var.set(data[legacy_name])
                        self.log(f"Loaded legacy {legacy_name}: {data[legacy_name]}")
                    
            except Exception as e:
                self.log(f"Error loading settings: {e}")


if __name__ == "__main__":
    app = VideoEncoderApp()
    app.mainloop()