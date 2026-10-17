@echo off
chcp 65001 >nul
title SVA Clone Dubbing - AI Mobile & PC Studio
echo ======================================================================
echo   🎬 SVA Clone Dubbing (Web APP តាមទូរស័ព្ទ & កុំព្យូទ័រ)
echo   - AI Transcribe Video ទៅជាអក្សរ Subtitle ខ្មែរ (Gemini)
echo   - ក្លូនសំឡេង VoxCPM & Edge TTS (Piseth / Sreymom)
echo   - ផ្សំសំឡេង និង Render វីដេអូពេញលេញ (FFmpeg)
echo ======================================================================
echo.

cd /d "%~dp0"

echo 🚀 កំពុងបើកដំណើរការម៉ាស៊ីនបម្រើ (Starting Server)...
echo 📱 អាចប្រើទូរស័ព្ទដៃស្កេន QR Code ក្នុងកម្មវិធីដើម្បីបញ្ជាពីចម្ងាយបាន!
echo.

python server.py

pause
