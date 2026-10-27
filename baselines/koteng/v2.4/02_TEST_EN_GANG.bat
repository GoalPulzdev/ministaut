@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title RBK Kvinner - Kontrollskanning uten publisering
if not exist ".venv\Scripts\python.exe" goto missing
.venv\Scripts\python.exe preflight_v24.py
if errorlevel 1 goto failed
.venv\Scripts\python.exe hourly_koteng.py --once
if errorlevel 1 goto failed
echo.
echo Testen er ferdig. Ingen ny maaling ble publisert av denne testen.
pause
exit /b 0
:missing
echo Installering mangler. Kjor 01_INSTALLER.bat forst.
pause
exit /b 2
:failed
echo FEIL i test. Kontroller melding og diagnostikk-mappen. IKKE start LIVE enna.
pause
exit /b 2
