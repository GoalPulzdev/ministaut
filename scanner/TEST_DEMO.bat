@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Syntetiske DEMO-data. Tester ikke live RBK.
where py >nul 2>&1
if %errorlevel%==0 (
 py -3 hurtigkart.py --demo
) else (
 python hurtigkart.py --demo
)
pause