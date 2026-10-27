@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title RBK Kvinner - Koteng 2.4 - Forstegangsinstallasjon
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer_v24.ps1"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo INSTALLASJON BLE IKKE FULLFORT - SE FEILMELDINGENE OVER.
if "%RC%"=="0" echo INSTALLASJON FERDIG. Neste steg: 02_TEST_EN_GANG.bat
pause
exit /b %RC%
