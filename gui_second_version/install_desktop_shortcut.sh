#!/bin/bash
# Install FLASH-TV Setup Wizard desktop shortcut
# Run this script once during device setup in the lab

set -e

# Get current user
USER_NAME=$(whoami)
USER_HOME="/home/$USER_NAME"

# Paths
SCRIPTS_PATH="$USER_HOME/flash-tv-scripts"
GUI_PATH="$SCRIPTS_PATH/gui_second_version"
DESKTOP_PATH="$USER_HOME/Desktop"

# Find Python 3.10 virtual environment for GUI
# NOTE: The GUI requires Python 3.10+, separate from the py38 CV pipeline venv
#
# Update this path if your Python 3.10 venv has a different name:
GUI_VENV_NAME="py310"  # <-- CHANGE THIS if needed

if [ -d "$USER_HOME/$GUI_VENV_NAME/bin" ]; then
    PYTHON_PATH="$USER_HOME/$GUI_VENV_NAME/bin/python"
elif [ -d "$USER_HOME/gui_venv/bin" ]; then
    PYTHON_PATH="$USER_HOME/gui_venv/bin/python"
else
    echo "ERROR: Python 3.10 virtual environment not found!"
    echo "Expected: $USER_HOME/$GUI_VENV_NAME"
    echo ""
    echo "Please create the venv first or update GUI_VENV_NAME in this script."
    exit 1
fi

echo "Using Python: $PYTHON_PATH"
echo "Python version: $($PYTHON_PATH --version)"

# Create assets directory if needed
mkdir -p "$GUI_PATH/assets"

# Create a simple icon if none exists (placeholder)
ICON_PATH="$GUI_PATH/assets/flash_tv_icon.png"
if [ ! -f "$ICON_PATH" ]; then
    echo "Note: No icon file found. Using system default."
    ICON_PATH="utilities-system-monitor"
fi

# Create desktop file
DESKTOP_FILE="$DESKTOP_PATH/flash-tv-setup.desktop"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=FLASH-TV Setup
Comment=FLASH-TV System Setup Wizard
Exec=$PYTHON_PATH $GUI_PATH/main.py
Icon=$ICON_PATH
Terminal=false
Categories=Utility;System;
StartupNotify=true
EOF

# Make executable
chmod +x "$DESKTOP_FILE"

# Trust the desktop file (GNOME)
if command -v gio &> /dev/null; then
    gio set "$DESKTOP_FILE" metadata::trusted true 2>/dev/null || true
fi

# Also create in applications menu
APPLICATIONS_DIR="$USER_HOME/.local/share/applications"
mkdir -p "$APPLICATIONS_DIR"
cp "$DESKTOP_FILE" "$APPLICATIONS_DIR/"

echo "Desktop shortcut installed successfully!"
echo "Location: $DESKTOP_FILE"
echo ""
echo "You can now double-click 'FLASH-TV Setup' on the desktop to launch the wizard."
