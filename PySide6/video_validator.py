"""
Video Validator - Health check and DTS issue detection (PySide6)
"""
import os
import subprocess
import re
from typing import Dict, Any

from models import AppState


class VideoValidator:
    """Basic video health check and DTS issue detection"""
    
    def __init__(self, ffmpeg_path: str, log_callback=None):
        self.ffmpeg_path = ffmpeg_path
        self.log = log_callback or (lambda msg, level="INFO": None)
        
    def quick_health_check(self, video_path: str) -> bool:
        """Quick basic health check"""
        cmd = [self.ffmpeg_path, "-v", "error", "-i", video_path, "-f", "null", "-"]
        try:
            result = subprocess.run(
                cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE,
                text=True, timeout=30
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            self.log(f"Health check timed out for {video_path}", "WARN")
            return False
        except Exception as e:
            self.log(f"Health check failed: {e}", "ERROR")
            return False
            
    def check_dts_issues(self, video_path: str) -> Dict[str, Any]:
        """Check for DTS/timestamp issues"""
        cmd = [self.ffmpeg_path, "-v", "error", "-i", video_path, "-f", "null", "-"]
        try:
            result = subprocess.run(
                cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE,
                text=True, timeout=30
            )
            
            issues = []
            stderr = result.stderr
            
            if "Non-monotonic DTS" in stderr:
                issues.append("DTS not monotonic")
            if "Application provided invalid" in stderr:
                issues.append("Invalid timestamps")
            if "packet lost" in stderr.lower():
                issues.append("Packet loss detected")
                
            return {
                'has_issues': len(issues) > 0,
                'issues': issues,
                'returncode': result.returncode,
                'stderr_preview': stderr[:500] if stderr else ""
            }
        except subprocess.TimeoutExpired:
            self.log(f"DTS check timed out for {video_path}", "WARN")
            return {'has_issues': True, 'issues': ['Check timed out'], 'returncode': -1}
        except Exception as e:
            self.log(f"DTS check failed: {e}", "ERROR")
            return {'has_issues': True, 'issues': [str(e)], 'returncode': -1}
            
    def analyze_frame_rate(self, video_path: str) -> Dict[str, Any]:
        """Check if video is VFR or CFR"""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "r_frame_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        
        try:
            result = subprocess.run(
                cmd, stderr=subprocess.PIPE, text=True, timeout=10
            )
            if result.returncode == 0 and result.stderr:
                match = re.search(r"(\d+(?:\.\d+)?)\s*fps", result.stderr)
                if match:
                    fps_str = match.group(1)
                    try:
                        fps = float(fps_str)
                        is_cfr = fps.is_integer() or (fps >= 23.0 and fps <= 30.0)
                        return {
                            'is_vfr': not is_cfr,
                            'fps': fps,
                            'fps_str': fps_str,
                            'is_problematic': fps < 15.0 or fps > 120.0
                        }
                    except ValueError:
                        pass
        except Exception as e:
            self.log(f"Frame rate analysis failed: {e}", "WARN")
        
        return {'fps': None, 'is_vfr': True, 'is_problematic': True}
        
    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """Get comprehensive video information"""
        import json
        
        cmd = [
            "ffprobe", "-v", "error",
            "-show_format", "-show_streams",
            "-of", "json",
            video_path
        ]
        
        try:
            result = subprocess.run(
                cmd, stderr=subprocess.PIPE, text=True, timeout=15
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
        except Exception as e:
            self.log(f"Video info retrieval failed: {e}", "ERROR")
            
        return {}
        
    def quick_audio_scan(self, video_path: str, scan_mode: str = 'fast') -> Dict[str, Any]:
        """Quick audio scan for issues"""
        result = {
            'filename': os.path.basename(video_path),
            'has_issues': False,
            'issues': {},
            'errors': []
        }
        
        # Check DTS issues
        dts_result = self.check_dts_issues(video_path)
        if dts_result['has_issues']:
            result['has_issues'] = True
            result['issues']['audio_dts'] = {
                'detected': True,
                'count': len(dts_result['issues']),
                'severity': 'high' if len(dts_result['issues']) > 2 else 'medium'
            }
            
        # Health check
        if not self.quick_health_check(video_path):
            result['has_issues'] = True
            result['issues']['health'] = {'detected': True}
            
        return result
