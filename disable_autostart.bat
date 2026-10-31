@echo off
title Disable Auto-Start on Windows Boot
cd /d "%~dp0"

echo ========================================================
echo   Disabling TikTok Auto-Reposter Windows Auto-Start
echo ========================================================
echo.

python -c "import os, win32com.client; s = win32com.client.Dispatch('WScript.Shell'); p = os.path.join(s.SpecialFolders('Startup'), 'TikTok-Auto-Reposter.lnk'); os.remove(p) if os.path.exists(p) else None; print('[OK] Removed shortcut from Startup.')"

echo.
echo [OK] Auto-start is now DISABLED.
echo.
pause
