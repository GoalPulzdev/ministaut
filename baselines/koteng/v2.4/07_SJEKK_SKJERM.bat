@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title RBK Kvinner - Koteng V2.4 - skjermkontroll
if not exist ".venv\Scripts\python.exe" goto missing
.venv\Scripts\python.exe sjekk_skjerm_v24.py
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%
:missing
echo Kjoer 01_INSTALLER.bat forst.
pause
exit /b 2
