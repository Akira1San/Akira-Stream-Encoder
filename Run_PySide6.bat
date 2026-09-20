@echo off
REM Video Encoder - PySide6 Launcher (Windows venv, launch-only)
REM Uses the venv in the program folder, no auto-install.

cd /d "%~dp0PySide6"

if not exist "%~dp0venv\Scripts\python.exe" (
    echo Error: venv not found at "%~dp0venv\Scripts\python.exe".
    echo Recreate it with: python -m venv venv
    pause
    exit /b 1
)

if not exist "main.py" (
    echo Error: main.py not found in "%CD%".
    pause
    exit /b 1
)

"%~dp0venv\Scripts\python.exe" main.py

if errorlevel 1 (
    echo.
    echo Error: Failed to start the application.
    pause
)
