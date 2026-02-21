"""
Reusable UI Components for Video Encoder
"""
import tkinter as tk
from tkinter import ttk


class CollapsibleFrame(ttk.Frame):
    """A collapsible frame with an arrow button to expand/collapse content"""
    def __init__(self, parent, title="", **kwargs):
        super().__init__(parent, **kwargs)
        self.title = title
        self.is_expanded = True
        
        # Header frame with title and arrow button
        self.header_frame = ttk.Frame(self)
        self.header_frame.pack(fill="x", padx=5, pady=2)
        
        # Arrow button (▼ when expanded, ► when collapsed)
        self.arrow_button = ttk.Button(
            self.header_frame, 
            text="▼", 
            width=3,
            command=self.toggle_collapse
        )
        self.arrow_button.pack(side="left")
        
        # Title label
        self.title_label = ttk.Label(
            self.header_frame, 
            text=title, 
            font=("Arial", 9, "bold")
        )
        self.title_label.pack(side="left", padx=(5, 0))
        
        # Content frame (this will be hidden/shown)
        self.content_frame = ttk.Frame(self)
        self.content_frame.pack(fill="both", expand=True, padx=5, pady=2)
        
    def toggle_collapse(self):
        """Toggle the collapsed/expanded state"""
        if self.is_expanded:
            # Collapse
            self.content_frame.pack_forget()
            self.arrow_button.config(text="►")
            self.is_expanded = False
        else:
            # Expand
            self.content_frame.pack(fill="both", expand=True, padx=5, pady=2)
            self.arrow_button.config(text="▼")
            self.is_expanded = True
    
    def get_content_frame(self):
        """Return the content frame where widgets should be added"""
        return self.content_frame