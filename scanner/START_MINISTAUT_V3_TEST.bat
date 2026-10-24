@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Ministaut V3 - Lokal testadministrasjon
echo =================================================
echo  MINISTAUT V3 - TESTPANEL (INGEN EDGE-SKANNING)
echo =================================================
echo.
echo  Dette panelet styrer KUN lokal V3-testtilstand.
echo  Bruk gammel START_BILLETTMONITOR.bat for ekte telling.
echo.
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 -m v3.gui
) else (
  python -m v3.gui
)
if errorlevel 1 (
  echo.
  echo Kunne ikke starte V3-panelet. Kontroller Python 3.10+.
  echo Hvis det staar "No module named tkinter" maa Python installeres med Tcl/Tk.
  pause
)
endlocal
