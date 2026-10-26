@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Koteng Arena - timevis privat Supabase-lagring
if exist .venv\Scripts\python.exe (
 .venv\Scripts\python.exe hourly_koteng.py --upload
) else (
 py -3 hourly_koteng.py --upload
)
pause
