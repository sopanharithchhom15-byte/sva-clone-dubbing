@echo off
chcp 65001 >nul
title SVA Clone Dubbing - Desktop Launcher
cd /d "%~dp0"

echo ========================================================
echo   🎬 កំពុងបើកកម្មវិធី SVA Clone Dubbing (Desktop App)...
echo ========================================================

python desktop_app.py
