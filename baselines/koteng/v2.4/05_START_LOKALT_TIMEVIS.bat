@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title RBK Kvinner - Lokal timevis kontroll UTEN publisering
if not exist ".venv\Scripts\python.exe" goto missing
.venv\Scripts\python.exe preflight_v24.py
if errorlevel 1 goto failed
.venv\Scripts\python.exe hourly_koteng.py
if errorlevel 1 goto failed
pause
exit /b 0
:missing
echo Installer forst med 01_INSTALLER.bat.
pause
exit /b 2
:failed
echo Skanning stoppet. Kontroller feilmeldingen.
pause
exit /b 2
