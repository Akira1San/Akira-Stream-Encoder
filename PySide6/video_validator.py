"""
Video Validator - Health check and DTS issue detection (PySide6)
"""
from typing import Dict, Any


class VideoValidator:
    """Basic video health check and DTS issue detection"""
    
    def __init__(self, backend, log_callback=None):
        self.backend = backend
        self.log = log_callback or (lambda msg, level="INFO": None)
        
    def quick_health_check(self, video_path: str) -> bool:
        """Quick basic health check via backend"""
        try:
            result = self.backend.validate(video_path)
            return result.get('is_valid', False)
        except Exception as e:
            self.log(f"Health check failed: {e}", "ERROR")
            return False
            
    def check_dts_issues(self, video_path: str) -> Dict[str, Any]:
        """Check for DTS/timestamp issues via backend"""
        try:
            result = self.backend.validate(video_path)
            issues = result.get('issues', [])
            return {
                'has_issues': len(issues) > 0,
                'issues': issues,
                'returncode': 0 if result.get('is_valid', False) else 1,
                'stderr_preview': result.get('stderr', '')
            }
        except Exception as e:
            self.log(f"DTS check failed: {e}", "ERROR")
            return {'has_issues': True, 'issues': [str(e)], 'returncode': -1}
            
    def analyze_frame_rate(self, video_path: str) -> Dict[str, Any]:
        """Check if video is VFR or CFR via backend"""
        try:
            info = self.backend.get_frame_rate(video_path)
            if info.get('fps') is not None:
                return {
                    'is_vfr': info.get('is_vfr', False),
                    'fps': info['fps'],
                    'fps_str': info.get('fps_str', str(info['fps'])),
                    'is_problematic': info.get('is_problematic', False)
                }
        except Exception as e:
            self.log(f"Frame rate analysis failed: {e}", "WARN")
        
        return {'fps': None, 'is_vfr': True, 'is_problematic': True}
        
    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """Get comprehensive video information via backend"""
        try:
            return self.backend.get_full_info(video_path)
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
