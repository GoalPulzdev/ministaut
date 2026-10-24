@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Ministaut V3 - Laer opp Koteng Arena
cls
echo ============================================================
echo   MINISTAUT V3 - KOTENG ARENA - STADIONOPPLAERING
echo ============================================================
echo.
echo Dette er en TEST som leser offentlige felt-tooltip med samme metode
echo som Lerkendal. Den publiserer INGEN billettall.
echo.
echo Lukk den gamle scannerens Edge-vindu for du starter.
echo En EGEN Edge-profil benyttes i denne opplaeringen.
echo.
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 -m v3.learn_koteng
) else (
  python -m v3.learn_koteng
)
if errorlevel 1 (
  echo.
  echo Opplaering feilet. Kontroller INSTALLER.bat og siste feilmelding.
)
echo.
echo Resultatet finner du i v3_learning\koteng_arena
echo Profilutkast finner du i v3_profiles\koteng_arena.v1.json
echo Dette er ikke en godkjent live-skanner.
pause
endlocal
