@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Bygger MinistautControl.exe (Windows-app uten terminalvindu) ===
if not exist "bygg\.venv\Scripts\python.exe" (
 py -3 -m venv "bygg\.venv" || goto failed
 "bygg\.venv\Scripts\python.exe" -m pip install --quiet pyinstaller==6.11.1 pillow==11.0.0 || goto failed
)
"bygg\.venv\Scripts\python.exe" "bygg\lag_ikon.py" "ministaut.ico" || goto failed
"bygg\.venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name MinistautControl --icon ..\ministaut.ico --add-data "..\ministaut.ico;." ^
  --distpath . --workpath "bygg\work" --specpath "bygg" main.py || goto failed
cscript //nologo "bygg\snarvei.vbs"
echo.
echo Ferdig: MinistautControl.exe. Start fra snarveien "Ministaut Scanner Control" pa skrivebordet.
pause
exit /b 0
:failed
echo BYGGING FEILET. Se melding over. 02_START_KONTROLLSENTER.bat fungerer fortsatt.
pause
exit /b 2
