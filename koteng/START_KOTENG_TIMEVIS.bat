@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Koteng Arena - timevis lokal kontroll
if exist .venv\Scripts\python.exe (
 .venv\Scripts\python.exe hourly_koteng.py
) else (
 py -3 hourly_koteng.py
)
pause
