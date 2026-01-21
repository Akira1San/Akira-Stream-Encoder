import tkinter as tk
from tkinter import ttk

class ToolTip:
    """Create a tooltip for a given widget"""
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.tipwindow = None

    def enter(self, event=None):
        self.showtip()

    def leave(self, event=None):
        self.hidetip()

    def showtip(self):
        if self.tipwindow or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + cy + self.widget.winfo_rooty() + 25
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                        background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                        font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

class EncodingPanel(ttk.LabelFrame):
    def __init__(self, parent, app_state):
        super().__init__(parent, text="Encoding Settings", padding=10)
        self.state = app_state
        self.create_widgets()

    def create_widgets(self):
        # Use vertical layout instead of grid for better collapsible behavior
        
        # Row 1: GPU and Encoder
        row1_frame = ttk.Frame(self)
        row1_frame.pack(fill="x", pady=2)
        ttk.Checkbutton(row1_frame, text="Use GPU (NVENC)", variable=self.state['use_gpu']).pack(side="left", padx=5)
        ttk.Label(row1_frame, text="Encoder:").pack(side="left", padx=(20, 5))
        ttk.Combobox(row1_frame, textvariable=self.state['encoder_var'], 
                     values=["h264_nvenc", "hevc_nvenc", "libx264", "libx265"], state="readonly", width=15).pack(side="left")

        # Row 2: Resolution and Framerate
        row2_frame = ttk.Frame(self)
        row2_frame.pack(fill="x", pady=2)
        ttk.Label(row2_frame, text="Resolution:").pack(side="left", padx=5)
        ttk.Combobox(row2_frame, textvariable=self.state['resolution_var'], 
                     values=["none", "1920x1080", "1280x720", "720x480", "720x404", "720x400", "640x480", "640x368"], 
                     state="readonly", width=15).pack(side="left", padx=(5, 20))
        
        ttk.Label(row2_frame, text="Framerate:").pack(side="left", padx=5)
        fr_frame = ttk.Frame(row2_frame)
        fr_frame.pack(side="left")
        ttk.Radiobutton(fr_frame, text="23.976", variable=self.state['framerate_var'], value="24000/1001").pack(side="left")
        ttk.Radiobutton(fr_frame, text="30", variable=self.state['framerate_var'], value="30").pack(side="left")

        # Row 3: Quality (CQ)
        row3_frame = ttk.Frame(self)
        row3_frame.pack(fill="x", pady=2)
        ttk.Label(row3_frame, text="Quality (CQ):").pack(side="left", padx=5)
        cq_frame = ttk.Frame(row3_frame)
        cq_frame.pack(side="left", fill="x", expand=True, padx=5)
        
        self.cq_label = ttk.Label(cq_frame, text=str(self.state['cq_var'].get()), width=3)
        self.cq_label.pack(side="right")
        
        # Update label instantly
        ttk.Scale(cq_frame, from_=18, to=30, variable=self.state['cq_var'], orient="horizontal", 
                  command=lambda v: self.cq_label.config(text=str(int(float(v))))).pack(side="left", fill="x", expand=True)

        # --- BITRATE CONTROLS ---
        ttk.Separator(self, orient='horizontal').pack(fill="x", pady=10)
        
        # Row 4: Bitrate Mode
        row4_frame = ttk.Frame(self)
        row4_frame.pack(fill="x", pady=2)
        ttk.Label(row4_frame, text="Bitrate Mode:").pack(side="left", padx=5)
        bitrate_mode_combo = ttk.Combobox(
            row4_frame,
            textvariable=self.state['bitrate_mode'],
            values=["CBR (Constant Bitrate)"],
            state="readonly",
            width=20
        )
        bitrate_mode_combo.pack(side="left", padx=5)
        # Set default to CBR
        if not self.state['bitrate_mode'].get():
            self.state['bitrate_mode'].set("CBR (Constant Bitrate)")
        ToolTip(bitrate_mode_combo, "CBR: Constant bitrate - maintains consistent quality for streaming")
        
        # Row 5: Target Bitrate
        row5_frame = ttk.Frame(self)
        row5_frame.pack(fill="x", pady=2)
        ttk.Label(row5_frame, text="Target Bitrate:").pack(side="left", padx=5)
        bitrate_frame = ttk.Frame(row5_frame)
        bitrate_frame.pack(side="left", padx=5)
        
        ttk.Entry(bitrate_frame, textvariable=self.state['target_bitrate'], width=8).pack(side="left", padx=(0, 5))
        ttk.Label(bitrate_frame, text="kbps").pack(side="left", padx=(0, 15))
        ttk.Checkbutton(bitrate_frame, text="Use Original", variable=self.state['use_orig_br_var']).pack(side="left", padx=(10, 0))

        # --- CONTAINER SELECTION ---
        ttk.Separator(self, orient='horizontal').pack(fill="x", pady=10)
        
        # Row 6: Container
        row6_frame = ttk.Frame(self)
        row6_frame.pack(fill="x", pady=2)
        ttk.Label(row6_frame, text="Container:").pack(side="left", padx=5)
        ttk.Combobox(
            row6_frame,
            textvariable=self.state['container'],
            values=["mp4", "mkv", "avi"],
            state="readonly",
            width=10
        ).pack(side="left", padx=5)

        # --- SCALE FILTER ---
        ttk.Separator(self, orient='horizontal').pack(fill="x", pady=10)
        
        # Row 7: Scale Mode and Algorithm
        row7_frame = ttk.Frame(self)
        row7_frame.pack(fill="x", pady=2)
        ttk.Label(row7_frame, text="Scale Mode:").pack(side="left", padx=5)
        scale_mode_combo = ttk.Combobox(
            row7_frame,
            textvariable=self.state['scale_mode'],
            values=["off", "on"],
            state="readonly",
            width=10
        )
        scale_mode_combo.pack(side="left", padx=5)
        ToolTip(scale_mode_combo, "Enable/disable advanced scaling algorithms.\nOff: Basic scaling\nOn: Use selected algorithm with quality settings")

        ttk.Label(row7_frame, text="Algorithm:").pack(side="left", padx=(20, 5))
        algorithm_combo = ttk.Combobox(
            row7_frame,
            textvariable=self.state['scale_algorithm'],
            values=["bilinear", "bicubic", "lanczos", "spline", "area"],
            state="readonly",
            width=10
        )
        algorithm_combo.pack(side="left", padx=5)
        ToolTip(algorithm_combo, "Scaling algorithm:\nBilinear: Fast, basic quality\nBicubic: Good balance of speed/quality\nLanczos: High quality, slower\nSpline: Smooth scaling\nArea: Best for downscaling")

        # Row 8: Quality
        row8_frame = ttk.Frame(self)
        row8_frame.pack(fill="x", pady=2)
        ttk.Label(row8_frame, text="Quality:").pack(side="left", padx=5)
        quality_combo = ttk.Combobox(
            row8_frame,
            textvariable=self.state['scale_quality'],
            values=["speed", "quality"],
            state="readonly",
            width=10
        )
        quality_combo.pack(side="left", padx=5)
        ToolTip(quality_combo, "Quality vs Speed trade-off:\nSpeed: Faster processing, standard quality\nQuality: Slower processing, enhanced accuracy")

        # --- NEW: FAST SPLIT ---
        ttk.Separator(self, orient='horizontal').pack(fill="x", pady=10)
        
        # Row 9: Fast Split
        row9_frame = ttk.Frame(self)
        row9_frame.pack(fill="x", pady=2)
        ttk.Checkbutton(row9_frame, text="Fast Split (No Re-encoding)\nKeeps original format/quality", 
                       variable=self.state['split_mode']).pack(side="left", padx=5)