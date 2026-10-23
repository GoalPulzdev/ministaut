@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo RBK HURTIGKART V18 - lag 4:5- og Story-bilder fra en lagret telling.
echo Bruk kun resultat.json fra en KOMPLETT kjøring.
echo.
set /p RESULT=Lim inn full sti til resultat.json: 
set RESULT=%RESULT:"=%
where py >nul 2>&1
if %errorlevel%==0 (
 py -3 lag_post.py --input "%RESULT%"
) else (
 python lag_post.py --input "%RESULT%"
)
echo.
pause