"""
Video Workspace - Main VideoTab layout and panel management
"""
import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from ui_components import CollapsibleFrame
from video_preview import VideoPreview
from encoding_settings import EncodingPanel
from subtitles import SubtitlesPanel
from color_correction import ColorCorrectionPanel
from geometry import GeometryPanel
from tracks_panel import TrackSelectionPanel
from trim_panel import TrimPanel
from scan_controller import ScanController
from scan_panel import ScanPanel


class VideoTab(ttk.Frame):
    """Workspace: Settings (Left) + Preview with Tabs (Right) - Enhanced Layout"""
    
    def __init__(self, parent, app_state, trim_controller, log_callback):
        """Initialize VideoTab"""
        super().__init__(parent)
        self.vars = app_state
        self.trim_controller = trim_controller
        self.log = log_callback
        self.config_tab = None
        self.current_video_path = None
        
        self.scan_controller = ScanController(self.vars, self.log)
        
        self.setup_layout()
    
    def set_config_tab(self, config_tab):
        """Set reference to config tab for cross-tab communication"""
        self.config_tab = config_tab
    
    def setup_layout(self):
        """Setup the main layout"""
        # --- MAIN HORIZONTAL SPLIT: Settings (Left) + Preview+Tabs (Right) ---
        main_paned = ttk.PanedWindow(self, orient="horizontal")
        main_paned.pack(fill="both", expand=True, padx=5, pady=5)
        
        # --- LEFT PANE: SETTINGS PANELS (Vertical Stack) ---
        settings_frame = ttk.Frame(main_paned)
        main_paned.add(settings_frame, weight=1)
        
        # Create scrollable canvas for settings
        canvas = tk.Canvas(settings_frame, highlightthickness=0, bg="white")
        scrollbar = ttk.Scrollbar(settings_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        # Configure scrolling
        def configure_scroll_region(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        scrollable_frame.bind("<Configure>", configure_scroll_region)
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel to canvas and scrollable_frame
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind("<MouseWheel>", _on_mousewheel)
        scrollable_frame.bind("<MouseWheel>", _on_mousewheel)
        
        # Make sure the canvas can receive focus for mousewheel events
        canvas.focus_set()
        
        # --- CORE SETTINGS PANELS (Stacked Vertically with Collapsible Frames) ---
        
        # Panel 1: Encoding Settings (Collapsible)
        encoding_collapsible = CollapsibleFrame(scrollable_frame, "Encoding Settings")
        encoding_collapsible.pack(fill="x", padx=5, pady=2)
        self.enc_panel = EncodingPanel(encoding_collapsible.get_content_frame(), self.vars)
        self.enc_panel.pack(fill="x", padx=5, pady=5)
        
        # Panel 2: Geometry Settings (Collapsible)
        geo_collapsible = CollapsibleFrame(scrollable_frame, "Geometry")
        geo_collapsible.pack(fill="x", padx=5, pady=2)
        self.geo_panel = GeometryPanel(geo_collapsible.get_content_frame(), self.vars, self.refresh_preview_from_settings)
        self.geo_panel.pack(fill="x", padx=5, pady=5)
        
        # Panel 3: Color Correction (Collapsible)
        color_collapsible = CollapsibleFrame(scrollable_frame, "Color Correction")
        color_collapsible.pack(fill="x", padx=5, pady=2)
        self.eq_panel = ColorCorrectionPanel(color_collapsible.get_content_frame(), self.vars, self.vars['deint'], self.refresh_preview_from_settings)
        self.eq_panel.pack(fill="x", padx=5, pady=5)
        
        # Panel 4: Subtitles (Collapsible)
        subs_collapsible = CollapsibleFrame(scrollable_frame, "Subtitles")
        subs_collapsible.pack(fill="x", padx=5, pady=2)
        self.subs_panel = SubtitlesPanel(subs_collapsible.get_content_frame(), self.vars, self.refresh_preview_from_settings)
        self.subs_panel.pack(fill="x", padx=5, pady=5)
        
        # Force update of scroll region after all panels are added
        self.after(100, lambda: canvas.configure(scrollregion=canvas.bbox("all")))
        
        # --- RIGHT PANE: PREVIEW AREA ---
        preview_frame = ttk.LabelFrame(main_paned, text="Real-time Preview", padding=10)
        main_paned.add(preview_frame, weight=2)

        # Initialize preview component
        self.preview = VideoPreview(preview_frame, self.vars, self.log)
        
        # --- TABS AREA (Inside Preview Frame) ---
        # Create notebook for specialized tabs
        self.tabs_notebook = ttk.Notebook(preview_frame)
        self.tabs_notebook.pack(fill="both", expand=True, pady=(5, 0))
        
        # Tab 1: Trim/Cut
        self.tab_trim_cut = ttk.Frame(self.tabs_notebook)
        self.tabs_notebook.add(self.tab_trim_cut, text="Trim/Cut")
        self.trim_panel = TrimPanel(
            self.tab_trim_cut, self.vars, self.trim_controller, self.log,
            self.set_cut_point, self.execute_cut
        )
        self.trim_panel.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Tab 2: Scan/Repair (Audio)
        self.tab_scan = ttk.Frame(self.tabs_notebook)
        self.tabs_notebook.add(self.tab_scan, text="Scan/Repair")
        self.scan_panel = ScanPanel(
            self.tab_scan,
            self.vars,
            self.scan_controller,
            self.log
        )
        self.scan_panel.pack(fill="both", expand=True, padx=5, pady=5)

    def refresh_preview_from_settings(self):
        """Called when settings change to re-render current frame"""
        if hasattr(self.preview, 'refresh_preview_from_settings'):
            self.preview.refresh_preview_from_settings()

    def on_file_select(self, event):
        """Handle file selection from config tab"""
        # Access the linked config_tab
        selection = self.config_tab.files_listbox.curselection() 
        if selection and self.preview.preview_enabled:
            index = selection[0]
            self.current_video_path = self.vars['input_files'][index]
            threading.Thread(target=self.load_video_metadata, args=(self.current_video_path,), daemon=True).start()

    def load_video_metadata(self, path):
        """Load video metadata and setup preview"""
        self.preview.load_video_metadata(path)
        
        # Detect tracks for trim/cut feature
        self.after(0, lambda: self.detect_tracks_for_trim(path))

    def detect_tracks_for_trim(self, path):
        """Detect tracks in video file for trim/cut feature"""
        if hasattr(self, 'trim_panel') and hasattr(self.trim_panel, 'tracks_panel'):
            self.trim_panel.tracks_panel.detect_tracks(path)
            # Reset cut point
            self.vars['cut_point_set'].set(False)
            self.trim_panel.reset_cut_status()
            self.log(f"Loaded video: {os.path.basename(path)}")
    
    def set_cut_point(self):
        """Save current timeline position as cut point"""
        if not hasattr(self, 'current_video_path'):
            self.log("No video selected")
            return
        
        cut_time = self.preview.timeline_var.get()
        
        # Validate cut position
        total_duration = self.preview.timeline.cget("to")
        valid, message = self.trim_controller.validate_cut_position(cut_time, total_duration)
        
        if not valid:
            self.trim_panel.update_cut_status(cut_time, message, valid=False)
            return
        
        # Align to nearest keyframe
        aligned_time = self.trim_controller.align_to_keyframe(
            self.current_video_path, cut_time
        )
        
        # Update SharedState
        self.vars['cut_position'].set(aligned_time)
        self.vars['cut_point_set'].set(True)
        
        # Format time for display
        mins, secs = divmod(int(aligned_time), 60)
        time_str = f"{mins:02d}:{secs:02d}"
        
        # Update UI
        if cut_time != aligned_time:
            display_msg = f"Cut Point: {time_str} (aligned from {cut_time:.2f}s)"
        else:
            display_msg = f"Cut Point: {time_str}"
        
        self.trim_panel.update_cut_status(aligned_time, display_msg, valid=True)
        self.log(display_msg)
    
    def execute_cut(self):
        """Execute the cut operation"""
        if not hasattr(self, 'current_video_path'):
            messagebox.showwarning("No Video", "Please select a video first.")
            return
        
        if not self.vars['cut_point_set'].get():
            messagebox.showwarning("No Cut Point", "Please set a cut point first using the timeline.")
            return
        
        # Confirm operation
        confirm = messagebox.askyesno(
            "Confirm Cut", 
            "This will create 2 files:\n"
            f"  1. Video from 0:00 to cut point\n"
            f"  2. Video from cut point to end\n\n"
            "Proceed?"
        )
        
        if not confirm:
            return
        
        # Get selected tracks
        tracks = self.trim_controller.get_selected_tracks()
        
        if not tracks:
            messagebox.showwarning("No Tracks", "Please select at least one track type.")
            return
        
        # Execute cut
        self.log("Starting cut operation...")
        cut_time = self.vars['cut_position'].get()
        
        success, message = self.trim_controller.execute_single_cut(
            self.current_video_path, cut_time, tracks
        )
        
        if success:
            self.log(message)
            messagebox.showinfo("Cut Complete", message)
        else:
            self.log(f"Cut failed: {message}")
            messagebox.showerror("Cut Failed", message)