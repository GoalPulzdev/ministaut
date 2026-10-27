@echo off
chcp 65001 >nul
cd /d "%~dp0"
setlocal
if not exist "adapters\koteng\01_INSTALLER.bat" (
 echo Koteng-motor mangler. Pakk ut hele pakken, ikke enkeltfiler.
 pause
 exit /b 2
)
echo === Koteng V2.4 bibliotek og Microsoft Edge-oppsett ===
call "adapters\koteng\01_INSTALLER.bat"
if errorlevel 1 (
 echo Installer feilet. Se feilmelding over.
 pause
 exit /b 2
)
echo === Kjor testene for kontrollprogrammet ===
py -3 -m unittest discover -s tests -v
pause
