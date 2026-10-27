@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title RBK Kvinner - Ministaut LIVE - hver time
if not exist ".venv\Scripts\python.exe" goto missing
.venv\Scripts\python.exe preflight_v24.py --require-token
if errorlevel 1 goto failed
.venv\Scripts\python.exe hourly_koteng.py --upload
if errorlevel 1 goto failed
echo.
echo Automatisk Koteng-kjoring er avsluttet.
pause
exit /b 0
:missing
echo Installer forst med 01_INSTALLER.bat.
pause
exit /b 2
:failed
echo STOPP: Forutsetning, skanning eller opplasting feilet.
pause
exit /b 2
