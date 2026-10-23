@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Installerer Python-biblioteker for RBK Billettmonitor V19...
where py >nul 2>&1
if %errorlevel%==0 (
 py -3 -m pip install -r requirements.txt
) else (
 python -m pip install -r requirements.txt
)
echo.
echo Ferdig. Ingen Chromium-installasjon trengs paa Windows. Bruk Microsoft Edge.
pause