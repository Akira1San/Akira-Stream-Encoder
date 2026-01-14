import tkinter as tk
from tkinter import ttk
from tracks_panel import TrackSelectionPanel


class TrimPanel(ttk.LabelFrame):
    """Container for trim/cut controls in General tab"""
    
    def __init__(self, parent, app_vars, trim_controller, log_callback, 
                 set_cut_callback, execute_cut_callback):
        super().__init__(parent, text="Trim/Cut Video", padding=10)
        self.vars = app_vars
        self.trim_controller = trim_controller
        self.log = log_callback
        
        # Store callbacks
        self.set_cut_callback = set_cut_callback
        self.execute_cut_callback = execute_cut_callback
        
        # Create widgets after callbacks are set
        self.create_widgets()
    
    def create_widgets(self):
        # Track Selection Panel
        self.tracks_panel = TrackSelectionPanel(
            self, self.vars, self.log,
            refresh_callback=self.set_cut_callback
        )
        self.tracks_panel.pack(fill="x", pady=5)
        
        # Cut Point Status Display
        status_frame = ttk.Frame(self)
        status_frame.pack(fill="x", pady=5)
        
        ttk.Label(status_frame, text="Status:").pack(side="left")
        self.cut_status_label = ttk.Label(
            status_frame, text="Not Set", 
            foreground="gray", font=("Arial", 10)
        )
        self.cut_status_label.pack(side="left", padx=10)
        
        # Button Frame
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", pady=10)
        
        ttk.Button(
            btn_frame, text="📍 Set Cut Point (Current Timeline Position)", 
            command=self.set_cut_callback
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.execute_btn = ttk.Button(
            btn_frame, text="✂️ Execute Cut", 
            command=self.execute_cut_callback,
            state="disabled"
        )
        self.execute_btn.pack(side="right")
    
    def update_cut_status(self, cut_time, message, valid=True):
        """Update cut status display"""
        color = "green" if valid else "red"
        self.cut_status_label.config(text=message, foreground=color)
        
        # Enable execute button only if cut point is valid
        self.execute_btn.config(state="normal" if valid else "disabled")
    
    def reset_cut_status(self):
        """Clear cut point status"""
        self.cut_status_label.config(text="Not Set", foreground="gray")
        self.execute_btn.config(state="disabled")
