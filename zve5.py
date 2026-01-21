import datetime
import json
import os
import platform
import subprocess
import threading
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

from encoding_settings import EncodingPanel
from subtitles import SubtitlesPanel
from color_correction import ColorCorrectionPanel
from geometry import GeometryPanel

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

# Check for PIL (Pillow)
try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageEnhance

    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("Warning: PIL (Pillow) not found. Video preview features will be disabled.")


class ConfigTab(ttk.Frame):
    """Handles System Paths and Input File Management"""

    def __init__(self, parent, app_vars, log_callback):
        super().__init__(parent)
        self.vars = app_vars
        self.log = log_callback # Store the log function
        #self.create_widgets()

        # --- FFmpeg Path Settings ---
        ffmpeg_frame = ttk.LabelFrame(self, text="System Paths", padding=10)
        ffmpeg_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(ffmpeg_frame, text="FFmpeg Path:").pack(anchor="w")
        ffmpeg_path_frame = ttk.Frame(ffmpeg_frame)
        ffmpeg_path_frame.pack(fill="x", pady=5)

        ttk.Entry(
            ffmpeg_path_frame, textvariable=self.vars["ffmpeg_path"], width=70
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(ffmpeg_path_frame, text="Browse", command=self.browse_ffmpeg).pack(
            side="right"
        )
        ttk.Button(
            ffmpeg_path_frame, text="Auto", command=self.auto_detect_ffmpeg
        ).pack(side="right", padx=(0, 5))

        # --- Output Folder ---
        output_frame = ttk.LabelFrame(self, text="Output Destination", padding=10)
        output_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(output_frame, text="Output Folder:").pack(anchor="w")
        folder_frame = ttk.Frame(output_frame)
        folder_frame.pack(fill="x", pady=5)

        ttk.Entry(folder_frame, textvariable=self.vars["output_folder"], width=70).pack(
            side="left", fill="x", expand=True, padx=(0, 5)
        )
        ttk.Button(folder_frame, text="Browse", command=self.browse_output_folder).pack(
            side="right"
        )

        # --- Input Files (Moved from Video Tab) ---
        list_frame = ttk.LabelFrame(self, text="Input Files Queue", padding=10)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill="x", pady=2)

        # Add Details Button
        self.app = app_vars # Reference to main app
        ttk.Button(btn_frame, text="Show Details", command=self.show_file_details).pack(side="left", padx=5)

        ttk.Button(btn_frame, text="Add Files", command=self.browse_input).pack(
            side="right"
        )
        ttk.Button(btn_frame, text="Clear List", command=self.clear_file_list).pack(
            side="right", padx=5
        )

        self.files_listbox = tk.Listbox(list_frame, height=10)
        self.files_listbox.pack(fill="both", expand=True, pady=5)

        # --- ADD THIS: INFO DISPLAY LABEL ---
        self.info_label = ttk.Label(list_frame, text="Select a file and click 'Show Details'...", 
                                   foreground="blue", font=("Arial", 9))
        self.info_label.pack(fill="x", pady=2)

    def browse_ffmpeg(self):
        if platform.system() == "Windows":
            filename = filedialog.askopenfilename(
                title="Select FFmpeg",
                filetypes=[("Executable", "*.exe"), ("All", "*.*")],
            )
        else:
            filename = filedialog.askopenfilename(
                title="Select FFmpeg", filetypes=[("All", "*.*")]
            )
        if filename:
            self.vars["ffmpeg_path"].set(filename)

    def auto_detect_ffmpeg(self):
        paths = []
        if platform.system() == "Windows":
            paths = [
                "C:\\ffmpeg\\bin\\ffmpeg.exe",
                "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
            ]
        else:
            paths = ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]

        for p in paths + ["ffmpeg"]:
            if os.path.exists(p) or p == "ffmpeg":
                try:
                    subprocess.run(
                        [p, "-version"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=2,
                        check=True,
                    )
                    self.vars["ffmpeg_path"].set(p)
                    return
                except:
                    pass

    def browse_output_folder(self):
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.vars["output_folder"].set(folder)

    def browse_input(self):
        filenames = filedialog.askopenfilenames(
            title="Select Video",
            filetypes=[("Video", "*.mp4 *.mkv *.avi *.mov"), ("All", "*.*")],
        )
        if filenames:
            for f in filenames:
                if f not in self.vars["input_files"]:
                    self.vars["input_files"].append(f)
                    self.files_listbox.insert(tk.END, os.path.basename(f))

    def clear_file_list(self):
        self.vars["input_files"].clear()
        self.files_listbox.delete(0, tk.END)

    def show_file_details(self):
        """Triggers info popup for selected file in main app"""
        selection = self.files_listbox.curselection()
        if selection:
            index = selection[0]
            if 0 <= index < len(self.vars['input_files']):
                filepath = self.vars['input_files'][index]
                # We need to call main app method. 
                # Since ConfigTab doesn't have main app ref, we use a workaround:
                # We will detect info here for now and show messagebox.
                self.detect_and_show_info(filepath)
            else:
                messagebox.showinfo("Info", "Select a valid file index.")
        else:
            messagebox.showwarning("Info", "Select a file first from the list.")

    def detect_and_show_info(self, filepath):
        self.log(f"Getting info for {os.path.basename(filepath)}...")
        
        cmd = [
            self.vars['ffmpeg_path'].get(), "-i", filepath,
            "-f", "null", "-"
        ]
        
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            stderr = result.stderr
            
            # Parse info lines
            info_text = []
            
            # Resolution
            import re
            match = re.search(r"\d{3,4}x\d{3,4}", stderr)
            if match: info_text.append(f"Resolution: {match.group()}")

            # Codec
            match = re.search(r"Stream #0:0.*Video: (\w+)", stderr)
            if match: info_text.append(f"Codec: {match.group(1)}")

            # Bitrate
            match = re.search(r"bitrate: (\d+) kb/s", stderr)
            if match: info_text.append(f"Bitrate: {match.group(1)} kbps")
            
            # Duration
            match = re.search(r"Duration: (\d{2}:\d{2}:\d{2})", stderr)
            if match: info_text.append(f"Duration: {match.group(1)}")

            # Construct display string
            display_msg = " | ".join(info_text) if info_text else "Could not parse video info."
            
            # --- UPDATE: Show in Label AND Log ---
            self.info_label.config(text=display_msg)
            self.log(f"File Info: {display_msg}")
            
        except Exception as e:
            err_msg = f"Failed to get info: {e}"
            self.info_label.config(text=err_msg)
            self.log(err_msg)

class VideoTab(ttk.Frame):
    """Workspace: Settings (Left) + Preview with Tabs (Right) - Enhanced Layout"""
    def __init__(self, parent, app_vars):
        super().__init__(parent)
        self.vars = app_vars
        self.preview_thread = None
        self.stop_preview = False
        self.default_font = self.get_default_font()
        
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
        
        # Make sure the canvas can receive focus for mouse wheel events
        canvas.focus_set()
        
        # --- CORE SETTINGS PANELS (Stacked Vertically with Collapsible Frames) ---
        
        # Panel 1: Encoding Settings (Collapsible)
        encoding_collapsible = CollapsibleFrame(scrollable_frame, "Encoding Settings")
        encoding_collapsible.pack(fill="x", padx=5, pady=2)
        self.enc_panel = EncodingPanel(encoding_collapsible.get_content_frame(), StateWrapper(self.vars))
        self.enc_panel.pack(fill="x", padx=5, pady=5)
        
        # Panel 2: Geometry Settings (Collapsible)
        geo_collapsible = CollapsibleFrame(scrollable_frame, "Geometry")
        geo_collapsible.pack(fill="x", padx=5, pady=2)
        self.geo_panel = GeometryPanel(geo_collapsible.get_content_frame(), StateWrapper(self.vars), self.refresh_preview_from_settings)
        self.geo_panel.pack(fill="x", padx=5, pady=5)
        
        # Panel 3: Color Correction (Collapsible)
        color_collapsible = CollapsibleFrame(scrollable_frame, "Color Correction")
        color_collapsible.pack(fill="x", padx=5, pady=2)
        self.eq_panel = ColorCorrectionPanel(color_collapsible.get_content_frame(), StateWrapper(self.vars), self.vars['deint'], self.refresh_preview_from_settings)
        self.eq_panel.pack(fill="x", padx=5, pady=5)
        
        # Panel 4: Subtitles (Collapsible)
        subs_collapsible = CollapsibleFrame(scrollable_frame, "Subtitles")
        subs_collapsible.pack(fill="x", padx=5, pady=2)
        self.subs_panel = SubtitlesPanel(subs_collapsible.get_content_frame(), StateWrapper(self.vars), self.refresh_preview_from_settings)
        self.subs_panel.pack(fill="x", padx=5, pady=5)
        
        # Force update of scroll region after all panels are added
        self.after(100, lambda: canvas.configure(scrollregion=canvas.bbox("all")))
        
        # --- RIGHT PANE: PREVIEW AREA ---
        preview_frame = ttk.LabelFrame(main_paned, text="Real-time Preview", padding=10)
        main_paned.add(preview_frame, weight=2)

        if not HAS_PIL:
            ttk.Label(preview_frame, text="Preview requires 'Pillow' library.", foreground="red").pack(pady=20)
            self.preview_enabled = False
        else:
            self.preview_enabled = True
            split_container = ttk.Frame(preview_frame)
            split_container.pack(fill="both", expand=True)
            
            left_frame = ttk.LabelFrame(split_container, text="Original", padding=5)
            left_frame.pack(side="left", fill="both", expand=True, padx=2)
            self.lbl_before = ttk.Label(left_frame, text="No Video", anchor="center")
            self.lbl_before.pack(fill="both", expand=True)
            
            right_frame = ttk.LabelFrame(split_container, text="Processed Preview", padding=5)
            right_frame.pack(side="right", fill="both", expand=True, padx=2)
            self.lbl_after = ttk.Label(right_frame, text="No Video", anchor="center")
            self.lbl_after.pack(fill="both", expand=True)

            time_frame = ttk.Frame(preview_frame)
            time_frame.pack(fill="x", pady=5)
            ttk.Label(time_frame, text="Timeline:").pack(side="left")
            self.timeline_var = tk.DoubleVar()
            self.timeline = ttk.Scale(time_frame, from_=0, to=100, variable=self.timeline_var, orient="horizontal", command=self.on_timeline_drag)
            self.timeline.pack(side="left", fill="x", expand=True, padx=5)
            self.time_label = ttk.Label(time_frame, text="00:00")
            self.time_label.pack(side="right")
            self.timeline.bind("<ButtonRelease-1>", lambda e: self.refresh_preview_from_settings())
            
            # --- TABS AREA (Inside Preview Frame) ---
            # Create notebook for future expansion
            self.tabs_notebook = ttk.Notebook(preview_frame)
            self.tabs_notebook.pack(fill="both", expand=True, pady=(5, 0))
            
            # Tab 1: General (placeholder for future content)
            self.tab_general = ttk.Frame(self.tabs_notebook)
            self.tabs_notebook.add(self.tab_general, text="General")
            ttk.Label(self.tab_general, text="General settings and information", 
                     font=("Arial", 12)).pack(expand=True)

    # --- Helper Methods ---
    def bind_release_to_preview(self, widget):
        widget.bind("<ButtonRelease-1>", lambda e: self.refresh_preview_from_settings())

    def get_default_font(self):
        fonts = []
        if platform.system() == "Windows":
            fonts = ["arial.ttf", "tahoma.ttf"]
        elif platform.system() == "Darwin": 
            fonts = ["/Library/Fonts/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"]
        else: 
            fonts = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
            
        for f in fonts:
            if os.path.exists(f):
                try: return ImageFont.truetype(f, 24)
                except: continue
        return ImageFont.load_default()

    def on_file_select(self, event):
        # Access the linked config_tab
        selection = self.config_tab.files_listbox.curselection() 
        if selection and self.preview_enabled:
            index = selection[0]
            self.current_video_path = self.vars['input_files'][index]
            threading.Thread(target=self.load_video_metadata, args=(self.current_video_path,), daemon=True).start()

    def load_video_metadata(self, path):
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            duration = float(res.stdout.strip())
            self.after(0, lambda: self.timeline.configure(to=duration))
            self.after(0, lambda: self.refresh_preview_from_settings())
        except: pass

    def on_timeline_drag(self, val):
        ts = float(val)
        mins, secs = divmod(int(ts), 60)
        self.time_label.config(text=f"{mins:02d}:{secs:02d}")

    def refresh_preview_from_settings(self):
        """Called when settings change to re-render current frame"""
        if self.preview_enabled and hasattr(self, 'current_video_path'):
            self.seek_preview(self.timeline_var.get())

    def seek_preview(self, timestamp):
        if not hasattr(self, 'current_video_path') or not os.path.exists(self.current_video_path): return
        
        if self.preview_thread and self.preview_thread.is_alive():
            self.stop_preview = True
        self.stop_preview = False
        self.preview_thread = threading.Thread(target=self.fetch_frame_task, args=(timestamp,), daemon=True)
        self.preview_thread.start()

    def fetch_frame_task(self, timestamp):
        if self.stop_preview: return
        
        path = self.current_video_path
        cmd = [
            self.vars['ffmpeg_path'].get(), "-ss", str(timestamp),
            "-i", path, "-vframes", "1", "-q:v", "2",
            "-f", "mjpeg", "-"
        ]
        
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            data, err = proc.communicate()
            if not self.stop_preview and data:
                img = Image.open(io.BytesIO(data))
                # Note: We resize here to fit UI (320x180), but we simulate crop BEFORE resize?
                # Actually, easier to simulate crop on small image for preview.
                img = img.resize((320, 180), Image.Resampling.LANCZOS)
                
                # Process for Preview (Crop + EQ + Subtitles)
                img_after = img.copy()
                
                # 1. Apply Geometry Crop Simulation
                if self.vars.get('force_widescreen', tk.BooleanVar(value=False)).get():
                    img_after = self.apply_crop_preview(img_after)
                
                # 2. Apply EQ
                if self.vars.get('eq_enable', tk.BooleanVar(value=True)).get():
                    img_after = self.apply_eq_preview(img_after)
                
                # 3. Draw Subtitles
                if self.vars['burn_subs'].get():
                    img_after = self.draw_subtitle_preview(img_after, timestamp)
                
                photo_before = ImageTk.PhotoImage(img)
                photo_after = ImageTk.PhotoImage(img_after)
                
                self.after(0, lambda: self.update_preview_images(photo_before, photo_after))
        except Exception as e:
            print(f"Preview error: {e}")

    def apply_crop_preview(self, img):
        """Simulates Widescreen Crop for preview"""
        w, h = img.size # Preview dimensions (e.g., 320x180)
        
        if self.vars.get('force_widescreen', tk.BooleanVar(value=False)).get():
            # We are assuming Source is 640x480 (4:3) and Target is 640x360 (16:9).
            # This requires cropping 60 pixels from top and bottom of the original.
            
            # Calculate scale factor between Original Width and Preview Width
            # Original = 640, Preview = 320. Scale = 0.5
            scale_factor = w / 640
            
            # Pixels to crop from Original (Total / 2 for Top and Bottom)
            # 480 - 360 = 120. 120 / 2 = 60.
            original_crop_amount = (480 - 360) // 2  # 60 pixels
            
            # Map to Preview dimensions
            preview_crop_amount = int(original_crop_amount * scale_factor)
            
            # Get Offset (Designed for Original dimensions)
            offset_orig = self.vars.get('geo_offset', tk.DoubleVar(value=0)).get()
            # Map to Preview dimensions
            offset_preview = offset_orig * scale_factor
            
            # Calculate Start Y
            # Default start is just the crop amount (e.g., 30px in preview)
            # We add the user offset to slide it up/down.
            start_y = int(preview_crop_amount + offset_preview)
            end_y = int(h - preview_crop_amount + offset_preview)
            
            # Clamp values to ensure we don't crop outside the image
            if start_y < 0: start_y = 0
            if end_y > h: end_y = h
            if start_y >= end_y: return img # Safety: prevent crash if slider is extreme
            
            # Perform Crop
            cropped_img = img.crop((0, start_y, w, end_y))
            
            # Resize back to full frame to simulate the "Zoom" effect
            return cropped_img.resize((w, h))
            
        return img

    def apply_eq_preview(self, img):
        """Simulates EQ filters in Python for fast preview"""
        
        # 1. Brightness
        # FFmpeg range: -1.0 to 1.0. PIL range: 0.0 to 2.0 (1.0 is neutral).
        b_val = self.vars.get('eq_brightness', tk.DoubleVar(value=0.0)).get()
        if abs(b_val) > 0.001:
            enh = ImageEnhance.Brightness(img)
            # We add the FFmpeg value to the PIL neutral point (1.0)
            img = enh.enhance(1.0 + b_val)

        # 2. Contrast
        # FFmpeg range: 0.0 to 2.0. PIL range: 0.0 to 2.0 (1.0 is neutral).
        c_val = self.vars.get('eq_contrast', tk.DoubleVar(value=1.0)).get()
        if abs(c_val - 1.0) > 0.001:
            enh = ImageEnhance.Contrast(img)
            img = enh.enhance(c_val)
            
        # 3. Saturation (Simulated)
        # FFmpeg range: 0.0 to 3.0. We use HSV in Python.
        s_val = self.vars.get('eq_saturation', tk.DoubleVar(value=1.0)).get()
        if abs(s_val - 1.0) > 0.001:
            # Convert to HSV, adjust S (Saturation), convert back
            img = img.convert("HSV")
            h, s, v = img.split()
            # Multiply the saturation channel
            s = s.point(lambda i: i * s_val)
            img = Image.merge("HSV", (h, s, v))
            img = img.convert("RGBA")

        return img

    def draw_subtitle_preview(self, img, timestamp):
        draw = ImageDraw.Draw(img, 'RGBA') 
        
        # Get actual subtitle text from file
        subtitle_path = self.find_subtitle(self.current_video_path)
        if subtitle_path:
            try:
                texts = self.parse_srt_file(subtitle_path, timestamp)
                if texts:
                    text = "\n".join(texts)
                else:
                    return img
            except Exception as e:
                text = "[Error reading subtitle file]"
        else:
            text = ""
        
        # Skip rendering if no text
        if not text:
            return img
        
        size = self.vars['sub_size'].get()
        color = self.vars['sub_color'].get()
        outline_color = self.vars['sub_outline_color'].get()
        outline_width = self.vars['sub_outline_width'].get()
        pos = self.vars['sub_position'].get()
        
        bg_color_hex = self.vars['sub_bg_color'].get()
        bg_opacity = self.vars['sub_bg_opacity'].get()
        
        try:
            if platform.system() == "Windows": font_path = "arial.ttf"
            elif platform.system() == "Darwin": font_path = "/Library/Fonts/Arial.ttf"
            else: font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            font = ImageFont.truetype(font_path, size)
        except: font = self.default_font

        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        w, h = img.size
        x = (w - text_w) / 2
        if pos == "top": y = 10
        elif pos == "center": y = (h - text_h) / 2
        else: y = h - text_h - 10
        
        if bg_opacity > 0.0:
            pad = 5
            bg_color_rgb = tuple(int(bg_color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            bg_alpha = int(bg_opacity * 255)
            draw.rectangle(
                [x - pad, y - pad, x + text_w + pad, y + text_h + pad],
                fill=bg_color_rgb + (bg_alpha,)
            )

        for adj_x in range(-outline_width, outline_width+1):
            for adj_y in range(-outline_width, outline_width+1):
                if adj_x == 0 and adj_y == 0: continue
                draw.text((x + adj_x, y + adj_y), text, font=font, fill=outline_color)
        draw.text((x, y), text, font=font, fill=color)
        return img

    def update_preview_images(self, p_before, p_after):
        self.lbl_before.configure(image=p_before, text="")
        self.lbl_before.image = p_before
        self.lbl_after.configure(image=p_after, text="")
        self.lbl_after.image = p_after 

    def find_subtitle(self, video_path):
        base = os.path.splitext(video_path)[0]
        for ext in [".srt", ".ass"]:
            if os.path.exists(base + ext):
                return base + ext
        return None

    def build_subtitle_filter_complex(self, sub_path):
        p = sub_path.replace("\\", "/").replace(":", "\\:")
        style = []
        
        if self.vars['sub_font'].get() != "Arial": style.append(f"Fontname={self.vars['sub_font'].get()}")
        if self.vars['sub_size'].get() != 24: style.append(f"Fontsize={self.vars['sub_size'].get()}")
        if self.vars['sub_color'].get() != "#FFFFFF": style.append(f"PrimaryColour={self.hex_to_ass(self.vars['sub_color'].get())}")
        if self.vars['sub_outline_color'].get() != "#000000": style.append(f"OutlineColour={self.hex_to_ass(self.vars['sub_outline_color'].get())}")
        if self.vars['sub_outline_width'].get() != 2: style.append(f"Outline={self.vars['sub_outline_width'].get()}")
        
        bg_opacity = self.vars['sub_bg_opacity'].get()
        if bg_opacity > 0.0:
            bg_color_hex = self.vars['sub_bg_color'].get()
            ass_bg = self.hex_to_ass(bg_color_hex, bg_opacity)
            style.append(f"BackColour={ass_bg}")
            style.append("BorderStyle=4")
        
        pos_map = {"bottom": 2, "top": 8, "center": 10}
        if self.vars['sub_position'].get() != "bottom": style.append(f"Alignment={pos_map[self.vars['sub_position'].get()]}")
        
        force_style = f":force_style='{','.join(style)}'" if style else ""
        return f"subtitles='{p}'{force_style}"

    def hex_to_ass(self, hex_color, opacity=1.0):
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        alpha = int((1.0 - opacity) * 255)
        return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"

    def parse_srt_file(self, sub_path, timestamp):
        """
        Parse SRT file and return list of subtitle texts for given timestamp.
        """
        try:
            with open(sub_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            try:
                with open(sub_path, 'r', encoding='latin-1') as f:
                    lines = f.readlines()
            except:
                raise Exception("Could not read subtitle file")
        except:
            raise Exception("Could not read subtitle file")
        
        subtitle_texts = []
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            if not line or line.isdigit():
                i += 1
                continue
            
            if '-->' in line:
                try:
                    parts = line.split('-->')
                    start_str = parts[0].strip()
                    end_str = parts[1].strip()
                    
                    start_time = self.srt_time_to_seconds(start_str)
                    end_time = self.srt_time_to_seconds(end_str)
                    
                    if start_time <= timestamp <= end_time:
                        i += 1
                        while i < len(lines):
                            text_line = lines[i].strip()
                            if not text_line or text_line.isdigit():
                                break
                            subtitle_texts.append(text_line)
                            i += 1
                        return subtitle_texts
                except:
                    pass
            
            i += 1
        
        return subtitle_texts

    def srt_time_to_seconds(self, time_str):
        """
        Convert SRT timestamp format (HH:MM:SS,mmm) to seconds.
        """
        if ',' in time_str:
            time_part, ms_part = time_str.split(',')
        else:
            time_part, ms_part = time_str, '000'
        
        parts = time_part.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
        milliseconds = int(ms_part)
        
        return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000

import io


class StateWrapper:
    """Wrapper that allows both dictionary and attribute access to vars"""
    def __init__(self, vars_dict):
        self._vars = vars_dict
    
    def __getitem__(self, key):
        return self._vars[key]
    
    def __setitem__(self, key, value):
        self._vars[key] = value
    
    def __getattr__(self, key):
        try:
            return self._vars[key]
        except KeyError:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{key}'")
    
    def __setattr__(self, key, value):
        if key == '_vars':
            super().__setattr__(key, value)
        else:
            self._vars[key] = value


class VideoEncoderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Video Encoder - Unified Workspace")
        self.geometry("1024x1024")
        self.current_process = None

        self.vars = {
            # General / IO
            'input_files': [],
            'output_folder': tk.StringVar(value=os.path.expanduser("~\\Desktop")),
            'ffmpeg_path': tk.StringVar(value="ffmpeg"),
            
            # Encoding
            'use_gpu': tk.BooleanVar(value=True),
            'encoder_var': tk.StringVar(value="h264_nvenc"),
            'resolution_var': tk.StringVar(value="none"),
            'framerate_var': tk.StringVar(value="24000/1001"),
            'cq_var': tk.IntVar(value=23),
            'use_orig_br_var': tk.BooleanVar(value=False),
            'max_br_var': tk.IntVar(value=4000),
            'container': tk.StringVar(value="mp4"),  # mp4, mkv, avi
            
            # --- Bitrate Controls ---
            'bitrate_mode': tk.StringVar(value="CBR (Constant Bitrate)"),
            'target_bitrate': tk.StringVar(value="2000"),
            
            # --- Scale Controls ---
            'scale_mode': tk.StringVar(value="off"),
            'scale_algorithm': tk.StringVar(value="bicubic"),
            'scale_quality': tk.StringVar(value="quality"),
            
            # --- Subtitle Variables ---
            'burn_subs': tk.BooleanVar(value=False),
            'sub_font': tk.StringVar(value="Arial"),
            'sub_size': tk.IntVar(value=24),
            'sub_position': tk.StringVar(value="bottom"),
            'sub_color': tk.StringVar(value="#FFFFFF"),
            'sub_outline_color': tk.StringVar(value="#000000"),
            'sub_bg_color': tk.StringVar(value="#000000"),
            'sub_outline_width': tk.IntVar(value=2),
            'sub_bg_opacity': tk.DoubleVar(value=0.5), # <-- This was missing

            # --- EQ Settings ---
            'eq_bypass': tk.BooleanVar(value=False),
            'eq_enable': tk.BooleanVar(value=False),  # Created dynamically but needed here
            'eq_brightness': tk.DoubleVar(value=0.0),
            'eq_contrast': tk.DoubleVar(value=1.0),
            'eq_saturation': tk.DoubleVar(value=1.0),
            'eq_gamma': tk.DoubleVar(value=1.0),
            'eq_gamma_r': tk.DoubleVar(value=1.0),
            'eq_gamma_g': tk.DoubleVar(value=1.0),
            'eq_gamma_b': tk.DoubleVar(value=1.0),

            # --- Filter Variables ---
            'deint': tk.BooleanVar(value=False),
            'denoise': tk.BooleanVar(value=False),
            'libplacebo': tk.BooleanVar(value=False),
            'vol_enable': tk.BooleanVar(value=False),
            'vol_val': tk.DoubleVar(value=0.0),
            'stretch_fill': tk.BooleanVar(value=False),

            # --- Geometry ---
            'force_widescreen': tk.BooleanVar(value=False),
            'geo_offset': tk.DoubleVar(value=0.0),

            # --- Cut Parts ---
            'cut_parts': tk.StringVar(value="1"),
            'split_duration_min': tk.IntVar(value=30),
            'split_mode': tk.BooleanVar(value=False),
        }

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

        # Notebook (Only 2 Tabs Now)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

        self.tab_config = ConfigTab(self.notebook, self.vars, self.log)
        self.notebook.add(self.tab_config, text="Config")

        self.tab_video = VideoTab(self.notebook, self.vars)

        self.tab_video.config_tab = self.tab_config

        self.notebook.add(self.tab_video, text="Video")

        # Bind listbox selection in Config to update Video Tab
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

        self.load_settings()

    def log(self, msg):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def start_encoding(self):
        if not self.vars["input_files"]:
            messagebox.showwarning("No Files", "Please add video files first.")
            return

        if (
            not os.path.exists(self.vars["ffmpeg_path"].get())
            and self.vars["ffmpeg_path"].get() != "ffmpeg"
        ):
            messagebox.showerror("FFmpeg Error", "FFmpeg path is invalid.")
            return

        # Validate H.265 hardware compatibility
        encoder = self.vars['encoder_var'].get()
        if encoder in ["hevc_nvenc", "libx265"]:
            if not self.validate_h265_hardware_compatibility():
                return

        # Validate container compatibility
        self.validate_container_codec()

        self.log("Starting batch encoding...")
        self.is_encoding = True
        self.processing_thread = threading.Thread(
            target=self.process_batch, daemon=True
        )
        self.processing_thread.start()

    def encode_single_file(self, input_path, output_file, target_bitrate=None, start_time_str=None, duration_str=None):
        """Encodes a single file with optional trimming/splitting"""
        try:
            # Build command
            cmd = self.build_ffmpeg_command(input_path, output_file, target_bitrate=target_bitrate, start_time_str=start_time_str, duration_str=duration_str)
            
            # Validate command before execution
            is_valid, validation_msg = self.validate_ffmpeg_command(cmd)
            if not is_valid:
                self.log(f"Command validation failed: {validation_msg}")
                messagebox.showerror("Command Validation Error", f"FFmpeg command validation failed:\n{validation_msg}")
                return
            
            self.log(f"Running: {' '.join(cmd)}")
            
            # Run FFmpeg using Popen
            # FIX: Changed from STDOUT to PIPE to avoid AttributeError issues on Windows
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, # Read from standard error pipe
                universal_newlines=True,
                encoding='utf-8', errors='replace'
            )
            
            # --- SAFETY CHECK ---
            if self.current_process is None or not hasattr(self.current_process, 'stderr'):
                raise Exception("FFmpeg process failed to start")
            
            # Read logs in real-time
            while True:
                line = self.current_process.stderr.readline() # Read from stderr pipe
                
                if not line and self.current_process.poll() is not None:
                    break
                
                if line:
                    # Update status label if we see time/frame data
                    if "time=" in line or "frame=" in line:
                        self.status_var.set(f"Processing... {line.strip()}")
                    
                    # Log specific lines (Progress)
                    # 'elapsed' and 'speed' are the lines we wanted to see.
                    if "elapsed=" in line or "speed=" in line:
                        self.log(f"Progress: {line.strip()}")
                    
                    # Log errors
                    elif "[Error" in line or "Error reinitializing" in line:
                        self.log(f"FFmpeg: {line.strip()}")

            # Wait for process to finish
            return_code = self.current_process.wait()
            
            if return_code != 0:
                encoder = self.vars['encoder_var'].get()
                self.log(f"Encoding FAILED for {os.path.basename(output_file)}. Return code: {return_code}")
                
                # H.265-specific error handling and fallback suggestions
                if encoder in ["hevc_nvenc", "libx265"]:
                    self._handle_h265_encoding_failure(return_code, encoder, output_file)
                else:
                    messagebox.showerror("Encoding Error", f"Encoding failed.\nReturn code: {return_code}")
            else:
                self.log(f"Successfully encoded {os.path.basename(output_file)}")
                
        except subprocess.TimeoutExpired:
            err_msg = "Encoding timed out."
            self.log(err_msg)
            messagebox.showerror("Error", err_msg)
        except Exception as e:
            encoder = self.vars['encoder_var'].get()
            err_msg = f"Exception during encoding:\n{e}"
            self.log(err_msg)
            
            # H.265-specific exception handling
            if encoder in ["hevc_nvenc", "libx265"]:
                self._handle_h265_encoding_exception(e, encoder)
            else:
                messagebox.showerror("Critical Error", err_msg)

    def _handle_h265_encoding_failure(self, return_code, encoder, output_file):
        """Handle H.265-specific encoding failures with fallback suggestions"""
        if encoder == "hevc_nvenc":
            messagebox.showerror(
                "H.265 NVENC Encoding Failed",
                f"H.265 hardware encoding failed (Return code: {return_code}).\n\n"
                "Possible causes:\n"
                "• GPU memory insufficient\n"
                "• Driver compatibility issues\n"
                "• Hardware encoder limitations\n\n"
                "Suggested solutions:\n"
                "• Try reducing resolution or quality settings\n"
                "• Switch to 'libx265' for CPU-based H.265 encoding\n"
                "• Update GPU drivers\n"
                "• Use H.264 encoding instead"
            )
        elif encoder == "libx265":
            messagebox.showerror(
                "libx265 Encoding Failed", 
                f"CPU-based H.265 encoding failed (Return code: {return_code}).\n\n"
                "Possible causes:\n"
                "• Insufficient system memory\n"
                "• Invalid encoding parameters\n"
                "• Corrupted input file\n\n"
                "Suggested solutions:\n"
                "• Reduce video resolution or quality settings\n"
                "• Increase available system memory\n"
                "• Try H.264 encoding instead\n"
                "• Check input file integrity"
            )
    
    def _handle_h265_encoding_exception(self, exception, encoder):
        """Handle H.265-specific encoding exceptions"""
        error_str = str(exception).lower()
        
        if "memory" in error_str or "out of memory" in error_str:
            messagebox.showerror(
                "H.265 Memory Error",
                f"H.265 encoding failed due to memory issues.\n\n"
                "Suggested parameter adjustments:\n"
                "• Reduce resolution (e.g., 1920x1080 → 1280x720)\n"
                "• Increase CRF value (lower quality, less memory)\n"
                "• Close other applications to free memory\n"
                f"• Switch from {encoder} to H.264 encoding"
            )
        elif "invalid" in error_str or "parameter" in error_str:
            messagebox.showerror(
                "H.265 Parameter Error",
                f"H.265 encoding failed due to invalid parameters.\n\n"
                "This may be caused by:\n"
                "• Incompatible resolution settings\n"
                "• Invalid quality range for H.265\n"
                "• Unsupported encoding options\n\n"
                "Try using default settings or switch to H.264 encoding."
            )
        else:
            messagebox.showerror("H.265 Encoding Error", f"H.265 encoding exception:\n{exception}")

    def process_batch(self):
        files = self.vars['input_files']
        
        # --- 1. PROCESS FILES ---
        for input_file in files:
            if not self.is_encoding: break
            
            # H.265-specific bitrate handling
            target_bitrate = None
            if self.vars.get('bitrate_mode', tk.StringVar()).get() == "CBR (Constant Bitrate)":
                if self.vars['use_orig_br_var'].get():
                    # Detect original bitrate for H.265 optimization
                    orig_bitrate = self.get_video_bitrate(input_file)
                    if orig_bitrate:
                        target_bitrate = self._optimize_h265_bitrate(orig_bitrate, input_file)
                        self.log(f"H.265 optimized bitrate: {target_bitrate} kbps (original: {orig_bitrate} kbps)")
                else:
                    # Use user-specified target bitrate
                    try:
                        target_bitrate = int(self.vars['target_bitrate'].get())
                        # Apply H.265 bitrate recommendations
                        target_bitrate = self._validate_h265_bitrate(target_bitrate, input_file)
                    except ValueError:
                        self.log("Invalid target bitrate specified, using quality-based encoding")
                        target_bitrate = None
            
            # Check Split Mode
            parts_count = int(self.vars['cut_parts'].get())
            
            if parts_count == 1:
                # --- NORMAL ENCODING (Existing Logic) ---
                container = self.vars['container'].get()
                base_name = os.path.splitext(os.path.basename(input_file))[0]
                output_file = os.path.join(self.vars['output_folder'].get(), f"encoded_{base_name}.{container}")
                self.encode_single_file(input_file, output_file, target_bitrate=target_bitrate)
            else:
                # --- SPLIT ENCODING (New Logic) ---
                self.log(f"Splitting {os.path.basename(input_file)} by duration...")
                
                total_duration = self.get_video_duration(input_file)
                
                if total_duration == 0.0:
                    self.log(f"Error: Could not determine duration for {os.path.basename(input_file)}")
                    continue

                # Get user setting (Minutes)
                split_min = self.vars['split_duration_min'].get()
                split_seconds = split_min * 60
                
                # Calculate parts
                num_parts = int(total_duration / split_seconds)
                if num_parts < 1:
                    num_parts = 1 # At least 1 part
                
                self.log(f"Total Duration: {total_duration}s. Splitting into {num_parts} parts ({split_min} mins each).")
                
                # Loop for each part
                for i in range(num_parts):
                    if not self.is_encoding: break
                    
                    # Calculate Start Time and End Time
                    start_time = i * split_seconds
                    end_time = start_time + split_seconds
                    
                    # Clamp End Time to Total Duration (for last part)
                    if end_time > total_duration:
                        end_time = total_duration
                    
                    # Format time string (HH:MM:SS)
                    sh, sm, ss = divmod(int(start_time), 3600)
                    sm, ss = divmod(sm, 60)
                    time_str = f"{sh:02d}:{sm:02d}:{ss:02d}"
                    
                    # Calculate Duration for this part
                    part_dur_sec = end_time - start_time
                    ph, pm, ps = divmod(int(part_dur_sec), 3600)
                    pm, ps = divmod(int(pm), 60)
                    dur_str = f"{ph:02d}:{pm:02d}:{ps:02d}"
                    
                    # Create Output Filename
                    base_name = os.path.splitext(os.path.basename(input_file))[0]
                    container = self.vars['container'].get()
                    output_file = os.path.join(self.vars['output_folder'].get(), f"{base_name}_Part{i+1}.{container}")
                    
                    self.status_var.set(f"Part {i+1}/{num_parts}: {os.path.basename(input_file)}")
                    
                    # Encode this part
                    self.encode_single_file(input_file, output_file, target_bitrate=target_bitrate, start_time_str=time_str, duration_str=dur_str)

        # --- END OF BATCH ---
        self.status_var.set("Batch Complete")
        self.log("All tasks finished.")
        self.is_encoding = False

    def cancel_encoding(self):
        self.is_encoding = False
        self.status_var.set("Cancelled")

    def get_video_bitrate(self, input_path):
        """
        Detect the video bitrate of the input file using ffprobe or ffmpeg.
        Returns bitrate in kbps (int) or None if failed.
        """
        # Try to find ffprobe based on ffmpeg path
        ffprobe_path = "ffprobe"
        if self.vars['ffmpeg_path'].get() != "ffmpeg":
            base_dir = os.path.dirname(self.vars['ffmpeg_path'].get())
            if base_dir:
                candidate = os.path.join(base_dir, "ffprobe.exe" if os.name == 'nt' else "ffprobe")
                if os.path.exists(candidate):
                    ffprobe_path = candidate
        
        self.log(f"Detecting bitrate for {os.path.basename(input_path)} using {ffprobe_path}...")
        
        try:
            # Method 1: ffprobe (cleaner)
            cmd = [
                ffprobe_path,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=bit_rate",
                "-of", "default=noprint_wrappers=1:nokey=1",
                input_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                br_bps = int(result.stdout.strip())
                br_kbps = br_bps // 1000
                self.log(f"Detected bitrate: {br_kbps} kbps")
                return br_kbps
        except Exception as e:
            self.log(f"ffprobe detection failed: {e}", "WARN")
        
        try:
            # Method 2: Fallback to parsing ffmpeg -i (messy but reliable if ffprobe missing)
            cmd = [self.vars['ffmpeg_path'].get(), "-i", input_path]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            stderr_output = result.stderr
            
            # Simple regex search for bitrate in the output line "bitrate: 5000 kb/s"
            import re
            match = re.search(r"bitrate:\s*(\d+)\s*kb/s", stderr_output)
            if match:
                br_kbps = int(match.group(1))
                self.log(f"Detected bitrate via ffmpeg output: {br_kbps} kbps")
                return br_kbps
        except Exception as e:
            self.log(f"ffmpeg bitrate parsing failed: {e}", "WARN")
            
        self.log("Could not detect original bitrate.", "WARN")
        return None

    def build_ffmpeg_command(self, input_path, output_path, target_bitrate=None, start_time_str=None, duration_str=None):
        # 1. Executable
        cmd = [self.vars['ffmpeg_path'].get()]

        # --- CHECK FAST SPLIT MODE ---
        if self.vars.get('split_mode', tk.BooleanVar(value=False)).get():
            self.log("Using Fast Split (Stream Copy)")
            cmd.extend(["-ss", start_time_str] if start_time_str else [])
            cmd.extend(["-t", duration_str] if duration_str else [])
            cmd.extend(["-i", input_path])
            cmd.extend(["-c", "copy"]) # Copy All streams
            cmd.extend(["-y", output_path])
            return cmd

        # --- NORMAL ENCODING MODE ---
        self.log("Normal Re-Encoding Mode")

        # 2. Trim Logic
        if start_time_str: cmd.extend(["-ss", start_time_str])
        if duration_str: cmd.extend(["-t", duration_str])

        # 3. Hardware Decoding
        # 3. Hardware Decoding Flags
        # REVERTED: Removed 'hwaccel_output_format' and 'device' to prevent crash.
        # We only use 'hwaccel cuda' which allows GPU decoding, 
        # and FFmpeg handles the transfer to encoder automatically.
        if self.vars['use_gpu'].get():
            cmd.extend(["-hwaccel", "cuda"])
            
        cmd.extend(["-i", input_path])
        cmd.extend(["-r", self.vars['framerate_var'].get()])
        
        encoder = self.vars['encoder_var'].get()
        cmd.extend(["-c:v", encoder])
        
        # H.265-specific parameter handling
        if encoder in ["hevc_nvenc", "libx265"]:
            self._apply_h265_parameters(cmd, encoder, target_bitrate)
        else:
            # H.264 parameter handling (existing logic)
            self._apply_h264_parameters(cmd, encoder, target_bitrate)
        
        # --- VIDEO FILTERS ---
        video_filters = []
        
        # 1. Resolution Handling (If "none", we detect source res to ensure compatibility)
        if self.vars['resolution_var'].get() != "none":
            target_res = self.vars['resolution_var'].get()
        else:
            # Detect Source Resolution to force "Copy" behavior
            # We check if we have stored source resolution, or detect on fly (heavy) or just don't scale.
            # For Normal Encoding, we usually leave it to auto, but to be safe:
            pass 
            
            # If we really want to force source res to ensure no scaling artifacts:
            # We could add logic here, but let's stick to explicit user selection for now.

        # 2. Geometry (Crop/Scale)
        if self.vars.get('force_widescreen', tk.BooleanVar(value=False)).get():
            target_res = self.vars['resolution_var'].get()
            if target_res == "none": target_res = "1920x1080" # Fallback or detect?
            # ... (Keep existing crop logic) ...
            # (If resolution is none, this math might fail, ensure target_res is valid)
            
        # 2. Scale
        # FIX: Removed ":force_original_aspect_ratio=increase" to prevent EINVAL crash
        if self.vars['resolution_var'].get() != "none":
            target_res = self.vars['resolution_var'].get()
            
            if self.vars.get('force_widescreen', tk.BooleanVar(value=False)).get():
                # Simple scale (Crop handles aspect ratio)
                video_filters.append(f"scale={target_res}")
            else:
                # Normal mode (Fill frame)
                video_filters.append(f"scale={target_res}")
            
# 4. Filters
        if self.vars['deint'].get(): video_filters.append("yadif")

        # --- COLOR CORRECTION (EQ) ---
        if self.vars.get('eq_enable', tk.BooleanVar(value=False)).get():
            eq_params = []
            
            brightness = self.vars.get('eq_brightness', tk.DoubleVar(value=0.0)).get()
            if abs(brightness) > 0.001:
                eq_params.append(f"brightness={brightness:.3f}")
            
            contrast = self.vars.get('eq_contrast', tk.DoubleVar(value=1.0)).get()
            if abs(contrast - 1.0) > 0.001:
                eq_params.append(f"contrast={contrast:.3f}")
            
            saturation = self.vars.get('eq_saturation', tk.DoubleVar(value=1.0)).get()
            if abs(saturation - 1.0) > 0.001:
                eq_params.append(f"saturation={saturation:.3f}")
            
            gamma = self.vars.get('eq_gamma', tk.DoubleVar(value=1.0)).get()
            if abs(gamma - 1.0) > 0.001:
                eq_params.append(f"gamma={gamma:.3f}")
            
            gamma_r = self.vars.get('eq_gamma_r', tk.DoubleVar(value=1.0)).get()
            gamma_g = self.vars.get('eq_gamma_g', tk.DoubleVar(value=1.0)).get()
            gamma_b = self.vars.get('eq_gamma_b', tk.DoubleVar(value=1.0)).get()
            
            if abs(gamma_r - 1.0) > 0.001 or abs(gamma_g - 1.0) > 0.001 or abs(gamma_b - 1.0) > 0.001:
                eq_params.append(f"gamma_r={gamma_r:.3f}")
                eq_params.append(f"gamma_g={gamma_g:.3f}")
                eq_params.append(f"gamma_b={gamma_b:.3f}")
            
            if eq_params:
                eq_filter = "eq=" + ":".join(eq_params)
                video_filters.append(eq_filter)
                self.log(f"Applying color correction: {eq_filter}")

        # --- SUBTITLE BURNING ---
        if self.vars['burn_subs'].get():
            subtitle_path = self.find_subtitle(input_path)
            if subtitle_path:
                subtitle_filter = self.build_subtitle_filter_complex(subtitle_path)
                video_filters.append(subtitle_filter)
                self.log(f"Burning subtitles from: {os.path.basename(subtitle_path)}")
            else:
                self.log(f"No subtitle file found for {os.path.basename(input_path)}")

        if video_filters:
            cmd.extend(["-vf", ",".join(video_filters)])

        # --- AUDIO ---
        cmd.extend(["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", "-channel_layout", "stereo"])

        # --- CONTAINER-SPECIFIC FLAGS ---
        container = self.vars['container'].get()
        
        if container == "mp4":
            cmd.extend(["-movflags", "+faststart"])
        elif container == "mkv":
            # MKV is flexible, no special flags needed
            pass
        elif container == "avi":
            cmd.extend(["-avoid_negative_ts", "make_zero"])

        # Add output format flag
        cmd.extend(["-f", container])
        
        cmd.extend(["-y", output_path])
        return cmd

    def find_subtitle(self, video_path):
        base = os.path.splitext(video_path)[0]
        for ext in [".srt", ".ass"]:
            if os.path.exists(base + ext):
                return base + ext
        return None

    def build_subtitle_filter_complex(self, sub_path):
        p = sub_path.replace("\\", "/").replace(":", "\\:")
        style = []
        
        if self.vars['sub_font'].get() != "Arial": style.append(f"Fontname={self.vars['sub_font'].get()}")
        if self.vars['sub_size'].get() != 24: style.append(f"Fontsize={self.vars['sub_size'].get()}")
        if self.vars['sub_color'].get() != "#FFFFFF": style.append(f"PrimaryColour={self.hex_to_ass(self.vars['sub_color'].get())}")
        if self.vars['sub_outline_color'].get() != "#000000": style.append(f"OutlineColour={self.hex_to_ass(self.vars['sub_outline_color'].get())}")
        if self.vars['sub_outline_width'].get() != 2: style.append(f"Outline={self.vars['sub_outline_width'].get()}")
        
        bg_opacity = self.vars['sub_bg_opacity'].get()
        if bg_opacity > 0.0:
            bg_color_hex = self.vars['sub_bg_color'].get()
            ass_bg = self.hex_to_ass(bg_color_hex, bg_opacity)
            style.append(f"BackColour={ass_bg}")
            style.append("BorderStyle=4")
        
        pos_map = {"bottom": 2, "top": 8, "center": 10}
        if self.vars['sub_position'].get() != "bottom": style.append(f"Alignment={pos_map[self.vars['sub_position'].get()]}")
        
        force_style = f":force_style='{','.join(style)}'" if style else ""
        return f"subtitles='{p}'{force_style}"

    def hex_to_ass(self, hex_color, opacity=1.0):
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        alpha = int((1.0 - opacity) * 255)
        return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"

    def _apply_h265_parameters(self, cmd, encoder, target_bitrate):
        """Apply H.265-specific encoding parameters"""
        if encoder == "hevc_nvenc":
            # GPU H.265 encoding parameters
            cmd.extend(["-preset", "p4"])
            if target_bitrate:
                cmd.extend(["-rc", "cbr"])
                cmd.extend(["-b:v", f"{target_bitrate}k", "-maxrate", f"{target_bitrate}k", "-bufsize", f"{target_bitrate * 2}k"])
                self.log(f"Using H.265 NVENC with CBR: {target_bitrate} kbps")
            else:
                cmd.extend(["-rc", "vbr"])
                cmd.extend(["-cq", str(self.vars['cq_var'].get()), "-b:v", "0k"])
                self.log(f"Using H.265 NVENC with CQ: {self.vars['cq_var'].get()}")
        elif encoder == "libx265":
            # CPU H.265 encoding parameters
            cmd.extend(["-preset", "medium"])
            if target_bitrate:
                cmd.extend(["-b:v", f"{target_bitrate}k"])
                self.log(f"Using libx265 with CBR: {target_bitrate} kbps")
            else:
                # Use CRF for libx265 (quality-based encoding)
                crf_value = max(18, min(28, self.vars['cq_var'].get()))  # Clamp to H.265 range
                cmd.extend(["-crf", str(crf_value)])
                self.log(f"Using libx265 with CRF: {crf_value} (H.265 optimized range)")
            
            # H.265-specific optimizations
            cmd.extend(["-x265-params", "keyint=144:min-keyint=144:bframes=0"])
        
        # Common H.265 parameters
        cmd.extend(["-pix_fmt", "yuv420p"])
        cmd.extend(["-profile:v", "main"])
        cmd.extend(["-level:v", "4.0"])
        
    def _apply_h264_parameters(self, cmd, encoder, target_bitrate):
        """Apply H.264-specific encoding parameters (existing logic)"""
        if self.vars['use_gpu'].get():
            cmd.extend(["-preset", "p4"])
            if target_bitrate:
                cmd.extend(["-rc", "cbr"])
                cmd.extend(["-b:v", f"{target_bitrate}k", "-maxrate", f"{target_bitrate}k", "-bufsize", f"{target_bitrate * 2}k"])
            else:
                cmd.extend(["-rc", "vbr"])
                cmd.extend(["-cq", str(self.vars['cq_var'].get()), "-b:v", "0k"])
        else:
            cmd.extend(["-preset", "medium"])
            if target_bitrate:
                cmd.extend(["-b:v", f"{target_bitrate}k"])
            else:
                cmd.extend(["-crf", str(self.vars['cq_var'].get())])
        
        # H.264 parameters
        cmd.extend(["-pix_fmt", "yuv420p"])
        cmd.extend(["-profile:v", "main"])
        cmd.extend(["-level:v", "4.0"])

    def check_encoder_availability(self, encoder):
        """Check if a specific encoder is available in the FFmpeg installation"""
        try:
            cmd = [self.vars['ffmpeg_path'].get(), "-encoders"]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            return encoder in result.stdout
        except Exception as e:
            self.log(f"Failed to check encoder availability: {e}")
            return False
    
    def validate_h265_hardware_compatibility(self):
        """Validate H.265 hardware compatibility and provide warnings/fallbacks"""
        encoder = self.vars['encoder_var'].get()
        
        if encoder == "hevc_nvenc":
            # Check if NVENC is available
            if not self.check_encoder_availability("hevc_nvenc"):
                result = messagebox.askyesno(
                    "H.265 NVENC Not Available",
                    "H.265 hardware encoding (hevc_nvenc) is not available.\n\n"
                    "This could be due to:\n"
                    "• Missing or outdated GPU drivers\n"
                    "• Incompatible GPU hardware\n"
                    "• FFmpeg built without NVENC support\n\n"
                    "Would you like to automatically switch to CPU-based H.265 encoding (libx265)?"
                )
                
                if result:
                    self.vars['encoder_var'].set("libx265")
                    self.log("Automatically switched to libx265 for H.265 encoding")
                    return True
                else:
                    return False
                    
        elif encoder == "libx265":
            # Check if libx265 is available
            if not self.check_encoder_availability("libx265"):
                messagebox.showerror(
                    "libx265 Not Available",
                    "CPU-based H.265 encoding (libx265) is not available.\n\n"
                    "Please install FFmpeg with libx265 support:\n"
                    "• Download FFmpeg with libx265 from https://ffmpeg.org/\n"
                    "• Or install via package manager (e.g., 'apt install ffmpeg' on Ubuntu)\n"
                    "• Ensure libx265 is included in your FFmpeg build"
                )
                return False
        
        return True
    
    def _handle_h265_encoding_exception(self, exception, encoder):
        """Handle H.265-specific encoding exceptions"""
        if "memory" in str(exception).lower() or "out of memory" in str(exception).lower():
            messagebox.showerror(
                "H.265 Memory Error",
                f"H.265 encoding failed due to memory issues.\n\n"
                "Suggested solutions:\n"
                "• Reduce video resolution\n"
                "• Lower quality settings (increase CRF/CQ value)\n"
                "• Close other applications to free memory\n"
                "• Use H.264 encoding for lower memory usage\n\n"
                f"Error details: {exception}"
            )
        else:
            messagebox.showerror(
                f"H.265 Encoding Error ({encoder})",
                f"H.265 encoding encountered an error.\n\n"
                f"Error details: {exception}\n\n"
                "Try switching to H.264 encoding if the problem persists."
            )
    
    def validate_ffmpeg_command(self, cmd):
        """Validate FFmpeg command for H.265-specific requirements"""
        try:
            # Basic command structure validation
            if not cmd or len(cmd) < 3:
                return False, "Command too short or empty"
            
            # Check for required FFmpeg executable
            if not cmd[0] or not ("ffmpeg" in cmd[0].lower()):
                return False, "Invalid FFmpeg executable path"
            
            # H.265-specific validation
            encoder = self.vars['encoder_var'].get()
            if encoder in ["hevc_nvenc", "libx265"]:
                # Check if encoder is specified in command
                if "-c:v" not in cmd or encoder not in cmd:
                    return False, f"H.265 encoder {encoder} not found in command"
                
                # Validate H.265-specific parameters
                if encoder == "libx265" and "-crf" in cmd:
                    try:
                        crf_index = cmd.index("-crf") + 1
                        if crf_index < len(cmd):
                            crf_value = int(cmd[crf_index])
                            if not (18 <= crf_value <= 28):
                                return False, f"libx265 CRF value {crf_value} outside recommended range (18-28)"
                    except (ValueError, IndexError):
                        return False, "Invalid CRF parameter for libx265"
                
                elif encoder == "hevc_nvenc" and "-cq" in cmd:
                    try:
                        cq_index = cmd.index("-cq") + 1
                        if cq_index < len(cmd):
                            cq_value = int(cmd[cq_index])
                            if not (18 <= cq_value <= 30):
                                return False, f"hevc_nvenc CQ value {cq_value} outside recommended range (18-30)"
                    except (ValueError, IndexError):
                        return False, "Invalid CQ parameter for hevc_nvenc"
            
            return True, "Command validation passed"
            
        except Exception as e:
            return False, f"Validation error: {e}"
        
        if encoder == "hevc_nvenc":
            if not self.check_encoder_availability("hevc_nvenc"):
                messagebox.showwarning(
                    "Hardware Compatibility Warning",
                    "NVIDIA HEVC encoder (hevc_nvenc) is not available.\n"
                    "This may be due to:\n"
                    "• Missing NVIDIA GPU\n"
                    "• Outdated GPU drivers\n"
                    "• FFmpeg not compiled with NVENC support\n\n"
                    "Recommendation: Use 'libx265' for CPU-based H.265 encoding."
                )
                return False
        elif encoder == "libx265":
            if not self.check_encoder_availability("libx265"):
                messagebox.showerror(
                    "Encoder Not Available",
                    "libx265 encoder is not available in your FFmpeg installation.\n\n"
                    "Please install FFmpeg with libx265 support:\n"
                    "• Windows: Download FFmpeg with libx265 from https://ffmpeg.org/\n"
                    "• Linux: Install ffmpeg with libx265 (e.g., apt install ffmpeg)\n"
                    "• macOS: Install via Homebrew: brew install ffmpeg"
                )
                return False
        
        return True

    def validate_ffmpeg_command(self, cmd):
        """Validate FFmpeg command structure and parameters"""
        if not cmd or len(cmd) < 3:
            return False, "Command too short"
        
        # Check for required components
        if "-i" not in cmd:
            return False, "Missing input file parameter (-i)"
        
        if "-c:v" not in cmd:
            return False, "Missing video codec parameter (-c:v)"
        
        encoder = self.vars['encoder_var'].get()
        
        # H.265-specific validation
        if encoder in ["hevc_nvenc", "libx265"]:
            if encoder == "libx265":
                # Validate CRF range for libx265
                if "-crf" in cmd:
                    try:
                        crf_idx = cmd.index("-crf") + 1
                        if crf_idx < len(cmd):
                            crf_value = int(cmd[crf_idx])
                            if not (18 <= crf_value <= 28):
                                return False, f"Invalid CRF value for libx265: {crf_value} (should be 18-28)"
                    except (ValueError, IndexError):
                        return False, "Invalid CRF parameter format"
                
                # Check for x265-specific parameters
                if "-x265-params" not in cmd:
                    self.log("Warning: No x265-specific parameters found")
            
            elif encoder == "hevc_nvenc":
                # Validate NVENC-specific parameters
                if "-preset" in cmd:
                    try:
                        preset_idx = cmd.index("-preset") + 1
                        if preset_idx < len(cmd):
                            preset = cmd[preset_idx]
                            valid_presets = ["p1", "p2", "p3", "p4", "p5", "p6", "p7"]
                            if preset not in valid_presets and not preset.startswith("slow"):
                                self.log(f"Warning: Unusual NVENC preset: {preset}")
                    except (ValueError, IndexError):
                        pass
        
        # Check for output file
        if not cmd[-1].endswith(('.mp4', '.mkv', '.avi')):
            return False, "Missing or invalid output file"
        
        return True, "Command validation passed"

    def validate_container_codec(self):
        """Warn if container/codec combination has issues"""
        container = self.vars['container'].get()
        codec = self.vars['encoder_var'].get()
        
        compatibility = {
            "mp4": ["h264_nvenc", "h264_amf", "libx264", "hevc_nvenc", "hevc_amf", "libx265"],
            "mkv": ["h264_nvenc", "h264_amf", "libx264", "hevc_nvenc", "hevc_amf", "libx265", "vp9", "av1"],
            "avi": ["h264_nvenc", "h264_amf", "libx264"]  # Limited support - no H.265
        }
        
        # Special handling for H.265 + AVI combination
        if codec in ["hevc_nvenc", "libx265"] and container == "avi":
            messagebox.showwarning(
                "H.265 Container Compatibility Warning",
                f"Warning: H.265 ({codec}) has limited compatibility with AVI containers.\n\n"
                "Issues you may encounter:\n"
                "• Playback problems on older devices\n"
                "• Compatibility issues with some media players\n"
                "• Potential file corruption\n\n"
                "Recommended alternatives:\n"
                "• MP4 container (best compatibility)\n"
                "• MKV container (full H.265 support)"
            )
            return
        
        if codec not in compatibility.get(container, []):
            messagebox.showwarning(
                "Compatibility Warning",
                f"Warning: {codec} may not be fully compatible with {container.upper()} container.\n"
                f"Recommended codecs: {', '.join(compatibility.get(container, []))}"
            )

    def save_settings(self):
        data = {
            k: v.get() if hasattr(v, "get") else v
            for k, v in self.vars.items()
            if hasattr(v, "get")
        }
        data["deint"] = self.vars["deint"].get()
        data["denoise"] = self.vars["denoise"].get()
        data["libplacebo"] = self.vars["libplacebo"].get()
        data["vol_enable"] = self.vars["vol_enable"].get()
        data["vol_val"] = self.vars["vol_val"].get()
        #data['autocrop'] = self.vars['autocrop'].get()
        data['stretch_fill'] = self.vars['stretch_fill'].get()

        # EQ Settings
        data['eq_bypass'] = self.vars['eq_bypass'].get()
        data['eq_bright'] = self.vars['eq_brightness'].get()
        data['eq_contrast'] = self.vars['eq_contrast'].get()
        data['eq_sat'] = self.vars['eq_saturation'].get()
        data['eq_gamma'] = self.vars['eq_gamma'].get()
        data['eq_rg'] = self.vars['eq_gamma_r'].get()
        data['eq_gg'] = self.vars['eq_gamma_g'].get()
        data['eq_gb'] = self.vars['eq_gamma_b'].get()

        data['cut_parts'] = self.vars['cut_parts'].get()

        try:
            with open("settings.json", "w") as f:
                json.dump(data, f)
            self.log("Settings saved.")
        except Exception as e:
            self.log(f"Error saving: {e}")

    def load_settings(self):
        if os.path.exists("settings.json"):
            try:
                with open("settings.json", "r") as f:
                    data = json.load(f)
                for k, v in data.items():
                    if k in self.vars and hasattr(self.vars[k], "set"):
                        self.vars[k].set(v)
                if hasattr(self, "tab_video"):
                    self.vars["deint"].set(data.get("deint", False))
                    self.vars["denoise"].set(data.get("denoise", False))
                    self.vars["libplacebo"].set(data.get("libplacebo", False))
                    self.vars["vol_enable"].set(data.get("vol_enable", False))
                    self.vars["vol_val"].set(data.get("vol_val", 0.0))
                    #self.vars['autocrop'].set(data.get('autocrop', False))
                    self.vars['stretch_fill'].set(data.get('stretch_fill', False))

                    self.vars['eq_bypass'].set(data.get('eq_bypass', False))
                    self.vars['eq_brightness'].set(data.get('eq_bright', 0.0))
                    self.vars['eq_contrast'].set(data.get('eq_contrast', 1.0))
                    self.vars['eq_saturation'].set(data.get('eq_sat', 1.0))
                    self.vars['eq_gamma'].set(data.get('eq_gamma', 1.0))
                    self.vars['eq_gamma_r'].set(data.get('eq_rg', 1.0))
                    self.vars['eq_gamma_g'].set(data.get('eq_gg', 1.0))
                    self.vars['eq_gamma_b'].set(data.get('eq_gb', 1.0))

                    self.vars['cut_parts'].set(data.get('cut_parts', '1'))                   
                    
            except Exception as e:
                self.log(f"Error loading settings: {e}")

    def get_video_duration(self, input_path):
        """
        Detects video duration. Tries ffprobe first (fast), then ffmpeg.
        Increased timeout for large files.
        """
        duration = 0.0
        
        # Try to find ffprobe
        ffprobe_path = "ffprobe"
        ffmpeg_path = self.vars['ffmpeg_path'].get()
        
        if ffmpeg_path != "ffmpeg" and os.path.exists(ffmpeg_path):
            base_dir = os.path.dirname(ffmpeg_path)
            # Try to find ffprobe.exe in same folder
            candidate = os.path.join(base_dir, "ffprobe.exe" if os.name == 'nt' else "ffprobe")
            if os.path.exists(candidate):
                ffprobe_path = candidate

        # Attempt 1: Use FFprobe (Fastest & Most Reliable)
        if ffprobe_path:
            try:
                cmd = [
                    ffprobe_path,
                    "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    input_path
                ]
                # Increased timeout to 60 seconds for large MKV files
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
                
                if result.returncode == 0 and result.stdout.strip():
                    duration = float(result.stdout.strip())
                    self.log(f"Duration detected via ffprobe: {duration} sec")
                    return duration
            except subprocess.TimeoutExpired:
                self.log(f"ffprobe timed out for {os.path.basename(input_path)}. Trying ffmpeg...")
            except Exception as e:
                self.log(f"ffprobe failed: {e}")

        # Attempt 2: Fallback to ffmpeg (Parsing stderr)
        try:
            cmd = [ffmpeg_path, "-i", input_path]
            # Increased timeout
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
            stderr_output = result.stderr
            
            # Regex for Duration
            import re
            match = re.search(r"Duration:\s*(\d{2}:\d{2}:\d{2})", stderr_output)
            if match:
                h, m, s = map(int, match.group(1).split(':'))
                duration = h * 3600 + m * 60 + s
                return duration
        except subprocess.TimeoutExpired:
            self.log(f"ffmpeg timed out for {os.path.basename(input_path)}. Cannot determine duration.", "WARN")
        except Exception as e:
            self.log(f"ffmpeg detection failed: {e}", "WARN")
            
        return duration

    def _optimize_h265_bitrate(self, original_bitrate, input_path):
        """Optimize bitrate for H.265 encoding based on original content and resolution"""
        encoder = self.vars['encoder_var'].get()
        
        # H.265 is typically 25-50% more efficient than H.264
        if encoder in ["hevc_nvenc", "libx265"]:
            # Get video resolution for bitrate recommendations
            resolution = self._get_video_resolution(input_path)
            
            # H.265 efficiency factor (reduce bitrate by 30-40% from H.264)
            efficiency_factor = 0.65  # 35% reduction
            optimized_bitrate = int(original_bitrate * efficiency_factor)
            
            # Apply resolution-based limits for H.265
            min_bitrate, max_bitrate = self._get_h265_bitrate_range(resolution)
            
            # Clamp to reasonable range
            optimized_bitrate = max(min_bitrate, min(max_bitrate, optimized_bitrate))
            
            return optimized_bitrate
        
        return original_bitrate
    
    def _validate_h265_bitrate(self, target_bitrate, input_path):
        """Validate and adjust target bitrate for H.265 encoding"""
        encoder = self.vars['encoder_var'].get()
        
        if encoder in ["hevc_nvenc", "libx265"]:
            resolution = self._get_video_resolution(input_path)
            min_bitrate, max_bitrate = self._get_h265_bitrate_range(resolution)
            
            if target_bitrate < min_bitrate:
                self.log(f"Warning: Target bitrate {target_bitrate} kbps too low for H.265, using {min_bitrate} kbps")
                return min_bitrate
            elif target_bitrate > max_bitrate:
                self.log(f"Warning: Target bitrate {target_bitrate} kbps too high for H.265, using {max_bitrate} kbps")
                return max_bitrate
        
        return target_bitrate
    
    def _get_h265_bitrate_range(self, resolution):
        """Get recommended bitrate range for H.265 based on resolution"""
        # H.265 bitrate recommendations (kbps)
        bitrate_ranges = {
            "1920x1080": (1500, 6000),   # 1080p
            "1280x720": (800, 3000),     # 720p
            "720x480": (400, 1500),      # 480p
            "640x480": (300, 1200),      # 480p (4:3)
            "640x368": (300, 1000),      # Low res
        }
        
        return bitrate_ranges.get(resolution, (500, 4000))  # Default range
    
    def _get_video_resolution(self, input_path):
        """Get video resolution from input file"""
        try:
            cmd = [
                self.vars['ffmpeg_path'].get(), "-i", input_path,
                "-f", "null", "-"
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            
            # Parse resolution from stderr
            import re
            match = re.search(r"(\d{3,4}x\d{3,4})", result.stderr)
            if match:
                return match.group(1)
        except Exception as e:
            self.log(f"Failed to detect resolution: {e}")
        
        return "1920x1080"  # Default fallback

if __name__ == "__main__":
    app = VideoEncoderApp()
    app.mainloop()
