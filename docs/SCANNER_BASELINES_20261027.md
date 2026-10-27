# Scanner-baselines og Git-arkiv — 27.10.2026

## Kildeoversikt

| Scanner/kampstrøm | Kodebase | Hva som er dokumentert | Hva som ikke er verifisert |
|---|---|---|---|
| RBK herrer, Lerkendal (seriekamper) | `scanner/` | 60 faste sittefelt; fungerende V19.1 lokal motor; V20/V21-baserte filer i Git; timeskanning mulig via `START_BILLETTMONITOR.bat` | At kildefilene i Git er byte-identiske med programmet som kjører på gammel PC |
| RBK herrer, Lerkendal (cup/annen kamp) | `scanner/` med annen `event_key` og kampoppsett | Samme stadium-/felttypemodell kan brukes for flere kamper; hver kamp egen historikk | Hvilken konkret cup-event som kjører, om lokale kalibreringsfiler er nyere enn Git, eller om det finnes en annen modifisert scannerinstallasjon |
| RBK Kvinner, Koteng Arena (Røa) | `baselines/koteng/v2.4/` **komplett i main (PR #28)** | Seks felter, 601 referanseseter; V1.8 låst profil, V2.4 justerer Edge viewport på ny skjerm; separert Supabase-ingest; dobbel kontroll i begge skannepass | Reell Edge-test på ny PC og sammenligning med faktisk kjørende lokal Koteng-installasjon. Git-baselinen er verifisert komplett |

**Merk:** De tre jobbtypene er ikke nødvendigvis tre forskjellige skannermotorer. Det skal være *én* Lerkendal-kodebase med flere uavhengige kampjobber, og *én* Koteng-kodebase/adaptersnapshot. Ikke kopier 30 000 linjer for hver nye kamp.

## Konkrete referanser
- **Repo**: https://github.com/GoalPulzdev/ministaut
- **Lerkendal motor**: `scanner/hurtigkart.py`, `scanner/scanner.py`, `scanner/match_config.py`, `scanner/schedule_control.py`, `scanner/sync_ministaut.py`, `scanner/tests/`.
- **Lerkendal kjente event-ID-er i kodehistorikk**: `6a9a7e3f3f93920b289b0675` og `6a9a7c2b15599587216e21f3`; kampnavn/cupstatus må verifiseres mot gjeldende lokale kampoppsett, ikke utledes fra filnavn.
- **Koteng checkout Røa**: `6aaceecebfe408c38e1712dd`.
- **Koteng hele V2.4 ZIP SHA256**: `b0ea10aacd80da2d2acf323dc2aadb5268cd9c6c8e0476bc6afa9cd0401d5d6a`.
- **Koteng V2.4 i Git:** `baselines/koteng/v2.4/` med 42 originalfiler + `ARCHIVE_MANIFEST.json`. Alle 42 Git-blob-hasher matcher original ZIP, inkludert PNG. PR #28 merget 27.10.2026.
- **Koteng profilen**: skjermens fysiske oppløsning kan variere, men verifisert Edge CSS viewport må være 1294 × 642 med zoom 0,9. 6/6 felt i 2 pass og uendret SHA kreves før måling.
- **Offentlig status**: Lerkendal scanner sender godkjent `accepted`; Koteng skanner sender verifisert observert `observed` fra valgt billettkategori. Publisering av absolutt salgsantall er **ikke** støttet.
- **Backend**: `supabase/functions/ministaut-ingest/index.ts` og `supabase/functions/ministaut-koteng-ingest/index.ts`. Ikke slå sammen funksjonene eller DB-tabellene uten egen migrasjonsoppgave og regresjonstester.

## Koteng V2.4 er arkivert i Git — ingen lokal import nødvendig
1. Hent oppdatert `main` fra GitHub; hele originale V2.4 ligger i `baselines/koteng/v2.4/`, inkludert de to PNG-filene og SHA-manifest.
2. Kjør Koteng-testene lokalt fra `baselines/koteng/v2.4`: `py -3 -m unittest discover -s tests -v`. Originalen bestod 60/60 tester ved arkivering, men Windows/Edge må fortsatt testes fysisk på ny PC.
3. Ikke kjør `tools/import_koteng_v24_to_repo.py --apply` på den arkiverte baseline; skriptet er kun nødvendig hvis en ny tom Git-referanse skal rekonstrueres fra ZIP.
4. Sammenlign den kjørende lokale Koteng-versjonen og de to øvrige scannerne med Git. Aldri commit `.ministaut-token`, output, Edge-profiler, cookies, historikk eller privat diagnostikk.

## Finn siste lokale Lerkendal- og cupkode
PC-agenten skal sammenligne Git-filer mot filene som faktisk brukes i begge kjørende mapper, inkludert:
- `hurtigkart.py`, `scanner.py`, `schedule_control.py`, `match_config.py`, `publication.py`, `sync_ministaut.py` og launcher-BAT.
- SHA256 per fil, Python-versjon, Playwright-versjon, Edge-versjon, CLI-parametere, skjermoppsett og event-ID.
- Kun anonymisert inventar av **filnavn og filhasher**, ikke tokens, lokal brukerkonto eller private profiler. Ikke eksporter reell historikk til repo.
- Når en lokal fil faktisk er nyere: arkiver som `baselines/lerkendal/<verifisert-versjon>/`, forklar forskjell, kjør tester, bevar gamle filer før den erstattes.
- Hver kamp får separat jobbconfig (event_key/arena/kategori/kickoff), men samme gjenbrukte motor.

## Konkrete leveransegates
- **Arkiv ferdig:** Git inneholder alle godkjente Koteng V2.4-filer inkl. referansebilder, og de to andre aktive kjøringenes kode og profil er sammenlignet mot det som kjører.
- **Utvikling starter:** Kun etter audit og skriftlig bekreftet lokal status; aktiv skanner og livefrontend skal ikke endres.
- **Produksjon:** Krever dokumentert test av min. to forskjellige kampjobber, feil/duplikater, pause/avspark, public status og rollback.
