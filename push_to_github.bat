@echo off
title Push to GitHub Repository
cd /d "%~dp0"

echo ========================================================
echo         Publish TikTok Auto-Reposter to GitHub
echo ========================================================
echo.
echo If you have not created a GitHub repo yet:
echo 1. Go to https://github.com/new
echo 2. Give it a name (e.g. tiktok-auto-reposter)
echo 3. Keep it Public or Private, and leave "Initialize with README" UNCHECKED
echo 4. Click "Create repository"
echo.
set /p REPO_URL="Enter your GitHub Repository URL (e.g. https://github.com/YourName/tiktok-auto-reposter.git): "

if "%REPO_URL%"=="" (
    echo [!] No URL provided. Aborting.
    pause
    exit /b 1
)

echo.
echo [*] Adding remote origin...
git remote remove origin >nul 2>&1
git remote add origin %REPO_URL%

echo [*] Renaming branch to main...
git branch -M main

echo [*] Pushing to GitHub...
git push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo [OK] Successfully published to GitHub!
    echo ========================================================
) else (
    echo.
    echo [!] Push failed. Please check your URL and GitHub permissions.
)

echo.
pause
