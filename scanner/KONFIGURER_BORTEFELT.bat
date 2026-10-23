@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo RBK V18 - BEKREFT LAASTE BORTEFELT PER KAMP
echo Ett eller to bortefelt kan holdes utenfor ordinaert salg.
echo Legg KUN inn felt som er bekreftet laast i denne kampen.
echo.
where py >nul 2>&1
if %errorlevel%==0 (
 py -3 kampoppsett.py
) else (
 python kampoppsett.py
)
echo.
pause