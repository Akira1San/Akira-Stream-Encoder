import tkinter as tk
from tkinter import ttk

class EncodingPanel(ttk.LabelFrame):
    def __init__(self, parent, app_state):
        super().__init__(parent, text="Encoding Settings", padding=10)
        self.state = app_state
        self.create_widgets()

    def create_widgets(self):
        # Use Grid layout for compactness
        ttk.Checkbutton(self, text="Use GPU (NVENC)", variable=self.state['use_gpu']).grid(row=0, column=0, sticky="w", padx=5)
        
        ttk.Label(self, text="Encoder:").grid(row=0, column=1, sticky="e", padx=5)
        ttk.Combobox(self, textvariable=self.state['encoder_var'], 
                     values=["h264_nvenc", "hevc_nvenc", "libx264"], state="readonly", width=15).grid(row=0, column=2)

        ttk.Label(self, text="Resolution:").grid(row=1, column=0, sticky="e", padx=5)
        ttk.Combobox(self, textvariable=self.state['resolution_var'], 
                     values=["none", "1920x1080", "1280x720", "720x480", "720x404", "640x480", "640x368"], 
                     state="readonly", width=15).grid(row=1, column=1, sticky="w")
        
        ttk.Label(self, text="Framerate:").grid(row=1, column=2, sticky="e", padx=5)
        fr_frame = ttk.Frame(self)
        fr_frame.grid(row=1, column=3, sticky="w")
        ttk.Radiobutton(fr_frame, text="23.976", variable=self.state['framerate_var'], value="24000/1001").pack(side="left")
        ttk.Radiobutton(fr_frame, text="30", variable=self.state['framerate_var'], value="30").pack(side="left")

        ttk.Label(self, text="Quality (CQ):").grid(row=2, column=0, sticky="e", padx=5)
        cq_frame = ttk.Frame(self)
        cq_frame.grid(row=2, column=1, columnspan=2, sticky="we", padx=5)
        
        self.cq_label = ttk.Label(cq_frame, text=str(self.state['cq_var'].get()), width=3)
        self.cq_label.pack(side="right")
        
        # Update label instantly
        ttk.Scale(cq_frame, from_=18, to=30, variable=self.state['cq_var'], orient="horizontal", 
                  command=lambda v: self.cq_label.config(text=str(int(float(v))))).pack(side="left", fill="x", expand=True)

        ttk.Checkbutton(self, text="Use Original Bitrate", variable=self.state['use_orig_br_var']).grid(row=3, column=0, sticky="w", padx=5)
        
        ttk.Label(self, text="Max Bitrate (kb/s):").grid(row=3, column=1, sticky="e", padx=5)
        ttk.Entry(self, textvariable=self.state['max_br_var'], width=10).grid(row=3, column=2, sticky="w")

        # --- CONTAINER SELECTION ---
        ttk.Label(self, text="Container:").grid(row=4, column=0, sticky="e", padx=5)
        ttk.Combobox(
            self,
            textvariable=self.state['container'],
            values=["mp4", "mkv", "avi"],
            state="readonly",
            width=10
        ).grid(row=4, column=1, sticky="w")

        # --- SCALE FILTER ---
        ttk.Separator(self, orient='horizontal').grid(row=5, column=0, columnspan=4, sticky="we", pady=10)
        
        ttk.Label(self, text="Scale Mode:").grid(row=6, column=0, sticky="e", padx=5)
        ttk.Combobox(
            self,
            textvariable=self.state['scale_mode'],
            values=["off", "on"],
            state="readonly",
            width=10
        ).grid(row=6, column=1, sticky="w")

        ttk.Label(self, text="Algorithm:").grid(row=6, column=2, sticky="e", padx=5)
        ttk.Combobox(
            self,
            textvariable=self.state['scale_algorithm'],
            values=["bilinear", "bicubic", "lanczos", "spline", "area"],
            state="readonly",
            width=10
        ).grid(row=6, column=3, sticky="w")

        ttk.Label(self, text="Quality:").grid(row=7, column=0, sticky="e", padx=5)
        ttk.Combobox(
            self,
            textvariable=self.state['scale_quality'],
            values=["speed", "quality"],
            state="readonly",
            width=10
        ).grid(row=7, column=1, sticky="w")

        # --- NEW: FAST SPLIT ---
        # We need a container for the new checkbutton. 
        # Since this class IS a Labelframe, we can just add to it.
        ttk.Separator(self, orient='horizontal').grid(row=8, column=0, columnspan=4, sticky="we", pady=10)
        
        ttk.Checkbutton(self, text="Fast Split (No Re-encoding)\nKeeps original format/quality", 
                       variable=self.state['split_mode']).grid(row=9, column=0, columnspan=4, sticky="w", pady=5)