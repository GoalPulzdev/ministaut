# MINISTAUT V2 — multi-arena og mange samtidige kamper

Dato 2026-10-24 · Teknisk beslutningsdokument
Status: anbefalt ny arkitektur, IKKE implementert. PR #17 er en prototyp og skal ikke merges som endelig fler-kampmotor.

## Problem i eksisterende prototype
Kodeinspeksjon på `feat/ministaut-event-registry-20261024`:
- `scanner/hurtigkart.py` (ca. 843 linjer) har skanning, kampbytte, HUD, planlegger, lagring og opplasting i samme kjørende prosess. Én Playwright page og én `start_next_cycle` gjenbrukes mellom kamper.
- `scanner/match_config.py` har global `SEATS` fra `stadion_felt.json` og `assert len(SEATS)==60`: Lerkendal er bygget inn i datavalideringen.
- `scanner/publication.py` validerer 60 felt og bruker Lerkendal 21 423 og 19 015.
- `scanner/sync_ministaut.py` har hardkodede kapasitets-/feltsforutsetninger.
- `web/index.html` presenterer bare Lerkendal-SVG og hardkodet seksjonslogikk.
- EventRegistry er lokalt JSON-register og et enkelt round-robin-tillegg, ikke en driftsikker jobbkø. Tidspunkter må legges inn manuelt, uten uavhengig metadata-verifikasjon.
- Maskinen kan stoppe, Edge kan forsvinne, en kamp kan henge og blokkere andre, og ingen sentral tilstand gir oversikt over forsøkte/mislykkede skanninger.

## Produktmodell
Ministaut skal håndtere RBK herrer/kvinner, hjemme/borte, alle stadionarenaer og mange samtidige arrangementer — **så lenge billettleverandør og kart er støttet og lovlig tilgjengelig**.
Et arrangement må IKKE velge `venue` automatisk ut fra kjønns- eller hjemme/borte-etikett.
En kamps kjøpbare kapasitet er en *inventarprofil*, ikke automatisk stadions offentlig oppgitte kapasitet.
Ved bortekamp er det mulig at bare bortefeltet er tilgjengelig gjennom RBKs billettlenke; presenter da «Ledige billetter i dette salget», aldri «Ledige på stadion».

## Arkitektur
```
Admin / operator UI --> Supabase matches + venue_profiles + scan_jobs
                         |
                    scheduler (periodisk)
                         |
                 job queue with leases
                         |
             scanner workers (1..N)
            /           |            \
     Vivenu seatmap  Other adapter  General Admission
            \           |            /
                 normalized inventory snapshot
                         |
                strict validation layer
                         |
               immutable raw evidence
                         |
          accepted scans + section measurements
                         |
             public read API / Ministaut UI
```

### Datakontrakt
`events`: id, provider, event_key, checkout_url, club_team, home_away, opponent, venue_id nullable, timezone, kickoff_utc, state (draft/discovery/ready/monitoring/paused/completed/error), created_at.
`venue_profiles`: venue_id, display_name, geometry_version, verified_at, map_type, max_advertised_capacity (optional), sections.
`inventory_profiles`: id, event_id, provider_adapter, scope ('all_numbered_seats'/'away_allocation'/'mixed'/'general_admission'), expected_section_count nullable, inventory_hash, verified_at.
`scan_jobs`: id, event_id, scheduled_for, claimed_at, lease_expires_at, worker_id, attempts, status, idempotency_key, error_code. Unique constraint (event_id, scheduled_for).
`scan_runs`: id, job_id, started_at, finished_at, provider_map_version, quality_status, source_hash, raw_evidence_location.
`measurements`: run_id, section_code, product_category, measured_available, observed_capacity, visibility, coverage_status.
`event_snapshots`: event_id, observed_at, inventory_profile_id, comparable_fingerprint, available_count, accepted, display_unit, quality_summary.
`worker_heartbeats`: worker_id, last_seen, version, active_job.
`event_history`: end reason, ended_at, last accepted snapshot.
Never use unknown=0.

### Lifecycle / scheduling
- Draft → discover event → verify kickoff and valid checkout → discover map/inventory → approve profile → monitoring.
- Every *ready* event gets its own due time (e.g., 60 minutes from last completed scan), not a global once-an-hour queue.
- At each scheduler tick create due jobs for all monitoring events with kickoff > now. Coalesce overdue windows after downtime; never backfill fake measurements.
- Atomic claim: one worker per job, lease + heartbeat, reclaim abandoned lease, idempotency on upload.
- Per-provider throttling, bounded concurrency (start 1–2 workers), retries with exponential backoff and jitter, circuit breaker on CAPTCHA/login/layout change, per-run deadline. A single bad stadium must not stop others.
- 10–15 min before kickoff, last scan may be scheduled only if it can complete safely before kickoff; no publishes at/after kickoff.
- At `now>=kickoff_utc` mark event completed, cancel pending jobs, retain history and archive. Do not delete.
- Paused events remain visible to operators with reason; do not confuse `no data` with `0 available`.
- Start/end times in UTC, show Europe/Oslo on UI; user-supplied local time must be validated for DST ambiguity.

### Scanner adapters
A `ScannerAdapter` must expose `discover(event)`, `read_inventory(event, profile)`, `normalize(result)`, `verify(result, profile)`.
- `VivenuNumberedSeatsAdapter`: read verified map metadata, stable section identifiers and capacity, validated seats and locked/hidden status.
- `VivenuGeneralAdmissionAdapter`: only if provider exposes a **verifiable** allocation count; else do not publish counts.
- `KotengArenaProfile` built from actual Edge reconnaissance; never reuse Lerkendal coordinates.
- `LerkendalLegacyAdapter` wraps existing tested 60-field engine *without changing its behavior*. Legacy scanner is the rollback path.
- Future other ticket vendors require new adapters. Never infer availability from price categories or absence of selectable seats.

### Operational admin UX
One place to paste a checkout link, detect event metadata, preview venue/coverage, confirm kickoff and activate.
Table: active/draft/needs map/paused/completed; last scan, next scan, quality, venue, inventory scope, worker state.
Actions: Add, Pause, Resume, Scan now, Edit metadata, Archive. No restarts.
Audit trail for manual edits; do not expose private scanner tokens in browser.

### Public UX
One compact supporter page with separate men's/women's matches and clear home/away and venue labels.
- Main KPI: `Ledige billetter i [avlest salg]` with scope.
- 24h change from compatible inventory profiles, normalized explicitly when not exactly 24h.
- Dynamic stadium map only if verified geometry exists. Generic inventory list otherwise.
- Keep linear 12h scenario optional, and never say a *stadium* is sold out when only a subset of inventory is sampled.
- Completed events move to archive; no more stale "live" badges.

### Migration path and acceptance gates
**M0: Freeze** — keep current stable Lerkendal scanner running. PR #17 remains draft pending separate review; don't merge prototype scheduler into main as production.
**M1: Data separation** — additive Supabase schema/migration with event metadata/profiles and job/run tables, RLS, no changes to existing scans. Backfill two known Lerkendal fixtures with explicitly verified metadata.
**M2: Adapter extraction** — wrap unchanged Lerkendal reader, fixtures and exact historical count tests, validate all 60 + old output payload compatibility.
**M3: Queue & workers** — one worker first, two Lerkendal matches sampled independently, simulated timeout/crash/restart, duplicate upload test, cutoff test. Enforce site rate limits.
**M4: Operator UI** — add/remove/pause matches without starting/stopping service; per-match health and logging.
**M5: Koteng** — manual approved map probe; separate adapter/profile and fixture tests; no public numbers before accepted full scan.
**M6: Bortekamp** — prove what the link measures (whole arena or RBK away allocation), label scope explicitly, then support new provider if applicable.
**M7: Cutover** — dual-run old/new without duplicate public writes, compare 24h of counts, run rollback drill, enable new orchestrator after QA.

### Minimum tests before multi-game rollout
- 10 queued events, 2 workers, no double claims, fair scheduling; hung job does not block others.
- Per-event one-hour interval within tolerated drift, independent of number of active events.
- Process crash after sample/before upload and after upload/before ack; idempotence and recovery.
- New event added while scanning; no restart, no disruption.
- Unknown/changed seats, area partial scope, locked fields, GA unknown; reject publication.
- Kickoff passed during scan; reject late publication, archive once; no post-kickoff jobs.
- DST boundary Europe/Oslo and invalid time zone.
- Legacy Molde/Start 60/60 fixtures and old live data remain unchanged.
- RBK Kvinner event link does not default to Lerkendal.

## Immediate decisions
1. Use Supabase as source of truth for matches, profiles, jobs and public snapshots, with a locally running Windows/Edge worker initially. A cloud worker is optional only if supported by the ticket supplier, access policy and reliable infrastructure.
2. Separate orchestration from data acquisition; no hotfixes in the old 843-line monolith as the target architecture.
3. Treat Koteng and away allocations as discovery tasks, not enabled counting until validated.
4. Make observing 10+ fixtures demonstrably safe before claiming scalable multi-arena support.

Owner approval requested for switching implementation from PR #17 prototype to M0–M7 rebuild.
