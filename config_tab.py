"""
Configuration Tab - Handles System Paths and Input File Management
"""
import datetime
import json
import os
import platform
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False
    DND_FILES = None

from video_validator import VideoValidator


class ConfigTab(ttk.Frame):
    """Handles System Paths and Input File Management"""

    def __init__(self, parent, app_vars, log_callback=None):
        """
        Initialize ConfigTab.
        log_callback can be None for testing purposes.
        """
        super().__init__(parent)
        
        # Constants
        ITEM_THRESHOLD = 8
        self.vars = app_vars
        self.log = log_callback
        self.ITEM_THRESHOLD = 8

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

        # --- Custom Output Filename ---
        ttk.Separator(output_frame, orient='horizontal').pack(fill='x', pady=8)

        ttk.Checkbutton(
            output_frame, 
            text="Custom Output Filename",
            variable=self.vars['use_custom_filename']
        ).pack(anchor='w')

        self.filename_entry = ttk.Entry(
            output_frame,
            textvariable=self.vars['custom_filename'],
            width=50,
            state='disabled'
        )
        self.filename_entry.pack(fill='x', pady=5)

        # Bind checkbox to enable/disable entry
        self.vars['use_custom_filename'].trace('w', self.on_custom_filename_toggle)
        
        # Bind split mode to disable custom filename
        self.vars['split_mode'].trace('w', self.on_split_mode_toggle)

        # --- Input Files (Moved from Video Tab) ---
        list_frame = ttk.LabelFrame(self, text="Input Files Queue", padding=10)
        list_frame.pack(fill="x", expand=False, padx=10, pady=5)

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
        ttk.Button(btn_frame, text="Clean Names", command=self.clean_filenames).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Join", command=self.join_files).pack(side="right", padx=5)

        ttk.Button(btn_frame, text="Validate Video", command=self.validate_video_file).pack(
            side="right", padx=5
        )
        
        self.files_listbox = tk.Listbox(list_frame, height=10)
        self.files_listbox.pack(fill="x", expand=False, pady=5)

        if HAS_DND:
            self.files_listbox.drop_target_register(DND_FILES)
            self.files_listbox.dnd_bind('<<Drop>>', self.on_drop)

        self.files_listbox.bind('<<ListboxSelect>>', self.on_listbox_select)

        # --- INFO DISPLAY LABEL ---
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

    def on_custom_filename_toggle(self, *args):
        """Enable/disable filename entry based on checkbox state"""
        if self.vars['use_custom_filename'].get():
            self.filename_entry.config(state='normal')
        else:
            self.filename_entry.config(state='disabled')
            self.vars['custom_filename'].set("")

    def on_split_mode_toggle(self, *args):
        """Disable custom filename when split mode is active"""
        if self.vars['split_mode'].get():
            # Disable custom filename in split mode
            self.vars['use_custom_filename'].set(False)
            self.filename_entry.config(state='disabled')
            self.vars['custom_filename'].set("")

    def browse_input(self):
        filenames = filedialog.askopenfilenames(
            title="Select Video",
            filetypes=[("Video", "*.mp4 *.mkv *.avi *.mov *.vob"), ("All", "*.*")],
        )
        if filenames:
            for f in filenames:
                if f not in self.vars["input_files"]:
                    self.vars["input_files"].append(f)
                    self.files_listbox.insert(tk.END, os.path.basename(f))

    def clear_file_list(self):
        self.vars["input_files"].clear()
        self.files_listbox.delete(0, tk.END)

    def on_listbox_select(self, event):
        """Ensure the selected item is visible in the listbox."""
        selection = self.files_listbox.curselection()
        if selection:
            self.files_listbox.see(selection[0])

    def on_drop(self, event):
        files = event.data
        if isinstance(files, str):
            files = files.split()
        
        for f in files:
            f = f.strip('{}')
            if os.path.exists(f) and f not in self.vars["input_files"]:
                self.vars["input_files"].append(f)
                self.files_listbox.insert(tk.END, os.path.basename(f))
                self.log(f"Added file: {os.path.basename(f)}")

    def show_file_details(self):
        """Triggers info popup for selected file in main app"""
        selection = self.files_listbox.curselection()
        if selection:
            index = selection[0]
            if 0 <= index < len(self.vars['input_files']):
                filepath = self.vars['input_files'][index]
                self.detect_and_show_info(filepath)
            else:
                messagebox.showinfo("Info", "Select a valid file index.")
        else:
            messagebox.showwarning("Info", "Select a file first from list.")

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
            
            # Show in Label AND Log
            self.info_label.config(text=display_msg)
            self.log(f"File Info: {display_msg}")
            
        except Exception as e:
            err_msg = f"Failed to get info: {e}"
            self.info_label.config(text=err_msg)
            self.log(err_msg)

    def validate_video_file(self):
        """Validate selected video file for health and DTS issues"""
        selection = self.files_listbox.curselection()
        if not selection:
            messagebox.showwarning("Validation", "Please select a file first.")
            return
        
        index = selection[0]
        if 0 <= index < len(self.vars['input_files']):
            filepath = self.vars['input_files'][index]
            self.run_validation(filepath)
        else:
            messagebox.showwarning("Validation", "Select a valid file index.")

    def run_validation(self, filepath):
        """Run video validation and show results"""
        validator = VideoValidator(getattr(self.vars, 'ffmpeg_path').get(), self.log)
        
        # Quick health check
        if not validator.quick_health_check(filepath):
            self.log("Quick health check failed")
            messagebox.showwarning("Video Validation", "❌ Quick health check failed. File may be corrupted.")
            return
        
        # DTS check
        dts_result = validator.check_dts_issues(filepath)
        
        # Frame rate analysis
        fps_info = validator.analyze_frame_rate(filepath)
        
        # Build results message
        issues = []
        warnings = []
        
        if dts_result['has_issues']:
            warnings.extend(dts_result['issues'])
        
        if fps_info.get('is_vfr', True):
            warnings.append(f"Variable frame rate: {fps_info.get('fps_str', 'unknown')}")
        
        if fps_info.get('is_problematic', True):
            warnings.append(f"Unusual frame rate: {fps_info.get('fps_str', 'unknown')}")
        
        # Show results
        if not issues and not warnings:
            result = messagebox.showinfo("Video Validation", "✅ Video appears healthy\n\nNo DTS or frame rate issues detected.")
        elif not warnings:
            result = messagebox.showinfo("Video Validation", f"⚠️ Warnings found:\n\n" + "\n".join(dts_result.get('issues', [])))
        elif not issues:
            result = messagebox.showinfo("Video Validation", f"⚠️ Minor issues found:\n\n" + "\n".join(warnings))
        else:
            result = messagebox.showwarning("Video Validation", f"❌ Issues found:\n\n" + "\n".join(dts_result['issues']) + "\n\nRecommendation: Consider re-encoding problematic files")
        
        self.log(f"Validation completed for {os.path.basename(filepath)}")
    def join_files(self):
        """Join queued input files into a single video if identical codecs/params."""
        import tempfile
        import os
        import threading
        from tkinter import messagebox, filedialog
        import subprocess

        files = [f for f in self.vars.get("input_files", []) if os.path.exists(f)]
        if len(files) < 2:
            messagebox.showinfo("Join", "Need at least 2 input files to join.")
            return
        if not self._files_identical(files):
            messagebox.showinfo("Join", "Files cannot be joined without re-encoding. Please re-encode to a common format first.")
            return

        with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt') as tf:
            list_path = tf.name
            for p in files:
                safe = p.replace("'", "'""'""'")
                tf.write("file '{}'\n".format(safe))

        first_ext = os.path.splitext(files[0])[1] or ".mp4"
        default_name = os.path.splitext(os.path.basename(files[0]))[0] + "_joined" + first_ext
        out_path = filedialog.asksaveasfilename(defaultextension=first_ext, initialfile=default_name, title="Save joined video as", filetypes=[("Video", "*"+first_ext), ("All", "*.*")])
        if not out_path:
            try:
                os.remove(list_path)
            except Exception:
                pass
            return

        ffmpeg_path_var = self.vars.get("ffmpeg_path")
        ffmpeg_path = ffmpeg_path_var.get() if isinstance(ffmpeg_path_var, tk.StringVar) else "ffmpeg"
        cmd = [ffmpeg_path, "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", out_path]

        def do_join():
            try:
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
                ok = res.returncode == 0
                err = res.stderr
            except Exception as e:
                ok = False
                err = str(e)

            def finish():
                try:
                    os.remove(list_path)
                except Exception:
                    pass
                if ok:
                    messagebox.showinfo("Join", f"Joined file created: {out_path}")
                else:
                    messagebox.showerror("Join", f"Failed to join files: {err}")

            self.after(0, finish)

        t = threading.Thread(target=do_join, daemon=True)
        t.start()

    def _files_identical(self, paths):
        """Return True if all inputs have identical video/audio params."""
        base = self._get_media_params(paths[0])
        for p in paths[1:]:
            if self._get_media_params(p) != base:
                return False
        return True

    def _get_media_params(self, path):
        """Return a simple dict of media params using ffprobe."""
        params = {}
        try:
            cmd_v = ["ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=codec_name,width,height,avg_frame_rate",
                     "-of", "default=noprint_wrappers=1:nokey=1", path]
            res = subprocess.run(cmd_v, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            lines = res.stdout.strip().splitlines()
            if len(lines) >= 4:
                params["vcodec"] = lines[0]
                params["width"] = lines[1]
                params["height"] = lines[2]
                params["fps"] = lines[3]
        except Exception:
            pass
        try:
            cmd_a = ["ffprobe", "-v", "error", "-select_streams", "a:0",
                     "-show_entries", "stream=codec_name",
                     "-of", "default=noprint_wrappers=1:nokey=1", path]
            res = subprocess.run(cmd_a, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            a = res.stdout.strip()
            if a:
                params["acodec"] = a
        except Exception:
            pass
        return params

    def clean_filenames(self):
        """Clean filenames in the Input Files Queue."""
        import os
        import re
        from tkinter import messagebox, Toplevel, Label, Button, Frame, Scrollbar, Listbox

        files = [f for f in self.vars.get("input_files", []) if os.path.exists(f)]
        if not files:
            messagebox.showinfo("Clean Names", "No files to clean.")
            return

        # Generate cleaned filenames
        cleaned = []
        for f in files:
            base = os.path.basename(f)
            cleaned_base = self._clean_filename(base)
            cleaned.append((f, cleaned_base))

        # Show preview dialog
        preview = Toplevel(self)
        preview.title("Clean Filenames - Preview")
        preview.geometry("600x400")

        Label(preview, text="Before -> After", font=("Arial", 10, "bold")).pack(pady=5)

        frame = Frame(preview)
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        listbox = Listbox(frame, height=15, width=80)
        scroll = Scrollbar(frame, orient="vertical", command=listbox.yview)
        listbox.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        listbox.pack(side="left", fill="both", expand=True)

        for orig, new in cleaned:
            listbox.insert("end", f"{orig} -> {new}")

        def apply_changes():
            errors = []
            for orig_path, new_base in cleaned:
                dirname = os.path.dirname(orig_path)
                new_path = os.path.join(dirname, new_base)
                if os.path.exists(new_path):
                    errors.append(f"Destination exists: {new_base}")
                    continue
                try:
                    os.rename(orig_path, new_path)
                except Exception as e:
                    errors.append(f"Failed to rename {orig_path}: {e}")
                    break

            if errors:
                messagebox.showerror("Clean Names", "\n".join(errors))
                preview.destroy()
                return

            # Update queue
            self.vars["input_files"] = [os.path.join(os.path.dirname(f), self._clean_filename(os.path.basename(f))) for f in files]
            self.files_listbox.delete(0, "end")
            for f in self.vars["input_files"]:
                self.files_listbox.insert("end", os.path.basename(f))

            messagebox.showinfo("Clean Names", "Filenames cleaned successfully.")
            preview.destroy()

        def cancel():
            preview.destroy()

        btn_frame = Frame(preview)
        btn_frame.pack(fill="x", pady=10)
        Button(btn_frame, text="Apply", command=apply_changes).pack(side="right", padx=5)
        Button(btn_frame, text="Cancel", command=cancel).pack(side="right", padx=5)

    def _clean_filename(self, filename):
        """Clean a filename by removing clutter and normalizing spaces."""
        import re
        base, ext = os.path.splitext(filename)
        # Preserve year (4 digits)
        year_match = re.search(r'\b(19|20)\d{2}\b', base)
        year = year_match.group(0) if year_match else None

        # Remove all dots (except the one before the file extension)
        base = base.replace('.', ' ')
        # Remove all underscores
        base = base.replace('_', ' ')
        # Remove all special characters (e.g., &, -, _)
        base = re.sub(r'[\-_&]', ' ', base)
        # Normalize spaces
        base = re.sub(r'\s+', ' ', base).strip()

        # Remove common clutter patterns
        patterns = [
            r'\bBDRip\b', r'\bx265\b', r'\bx264\b', r'\bAC3\b', r'\bAAC\b',
            r'\bbgaudio\b', r'\bDUAL\b', r'\bAUDiO\b', r'\bBluRay\b', r'\bDVDRip\b',
            r'\bH\b', r'\b265\b', r'\bWAR\b', r'\bSiSO\b', r'\bfmp4\b', r'\btv\b',
            r'\bgpu\b', r'\bpart01\b', r'\bjoined\b', r'\bencoded\b', r'\bmucker\b',
            r'\bAtany\b', r'\bStezarai\b', r'\bBG\b', r'\bAudio\b', r'\bBGAUDiO\b',
            r'\b10\b', r'\bbit\b', r'\b1080p\b', r'\b720x404\b',
            r'\b576p\b', r'\bWEBRip\b', r'\bHUD\b', r'\bAtany Stezarai\b', r'\bVHS\b',
            r'\b720p\b', r'\bBluRay\b', r'\bAC3\b', r'\bAVS\b', r'\bDD5\.1\b'
        ]
        for pat in patterns:
            base = re.sub(pat, '', base, flags=re.IGNORECASE)

        # Reinsert year if found
        if year:
            base = re.sub(r'\b(19|20)\d{2}\b', year, base)

        # Remove any remaining numbers that are not part of the year
        base = re.sub(r'\b\d{1,3}\b', '', base)

        # Remove any remaining words that are not part of the title
        base = re.sub(r'\b\w{1,2}\b', '', base)

        # Remove any remaining extra spaces
        base = re.sub(r'\s+', ' ', base).strip()

        return f"{base}{ext}"