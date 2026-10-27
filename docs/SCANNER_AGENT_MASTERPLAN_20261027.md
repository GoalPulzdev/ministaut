# MINISTAUT SCANNER PLATFORM — MASTERPLAN FOR LOKAL PC-AGENT

Dato: 27. oktober 2026. Eier: GoalPulz AS. Repo: `GoalPulzdev/ministaut`.

## 0. Oppdraget i én setning
Utvikle **ett robust Windows-program som overvåker flere billettkamper parallelt, uavhengig av lag og stadion**, ved å gjenbruke dokumentert riktig skannelogikk, isolere arenaspesifikk kalibrering og kvalitetssikre alle resultater før overføring til Ministaut.

**Prioritet:** korrekt avlesning og sikkerhet > kontinuerlig drift > enkel bruk > ytelse > avansert funksjonalitet. Dette er et langsiktig program, ikke en rask sammenslåing av tre skript.

## 1. Autoritative baselines — IKKE overskriv

| Kilde | Status i repo | Hva agenten skal gjøre |
|---|---|---|
| `scanner/` | Eksisterende Lerkendal-kode i `main`; V20/V21-baserte skript, V19.1 dokumentert fungerende som stabil lokal baseline | Les, test og bruk som referanse; ikke modifiser den aktive skannermotoren i første fase |
| Lerkendal herrekamp A | Samme `scanner/`-motor, egen `checkout`/`event_key` | Separat jobb og historikk, **ikke** ny kopi av motorkoden |
| Lerkendal herrekamp B / cup | Samme motor dersom kart og feltmodell er Lerkendal; eksakt kamp-ID og lokale avvik må verifiseres på aktiv PC | Separat jobb og historikk; ikke anta at cup er særskilt arenaadapter |
| Koteng Arena | Verifisert V1.8-motor pakket som V2.4 for ny skjerm; **komplett i `main` siden PR #28** (42 originale filer, låst profil, PNG-referanser og SHA-manifest) | Bruk eksisterende `baselines/koteng/v2.4/` direkte som låst referanse; verifiser mot faktisk kjørende Windows-installasjon og kjør de 60 lokale Koteng-testene |
| Frontend | `web/` og Vercel-produksjon | Må ikke endres før datakontrakt, testmiljø og regressjonskontroll er på plass |
| Supabase | Egen `ministaut-ingest` for Lerkendal, `ministaut-koteng-ingest` for Koteng; separate tabeller/policies | Ikke kjør migreringer eller endre produksjonsdata under inventar- og kodenormalisering |

### Følgende er bekreftet vs. ikke bekreftet
- **Bekreftet lokalt av bruker:** Lerkendal V19.1, kontrollene «Ny sjekk» og «Bytt kamp», Koteng V1.8 med 6/6 felt i to pass og profil låst. Koteng V2.4 har automatisk viewport på 1294×642 CSS px og 90 % sidezoom, men må fysisk testes på ny Windows-PC.
- **Kjent kode:** Lerkendal med 60 sittefelt, standard kontroll mot 21 423 total stadionkapasitet; Koteng VIP 71, Felt 1 49, Felt 2 160, Felt 3 120, Felt 4 152, Felt 5 49 = 601 referanseseter. Ståplass A/B utenfor Koteng-tellingen. Bortefelt og ikke-åpne seksjoner må ikke tolkes som solgt.
- **Må verifiseres før merge:** Siste faktisk kjørende menns/cup-programfiler og lokale kampoppsett på PC. En Git-versjon er ikke automatisk identisk med det som kjører. Ikke erklær «tre komplette skannere importert» før kildefil-hash, kjøringsmiljø og faktisk kamp-ID for hver er kontrollert.

## 2. Agentregler — ufravikelige
1. Opprett egen Git-branch `feat/scanner-platform-*` og jobb i ny katalog `apps/scanner-control/` / `packages/scanner-core/` / `packages/stadium-adapters/` eller tilsvarende. Bevar `scanner/` og `baselines/koteng/v2.4/` uendret som historiske referanser.
2. Aldri commit private `.ministaut-token`, `.env`, browserprofiler, cookies, innloggingsdata, kontakter, lokale diagnostikker eller produksjonshistorikk. Legg til eksplisitte `.gitignore`-regler og test at hemmeligheter ikke havner i Git-indeks.
3. Aldri kjøp, klikk, legg i handlekurv, reserver eller utsted billetter; kun lese offentlig tilgjengelige kart/verktøytips i Edge. Respekter nettstedets vilkår, robust rate limiting og normal bruk.
4. Et feil, manglende eller inkomplett felt er **ikke 0 ledige**. `locked` må være eksplisitt dokumentert. `0 ledige` kan kun komme fra faktisk avlest, gyldig verdi.
5. Ingen godkjenning basert på at totalsummen likner forrige verdi; bekreft identitet, kapasitet, alle felt, to uavhengige observasjoner og rett kamp-ID. Ved differanse: behold tidligere gyldige tall med originalt tidsstempel og `stale`-merking.
6. Ikke slå av profillås, skjermgeometri eller datakvalitetskontroll for å få passering. Nye layoutvarianter krever ny versjonert, manuelt godkjent kalibrering.
7. Ikke endre produksjons-Supabase, publikumsfrontend eller aktiver auto-publisering før separat test og eksplisitt kvalitetssjekk. `observed` er **observerte ledige i valgt billettkategori**, ikke bekreftede salg.
8. Behold aktiv Lerkendal/Koteng-kjøring på gammel PC inntil migrering er testet. Aldri start samme kamp med to aktive produsenter; bruk «leader lease» per kamp/arena/PC.
9. Ingen GitHub Actions: bruker tester lokalt på Windows Edge. Kjør lokale tester og manuell godkjenning; dokumenter nøyaktig kommando og resultat i PR.
10. Alle endringer skal være etterprøvbare: versjon, commit SHA, profil SHA, fixture URL, valgt kategori, kalibrerings-ID, skanner-ID, innlesingspunkt og observerte tider.

## 3. Mål: Én kontrollapp, mange uavhengige kamper

### Operatørens opplevelse
- Start ett Windows-program med enkel «Kamper»-oversikt. Vis kort for RBK, RBK Kvinner og fremtidige lag/arenaer, men **ikke hardkod programmet til RBK**.
- `Legg til kamp`: lim inn offentlig checkout-URL, velg eller oppdag leverandør/arena, velg lag og kategori, legg inn avspark i Europe/Oslo, valider før oppstart.
- `Kjør én kontroll`, `Start timevis`, `Pause`, `Bytt kamp`, `Avslutt ved avspark`, `Vis siste avlesning`, `Vis avvik`, `Åpne Edge`, `Kalibrering`, `Historikk`.
- Status per kamp: `KLAR`, `MÅ KALIBRERES`, `SKANNER`, `BEKREFTET LOKALT`, `KØET`, `SENDT`, `PUBLISERT OBSERVASJON`, `FORSINKET`, `TRENGER GJENNOMGANG`, `STOPPET VED AVSPARK`.
- En tydelig global oversikt: siste kjøring, neste planlagte, antall felter kontrollert, ledige sitteplasser, endring siden sammenlignbar måling, feilmelding og dataalder.
- Det må være mulig å legge til en ny kamp **uten restart**, og samme stadionprofil skal kunne gjenbrukes **etter kamp-spesifikk verifikasjon**, ikke ved blindt kopierte koordinater.

### Arkitektur — bruk adaptere, ikke duplisering
- **Core**: JobScheduler, MatchRegistry, ScanOrchestrator, BrowserPool, MeasurementNormalizer, QualityGate, HistoryStore, SyncQueue, AuditLog.
- **Provider adapters**: `rbk_checkout_edge` først; andre billettleverandører først når ny adapter er dokumentert og testet. Ikke anta at TicketCo/andre leverandører kan skannes som RBK.
- **Stadium profiles**: `lerkendal-v1` (60 sittefelt), `koteng-v1.8` (seks sittefelt), senere arenaer med egne versjoner. Profilen inneholder felt-ID, kapasitet, ståplassklassifisering, valideringsregler, layoutvariant, normaliseringspunkter og kalibreringsbevis.
- **Event profiles**: `event_key`, `team_key`, stadium, `kickoff_at`, checkout URL, salgs-/kategoriutvalg, bortefeltunntak, `profile_version`, status og eier-lease.
- **Database**: Lokal SQLite WAL som tåler krasj, med separate entiteter `teams`, `venues`, `profiles`, `events`, `scan_jobs`, `scan_runs`, `section_observations`, `quality_decisions`, `outbox`, `sync_receipts`, `forecast_snapshots`. UTC internt, Europe/Oslo i skjermbildet.
- **Cloud-sync**: separat adapter for gammel Lerkendal API og Koteng API; på lengre sikt én ny versjonert kontrakt som støtter vilkårlig profil, men først etter sikker migrering og rollbackplan.
- **UI**: lettvekts lokal admin (f.eks. FastAPI + lokal nettleser eller kompakt desktopapp), men ikke tung frontend før skannemotor og jobbkø er kvalitetssikret. UI må aldri ha direkte service-role-nøkler i nettleseren.

## 4. Jobber og planlegging
- En jobb per `event_key + kategori + profil`, ikke per lag. Flere lag/turneringer kan dele stadion, men aldri dataserie uten identisk kamp-ID.
- Timevis kontroll som standard; per-arena kontrollert frekvens og jitter for å spre belastning. Begrens parallellitet mot samme nettsted. Dedikert Edge-kontekst per jobb eller kontrollert pool med isolerte sessions.
- Monoton klokke internt for venting og en tids- og tidssonesikker avsparkgrense; stopp senest ved avspark, ikke etter eller på grunn av sommertidsskifte.
- Windows dvale/nettfeil/Edge-krasj: restart med kontrollert backoff, ingen catch-up-storm, ingen duplikatpublisering.
- OS-autostart **valgfritt** med Windows Task Scheduler (kun lokalt, krever operatørgodkjenning), automatisk gjenopptakelse, health-check, watchdog og tydelig stoppknapp.
- Leader lease i SQLite/lokal prosess + serverstyrt `scanner_id/lease` ved behov. På to PC-er med samme kamp skal bare én kunne sende publiserbare målinger. `source_run_id` må være idempotent ved retry.

## 5. Skannermotor, kart og profilkontroll
- Bygg `ScanObservation` med feltnavn, free, capacity, koordinat, tooltip-kilde, tidspunkt, pass-ID, kartgeometri, kildeprofil SHA og kategori. Del raw/observasjon fra normalisert/akseptert resultat.
- Koteng: behold den eksisterende dobbelpassmotoren og profil-SHA; 1294×642 CSS viewport og 90 % zoom. Geometri er CSS-piksler og må aldri forveksles med bildepiksler. På annen skjerm bruk viewport-lås når mulig; hvis ikke, stans for re-kalibrering.
- Lerkendal: bevar de 60 kjente feltene, kapasitetene og manuelle bortefelt-regler; felt som er låst er ikke solgt, og ståplassstatus er ukjent uten egen kilde.
- Ulik kategori: aldri kombiner «VIP», ordinær og andre kategorier uten eksplisitt dokumentert union og duplikatkontroll.
- 2+ uavhengige kontroller per felt; etterkontroll kun manglende/avvikende. På feil: klassifiser `wrong_section`, `tooltip_hidden`, `map_changed`, `category_changed`, `timeout`, `capacity_mismatch`, `partial_coverage`.
- Ikke stol på en gammel referanse når nye kamper har nytt layout. Krev signert/hash-verifisert profil og event matching. Gjør visuell rapport av kart/ankerpunkter for operatør, uten å publisere sensitiv lokal tilstand.

## 6. Datakontrakt og målekvalitet
Anbefalt normalisert skjema (før publisering):

```json
{
  "schema_version": 1,
  "scanner_id": "local-device-id",
  "event_key": "checkout-event-key",
  "team_key": "rbk-men",
  "venue_key": "lerkendal",
  "source_provider": "rbk_checkout_edge",
  "profile_version": "lerkendal-v1",
  "profile_sha256": "...",
  "category_key": "observed-category",
  "observed_at_utc": "2026-10-27T10:00:00Z",
  "section_count_expected": 60,
  "section_count_verified": 60,
  "available_seated": 0,
  "sections": [{"code":"EXAMPLE","free":0,"capacity":1,"passes":2}],
  "standing_availability": "unknown",
  "locked_sections": [],
  "quality_status": "local_verified",
  "publication_status": "not_published",
  "run_id": "unique-id"
}
```

**Merk:** `0` i JSON over er en ren skjemaeksempelverdi, ikke en virkelig måling.

Valider før `local_verified`: alle påkrevde felt i valgt arena, ingen duplikater, free heltall 0..capacity, samsvarende kapasitet og sum, to uavhengige pass, ingen uklar kategori, ingen uforutsette låste felt, korrekt URL/arrangement/profil. `published_observed` kan kreve ytterligere godkjenningsregler per arena.

Offentlig publikumsmetrikk = **antall sitteplasser observerbart tilgjengelig å kjøpe i valgt billettkart/kategori**. `estimert utilgjengelig` = separat og tydelig merket differanse fra *dokumentert sammenlignbar kapasitet*. Aldri kall dette `solgte` uten verifiserte salgskilder. Ståplasser/ikke åpne felter skal ikke oppblåse antall ledige.

## 7. Synk, offline og sikkerhet
- Durable outbox: lokal SQLite-rad med payload-hash; send først etter quality gate. Ved nettfeil behold målingen og retry eksponentielt med jitter. Bekreft svar + samme `run_id` før status `sent`.
- Feilede forsøk skal ikke gjøre UI-tall null; behold siste gyldige punkt og merk dataalder.
- Secret-injeksjon via Windows Credential Manager eller lokal hemmelig fil med restriktive NTFS-rettigheter (aldri i Git). Bruk minste rettigheter, skil scanner-token fra database service-role.
- RLS/kategorifilter i frontend skal fremdeles hindre at `pending`/`rejected` blir offentlig. API-et skal avvise gammelt/stale/duplikat event-id/kapasitet/feil profil.
- Logg uten personopplysninger, tokens eller cookies. Maskér query-parametre, begrens diagnostikkretensjon og lag versjonsstemplede logs.
- Respekter RBKs tilgjengelighet, begrens forespørsler og innfør stopp ved blokkering/403/429. Ingen CAPTCHAs eller autentiseringsomgåelse.

## 8. Testing — absolutt nødvendig
- Unit: parser, tolkningsregler, summer, låste felt, kodegeometri, UTC/DST, scheduler, database-transaksjoner, idempotens, statusmaskin.
- Fixtures: Lerkendal 60/60 og Koteng 6/6; bevisst feilkapasitet, feil kategori, én manglende sektor, to motstridende pass, endret sidezoom, smal skjerm.
- Integrasjon: fake Edge/Playwright før live, SQLite-krasj midt i skriving, nettfeil mens opplasting pågår, gjenopprett etter PC-dvale, to samtidige identiske kampjobber, flere uavhengige kampjobber.
- End-to-end lokalt på PC: minst to separate kamper i kø, faktisk Edge, full lagring og trygg opplasting til testmiljø; kontroller at gamle Lerkendal-målinger og Supabase-tabeller er uendret.
- Regresjonssuite: kjør **alle** eksisterende tester i `scanner/tests/` og `baselines/koteng/v2.4/tests/`, ingen fallende tester. Ingen GitHub Actions brukes.
- Mål: 100 % feltdatasamsvar i verifiserte snapshots, 0 tverrkamp-lekkasjer, 0 uverifiserte publiseringer, ingen datatap ved nettfeil. Målt skannetid, P50/P95, CPU/RAM og feilrate; ikke oppgi fiktive ytelsestall.

## 9. Faser og obligatoriske leveranser

### Fase 0 — Arkivering og baseline
- Importer V2.4 med SHA-verifiserende script, commit alle 41 ikke-hemmelige kildefiler, tester og referansebilder.
- Identifiser hver av de to Lerkendal-kjøringene (inkludert cup) på operatør-PC; noter aktiverte event-nøkler, faktisk kodecommit/lokal filhash og unntak. Ikke kopier tokens/historikk.
- Skriv `docs/SCANNER_BASELINE_AUDIT.md` med verifisert kodeversjon, skjerm/Edge, teststatus, konfigurasjoner og event ID per kjøring.
- Kjør eksisterende regresjonstester, dokumenter feil.
- **Gate**: Ingen ny koding før disse baseline-bevisene er sjekket inn og reviewet.

### Fase 1 — Felles datamodell og lagring
- Foreslå og implementer adaptergrensesnitt i nye moduler. Legacy-skript forblir urørt. Beskriv migreringsplan for gamle historikkfiler uten produksjonsskriving.
- SQLite + outbox + quality gate. Enhets- og simuleringstester.
- **Gate**: samme resultater som legacy på fixtures, ingen manglende felt eller tverrkamp-tall.

### Fase 2 — Flerkamp, robust timeskanning
- Lokal admin viser flere kamper; nye kamper uten restart. Edge-kontekster og jobbplan med kontrollert concurrency.
- Lease/idempotens, restart etter feil, stopp ved avspark, status og audittrail.
- **Gate**: 48 timer lokal simulering med 3 kampjobber, feilinjeksjon og null dupliserte publiseringer.

### Fase 3 — Arena-/tilpasningsmotor
- Versjonerte Lerkendal- og Koteng-adaptere, visuell ankerkontroll, opplæringsflyt med manuell godkjenning.
- Opprette ny kamp på kjent arena uten å starte motoren på nytt; godkjenn alltid billettkategori/kamp-ID.
- **Gate**: V19.1 og V1.8-kvalitetskontroller bevares eller forbedres på fysisk PC.

### Fase 4 — Supabase og frontend-integrasjon
- Oversett intern kontrakt til eksisterende to ingest-endepunkter i første omgang. Planlegg eventuell felles DB-API-migrering separat med RLS, QA og rollback.
- Ingen endringer i `web/` eller Supabase produksjon uten staging + eiergodkjenning. Kontroller RBK/RBK Kvinner-lagfiltrering og historikk.
- **Gate**: test av én virkelig ny godkjent scan per arena; verifisert match_id, tid, seksjoner og sum i UI.

### Fase 5 — Drift og avanserte funksjoner
- Windows MSI/MSIX/installer først etter funksjonell stabilitet; signering og autostart. Konfigurerbar frekvens og retry, PC-/Edge-helse, eksport av supportpakke uten hemmeligheter.
- Flere leverandører/arenaer kun som selvstendige adapterprosjekter. Prognoser/cache, varselgrenser, stadionvarmekart, rekordmodul etter riktig historikk.
- **Gate**: driftsmanual, sikker rollback og godkjent pilot med minst tre reelle kamper (kan være på ulike tidspunkt).

## 10. Rapportering fra agenten
Ved hver PR: (1) kode som er endret, (2) hvilke baselines som ble brukt, (3) faktisk kjørt testkommando + resultat, (4) hvilke scenarioer som er kun simulert, (5) Edge-skjermbilder/diagnostikk **lagret lokalt**, (6) ingen produksjonsendringer uten tillatelse, (7) ytelsestall, (8) kjente begrensninger, (9) rollback.

**Startoppgave for lokal agent:** Kun Fase 0: hent allerede arkivert Koteng V2.4 fra Git, sammenlign alle lokale skannermapper mot baselines, dokumenter versjoner og kjør tester. Ikke redesign grensesnitt, endre skannemotor eller Supabase ennå.