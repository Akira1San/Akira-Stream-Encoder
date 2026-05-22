#!/bin/bash
# Video Encoder - PySide6 Launcher

# Change to the PySide6 directory using absolute path
cd "/home/akira/akira/myencoder/MyEncoder/PySide6" || {
    echo "Error: Cannot find /home/akira/akira/myencoder/MyEncoder/PySide6"
    read -p "Press Enter to continue..."
    exit 1
}

# Activate virtual environment
source "/home/akira/akira/myencoder/MyEncoder/venv/bin/activate"

# Run the application
if command -v python3 &> /dev/null; then
    python3 main.py
elif command -v python &> /dev/null; then
    python main.py
else
    echo "Error: Python not found. Please install Python 3."
    read -p "Press Enter to continue..."
    exit 1
fi

if [ $? -ne 0 ]; then
    echo
    echo "Error: Failed to start the application."
    echo "Make sure Python and PySide6 are installed."
    read -p "Press Enter to continue..."
fi
