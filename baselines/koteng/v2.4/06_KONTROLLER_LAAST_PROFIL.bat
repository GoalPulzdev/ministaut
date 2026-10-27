@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title RBK Kvinner - Kontroller godkjent Koteng-profil
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe profile_lock.py
) else (
  py -3 profile_lock.py
)
pause
