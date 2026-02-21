import os
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

    def check_audio_dts_detailed(self, video_path, scan_mode='fast'):
        """Detailed DTS analysis for audio streams"""
        cmd = [self.ffmpeg_path, "-v", "error", "-i", video_path, "-f", "null", "-"]
        
        try:
            timeout_val = 60 if scan_mode == 'thorough' else 30
            result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True, timeout=timeout_val)
            stderr = result.stderr
            
            dts_pattern = r"Non-monotonic DTS"
            dts_matches = re.findall(dts_pattern, stderr)
            
            dts_count = len(dts_matches)
            if dts_count == 0:
                severity = 'none'
            elif dts_count < 5:
                severity = 'mild'
            elif dts_count < 20:
                severity = 'moderate'
            else:
                severity = 'severe'
            
            return {
                'detected': dts_count > 0,
                'count': dts_count,
                'severity': severity,
                'stderr_preview': stderr[:500] if stderr else ""
            }
        
        except Exception as e:
            error_msg = str(e)
            error_type = 'dts_check_failed'
            
            if "TimeoutExpired" in error_msg or "timed out" in error_msg:
                error_type = 'dts_check_timeout'
            
            return {
                'detected': False,
                'error': error_msg,
                'error_type': error_type,
                'severity': 'N/A',
                'stderr_preview': ''
            }

    def check_audio_sync(self, video_path):
        """Detect audio sync issues using ffprobe"""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "packet=pts_time,dts_time",
            "-of", "csv=p=0",
            video_path
        ]
        
        try:
            result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, 
                                 text=True, timeout=30)
            
            if result.returncode == 0 and result.stdout:
                packets = result.stdout.strip().split('\n')[:100]
                
                offsets = []
                for packet in packets:
                    try:
                        pts, dts = packet.split(',')
                        offset = abs(float(pts) - float(dts))
                        offsets.append(offset)
                    except (ValueError, IndexError):
                        continue
                
                if offsets:
                    avg_offset = sum(offsets) / len(offsets)
                    if avg_offset > 0.05:
                        return {
                            'detected': True,
                            'offset_ms': int(avg_offset * 1000),
                            'severity': 'moderate' if avg_offset < 0.2 else 'severe'
                        }
            
            return {'detected': False}
        
        except Exception as e:
            error_msg = str(e)
            error_type = 'sync_check_failed'
            
            if "TimeoutExpired" in error_msg or "timed out" in error_msg:
                error_type = 'sync_check_timeout'
            
            return {
                'detected': False,
                'error': error_msg,
                'error_type': error_type,
                'offset_ms': 0,
                'severity': 'N/A'
            }

    def check_audio_codec_health(self, video_path):
        """Check audio codec compatibility and health"""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,sample_rate,channels,bit_rate",
            "-of", "json",
            video_path
        ]
        
        try:
            result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE,
                                 text=True, timeout=15)
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                streams = data.get('streams', [])
                
                if streams:
                    stream = streams[0]
                    codec = stream.get('codec_name', '')
                    sample_rate = int(stream.get('sample_rate', 0))
                    channels = stream.get('channels', 0)
                    
                    issues = []
                    
                    if codec.lower() in ['ac3', 'dts', 'eac3']:
                        issues.append('Surround codec may need conversion')
                    
                    if sample_rate not in [44100, 48000]:
                        issues.append(f'Non-standard sample rate: {sample_rate}Hz')
                    
                    if channels > 2:
                        issues.append(f'Multi-channel audio: {channels}ch')
                    
                    return {
                        'detected': len(issues) > 0,
                        'codec': codec,
                        'sample_rate': sample_rate,
                        'channels': channels,
                        'issues': issues
                    }
        
        except Exception as e:
            error_msg = str(e)
            error_type = 'codec_check_failed'
            
            if "TimeoutExpired" in error_msg or "timed out" in error_msg:
                error_type = 'codec_check_timeout'
            
            return {
                'detected': False,
                'error': error_msg,
                'error_type': error_type,
                'codec': 'unknown',
                'sample_rate': 0,
                'channels': 0,
                'issues': [],
                'severity': 'N/A'
            }
        
        return {'detected': False}

    def quick_audio_scan(self, video_path, scan_mode='fast'):
        """Fast/thorough audio health check (all-in-one)"""
        import datetime
        
        results = {
            'filename': os.path.basename(video_path),
            'file_path': video_path,
            'has_issues': False,
            'scan_mode': scan_mode,
            'issues': {
                'audio_dts': {},
                'audio_sync': {},
                'codec_health': {}
            },
            'can_fix': True,
            'scan_time': datetime.datetime.now().isoformat()
        }
        
        results['issues']['audio_dts'] = self.check_audio_dts_detailed(video_path, scan_mode)
        results['issues']['audio_sync'] = self.check_audio_sync(video_path)
        results['issues']['codec_health'] = self.check_audio_codec_health(video_path)
        
        for issue_type, issue_data in results['issues'].items():
            if 'error' in issue_data:
                results['has_issues'] = True
                results['can_fix'] = False
                
                if 'errors' not in results:
                    results['errors'] = []
                
                results['errors'].append({
                    'type': issue_type,
                    'error': issue_data.get('error', 'Unknown error'),
                    'error_type': issue_data.get('error_type', 'unknown')
                })
            elif issue_data.get('detected', False):
                results['has_issues'] = True
                results['can_fix'] = results['can_fix'] and issue_data.get('detected', True)
        
        return results
