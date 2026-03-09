"""
Main Application Window - PySide6 Port
"""
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QTextEdit,
    QSplitter, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QFont, QIcon

from models import AppState
from config import SETTINGS_FILE
from config_tab import ConfigTab
from video_workspace import VideoWorkspace
from composition import CompositionTab
from tracks_tab import TracksTab


class LogWidget(QTextEdit):
    """Custom log display widget"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        # QTextDocument has maximumBlockCount, not QTextEdit
        self.document().setMaximumBlockCount(1000)
        self.setFont(QFont("Consolas", 9))
        
    def log(self, message: str, level: str = "INFO"):
        """Add a log entry with color coding"""
        colors = {
            "INFO": "#000000",
            "WARN": "#FF8C00",
            "ERROR": "#FF0000",
            "SUCCESS": "#008000"
        }
        color = colors.get(level, "#000000")
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        html = f'<span style="color: #666666;">[{timestamp}]</span> '
        html += f'<span style="color: {color};">{message}</span>'
        
        self.append(html)
        
        # Auto-scroll to bottom
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Video Encoder - PySide6")
        self.setMinimumSize(1200, 900)
        
        # Initialize application state
        self.app_state = AppState(self)
        self.app_state.log_message.connect(self.on_log_message)
        
        # Setup UI
        self.setup_ui()
        
        # Load settings
        self.load_settings()
        
    def setup_ui(self):
        """Setup the main UI layout"""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        # Main layout
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # === MAIN SECTION: Tab Widget ===
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Config Tab
        self.config_tab = ConfigTab(self.app_state)
        self.config_tab.file_selected.connect(self.on_file_selected)
        self.config_tab.dvd_imported.connect(self.on_dvd_imported)
        self.tab_widget.addTab(self.config_tab, "⚙️ Config")
        
        # Video Tab
        self.video_tab = VideoWorkspace(self.app_state)
        self.tab_widget.addTab(self.video_tab, "🎬 Video")
        
        # Tracks Tab
        self.tracks_tab = TracksTab(self.app_state)
        self.tab_widget.addTab(self.tracks_tab, "📊 Tracks")
        
        # Composition tab
        self.composition_tab = CompositionTab(self.app_state)
        self.tab_widget.addTab(self.composition_tab, "🎨 Composition")
        
        # === STATUS BAR ===
        self.statusBar().showMessage("Ready")
        
        # Log initial message
        self.log("Application started (PySide6)", "INFO")
        
    def on_log_message(self, message: str, level: str):
        """Handle log messages from app state"""
        # Forward log messages to video tab's log widget if it exists
        if hasattr(self, 'video_tab') and hasattr(self.video_tab, 'log_widget'):
            self.video_tab.log_widget.log(message, level)
        
        # Also update status bar for important messages
        if level in ("ERROR", "WARN"):
            self.statusBar().showMessage(message, 5000)
        
    def log(self, message: str, level: str = "INFO"):
        """Convenience method for logging"""
        self.app_state.log(message, level)
        
    def load_settings(self):
        """Load application settings from file"""
        try:
            if SETTINGS_FILE.exists():
                import json
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
                    
                # Apply settings
                if 'ffmpeg_path' in settings:
                    self.app_state.ffmpeg_path = settings['ffmpeg_path']
                if 'output_folder' in settings:
                    self.app_state.output_folder = settings['output_folder']
                    
                self.log("Settings loaded", "INFO")
        except Exception as e:
            self.log(f"Failed to load settings: {e}", "WARN")
            
    def save_settings(self):
        """Save application settings to file"""
        try:
            settings = {
                'ffmpeg_path': self.app_state.ffmpeg_path,
                'output_folder': self.app_state.output_folder,
            }
            
            import json
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=2)
                
            self.log("Settings saved", "INFO")
        except Exception as e:
            self.log(f"Failed to save settings: {e}", "ERROR")
            
    def on_file_selected(self, file_path: str):
        """Handle file selection from config tab"""
        # Switch to video tab
        self.tab_widget.setCurrentWidget(self.video_tab)
        # Load video in workspace
        self.video_tab.set_video(file_path)
        # Also load in tracks tab
        if hasattr(self, 'tracks_tab'):
            self.tracks_tab.load_video(file_path)
    
    def on_dvd_imported(self):
        """Handle DVD import - update subtitles panel with DVD subtitle tracks"""
        # Update the subtitles panel to show DVD subtitle selector
        self.video_tab.subs_panel.update_dvd_subtitles()
        
    def closeEvent(self, event):
        """Handle window close event"""
        self.save_settings()
        event.accept()


def main():
    """Application entry point"""
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    app.setApplicationName("VideoEncoder")
    app.setApplicationVersion("2.0.0")
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
