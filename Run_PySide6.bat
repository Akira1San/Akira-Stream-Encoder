@echo off
REM Video Encoder - PySide6 Launcher
REM Change to PySide6 directory and run the application

cd /d "%~dp0\PySide6"
python main.py

if errorlevel 1 (
    echo.
    echo Error: Failed to start the application.
    echo Make sure Python and PySide6 are installed.
    pause
)
