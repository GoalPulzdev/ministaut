@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Koteng har na 6 bekreftede sitteomrader. Mer stadionopplaering er ikke nodvendig.
echo Starter kontroll av Felt 1-5 og VIP fra tidligere innlaerte punkter...
echo.
call "%~dp0START_KOTENG_KONTROLL.bat"
