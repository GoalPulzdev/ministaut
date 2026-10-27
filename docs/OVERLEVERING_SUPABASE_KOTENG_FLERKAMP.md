# Overlevering: Supabase for Koteng flerkamp (Rosenborg–Brøndby)

Dato: 27.10.2026. Branch: `feat/scanner-control-v0.2` (PR #27). Frist: **29.10.2026 kl. 18:00** (avspark Rosenborg–Brøndby).

## Bakgrunn
Scanner Control 0.2 kjører live på operatør-PC-en, i `Desktop\Ministaut_Control_V0.2`, med `MinistautControl.exe`. Den gamle terminalskanneren (`hurtigkart.py --multi`) er stoppet.

Koteng-motoren kan nå skanne alle godkjente kamper på Koteng Arena:
- Adapteren er `scanner-control/engines/koteng_once.py`.
- Den forseglede stadionlåsen fra V1.8 (SHA) verifiseres uendret ved hver skanning.
- Rosenborg–Brøndby er testet lokalt: 6/6 felt i to pass, 316 ledige.

Det gjenstår bare serversiden. Den deployede `ministaut-koteng-ingest` godtar i dag kun Røa-ID-en, så Brøndby-målinger avvises.

## Oppgave for neste agent

### 1. Kontroller at deployet funksjon ikke er nyere enn repoet
```bash
supabase login            # eller SUPABASE_ACCESS_TOKEN
supabase functions download ministaut-koteng-ingest --project-ref khetbokxbcujwcurvviu
```
Sammenlign med `git show origin/main:supabase/functions/ministaut-koteng-ingest/index.ts`. Hvis deployet versjon avviker fra `main`, skal du **stoppe og flette** før du deployer.

### 2. Deploy den oppdaterte funksjonen
Endringen ligger i `supabase/functions/ministaut-koteng-ingest/index.ts` (diff: `git diff origin/main -- supabase/functions`).
- `event_key` slås opp i `ministaut_koteng_matches` i stedet for å sammenlignes med en hardkodet Røa-ID.
- Kampen må ha `venue_id='koteng_arena'` og `is_published=true`.
- Alle andre kontroller er uendret: token, profilversjon, 6 felt, kapasiteter, to pass, `source_run_id`-idempotens. Røa fungerer som før.
```bash
supabase functions deploy ministaut-koteng-ingest --project-ref khetbokxbcujwcurvviu
```
Bruk samme JWT-innstilling som dagens deploy. Funksjonen autentiserer selv med `x-ministaut-token`, så den må ikke kreve JWT hvis den ikke gjør det i dag.

### 3. Registrer Brøndby
Kjør `supabase/koteng_brondby_20261029.sql`. Kontroller kolonnene i `ministaut_koteng_matches` først: nettsiden leser `id,event_key,title,kickoff_at,venue_id,team_category,is_published`. Hvis tabellen har andre `NOT NULL`-kolonner, sett dem slik Røa-raden har dem.
```sql
select * from ministaut_koteng_matches where event_key='6aaceecebfe408c38e1712dd';  -- mal
```
Raden gjør at kampen vises på nettsiden under RBK Kvinner (`is_published=true`).

### 4. Verifiser
- Bekreft at Røa fortsatt publiseres. Neste timeskanning kommer automatisk fra Scanner Control på operatør-PC-en.
- Slå på Live for Brøndby i Scanner Control: velg kampen og trykk «Live av/på». Det krever operatøren på PC-en, eller endring av jobben (`upload=true`) i `state/control.sqlite3` via `app.runner.Controller.enable(key, True, True)`.
- Første måling skal ha status `sendt` i utboksen, og raden skal finnes i `ministaut_koteng_scans` for Brøndby-matchen.

## Ikke gjør
- Ikke endre `ministaut-ingest` (Lerkendal). Den oppretter nye kamper selv og fungerer.
- Ikke slå sammen Koteng- og Lerkendal-tabellene.
- Ikke legg token i Git. Operatør-PC-en har token lokalt i `adapters/*/.ministaut-token`.

## Kjente funn (til eier av Koteng V2.4, PR #28)
`baselines/koteng/v2.4/koteng_scanner.py` avviser alle skjermer på operatør-PC-en:
1. `desktop_can_show_locked_window` sammenligner vinduet med `window.screen`. Den verdien emulerer Playwright til selve visningsstørrelsen (1294×642), så den er alltid mindre enn ytre vindu (1311×777). `windows_primary_work_area()` finnes, men kalles ikke her.
2. Brøkdelsskalering i Windows (`devicePixelRatio` 0,99999999) gir `innerHeight` 643. Kontrollene krever nøyaktig 642, mens ankerkontrollen ellers tåler ±8 px.

Operatør-PC-en kjører derfor V2.3 med én pilotendring (Edge settes til 1294×642 i stedet for å maksimeres; se `adapters/koteng/PILOT_ENDRING_VINDUSSTORRELSE.txt` på PC-en). Profil og lås er uendret.
