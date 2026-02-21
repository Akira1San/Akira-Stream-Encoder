"""
Main Application - VideoEncoderApp class and encoding logic
"""
import datetime
import json
import os
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, ttk


class VideoEncoderApp(tk.Tk):
    """Main Video Encoder Application"""
    
    def __init__(self):
        super().__init__()
        self.title("Video Encoder - Unified Workspace")
        self.geometry("1024x1024")
        self.current_process = None
        self.is_encoding = False

        # Initialize shared state variables
        self.vars = self.init_shared_state()
        
        # Setup UI
        self.setup_ui()
        
        # Load settings
        self.load_settings()

    def init_shared_state(self):
        """Initialize all shared state variables"""
        return {
            # General / IO
            'input_files': [],
            'output_folder': tk.StringVar(value=os.path.expanduser("~\\Desktop")),
            'ffmpeg_path': tk.StringVar(value="ffmpeg"),
            'use_custom_filename': tk.BooleanVar(value=False),
            'custom_filename': tk.StringVar(value=""),
            'split_mode': tk.BooleanVar(value=False),
            
            # Encoding
            'use_gpu': tk.BooleanVar(value=True),
            'encoder_var': tk.StringVar(value="h264_nvenc"),
            'resolution_var': tk.StringVar(value="none"),
            'framerate_var': tk.StringVar(value="24000/1001"),
            'cq_var': tk.IntVar(value=23),
            'use_orig_br_var': tk.BooleanVar(value=False),
            'max_br_var': tk.IntVar(value=4000),
            
            # Subtitle Variables
            'burn_subs': tk.BooleanVar(value=False),
            'sub_font': tk.StringVar(value="Arial"),
            'sub_size': tk.IntVar(value=24),
            'sub_position': tk.StringVar(value="bottom"),
            'sub_color': tk.StringVar(value="#FFFFFF"),
            'sub_outline_color': tk.StringVar(value="#000000"),
            'sub_bg_color': tk.StringVar(value="#000000"),
            'sub_outline_width': tk.IntVar(value=2),
            'sub_bg_opacity': tk.DoubleVar(value=0.5),

            # EQ Settings
            'eq_enable': tk.BooleanVar(value=False),
            'eq_bypass': tk.BooleanVar(value=False),
            'eq_brightness': tk.DoubleVar(value=0.0),
            'eq_contrast': tk.DoubleVar(value=1.0),
            'eq_saturation': tk.DoubleVar(value=1.0),
            'eq_gamma': tk.DoubleVar(value=1.0),
            'eq_gamma_r': tk.DoubleVar(value=1.0),
            'eq_gamma_g': tk.DoubleVar(value=1.0),
            'eq_gamma_b': tk.DoubleVar(value=1.0),

            # Filter Variables
            'deint': tk.BooleanVar(value=False),
            'denoise': tk.BooleanVar(value=False),
            'libplacebo': tk.BooleanVar(value=False),
            'vol_enable': tk.BooleanVar(value=False),
            'vol_val': tk.DoubleVar(value=0.0),
            'stretch_fill': tk.BooleanVar(value=False),

            # Geometry
            'force_widescreen': tk.BooleanVar(value=False),
            'geo_offset': tk.DoubleVar(value=0.0),

            # Cut/Trim
            'cut_parts': tk.StringVar(value="1"),
            'split_duration_min': tk.IntVar(value=30),
            'cut_position': tk.DoubleVar(value=0.0),
            'cut_point_set': tk.BooleanVar(value=False),
        }

    def setup_ui(self):
        """Setup the main UI"""
        # Import here to avoid circular imports
        from config_tab import ConfigTab
        from video_workspace import VideoTab
        from trim_controller import TrimController
        from controller import VideoController
        
        # Initialize controllers
        self.trim_controller = TrimController(self.vars, self.log)
        self.video_controller = VideoController(self.vars, self.log)
        
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
        self.tab_config = ConfigTab(self.notebook, self.vars, self.log)
        self.notebook.add(self.tab_config, text="Config")

        self.tab_video = VideoTab(self.notebook, self.vars, self.trim_controller, self.log)
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
        """Log message with timestamp"""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def start_encoding(self):
        """Start the encoding process"""
        if not self.vars["input_files"]:
            messagebox.showwarning("No Files", "Please add video files first.")
            return

        if (
            not os.path.exists(self.vars["ffmpeg_path"].get())
            and self.vars["ffmpeg_path"].get() != "ffmpeg"
        ):
            messagebox.showerror("FFmpeg Error", "FFmpeg path is invalid.")
            return

        self.log("Starting batch encoding...")
        self.is_encoding = True
        self.processing_thread = threading.Thread(
            target=self.video_controller.process_batch, 
            args=(self.status_var,), 
            daemon=True
        )
        self.processing_thread.start()

    def cancel_encoding(self):
        """Cancel the encoding process"""
        self.is_encoding = False
        self.status_var.set("Cancelled")
        if hasattr(self, 'video_controller') and self.video_controller.current_process:
            try:
                self.video_controller.current_process.terminate()
            except:
                pass

    # Remove the placeholder process_batch method since we're using VideoController's implementation

    def save_settings(self):
        """Save current settings to JSON file"""
        data = {
            k: v.get() if hasattr(v, "get") else v
            for k, v in self.vars.items()
            if hasattr(v, "get")
        }
        
        try:
            with open("settings.json", "w") as f:
                json.dump(data, f)
            self.log("Settings saved.")
        except Exception as e:
            self.log(f"Error saving: {e}")

    def load_settings(self):
        """Load settings from JSON file"""
        if os.path.exists("settings.json"):
            try:
                with open("settings.json", "r") as f:
                    data = json.load(f)
                for k, v in data.items():
                    if k in self.vars and hasattr(self.vars[k], "set"):
                        self.vars[k].set(v)
                self.log("Settings loaded.")
            except Exception as e:
                self.log(f"Error loading settings: {e}")


if __name__ == "__main__":
    app = VideoEncoderApp()
    app.mainloop()