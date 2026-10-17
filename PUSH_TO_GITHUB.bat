@echo off
chcp 65001 >nul
title Push to GitHub for Cloud Hosting Deployment
set PATH=%~dp0bin\git\cmd;%PATH%

echo ======================================================================
echo   🚀 SVA CLONE DUBBING - PUSH TO GITHUB
echo ======================================================================
echo.
echo ដោយសារ GitHub មិនអនុញ្ញាតឱ្យប្រើ Password ធម្មតាទេ 
echo GitHub តម្រូវឱ្យប្រើ Personal Access Token (PAT)។
echo.
echo 💡 ប្រសិនបើមិនទាន់មាន Token ទេ សូមបើក Link នេះដើម្បីយក (៣០ វិនាទី)៖
echo 👉 https://github.com/settings/tokens/new
echo (គ្រាន់តែគ្រីសធិកលើ 'repo' រួចចុច Generate Token យកលេខកូដមក Paste)
echo.
echo ======================================================================
set /p GH_TOKEN="សូមបិទភ្ជាប់ (Paste) GitHub Token របស់អ្នកនៅទីនេះ: "

if "%GH_TOKEN%"=="" (
    echo [!] អ្នកមិនបានបញ្ចូល Token ឡើយ!
    pause
    exit /b
)

echo.
echo [1/3] កំពុងរៀបចំ Git...
git init >nul 2>nul
git config user.name "Panharith"
git config user.email "panharith@example.com"
git branch -M main

echo [2/3] កំពុងបន្ថែម និង Commit ឯកសារ...
git add .
git commit -m "Deploy SVA Clone Dubbing to Cloud Hosting" >nul 2>nul

echo [3/3] កំពុង Push ឡើងទៅ GitHub...
git push https://%GH_TOKEN%@github.com/sopanharithchhom15-byte/sva-clone-dubbing.git main --force

if %errorlevel% equ 0 (
    echo.
    echo ======================================================================
    echo ✅ ជោគជ័យ ១០០%! កូដទាំងអស់បានឡើងទៅកាន់ GitHub រួចរាល់ហើយ!
    echo.
    echo ជំហានបន្ទាប់៖ ចូលទៅ Render.com ដើម្បីយក Link អចិន្ត្រៃយ៍៖
    echo 1. បើក: https://dashboard.render.com
    echo 2. ចុច "+ New" -> "Web Service"
    echo 3. ជ្រើសរើស "sva-clone-dubbing" រួចចុច "Deploy"
    echo ======================================================================
) else (
    echo.
    echo ❌ បរាជ័យក្នុងការ Push! សូមពិនិត្យមើល Token ថាតើត្រឹមត្រូវ និងបាន Tick លើ 'repo' ដែរឬទេ។
)
echo.
pause
