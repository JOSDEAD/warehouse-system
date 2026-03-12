#!/bin/bash
# ============================================================
#  Warehouse Audio Daemon - macOS Build Script
#  Produces: dist/bodega-daemon
# ============================================================

set -e

echo ""
echo "Building Warehouse Audio Daemon for macOS..."
echo ""

# Install / upgrade build tools
pip install --upgrade pyinstaller

# Bundle into a single binary; embed the sounds/ folder
pyinstaller \
    --onefile \
    --name "bodega-daemon" \
    --add-data "sounds:sounds" \
    --hidden-import pygame \
    --hidden-import pygame.mixer \
    --hidden-import websockets \
    --hidden-import colorama \
    --hidden-import dotenv \
    daemon.py

echo ""
if [ -f "dist/bodega-daemon" ]; then
    echo "SUCCESS! Executable created: dist/bodega-daemon"
    chmod +x dist/bodega-daemon
else
    echo "BUILD FAILED - check output above for errors."
    exit 1
fi
echo ""
