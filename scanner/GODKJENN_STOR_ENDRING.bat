@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo RBK V18 - MANUELL GODKJENNING AV UVANLIG STOR ENDRING
echo Bruk bare dette naar du har verifisert at tallene i resultat.json er korrekte.
echo.
set /p RESULT=Full sti til resultat.json: 
set RESULT=%RESULT:"=%
set /p AGREED=Skriv BEKREFT for aa fortsette: 
if not "%AGREED%"=="BEKREFT" (
 echo Avbrutt. Historikken er ikke endret.
 pause
 exit /b 1
)
where py >nul 2>&1
if %errorlevel%==0 (
 py -3 lag_post.py --input "%RESULT%" --approve-large-change
) else (
 python lag_post.py --input "%RESULT%" --approve-large-change
)
pause