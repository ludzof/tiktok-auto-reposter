@echo off
title Enable Auto-Start on Windows Boot
cd /d "%~dp0"

echo ========================================================
echo   Enabling TikTok Auto-Reposter Windows Auto-Start
echo ========================================================
echo.

python -c "import os, win32com.client; s = win32com.client.Dispatch('WScript.Shell'); p = os.path.join(s.SpecialFolders('Startup'), 'TikTok-Auto-Reposter.lnk'); sc = s.CreateShortCut(p); sc.TargetPath = os.path.abspath('start_scheduler.bat'); sc.WorkingDirectory = os.path.abspath('.'); sc.WindowStyle = 7; sc.Description = 'TikTok Auto Reposter'; sc.Save(); print('[OK] Shortcut enabled at:', p)"

echo.
echo [OK] Auto-start is ENABLED!
echo Every time you turn on your PC and log in, the reposter will start minimized in your taskbar.
echo.
pause
