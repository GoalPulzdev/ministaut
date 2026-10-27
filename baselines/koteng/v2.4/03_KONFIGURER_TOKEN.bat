@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title RBK Kvinner - Konfigurer privat opplastingstoken
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sett_token_v24.ps1"
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%
