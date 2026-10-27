@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Koteng Arena - Kontroller laast profil
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe profile_lock.py
) else (
  py -3 profile_lock.py
)
pause
