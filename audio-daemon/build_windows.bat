@echo off
REM ============================================================
REM  Warehouse Audio Daemon - Windows Build Script
REM  Produces: dist\bodega-daemon.exe
REM ============================================================

echo.
echo Building Warehouse Audio Daemon for Windows...
echo.

REM Install / upgrade build tools
pip install --upgrade pyinstaller

REM Bundle into a single .exe; embed the sounds/ folder
pyinstaller ^
    --onefile ^
    --name "bodega-daemon" ^
    --add-data "sounds;sounds" ^
    --hidden-import pygame ^
    --hidden-import pygame.mixer ^
    --hidden-import websockets ^
    --hidden-import colorama ^
    --hidden-import dotenv ^
    daemon.py

echo.
if exist dist\bodega-daemon.exe (
    echo SUCCESS! Executable created: dist\bodega-daemon.exe
) else (
    echo BUILD FAILED - check output above for errors.
)
echo.
pause
