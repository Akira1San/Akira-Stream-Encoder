"""
HandBrakeCLI wrapper for DVD subtitle burning
"""
import subprocess
import re
import os
import shutil
from datetime import datetime
from typing import List, Dict, Optional, Callable

from backends.ffmpeg_escaping import format_command_for_log


# ISO 639-1 (2-letter) to ISO 639-2 (3-letter) language code mapping
# This is needed because the app's IFO parsing gives 2-letter codes
# while HandBrake JSON output gives 3-letter codes
ISO639_1_TO_639_2 = {
    "aa": "aar", "ab": "abk", "ae": "ave", "af": "afr", "ak": "aka",
    "am": "amh", "an": "arg", "ar": "ara", "as": "asm", "av": "ava",
    "ay": "aym", "az": "aze", "ba": "bak", "be": "bel", "bg": "bul",
    "bh": "bih", "bi": "bis", "bm": "bam", "bn": "ben", "bo": "bod",
    "br": "bre", "bs": "bos", "ca": "cat", "ce": "che", "ch": "cha",
    "co": "cos", "cr": "cre", "cs": "ces", "cu": "chu", "cv": "chv",
    "cy": "cym", "da": "dan", "de": "deu", "dv": "div", "dz": "dzo",
    "ee": "ewe", "el": "ell", "en": "eng", "eo": "epo", "es": "spa",
    "et": "est", "eu": "eus", "fa": "fas", "ff": "ful", "fi": "fin",
    "fj": "fij", "fo": "fao", "fr": "fra", "fy": "fry", "ga": "gle",
    "gd": "gla", "gl": "glg", "gn": "grn", "gu": "guj", "gv": "glv",
    "ha": "hau", "he": "heb", "hi": "hin", "ho": "hmo", "hr": "hrv",
    "ht": "hat", "hu": "hun", "hy": "hye", "hz": "her", "ia": "ina",
    "id": "ind", "ie": "ile", "ig": "ibo", "ii": "iii", "ik": "ipk",
    "in": "ind", "is": "isl", "it": "ita", "iu": "iku", "ja": "jpn",
    "jv": "jav", "ka": "kat", "kg": "kon", "ki": "kik", "kj": "kua",
    "kk": "kaz", "kl": "kal", "km": "khm", "kn": "kan", "ko": "kor",
    "kr": "kau", "ks": "kas", "ku": "kur", "kv": "kom", "kw": "cor",
    "ky": "kir", "la": "lat", "lb": "ltz", "lg": "lug", "li": "lim",
    "ln": "lin", "lo": "lao", "lt": "lit", "lu": "lub", "lv": "lav",
    "mg": "mlg", "mh": "mah", "mi": "mri", "mk": "mkd", "ml": "mal",
    "mn": "mon", "mr": "mar", "ms": "msa", "mt": "mlt", "my": "mya",
    "na": "nau", "nb": "nob", "nd": "nde", "ne": "nep", "ng": "ndo",
    "nl": "nld", "nn": "nno", "no": "nor", "nr": "nbl", "nv": "nav",
    "ny": "nya", "oc": "oci", "oj": "oji", "om": "orm", "or": "ori",
    "os": "oss", "pa": "pan", "pi": "pli", "pl": "pol", "ps": "pus",
    "pt": "por", "qu": "que", "rm": "roh", "rn": "run", "ro": "ron",
    "ru": "rus", "rw": "kin", "sa": "san", "sc": "srd", "sd": "snd",
    "se": "sme", "sg": "sag", "sh": "hbs", "si": "sin", "sk": "slk",
    "sl": "slv", "sm": "smo", "sn": "sna", "so": "som", "sq": "sqi",
    "sr": "srp", "ss": "ssw", "st": "sot", "su": "sun", "sv": "swe",
    "sw": "swa", "ta": "tam", "te": "tel", "tg": "tgk", "th": "tha",
    "ti": "tir", "tk": "tuk", "tl": "tgl", "tn": "tsn", "to": "ton",
    "tr": "tur", "ts": "tso", "tt": "tat", "tw": "twi", "ty": "tah",
    "ug": "uig", "uk": "ukr", "ur": "urd", "uz": "uzb", "ve": "ven",
    "vi": "vie", "vo": "vol", "wa": "wln", "wo": "wol", "xh": "xho",
    "yi": "yid", "yo": "yor", "za": "zha", "zh": "zho", "zu": "zul",
}


class HandBrakeHandler:

    ENCODER_MAP = {
        "h264_nvenc": "nvenc_h264",
        "hevc_nvenc": "nvenc_h265",
        "libx264": "x264",
        "libx265": "x265",
        "mpeg2video": "mpeg2",
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
        import json
        cmd = [self.handbrake_path, "-i", dvd_path, "-t", str(title_number), "--scan", "--json"]
        try:
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=120
            )
            output = result.stdout
            # Extract JSON after "JSON Title Set:" header (json may be mixed with version info)
            json_start = output.find("JSON Title Set:")
            if json_start >= 0:
                output = output[json_start + len("JSON Title Set:"):]
            data = json.loads(output)
            subtitles = []
            for title in data.get('TitleList', []):
                for sub in title.get('SubtitleList', []):
                    subtitles.append({
                        'track': sub['TrackNumber'],
                        'language_code': sub.get('LanguageCode', ''),
                        'language': sub.get('Language', ''),
                    })
            self.log(f"HandBrake: found {len(subtitles)} subtitle track(s) via JSON", "INFO")
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
                         audio_mode: str = "encode",
                         start_time: Optional[str] = None,
                         duration: Optional[str] = None) -> subprocess.Popen:
        cmd = [self.handbrake_path]
        cmd.extend(["-i", input_path])
        cmd.extend(["-t", str(title_number)])
        cmd.extend(["-o", output_path])

        if subtitle_track is not None and subtitle_track >= 0:
            cmd.extend(["--subtitle", str(subtitle_track)])
            if burn:
                cmd.extend(["--subtitle-burned"])

        if start_time:
            cmd.extend(["--start-at", f"duration:{start_time}"])
        if duration:
            cmd.extend(["--stop-at", f"duration:{duration}"])

        encoder = self.ENCODER_MAP.get(video_encoder, "x264")
        cmd.extend(["-e", encoder])

        if target_bitrate:
            cmd.extend(["-b", target_bitrate])
        else:
            cmd.extend(["-q", str(quality)])

        if width > 0 and height > 0:
            cmd.extend(["--width", str(width), "--height", str(height)])
        if framerate:
            hb_framerate = framerate
            if '/' in framerate:
                try:
                    num, den = framerate.split('/')
                    hb_framerate = f"{float(num) / float(den):.3f}"
                except (ValueError, ZeroDivisionError):
                    pass
            cmd.extend(["-r", hb_framerate])

        cmd.extend(["-a", str(audio_track)])
        if audio_mode == "encode":
            cmd.extend(["-E", "aac"])
            cmd.extend(["-B", "128"])
        else:
            cmd.extend(["-E", "copy"])

        cmd.extend(["-f", container])

        self.log(f"HandBrake command: {format_command_for_log(cmd)}", "INFO")

        log_path = output_path + ".log"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a") as f:
            f.write(f"[{timestamp}] Command: {format_command_for_log(cmd)}\n")

        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
