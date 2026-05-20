"""
HandBrakeCLI wrapper for DVD subtitle burning
"""
import subprocess
import re
import os
import shutil
from typing import List, Dict, Optional, Callable


class HandBrakeHandler:

    ENCODER_MAP = {
        "h264_nvenc": "nvenc_h264",
        "hevc_nvenc": "nvenc_h265",
        "libx264": "x264",
        "libx265": "x265",
    }

    def __init__(self, handbrake_path: str = "HandBrakeCLI", log_callback: Callable = None):
        self.handbrake_path = handbrake_path
        self.log = log_callback or (lambda msg, level="INFO": None)

    @staticmethod
    def check_available(handbrake_path: str = "HandBrakeCLI") -> bool:
        path = shutil.which(handbrake_path)
        if not path:
            path = handbrake_path
            if not os.path.isfile(path):
                return False
        try:
            result = subprocess.run(
                [path, "--version"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def scan_titles(self, dvd_path: str) -> List[dict]:
        self.log(f"HandBrake: scanning titles in {dvd_path}", "INFO")
        cmd = [self.handbrake_path, "-i", dvd_path, "--scan"]
        try:
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=120
            )
            output = result.stderr
            titles = []
            title_pattern = re.compile(r'\+ title (\d+):')
            duration_pattern = re.compile(r'\+ duration:\s+(\d{2}):(\d{2}):(\d{2})')

            current_title = None
            for line in output.splitlines():
                title_match = title_pattern.search(line)
                if title_match:
                    current_title = {'title_number': int(title_match.group(1))}
                    titles.append(current_title)
                    continue

                if current_title is not None:
                    dur_match = duration_pattern.search(line)
                    if dur_match:
                        h, m, s = int(dur_match.group(1)), int(dur_match.group(2)), int(dur_match.group(3))
                        current_title['duration_seconds'] = h * 3600 + m * 60 + s

            self.log(f"HandBrake: found {len(titles)} title(s)", "INFO")
            return titles
        except Exception as e:
            self.log(f"HandBrake scan failed: {e}", "ERROR")
            return []

    def scan_subtitles(self, dvd_path: str, title_number: int) -> List[dict]:
        self.log(f"HandBrake: scanning subtitles for title {title_number}", "INFO")
        cmd = [self.handbrake_path, "-i", dvd_path, "-t", str(title_number), "--scan"]
        try:
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=120
            )
            output = result.stderr
            subtitles = []
            in_subtitle_section = False
            for line in output.splitlines():
                if '+ subtitle tracks' in line:
                    in_subtitle_section = True
                    continue
                if in_subtitle_section:
                    if line.strip().startswith('+ ') and 'subtitle' not in line and 'track' not in line and not re.match(r'^\s+\+ \d+', line):
                        in_subtitle_section = False
                        continue
                    match = re.match(r'^\s+\+ (\d+), (.+) \(track', line)
                    if match:
                        subtitles.append({
                            'track': int(match.group(1)),
                            'language': match.group(2).strip()
                        })
            self.log(f"HandBrake: found {len(subtitles)} subtitle track(s)", "INFO")
            return subtitles
        except Exception as e:
            self.log(f"HandBrake subtitle scan failed: {e}", "ERROR")
            return []

    def encode_with_subs(self, input_path: str, output_path: str,
                         title_number: int,
                         subtitle_track: Optional[int] = None,
                         burn: bool = True,
                         video_encoder: str = "x264",
                         quality: int = 23,
                         audio_track: int = 1,
                         framerate: str = "",
                         width: int = 0,
                         height: int = 0,
                         target_bitrate: str = "",
                         container: str = "mp4",
                         audio_mode: str = "encode") -> subprocess.Popen:
        cmd = [self.handbrake_path]
        cmd.extend(["-i", input_path])
        cmd.extend(["-t", str(title_number)])
        cmd.extend(["-o", output_path])

        if subtitle_track is not None and subtitle_track >= 0:
            hb_track = subtitle_track + 1
            cmd.extend(["--subtitle", str(hb_track)])
            if burn:
                cmd.extend(["--subtitle-burned"])

        encoder = self.ENCODER_MAP.get(video_encoder, "x264")
        cmd.extend(["-e", encoder])

        if target_bitrate:
            cmd.extend(["-b", target_bitrate])
        else:
            cmd.extend(["-q", str(quality)])

        if width > 0 and height > 0:
            cmd.extend(["--width", str(width), "--height", str(height)])
        if framerate:
            cmd.extend(["-r", framerate])

        cmd.extend(["-a", str(audio_track)])
        if audio_mode == "encode":
            cmd.extend(["-E", "aac"])
            cmd.extend(["-B", "128"])
        else:
            cmd.extend(["-E", "copy"])

        cmd.extend(["-f", container])

        self.log(f"HandBrake command: {' '.join(cmd)}", "INFO")

        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
