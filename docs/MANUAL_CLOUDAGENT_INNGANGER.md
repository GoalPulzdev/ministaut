# Manual for cloudagent: lagre inngang per felt (Lerkendal)

Prosjekt: Supabase `khetbokxbcujwcurvviu`. SQL: `supabase/lerkendal_section_entrances.sql`.

## Mål
Ny kolonne `entrance` (text) i `public.ministaut_sections`, med inngang(er) for hvert av de 60 sittefeltene på Lerkendal, klar til visning: `"5"`, `"15 og 17"`. PRESSE har ingen oppgitt inngang (`null`). Kolonnen brukes bare til presentasjon.

## Steg
1. Les først (bare lesing):
   ```sql
   select section_code, capacity from public.ministaut_sections order by section_code;
   select policyname, cmd, roles from pg_policies where schemaname='public' and tablename='ministaut_sections';
   ```
   Forventet: 60 rader med samme feltkoder som i SQL-filen. Hvis koder mangler eller avviker, stopp og rapporter.
2. Kjør `supabase/lerkendal_section_entrances.sql` i én transaksjon. Kontrollspørringen i filen skal gi `felt=60, med_inngang=59`.
3. Verifiser offentlig lesing slik nettsiden gjør:
   ```bash
   curl -s 'https://khetbokxbcujwcurvviu.supabase.co/rest/v1/ministaut_sections?select=section_code,capacity,entrance&order=section_code' \
     -H 'apikey: sb_publishable_0JuYQgbiXWfx103zy7j85Q_muDiicIL'
   ```
   Forventet: 60 rader med de tre kolonnene. `select=*` skal feile hvis tabellen har andre kolonner. Det er riktig, fordi bare tre kolonner er åpnet.

## Ikke gjør
- Ikke endre `capacity`, feltkoder eller andre kolonner.
- Ikke endre `ministaut-ingest` eller andre tabeller.
- Ikke gi offentlig lesing av andre kolonner enn `section_code`, `capacity` og `entrance`.

## Tilbakerulling
```sql
drop policy if exists ministaut_public_sections_read on public.ministaut_sections;
revoke select on public.ministaut_sections from anon, authenticated;
alter table public.ministaut_sections drop column if exists entrance;
```

## Rapporter tilbake
Rapporten skal inneholde:
- Resultatet av kontrollspørringen.
- Utdraget fra curl-kallet i steg 3.
- Eventuelle avvik.
