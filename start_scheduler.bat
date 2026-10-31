@echo off
title TikTok Chronological Queue Scheduler
cd /d "%~dp0"
echo ========================================================
echo   TikTok Auto-Reposter: Starting Queue Daemon
echo ========================================================
echo.
timeout /t 5 /nobreak >nul 2>&1
python scheduler.py
pause
