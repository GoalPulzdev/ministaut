@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo V16: Start med ett punkt per felt, deretter flere kun paa manglende felt.
where py >nul 2>&1
if %errorlevel%==0 (
 py -3 hurtigkart.py --extra --max-points 350
) else (
 python hurtigkart.py --extra --max-points 350
)
pause