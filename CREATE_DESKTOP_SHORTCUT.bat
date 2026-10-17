@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================================
echo   🎬 SVA Clone Dubbing - បង្កើត Shortcut លើ Desktop
echo ========================================================

cscript //nologo make_shortcut.vbs

echo.
echo [OK] បានបង្កើត Shortcut "SVA Clone Dubbing" លើ Desktop របស់អ្នករួចរាល់!
echo លោកអ្នកអាចចុចពីរដង (Double-click) លើរូប Icon លើ Desktop ដើម្បីបើកកម្មវិធីបានភ្លាមៗ។
echo.
pause
