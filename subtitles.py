import tkinter as tk
from tkinter import ttk, colorchooser

class SubtitlesPanel(ttk.LabelFrame):
    def __init__(self, parent, app_state, refresh_callback):
        super().__init__(parent, text="Subtitle Settings (Preview Enabled)", padding=10)
        self.state = app_state
        self.refresh_callback = refresh_callback
        self.create_widgets()

    def create_widgets(self):
        # Burn Checkbox
        ttk.Checkbutton(self, text="Burn Subtitles into Video", 
                        variable=self.state.burn_subs,
                        command=self.refresh_callback).pack(anchor="w", pady=5)

        # Row 1: Font & Size
        f_frame = ttk.Frame(self)
        f_frame.pack(fill="x", pady=2)
        ttk.Label(f_frame, text="Font:").pack(side="left")
        ttk.Combobox(f_frame, textvariable=self.state.sub_font, values=["Arial", "Courier", "Times"], state="readonly", width=10).pack(side="left", padx=5)
        
        ttk.Label(f_frame, text="Size:").pack(side="left")
        self.sub_size_label = ttk.Label(f_frame, text=str(self.state.sub_size.get()), width=3)
        self.sub_size_label.pack(side="left")
        sub_scale = ttk.Scale(f_frame, from_=10, to=50, variable=self.state.sub_size, orient="horizontal", length=100, 
                              command=lambda v: self.sub_size_label.config(text=str(int(float(v)))))
        sub_scale.pack(side="left", padx=5)
        self.bind_release_to_preview(sub_scale)

        # Row 2: Position & Colors
        p_frame = ttk.Frame(self)
        p_frame.pack(fill="x", pady=2)
        ttk.Label(p_frame, text="Position:").pack(side="left")
        # winfo_children()[1] gets the combobox (index 1) inside this frame
        ttk.Combobox(p_frame, textvariable=self.state.sub_position, values=["bottom", "top", "center"], state="readonly", width=10).pack(side="left", padx=5)
        self.bind_release_to_preview(p_frame.winfo_children()[1])

        c_frame = ttk.Frame(self)
        c_frame.pack(fill="x", pady=5)
        ttk.Button(c_frame, text="Text Color", command=lambda: self.choose_color(self.state.sub_color)).pack(side="left", padx=2)
        ttk.Button(c_frame, text="Outline Color", command=lambda: self.choose_color(self.state.sub_outline_color)).pack(side="left", padx=2)
        ttk.Button(c_frame, text="BG Color", command=lambda: self.choose_color(self.state.sub_bg_color)).pack(side="left", padx=2)
        
        # Row 3: Outline Width
        ttk.Label(self, text="Outline Width:").pack(anchor="w")
        ol_frame = ttk.Frame(self)
        ol_frame.pack(fill="x")
        self.ol_label = ttk.Label(ol_frame, text=str(self.state.sub_outline_width.get()), width=3)
        self.ol_label.pack(side="left")
        ol_scale = ttk.Scale(ol_frame, from_=0, to=5, variable=self.state.sub_outline_width, orient="horizontal",
                            command=lambda v: self.ol_label.config(text=str(int(float(v)))))
        ol_scale.pack(side="left", fill="x", expand=True)
        self.bind_release_to_preview(ol_scale)

        # Row 4: BG Opacity
        ttk.Label(self, text="BG Opacity (Transparency):").pack(anchor="w")
        bg_op_frame = ttk.Frame(self)
        bg_op_frame.pack(fill="x")
        self.bg_op_label = ttk.Label(bg_op_frame, text=str(self.state.sub_bg_opacity.get()), width=3)
        self.bg_op_label.pack(side="left")
        bg_op_scale = ttk.Scale(bg_op_frame, from_=0.0, to=1.0, variable=self.state.sub_bg_opacity, 
                                orient="horizontal", 
                                command=lambda v: self.bg_op_label.config(text=str(round(float(v), 1))))
        bg_op_scale.pack(side="left", fill="x", expand=True)
        self.bind_release_to_preview(bg_op_scale)

    # --- THIS METHOD WAS MISSING ---
    def bind_release_to_preview(self, widget):
        widget.bind("<ButtonRelease-1>", lambda e: self.refresh_callback())

    def choose_color(self, var):
        c = colorchooser.askcolor(initialcolor=var.get())[1]
        if c: 
            var.set(c)
            self.refresh_callback()