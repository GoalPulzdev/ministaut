@echo off
cd /d "%~dp0"
if exist "sources\ministaut\scanner\hurtigkart.py" (
 echo Lerkendal-koden finnes allerede. Oppdatering krever separat kontroll.
 pause
 exit /b 0
)
where git >nul 2>&1
if errorlevel 1 (
 echo Installer Git for Windows forst: https://git-scm.com/downloads/win
 pause
 exit /b 2
)
if not exist "sources" mkdir "sources"
git clone --depth 1 https://github.com/GoalPulzdev/ministaut.git "sources\ministaut"
if errorlevel 1 (
 echo Git clone feilet. Kontroller Git-innlogging og nettverk.
 pause
 exit /b 2
)
echo Lerkendal-kode hentet til isolert mappe. IKKE start dobbelt mot aktiv produksjon.
pause
