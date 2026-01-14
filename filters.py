import tkinter as tk
from tkinter import ttk


class FiltersPanel(ttk.Frame):
    """A reusable UI component for Video and Audio Filters"""

    def __init__(self, parent, app_state):
        super().__init__(parent)
        self.state = app_state
        self.create_widgets()

    def create_widgets(self):
        # Main Frame for Filters
        filt_frame = ttk.LabelFrame(self, text="Video & Audio Filters", padding=10)
        filt_frame.pack(fill="x", padx=10, pady=5)

        # --- Video Filters Column ---
        v_filt_col = ttk.Frame(filt_frame)
        v_filt_col.pack(side="left", fill="x", expand=True, padx=5)
        
        ttk.Label(v_filt_col, text="Video Filters", font=("Arial", 9, "bold")).pack(anchor="w")
        
        # --- NEW: Stretch to Fill ---
        # If checked, it will force video to fill frame (Ignore Aspect Ratio)
        # if not hasattr(self.state, 'stretch_fill'):
        #     self.state.stretch_fill = tk.BooleanVar(value=False)
             
        # ttk.Checkbutton(v_filt_col, text="Stretch to Fill Frame\n(Ignore Aspect Ratio)", variable=getattr(self.state, 'stretch_fill')).pack(anchor="w")

        ttk.Checkbutton(
            v_filt_col, text="Deinterlace (Yadif)", variable=self.state['deint']
        ).pack(anchor="w")
        ttk.Checkbutton(
            v_filt_col, text="Denoise (HQDN3D)", variable=self.state['denoise']
        ).pack(anchor="w")
        ttk.Checkbutton(
            v_filt_col, text="Libplacebo Scaling", variable=self.state['libplacebo']
        ).pack(anchor="w")
    
        # --- Audio Filters Column ---
        a_filt_col = ttk.Frame(filt_frame)
        a_filt_col.pack(side="left", fill="x", expand=True, padx=5)

        ttk.Label(a_filt_col, text="Audio Filters", font=("Arial", 9, "bold")).pack(
            anchor="w"
        )

        ttk.Checkbutton(
            a_filt_col, text="Enable Volume", variable=self.state['vol_enable']
        ).pack(anchor="w")

        vol_input_frame = ttk.Frame(a_filt_col)
        vol_input_frame.pack(fill="x", pady=2)
        ttk.Entry(vol_input_frame, textvariable=self.state['vol_val'], width=10).pack(
            side="left", padx=5
        )
        ttk.Label(vol_input_frame, text="(dB)").pack(side="left")
