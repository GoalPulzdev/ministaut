@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
 py -3 hurtigkart.py --manual-only
) else (
 python hurtigkart.py --manual-only
)
pause