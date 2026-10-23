@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Kobler til en Edge-fane som allerede er aapen MED debugging aktivert.
where py >nul 2>&1
if %errorlevel%==0 (
 py -3 hurtigkart.py --attach-only
) else (
 python hurtigkart.py --attach-only
)
pause