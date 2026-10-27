# MINISTAUT SCANNER CONTROL 0.1 — WINDOWS

**Dette er en reell første versjon av et samlet kontrollprogram, ikke ferdig fullautonom skanning av enhver arena.** Kjernen er en lokal tkinter-applikasjon med SQLite, kampregister, kvalitetskontroll, Koteng-timeskanning og Lerkendal-arvemotor.

## Installering

1. Pakk ut **hele mappen** `Ministaut_Control`. Installer Microsoft Edge.
2. Kjør `01_INSTALLER.bat` (setter opp Koteng V2.4 og Playwright/Pillow i eget .venv).
3. Kjør `02_START_KONTROLLSENTER.bat`. Det skal åpnes en mørkegrønn Windows-app.
4. Tre kamper er registrert som **deaktiverte** eksempler: Rosenborg–Røa (Koteng), Rosenborg–Molde og Rosenborg–Start (Lerkendal). Kontroller kampdato, kategorier og URL før aktivering.
5. Velg RBK Kvinner – Røa, trykk `Test én gang`. Ved vellykket lokal skanning vises siste observerte ledige som et lokalt tall; ingen data sendes.
6. Stopp gammel Koteng-sesjon på den andre PC-en før du slår på live. Velg `Aktiver / Deaktiver`, deretter `Live AV/PÅ` og bekreft. Koteng styres sentralt **hver time** mens kontrollprogrammet er åpent og PC er våken.
7. For Lerkendal (herrer/cup), kjør `03_LAST_NED_LERKENDAL.bat` for å hente eksisterende kildekode til en **egen** mappe. Installer dens krav etter README i den kopierte `scanner`-mappen. Velg kamp og `Start nå` for å åpne en egen interaktiv Edge-konsoll som fortsatt styrer sin egen timeskanning **og egen publisering**. LIVE-bryteren i kontrollpanelet har ikke kontroll over den gamle Lerkendal-motorens publisering. **Start bare én Lerkendal-sesjon på samme PC.**

## Sikkerhet og datakvalitet

- **Ingenting skannes automatisk ved første start.** Du må aktivere en kamp.
- Original Koteng V2.4-profil, referansebilder, skanner og live-sidecar følger med og er urørt.
- En fullført Koteng-skanning må i tillegg bestå kildeprogrammets egen kryptografiske profil- og sektorkontroll før tall lagres i kontrollprogrammets SQLite-historikk.
- `LIVE` publiserer kun samme kontrollerte Koteng-måling til eksisterende separat Supabase-endepunkt som `observed`, og bare med skannertoken lokalt i `adapters/koteng/.ministaut-token` eller miljøvariabel `MINISTAUT_TOKEN`.
- **Legg aldri token i Git eller i chatten.** Kjør Koteng sin `03_KONFIGURER_TOKEN.bat` for lokal oppsetting.
- Kontroller at en annen PC **ikke** skanner/publiserer samme event; per-PC låsefil hindrer lokale duplikater, men felles server-side lease er neste utviklingstrinn.
- Ståplasser er ikke inkludert i sitteplasstallet; det er ikke bekreftede salg.
- Kjøring stopper ved kampstart som standard for **nye jobber**. Hvis en skanning allerede pågår ved avspark må den overvåkes; dette er ikke ennå en Windows-tjeneste med prosessgruppekontroll.
- Programmet endrer ikke Vercel, Supabase-skjema, eksisterende Lerkendal-kode eller skannerinstallasjonen på annen PC.
- All lokal historikk og logg ligger i `state/` og er Git-ignorert.

## Status

| Modul | Tilgjengelig i 0.1 | Begrensning |
|---|---|---|
| Lokal Windows-app med lag/kamper | Ja | Krever Python med Tkinter |
| Koteng V2.4 hel motor | Ja | Profillås er foreløpig knyttet til Røa-kamp-ID |
| Koteng automatisk per time | Ja | Appen og Edge/PC må være aktive |
| Intern SQLite-historikk | Ja | Bare lokalt nyverifiserte Koteng-målinger; ikke import av gamle |
| Lerkendal herrer/cup | Koble til eksisterende kildekode | Interaktiv motor med egen timesløyfe, ikke en ny én-gang-adapter ennå |
| Nye kamper | Registrering fungerer | Krever verifisert stadionprofil og arrangementsspesifikt oppsett før kjøring |
| Supabase | Bruker eksisterende endepunkt | Krever lokal token, ingen endring av API |
| Server-side lease / drift uten pålogget PC | Nei | Må bygges og gjennomgås før full produksjon |

## Tester

`py -3 -m unittest discover -s tests -v` kjøres uten nettverk. Koteng egne tester: åpne PowerShell i `adapters/koteng` og kjør `.venv\Scripts\python.exe -m unittest discover -s tests -v`.

**Feil/rollback:** Stopp kontrollprogrammet og start den fungerende, gamle scannerinstallasjonen igjen. Controlleren erstatter ingen kildemotor eller eksisterende historikk.
