import tkinter as tk
from tkinter import ttk, messagebox

class ToolTip:
    """Creates a tooltip for a given widget."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        x, y, _, _ = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

class ColorCorrectionPanel(ttk.LabelFrame):
    def __init__(self, parent, app_state, denoise_check_var, refresh_callback):
        super().__init__(parent, text="Color Correction (EQ)", padding=10)
        self.state = app_state
        self.denoise_var = denoise_check_var
        self.refresh_callback = refresh_callback
        self.create_widgets()

    def create_widgets(self):
        # --- Top Controls ---
        top_ctrl_frame = ttk.Frame(self)
        top_ctrl_frame.pack(fill="x", pady=5)
        
        ttk.Checkbutton(top_ctrl_frame, text="Enable Color Correction", variable=self.state.eq_enable, 
                       command=self.refresh_callback).pack(side="left", padx=5) # <--- Changed here
        
        ttk.Button(top_ctrl_frame, text="Reset All", command=self.reset_defaults).pack(side="right", padx=5)

        # --- Sliders Helper (Using PACK instead of GRID) ---
        
        # 1. Brightness
        self.create_slider_row("Brightness", "eq_brightness", -0.10, 0.10, 0.00,
                              "Adjusts black level. \nVHS tapes rarely need more than +/- 0.05.")

        # 2. Contrast
        self.contrast_label = self.create_slider_row("Contrast", "eq_contrast", 0.80, 1.30, 1.00,
                              "Increases separation between dark and bright areas. \nToo much will crush VHS shadow detail.")

        # 3. Saturation
        self.create_slider_row("Saturation", "eq_saturation", 0.70, 1.10, 1.00,
                              "Color intensity. \nHigh values can cause VHS color bleeding.")

        # 4. Gamma
        self.create_slider_row("Gamma", "eq_gamma", 0.90, 1.10, 1.00,
                              "Adjusts midtone brightness without affecting black/white points.")

        # --- RGB Gamma Section ---
        ttk.Separator(self, orient='horizontal').pack(fill='x', pady=10)
        
        self.link_rgb_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self, text="Link RGB Gamma (White Balance)", variable=self.link_rgb_var).pack(anchor="w", pady=5)

        # RGB Sliders
        self.create_rgb_slider_row("R", "eq_gamma_r", 0.95, 1.05, 1.00)
        self.create_rgb_slider_row("G", "eq_gamma_g", 0.95, 1.05, 1.00)
        self.create_rgb_slider_row("B", "eq_gamma_b", 0.95, 1.05, 1.00)

    def create_slider_row(self, label_text, var_name, min_v, max_v, default_v, tooltip_text):
        """Helper to create a standard slider row using PACK"""
        # Container for this specific row
        row_frame = ttk.Frame(self)
        row_frame.pack(fill="x", pady=2)
        
        # Left: Label
        ttk.Label(row_frame, text=label_text, width=12).pack(side="left", padx=5)
        
        # Center: Scale Frame
        s_frame = ttk.Frame(row_frame)
        s_frame.pack(side="left", fill="x", expand=True)

        # Initialize var if not exists
        if not hasattr(self.state, var_name):
            setattr(self.state, var_name, tk.DoubleVar(value=default_v))

        # Range Labels
        ttk.Label(s_frame, text=str(min_v), font=("Arial", 8)).pack(side="left")
        
        # The Scale
        scale = ttk.Scale(s_frame, from_=min_v, to=max_v, variable=getattr(self.state, var_name), 
                          orient="horizontal", length=150,
                          command=lambda v, l=label_text: self.on_slider_change(v, var_name, l))
        scale.pack(side="left", padx=5)
        
        # Bind Double Click to Reset
        scale.bind("<Double-Button-1>", lambda e, vn=var_name, dv=default_v: self.reset_single(vn, dv))
        
        # ToolTip
        ToolTip(scale, tooltip_text)
        
        ttk.Label(s_frame, text=str(max_v), font=("Arial", 8)).pack(side="left")

        # Right: Value Display
        val_label = ttk.Label(row_frame, text=str(default_v), width=6, foreground="black", anchor="w")
        val_label.pack(side="right", padx=5)
        
        # Store ref to label to update color later
        if label_text == "Contrast":
            self.contrast_val_label = val_label

    def create_rgb_slider_row(self, color, var_name, min_v, max_v, default_v):
        row_frame = ttk.Frame(self)
        row_frame.pack(fill="x", pady=2)

        ttk.Label(row_frame, text=f"{color} Gamma", width=12).pack(side="left", padx=5)
        
        if not hasattr(self.state, var_name):
            setattr(self.state, var_name, tk.DoubleVar(value=default_v))

        s_frame = ttk.Frame(row_frame)
        s_frame.pack(side="left", fill="x", expand=True)
        
        scale = ttk.Scale(s_frame, from_=min_v, to=max_v, variable=getattr(self.state, var_name), 
                          orient="horizontal", length=150,
                          command=lambda v, c=color, vn=var_name: self.on_rgb_change(v, c, vn))
        scale.pack(side="left", padx=5)
        
        val_label = ttk.Label(row_frame, text=str(default_v), width=6, anchor="w")
        val_label.pack(side="right", padx=5)

    # --- Logic Handlers ---

    def on_slider_change(self, value, var_name, label):
        # Update Label Text
        float_val = round(float(value), 3)
        
        # Find the label widget (a bit hacky but efficient)
        # We iterate children to find one displaying this value
        # Actually, better to use the stored reference for Contrast
        if label == "Contrast":
            self.contrast_val_label.config(text=str(float_val))
            # Warning Logic
            if float_val > 1.2:
                self.contrast_val_label.config(foreground="red")
            else:
                self.contrast_val_label.config(foreground="black")
        
        # Saturation Logic
        if var_name == "eq_saturation":
            self.check_saturation_logic(float_val)

    def on_rgb_change(self, value, color, var_name):
        # Logic for Linking
        float_val = round(float(value), 3)
        
        if self.link_rgb_var.get():
            # Update all three
            self.state.eq_gamma_r.set(float_val)
            self.state.eq_gamma_g.set(float_val)
            self.state.eq_gamma_b.set(float_val)
            # Note: Updating text labels for G and B visually is tricky without references.
            # For simplicity, we assume the slider position updates visually.

    def check_saturation_logic(self, val):
        # "Auto-reduce saturation if noise reduction is disabled"
        if not self.denoise_var.get() and val > 1.0:
            # Snap it back to 1.0 and warn user
            self.state.eq_saturation.set(1.0)
            messagebox.showwarning("EQ Warning", "Saturation cannot be boosted above 1.0 when Noise Reduction is disabled.\n(It would emphasize tape noise).")

    def reset_single(self, var_name, default_val):
        getattr(self.state, var_name).set(default_val)

    def reset_defaults(self):
        defaults = {
            'eq_brightness': 0.00,
            'eq_contrast': 1.00,
            'eq_saturation': 1.00,
            'eq_gamma': 1.00,
            'eq_gamma_r': 1.00,
            'eq_gamma_g': 1.00,
            'eq_gamma_b': 1.00,
        }
        for k, v in defaults.items():
            getattr(self.state, k).set(v)