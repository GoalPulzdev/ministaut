# Supabase GoalPulz Sql

Prosjektref: `khetbokxbcujwcurvviu` (eu-central-1). Opprettede `ministaut_` tabeller: `matches`, `sections`, `scans`, `section_measurements`, `scanner_tokens` og `scan_jobs`. Alle har RLS. Kun publiserte kamper og godkjente målinger kan leses anonymt.

Den aktive Edge Function er `ministaut-ingest`. Endepunktet er autentisert med `x-ministaut-token` som sammenlignes mot SHA-256-hash lagret i databasetabellen `ministaut_scanner_tokens`. En privat token skal ALDRI commit'es.

Et fullstendig resultat bestaar av 60 registrerte sittefelt, eller 58-59 registrerte sittefelt og 1-2 bekreftet laaste felt. Ett felt som bare har 0 ledige er ikke dokumentasjon pa bekreftet utsolgt.