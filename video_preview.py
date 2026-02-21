"""
Video Preview Component - Handles real-time preview functionality
"""
import io
import os
import platform
import subprocess
import threading
import tkinter as tk
from tkinter import ttk

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageEnhance
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class VideoPreview:
    """Handles video preview functionality"""
    
    def __init__(self, parent_frame, vars_dict, log_callback):
        self.vars = vars_dict
        self.log = log_callback
        self.preview_thread = None
        self.stop_preview = False
        self.current_video_path = None
        self.default_font = self.get_default_font()
        
        self.setup_preview_ui(parent_frame)
    
    def setup_preview_ui(self, parent_frame):
        """Setup the preview UI components"""
        if not HAS_PIL:
            ttk.Label(parent_frame, text="Preview requires 'Pillow' library.", foreground="red").pack(pady=20)
            self.preview_enabled = False
            return
        
        self.preview_enabled = True
        split_container = ttk.Frame(parent_frame)
        split_container.pack(fill="both", expand=True)
        
        left_frame = ttk.LabelFrame(split_container, text="Original", padding=5)
        left_frame.pack(side="left", fill="both", expand=True, padx=2)
        self.lbl_before = ttk.Label(left_frame, text="No Video", anchor="center")
        self.lbl_before.pack(fill="both", expand=True)
        
        right_frame = ttk.LabelFrame(split_container, text="Processed Preview", padding=5)
        right_frame.pack(side="right", fill="both", expand=True, padx=2)
        self.lbl_after = ttk.Label(right_frame, text="No Video", anchor="center")
        self.lbl_after.pack(fill="both", expand=True)

        time_frame = ttk.Frame(parent_frame)
        time_frame.pack(fill="x", pady=5)
        ttk.Label(time_frame, text="Timeline:").pack(side="left")
        self.timeline_var = tk.DoubleVar()
        self.timeline = ttk.Scale(time_frame, from_=0, to=100, variable=self.timeline_var, orient="horizontal", command=self.on_timeline_drag)
        self.timeline.pack(side="left", fill="x", expand=True, padx=5)
        self.time_label = ttk.Label(time_frame, text="00:00")
        self.time_label.pack(side="right")
        self.timeline.bind("<ButtonRelease-1>", lambda e: self.refresh_preview_from_settings())
    
    def get_default_font(self):
        """Get default font for subtitle rendering"""
        fonts = []
        if platform.system() == "Windows":
            fonts = ["arial.ttf", "tahoma.ttf"]
        elif platform.system() == "Darwin": 
            fonts = ["/Library/Fonts/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"]
        else: 
            fonts = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
            
        for f in fonts:
            if os.path.exists(f):
                try: 
                    return ImageFont.truetype(f, 24)
                except: 
                    continue
        return ImageFont.load_default()
    
    def load_video_metadata(self, path):
        """Load video metadata and setup timeline"""
        self.current_video_path = path
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            duration = float(res.stdout.strip())
            self.timeline.configure(to=duration)
            self.refresh_preview_from_settings()
        except: 
            pass
    
    def on_timeline_drag(self, val):
        """Handle timeline drag events"""
        ts = float(val)
        mins, secs = divmod(int(ts), 60)
        self.time_label.config(text=f"{mins:02d}:{secs:02d}")

    def refresh_preview_from_settings(self):
        """Called when settings change to re-render current frame"""
        if self.preview_enabled and hasattr(self, 'current_video_path') and self.current_video_path:
            self.seek_preview(self.timeline_var.get())

    def seek_preview(self, timestamp):
        """Seek to specific timestamp and update preview"""
        if not hasattr(self, 'current_video_path') or not os.path.exists(self.current_video_path): 
            return
        
        if self.preview_thread and self.preview_thread.is_alive():
            self.stop_preview = True
        self.stop_preview = False
        self.preview_thread = threading.Thread(target=self.fetch_frame_task, args=(timestamp,), daemon=True)
        self.preview_thread.start()

    def fetch_frame_task(self, timestamp):
        """Background task to fetch and process frame"""
        if self.stop_preview: 
            return
        
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
                img = img.resize((320, 180), Image.Resampling.LANCZOS)
                
                # Process for Preview (Crop + EQ + Subtitles)
                img_after = img.copy()
                
                # 1. Apply Geometry Crop Simulation
                if self.vars['force_widescreen'].get():
                    img_after = self.apply_crop_preview(img_after)
                
                # 2. Apply EQ
                if self.vars['eq_enable'].get():
                    img_after = self.apply_eq_preview(img_after)
                
                # 3. Draw Subtitles
                if self.vars['burn_subs'].get():
                    img_after = self.draw_subtitle_preview(img_after, timestamp)
                
                photo_before = ImageTk.PhotoImage(img)
                photo_after = ImageTk.PhotoImage(img_after)
                
                # Schedule UI update on main thread
                if hasattr(self, 'lbl_before'):  # Check if UI still exists
                    self.lbl_before.after(0, lambda: self.update_preview_images(photo_before, photo_after))
        except Exception as e:
            print(f"Preview error: {e}")

    def apply_crop_preview(self, img):
        """Simulates Widescreen Crop for preview"""
        w, h = img.size # Preview dimensions (e.g., 320x180)
        
        if self.vars['force_widescreen'].get():
            # Calculate scale factor between Original Width and Preview Width
            scale_factor = w / 640
            
            # Pixels to crop from Original (Total / 2 for Top and Bottom)
            original_crop_amount = (480 - 360) // 2  # 60 pixels
            
            # Map to Preview dimensions
            preview_crop_amount = int(original_crop_amount * scale_factor)
            
            # Get Offset (Designed for Original dimensions)
            offset_orig = self.vars['geo_offset'].get()
            # Map to Preview dimensions
            offset_preview = offset_orig * scale_factor
            
            # Calculate Start Y
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
        b_val = self.vars['eq_brightness'].get()
        if abs(b_val) > 0.001:
            enh = ImageEnhance.Brightness(img)
            img = enh.enhance(1.0 + b_val)

        # 2. Contrast
        c_val = self.vars['eq_contrast'].get()
        if abs(c_val - 1.0) > 0.001:
            enh = ImageEnhance.Contrast(img)
            img = enh.enhance(c_val)
            
        # 3. Saturation (Simulated)
        s_val = self.vars['eq_saturation'].get()
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
        """Draw subtitle overlay on preview image"""
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
        except: 
            font = self.default_font

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
        """Update preview images on UI thread"""
        if hasattr(self, 'lbl_before') and hasattr(self, 'lbl_after'):
            self.lbl_before.configure(image=p_before, text="")
            self.lbl_before.image = p_before
            self.lbl_after.configure(image=p_after, text="")
            self.lbl_after.image = p_after 

    def find_subtitle(self, video_path):
        """Find subtitle file for given video"""
        if not video_path:
            return None
        base = os.path.splitext(video_path)[0]
        for ext in [".srt", ".ass"]:
            if os.path.exists(base + ext):
                return base + ext
        return None

    def parse_srt_file(self, sub_path, timestamp):
        """Parse SRT file and return list of subtitle texts for given timestamp"""
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
        """Convert SRT timestamp format (HH:MM:SS,mmm) to seconds"""
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