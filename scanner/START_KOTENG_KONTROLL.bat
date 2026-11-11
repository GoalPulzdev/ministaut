@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Ministaut V3 - Kontroller Kotengs 6 sittefelt
cls
echo ========================================================
echo  MINISTAUT V3 - KOTENG (KUN 6 SITTENDE OMRADER)
echo ========================================================
echo.
echo All stadionkartlegging er avsluttet. Programmet leser kun
echo lagrede musepunkter for Felt 1-5 + VIP to ganger.
echo.
echo Koteng-profil maa ligge i v3_profiles\koteng_arena.v1.json
echo eller v3_profiles\koteng_arena.v2.json
echo Kopier profilen fra den gamle testmappen hvis den mangler.
echo.
echo Ingen billetter klikkes eller reserveres.
echo Ingen data sendes til Supabase eller nettsiden.
echo.
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 -m v3.verify_koteng
) else (
  python -m v3.verify_koteng
)
if errorlevel 1 (
  echo.
  echo Koteng ble IKKE fullstendig kontrollert, eller en feil oppsto.
  echo Les feilmelding over og bevar filene i v3_learning.
)
echo.
echo JSON-rapport i v3_learning\koteng_arena
pause
endlocal
