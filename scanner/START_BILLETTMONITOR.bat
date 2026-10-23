@echo off
chcp 65001 >nul
cd /d "%~dp0"
title RBK Billettmonitor V20 - flerbrukssesjon
cls
echo ==================================================
echo    RBK BILLETTMONITOR V20 - KONTROLLSENTER
 echo ==================================================
echo.
echo Start en kamp med checkout-adressen.
echo Etter forste sjekk: Automatisk ny telling hver time.
echo Alle godkjente maalinger lagres, og historikkgrafen oppdateres.
echo Du trenger IKKE starte dette programmet igjen.
echo.
where py >nul 2>&1
if %errorlevel%==0 (
 py -3 hurtigkart.py --auto-hours 1
) else (
 python hurtigkart.py --auto-hours 1
)
echo.
echo Sesjonen er avsluttet. Alle resultater ligger i output.
pause