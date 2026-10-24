# Ministaut: utvidelse til RBK Kvinner og Koteng Arena

Dato: 24.10.2026
Status: teknisk plan / onboarding blokkert inntil ekte kart og setetall er målt og bekreftet
Eksempel-URL: https://billett.rbk.no/checkout/6aaceecebfe408c38e1712dd

## Mål
Én offentlig Ministaut for Rosenborgs herre- og kvinnelag. Vis samme kampkort, tilgjengelige seter, historikk, tempo, døgnpuls og prognoser når grunnlagsdata finnes, men velg stadion/kart per arrangement. Bevar eksisterende herre-/Lerkendal-løsning uendret og trygg.

## Verifiserte fakta og usikkerhet
- RBKs kampdagsinfo beskriver Koteng Arena med fem nummererte sittefelt, egen ståtribune, bortefelt 5, HC i felt 4 og gule VIP-seter. Referanse: https://billett.rbk.no/p/kampdagsinfo-koteng-arena
- RBK Kvinner spiller kamper både på Koteng Arena og Lerkendal: arena må være en *arrangementsegenskap*, ikke en antakelse basert på kjønn.
- Brukeroppgitt checkout-URL har gyldig format, men kartets faktiske struktur, billettprodukt, kapasitet og hvilket arrangement URL-en viser er IKKE bekreftet gjennom nettleserskanning.
- **Aldri anta at nummereringen 1–5 er identisk med scannerens tooltip-IDer, eller at ståplasser er målbare som nummererte seter.**

## Nåværende tekniske bindinger som må brytes opp
1. `scanner/match_config.py` laster `stadion_felt.json` som global `SEATS` og krever nøyaktig 60 felt.
2. `scanner/publication.py` bruker Lerkendal `TOTAL_PLACES=21423`, `EXPECTED_SEATED_MAP=19015`, global `validate_complete` for 60 felt.
3. `scanner/hurtigkart.py` og eksisterende museankre er kalibrert for Lerkendal; ingen dokumentasjon for Koteng-gjenkjennelse.
4. `scanner/sync_ministaut.py` skriver total_capacity=21423 og Lerkendal-spesifikt resultatformat.
5. `web/index.html` har et hardkodet Lerkendal-SVG med 60 sektorer, og `renderSections` krever 60 felt. Kapasitets-/prognoseforutsetninger må gjennomgås.
6. Supabase `ministaut_matches`, `ministaut_scans` og `ministaut_section_measurements` er i drift og må ikke ødelegges eller bakfylle feil verdier.

## Implementeringsløp (små PR-er)

### A — Arrangements- og arenaprofil
- Innfør `venue_id`, `venue_name`, `team_category` (men/women) og `inventory_model` (numbered_seats/general_admission/mixed) i en bakoverkompatibel konfigurasjon.
- Bruk `venue_id=lerkendal` som eksplisitt fallback på eksisterende kamper ved migrering.
- Registrer `venue_id=koteng_arena` kun når aktuell checkout-kamp er bekreftet å spille på Koteng.
- Stadium-profiler har egen `seat_sections`, `capacity_verified_at`, `standing_sections`, `geometry_version`. Ukjent kapasitet er `null`, ikke 0.
- Arena må knyttes til kamp, ikke automatisk til kvinner.

### B — Koteng kart-rekognosering og ny scannerprofil
- Ta kontrollert, manuell referanseavlesning av checkout `6aaceecebfe408c38e1712dd` i lokal Windows Edge.
- Dokumenter alle tilgjengelige billettkategorier, faktiske feltnavn og tooltips, hvor mange kjøpbare seter som er eksponert, og om ståplass-salg har beholdning.
- Lag referansefil for Koteng isolert fra `stadion_felt.json`; sett ingen kapasitet ut fra gjetning.
- Test muse-/hover-motor mot et lokalt fixture og virkelig Koteng-kart; aldri klikk eller reserver billetter.
- Valider fullstendige Koteng-tellinger mot den verifiserte *Koteng*-profilen i stedet for Lerkendals 60 felt.
- Oppretthold samme manuelle og automatiske kontroller for eksisterende 60-felts scanner. Ingen globale justeringer av ankerpunkter.

### C — Datakontrakt, kvalitetssperrer og historikk
- Utvid ingest med bekreftet arena-/kartprofil og profilversjon, og bind scans til match.
- Gjenbruk `source_run_id`-deduplisering; godta bare fullstendige profil-validerte snapshots.
- Bekreft at SQL-begrensninger, RLS og frontend-queryer tillater alternative sett med seksjoner uten å svekke datakontroll.
- Ikke sammenlign målinger med forskjellig profiler, dekningsversjoner, låste felt eller billettinventar.
- Separate tidsserier, prognoser, rekorder og seksjonsendringer per kamp. Eksisterende Molde/Start-data urørt.
- Ikke beregn `21423 - ledige` eller `19015 - ledige` for Koteng.

### D — Offentlig visning
- Kampvelger med RBK Menn / RBK Kvinner eller tydelig klubbkategori. Vis arena i kampkort.
- Koteng får egen **skjematisk** arenaillustrasjon for de fem feltene etter verifisert plassering; Lerkendal-SVG gjenbrukes bare på Lerkendal.
- Der stadiondata ikke er verifisert, vis kun overskrift, direkte billettlenke og status `Avventer første godkjente telling`; ikke falskt stadionkart eller utsolgtprognose.
- Bruk eksisterende korte supporterord: `Ledige sitteplasser`, `24 t`, `Siden sist`, `Hvis tempoet fortsetter`. Skjul manglende pulser.
- Ståplasser: eget mål kun dersom billettsystemet publiserer verifiserbar lagerbeholdning. Ikke kombiner «seter» og «billetter» uten presis definisjon.
- Den lineære 12-timers prognosen gjelder kun målt sitteledighet, og merkes som scenario, aldri bekreftet utsolgt.

### E — Test/godkjenning
- Eksisterende `web/stadium-layout.test.cjs` og `web/section-insights.test.cjs` skal fortsatt bestå uendret.
- Koteng-fixture tester: 5 kjente felt, manglende/ukjent kapasiteter, HC/VIP, låste felt, ståplass med ukjent ledighet, ugyldig/ufullstendig scan, feil stadiumprofil, feil totaltall.
- Test 2 samtidige kamper på ulike arenaer, bytte mellom dem uten data-/kartlekkasje, oppdatert 12t/24t-prognose bare på korrekte målinger.
- Virkelig lokal Koteng-scan med fullstendig kvalitetsrapport før første publisering.
- Visuell QA på mobil og desktop; dokumenter RBK-billettsidens ulike layouts.

## Stoppskilt
- Ingen automatisk publisering av Koteng-tall før sektorer/kapasiteter er verifisert.
- Ingen ombruk av `SEATS` eller museankre fra Lerkendal til Koteng.
- Ingen hardkodet 21423/19015 på kvinnelagets Koteng-kamper.
- Ingen endring av eksisterende historiske data eller fungerende timekontroll.
- Ikke anta at en RBK Kvinner-kamp alltid går på Koteng Arena.

## Første praktiske oppdrag for PC-agenten
1. Åpne oppgitt checkout-URL i egen Edge-profil og logg arrangementsnavn, dato, arena og faktiske kartdetaljer.
2. Dokumenter feltnavn, sittekapasiteter, eventuelle ståplasser, VIP/HC og hvordan gratis/betalte/ordinære billetter presenteres.
3. Lag fixture fra kartets faktiske HTML og få verifiserte Koteng-tester grønne.
4. Implementer arenaadskilt scannerprofil på branch, uten å modifisere fungerende Lerkendal-regresjon.
5. Lever kode, skjermbilder og testlogg i PR; **ikke** aktiver publisering før datasjekk.

Referanser:
- https://billett.rbk.no/p/kampdagsinfo-koteng-arena
- https://www.rbk.no/billetter/kampdagsinfo-kvinner
