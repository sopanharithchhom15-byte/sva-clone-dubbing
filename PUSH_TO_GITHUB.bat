@echo off
chcp 65001 >nul
title Push to GitHub for Cloud Hosting Deployment
echo ======================================================================
echo   🚀 SVA CLONE DUBBING - PUSH TO GITHUB (RENDER / RAILWAY)
echo ======================================================================
echo.

where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] Git មិនទាន់ត្រូវបានស្គាល់ក្នុង Command Prompt នៅឡើយទេ។
    echo [!] សូម Restart Terminal ឬបើក Git Bash ដើម្បីដំណើរការ។
    pause
    exit /b
)

echo [1/4] កំពុងរៀបចំ Git Repository...
if not exist ".git" (
    git init
)

echo [2/4] កំពុងបន្ថែមឯកសារ (Stage files)...
git add .

echo [3/4] កំពុង Commit...
git commit -m "Deploy SVA Clone Dubbing to Cloud Hosting"

echo.
echo ======================================================================
echo សូមបញ្ចូល Link GitHub Repository របស់អ្នក (ឧទាហរណ៍៖ https://github.com/username/sva-clone-dubbing.git)
echo ======================================================================
set /p REPO_URL="Link GitHub: "

if "%REPO_URL%"=="" (
    echo [!] អ្នកមិនបានបញ្ចូល Link GitHub ឡើយ!
    pause
    exit /b
)

echo [4/4] កំពុង Push ឡើងទៅ GitHub...
git branch -M main
git remote remove origin >nul 2>nul
git remote add origin %REPO_URL%
git push -u origin main

echo.
echo ======================================================================
echo ✅ ជោគជ័យ! កូដត្រូវបាន Push ឡើងទៅ GitHub រួចរាល់ហើយ!
echo ឥឡូវនេះអ្នកអាចចូលទៅកាន់ Render.com ឬ Railway.app ដើម្បី Deploy បានភ្លាមៗ។
echo ======================================================================
pause
