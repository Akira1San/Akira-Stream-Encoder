import tkinter as tk
from tkinter import ttk

class GeometryPanel(ttk.LabelFrame):
    def __init__(self, parent, app_state, refresh_callback):
        super().__init__(parent, text="Aspect Ratio & Geometry", padding=10)
        self.state = app_state
        self.refresh_callback = refresh_callback
        self.create_widgets()

    def create_widgets(self):
        # --- Force 16:9 Widescreen ---
        self.widescreen_active = tk.BooleanVar(value=False)
        
        ttk.Checkbutton(self, text="Force 16:9 Widescreen\n(Crop Top/Bottom Black Bars)", 
                       variable=self.widescreen_active, 
                       command=self.refresh_callback).pack(anchor="w", pady=10)
        
        # --- Vertical Offset (Slider) ---
        self.offset_label_frame = ttk.Frame(self)
        self.offset_label_frame.pack(fill="x", pady=5)
        
        ttk.Label(self.offset_label_frame, text="Crop Vertical Offset:").pack(side="left")
        self.val_label = ttk.Label(self.offset_label_frame, text="0", width=5)
        self.val_label.pack(side="right")
        
        self.offset_slider = ttk.Scale(self, from_=-100, to=100, variable=self.state['geo_offset'], 
                                   orient="horizontal", 
                                   command=lambda v: self.update_offset(v))
        self.offset_slider.pack(fill="x")
        self.offset_slider.bind("<ButtonRelease-1>", lambda e: self.refresh_callback())

        # --- NEW: SPLIT MODE ---
        split_frame = ttk.LabelFrame(self, text="Split Video", padding=10)
        split_frame.pack(fill="x", pady=10)

        # 1. Checkbox to Enable/Disable Feature
        self.split_duration_active = tk.BooleanVar(value=False)
        ttk.Checkbutton(split_frame, text="Split by Duration", 
                       variable=self.split_duration_active, 
                       command=self.toggle_split_ui).pack(anchor="w", pady=5)

        # 2. Frame for Options (Starts Disabled)
        self.options_frame = ttk.Frame(split_frame)
        self.options_frame.pack(fill="x", pady=2)

        # Variable to store number of parts
        ttk.Label(self.options_frame, text="Chunk Length (Minutes):").pack(side="left")
        
        self.parts_combo = ttk.Combobox(self.options_frame, textvariable=self.state['split_duration_min'], 
                                     values=["10", "20", "30", "40", "50", "60"], 
                                     state="disabled", width=10) # Disabled initially
        self.parts_combo.pack(side="left", padx=5)
        
        # Bind change to refresh (optional)
        self.state['split_duration_min'].trace_add("write", lambda *args: self.refresh_callback())

    def update_offset(self, value):
        self.val_label.config(text=str(int(float(value))))

    def toggle_split_ui(self):
        """Enable or Disable parts dropdown based on checkbox"""
        if self.split_duration_active.get():
            self.parts_combo.config(state="readonly")
        else:
            self.parts_combo.config(state="disabled")