# MINISTAUT SCANNER CONTROL 0.2 — WINDOWS

**Dette er en reell første versjon av et samlet kontrollprogram, ikke ferdig fullautonom skanning av enhver arena.** Kjernen er en lokal tkinter-applikasjon med SQLite, kampregister, kvalitetskontroll, Koteng-timeskanning og Lerkendal-arvemotor.

## Nytt i 0.2

- **Publisering går gjennom kontrollprogrammets egen etterkontroll.** I 0.1 lastet Koteng-motoren opp (`--upload`) *før* kontrollprogrammet hadde verifisert rapporten. Nå kjøres motoren alltid uten opplasting. Bare en diagnostikk som består etterkontrollen legges i en **varig utboks** (SQLite) og sendes med `sync_koteng.py --send`.
- **Utboksen tåler nettfeil og krasj.** Feilede sendinger prøves på nytt etter 2, 4, 8 … maks 60 min (med litt tilfeldig spredning). Etter 8 forsøk, eller når målingen er eldre enn 6 timer, forkastes den. Måle-ID-en er den samme ved hvert forsøk, så Supabase lagrer aldri duplikater. Slår du av Live, publiseres ingenting som ligger i kø.
- **Låser etter krasj:** Hver lås lagrer PID for kontrollprogram og skanner. En gammel lås gir status `TRENGER GJENNOMGANG` i stedet for evige nye forsøk. Knappen `Frigi lås` nekter så lenge en registrert prosess fortsatt kjører.
- **Bare ett kontrollsenter per mappe.** Programmet åpnes ikke to ganger samtidig.
- **Sperre før avspark:** Ingen ny skanning starter de siste *N* minuttene før avspark (standard 20, kan settes per kamp). En skanning som pågår ved avspark stoppes og får status `STOPPET VED AVSPARK`.
- **Avspark i norsk tid:** Dato `dd.mm.åååå` og klokkeslett `tt:mm`, med riktig sommer-/vintertid uten ekstra pakker. Alle tider vises i norsk tid.
- **Bedre oversikt:** Kolonner for endring siden forrige måling og målingens alder, fargekodet status (`KØET`, `SKANNER · 4 min` osv.) og faner for målinger med publiseringsstatus, kjøringer, skannerlogg og hendelser. Tabellene blinker ikke og beholder valget ved oppdatering.
- **Systemsjekk** (knapp): Python, Edge, diskplass, Git, motorfiler, `.venv`, Playwright og om token finnes. Selve tokenet leses aldri.
- **Slett kamp** og trygg redigering. Billett-URL kan ikke endres på en eksisterende kamp, og en redigert kamp lagres alltid som deaktivert.
- **Lerkendal som vanlig jobb (`lerkendal_v23`):** `engines/lerkendal_once.py` kjører den uendrede V23-motoren (`hurtigkart.py`) én runde uten ENTER og uten konsoll. Adapteren:
  - kontrollerer at Edge viser riktig kamp før tellingen
  - velger «Bare nødvendig» på cookiebanneret, som ellers dekker felt C–J
  - blokkerer motorens egen opplasting
  - bruker egen Edge-profil og port 9231, mens produksjonsskanneren bruker 9222

  Etterpå kjører kontrollprogrammet motorens `validate_complete` på nytt (60/60 felt, kapasitet, konflikter, kartstruktur) og publiserer via utboksen med samme `source_run_id` som V23. Koteng og Lerkendal kan kjøre samtidig, og en skanning som henger stoppes etter 30 min. Installasjon: kopier V23-mappen til `adapters/lerkendal` **uten** `.ministaut-token`, `edge_scanner_profile` og `output`. Legg token der først når Live skal på, og ta da denne kampen ut av den gamle skannerens `kamper.json`.
- **Ekte Windows-app:** `MinistautControl.exe` (PyInstaller, `--windowed`) med eget ikon og snarvei på skrivebordet. Ingen terminalvinduer, heller ikke for Koteng-skanning, etterkontroll og sending. Lerkendal-motoren åpner fortsatt sitt eget konsollvindu, fordi den venter på ENTER fra operatøren. Ved feil vises en dialog, og detaljene lagres i `state/logs/app-feil-*.log`.
- Lukker du programmet mens en skanning kjører, får du tilbud om å stoppe alle skanninger først.
- Feilrettinger: Hvert knappetrykk startet en ny oppdateringssløyfe hvert 2. sekund (de hopet seg opp). Feil under planlegging kunne stoppe hele sløyfen.

### Oppgradere fra 0.1
Lukk kontrollsenteret og **ta en kopi av `state/control.sqlite3`** (trengs hvis du vil tilbake til 0.1, fordi 0.1 ikke kan lese kampoppsett lagret av 0.2). Kopier `app/`, `tests/`, `main.py`, `LES_MEG.md` og `*.bat` fra 0.2 over den gamle `Ministaut_Control`-mappen. **Behold** `adapters/`, `sources/` og `state/`. Databasen oppgraderes automatisk, og historikken beholdes. Aktiver Live på nytt etter første testkjøring.

## Installering

1. Pakk ut **hele mappen** `Ministaut_Control`. Installer Microsoft Edge.
2. Kjør `01_INSTALLER.bat` (setter opp Koteng V2.4 og Playwright/Pillow i eget .venv).
3. Kjør `05_BYGG_WINDOWS_APP.bat` én gang. Den lager `MinistautControl.exe` og snarveien **Ministaut Scanner Control** på skrivebordet. Start programmet derfra, uten terminalvindu. `02_START_KONTROLLSENTER.bat` fungerer fortsatt som reserve.
4. Tre kamper er registrert som **deaktiverte** eksempler: Rosenborg–Røa (Koteng), Rosenborg–Molde og Rosenborg–Start (Lerkendal). Kontroller kampdato, kategorier og URL før aktivering.
5. Velg RBK Kvinner – Røa, trykk `Test én gang`. Ved vellykket lokal skanning vises siste observerte ledige som et lokalt tall; ingen data sendes.
6. Trykk `Systemsjekk`. Stopp gammel Koteng-sesjon på den andre PC-en før du slår på live. Velg `Aktiver / Deaktiver`, deretter `Live AV/PÅ` og bekreft. Koteng styres sentralt **hver time** mens kontrollprogrammet er åpent og PC er våken.
7. For Lerkendal (herrer/cup), kjør `03_LAST_NED_LERKENDAL.bat` for å hente eksisterende kildekode til en **egen** mappe. Installer dens krav etter README i den kopierte `scanner`-mappen. Velg kamp og `Start nå` for å åpne en egen interaktiv Edge-konsoll som fortsatt styrer sin egen timeskanning **og egen publisering**. LIVE-bryteren i kontrollpanelet har ikke kontroll over den gamle Lerkendal-motorens publisering. **Start bare én Lerkendal-sesjon på samme PC.**

## Sikkerhet og datakvalitet

- **Ingenting skannes automatisk ved første start.** Du må aktivere en kamp.
- Original Koteng V2.4-profil, referansebilder, skanner og live-sidecar følger med og er urørt.
- En fullført Koteng-skanning må i tillegg bestå kildeprogrammets egen kryptografiske profil- og sektorkontroll før tall lagres i kontrollprogrammets SQLite-historikk.
- `LIVE` publiserer kun samme kontrollerte Koteng-måling, via utboksen, til eksisterende separat Supabase-endepunkt som `observed`, og bare med skannertoken lokalt i `adapters/koteng/.ministaut-token` eller miljøvariabel `MINISTAUT_TOKEN`.
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
| Lerkendal herrer/cup | Ja (0.2): `lerkendal_v23` én-runde-adapter | Testet 27.10: 60/60 felt, 4019 ledige (produksjon 4023 fem min før). `lerkendal_legacy` finnes fortsatt |
| Nye kamper | Registrering fungerer | Krever verifisert stadionprofil og arrangementsspesifikt oppsett før kjøring |
| Supabase | Bruker eksisterende endepunkt | Krever lokal token, ingen endring av API |
| Varig utboks med ny sending | Ja (0.2) | Kun Koteng; Lerkendal publiserer selv |
| Server-side lease / drift uten pålogget PC | Nei | Må bygges og gjennomgås før full produksjon |

## Tester

`py -3 -m unittest discover -s tests -v` kjøres uten nettverk. Koteng egne tester: åpne PowerShell i `adapters/koteng` og kjør `.venv\Scripts\python.exe -m unittest discover -s tests -v`.

**Feil/rollback:** Stopp kontrollprogrammet og start den fungerende, gamle scannerinstallasjonen igjen. Controlleren erstatter ingen kildemotor eller eksisterende historikk.
