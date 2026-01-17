import subprocess
import re


class VideoValidator:
    """Basic video health check and DTS issue detection"""
    
    def __init__(self, ffmpeg_path, log_callback):
        self.ffmpeg_path = ffmpeg_path
        self.log = log_callback
    
    def quick_health_check(self, video_path):
        """Quick basic health check"""
        cmd = [self.ffmpeg_path, "-v", "error", "-i", video_path, "-f", "null", "-"]
        try:
            result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, timeout=30)
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            self.log(f"Health check timed out for {video_path}")
            return False
        except Exception as e:
            self.log(f"Health check failed: {e}")
            return False
    
    def check_dts_issues(self, video_path):
        """Check for DTS/timestamp issues"""
        cmd = [self.ffmpeg_path, "-v", "error", "-i", video_path, "-f", "null", "-"]
        try:
            result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, timeout=30)
            
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
            self.log(f"DTS check timed out for {video_path}")
            return {'has_issues': True, 'issues': ['Check timed out'], 'returncode': -1}
        except Exception as e:
            self.log(f"DTS check failed: {e}")
            return {'has_issues': True, 'issues': [str(e)], 'returncode': -1}
    
    def analyze_frame_rate(self, video_path):
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
            result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True, timeout=10)
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
            self.log(f"Frame rate analysis failed: {e}")
        
        return {'fps': None, 'is_vfr': True, 'is_problematic': True}
    
    def get_video_info(self, video_path):
        """Get comprehensive video information"""
        import json
        
        cmd = [
            "ffprobe", "-v", "error",
            "-show_format", "-show_streams",
            "-of", "json",
            video_path
        ]
        
        try:
            result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True, timeout=15)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                format_info = data.get('format', {})
                streams = data.get('streams', [])
                
                video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
                
                if video_stream:
                    duration = float(format_info.get('duration', 0))
                    return {
                        'duration': duration,
                        'size': f"{video_stream.get('width', 0)}x{video_stream.get('height', 0)}",
                        'bitrate': int(format_info.get('bit_rate', 0) // 1000) if format_info.get('bit_rate') else 0,
                        'fps': video_stream.get('r_frame_rate', 'unknown'),
                        'codec': video_stream.get('codec_name', 'unknown'),
                        'format': format_info.get('format_name', 'unknown')
                    }
        except Exception as e:
            self.log(f"Video analysis failed: {e}")
        
        return {}
