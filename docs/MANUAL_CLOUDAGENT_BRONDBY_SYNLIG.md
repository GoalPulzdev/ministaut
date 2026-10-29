# Manual for cloudagent: gjør Rosenborg–Brøndby synlig på Ministaut

Dato: 28.10.2026. Frist: **før avspark 29.10.2026 kl. 18:00 (Oslo) = 17:00 UTC**.
Prosjekt: Supabase `khetbokxbcujwcurvviu`. Repo: `GoalPulzdev/ministaut`, branch `feat/scanner-control-v0.2` (PR #27).

## Mål og ferdig-kriterium
Kampen **Rosenborg – Brøndby** (event_key `6ac390963b28cba4d656278f`, UWEC, Koteng Arena) skal vises på nettsiden under RBK Kvinner, med ledige plasser fra skanneren.

Oppgaven er ferdig når alle tre punktene stemmer:
1. Den offentlige REST-spørringen i steg 4 returnerer Brøndby-raden.
2. `ministaut_koteng_scans` har minst én rad med `reading_status='observed'` for Brøndby-matchen.
3. Røa (`6aaceecebfe408c38e1712dd`) får fortsatt nye skanninger.

## Status før du starter (verifisert 28.10 ca. kl. 11)
- **Edge-funksjonen `ministaut-koteng-ingest` er allerede deployet i flerkampversjonen.** Den svarer `503 {"error":"Event not published"}` for Brøndby, og den feilmeldingen finnes bare i den nye koden (`supabase/functions/ministaut-koteng-ingest/index.ts`, linje 34). Du skal **ikke** deploye funksjonen på nytt.
- **Det eneste som mangler er raden i `ministaut_koteng_matches`.** Den offentlige listen viser bare Røa.
- Operatør-PC-en (Scanner Control 0.2) skanner Brøndby og har Live på. Siste lokale måling ga 317 ledige, 6/6 felt. Målingen ligger i utboksen med status `venter` og prøves på nytt automatisk med økende ventetid, opptil 60 minutter mellom forsøkene. Nye timesmålinger kommer i tillegg. Du trenger ikke røre PC-en.
- Nettsiden (`web/index.html`, linje 1966) henter alle rader med `is_published=eq.true` fra `ministaut_koteng_matches`. Den bruker `team_category='women'` for å velge kvinnefanen og tabellen `ministaut_koteng_scans`, og viser skanninger med `reading_status in (observed,accepted)`. Raden alene gjør derfor kampen synlig, og ingen endring i frontend trengs.

## Steg

### 1. Les tabellstrukturen og Røa-raden (bare lesing)
```sql
select column_name, data_type, is_nullable, column_default
from information_schema.columns
where table_schema='public' and table_name='ministaut_koteng_matches'
order by ordinal_position;

select * from ministaut_koteng_matches where event_key='6aaceecebfe408c38e1712dd';
select * from ministaut_koteng_matches where event_key='6ac390963b28cba4d656278f';
```
- Hvis Brøndby-raden allerede finnes, går du til steg 3.
- Hvis tabellen har flere `NOT NULL`-kolonner uten default enn de som er satt i steg 2, kopierer du verdiene fra Røa-raden. Unntaket er felter som er kampspesifikke, som tittel, tidspunkt og URL. Dem setter du riktig for Brøndby.

### 2. Legg inn Brøndby
Det er samme innhold som `supabase/koteng_brondby_20261029.sql`:
```sql
insert into ministaut_koteng_matches (event_key, title, kickoff_at, venue_id, team_category, is_published)
values ('6ac390963b28cba4d656278f', 'Rosenborg – Brøndby', '2026-10-29T17:00:00Z', 'koteng_arena', 'women', true)
on conflict (event_key) do nothing;
```
- Tittelen bruker tankestrek (–), slik Røa-raden gjør. Sjekk skrivemåten mot Røa-raden.
- Avsparket er kl. 18:00 norsk tid. Det er vintertid (CET, UTC+1) fra 25.10, så tidspunktet blir `17:00:00Z`.
- Hvis `on conflict` feiler fordi `event_key` ikke har en unik-indeks, må du **ikke** legge til en indeks. Sjekk først med `select` at raden ikke finnes, og kjør så insert uten `on conflict`.

### 3. Hvis raden finnes, men ikke vises
```sql
update ministaut_koteng_matches
set is_published=true, venue_id='koteng_arena', team_category='women'
where event_key='6ac390963b28cba4d656278f';
```
Endre bare disse feltene, og bare på Brøndby-raden.

### 4. Verifiser offentlig synlighet (som nettsiden ser det)
```bash
curl -s 'https://khetbokxbcujwcurvviu.supabase.co/rest/v1/ministaut_koteng_matches?select=id,event_key,title,kickoff_at,venue_id,team_category&is_published=eq.true&order=kickoff_at.asc' \
  -H 'apikey: sb_publishable_0JuYQgbiXWfx103zy7j85Q_muDiicIL'
```
Forventet resultat er både Røa og Brøndby. Hvis Brøndby mangler her, men finnes i SQL, er det RLS. Sammenlign da policyene på tabellen, og se om Røa-raden har en verdi som Brøndby mangler. Ikke slå av RLS, og ikke lag en bred `select`-policy. Rett raden i stedet.

### 5. Verifiser at målinger kommer inn
Operatør-PC-en sender automatisk. Vent til neste forsøk, opptil cirka 60 minutter, og kjør:
```sql
select s.observed_at, s.available_seated, s.reading_status, s.created_at
from ministaut_koteng_scans s join ministaut_koteng_matches m on m.id=s.match_id
where m.event_key in ('6ac390963b28cba4d656278f','6aaceecebfe408c38e1712dd')
order by s.observed_at desc limit 10;
```
- Forventet er minst én Brøndby-rad med `reading_status='observed'` og cirka 300–320 ledige. Røa skal ha rader fra den siste timen.
- Hvis det ikke har kommet noe etter 90 minutter, ser du i loggene for edge-funksjonen (`ministaut-koteng-ingest`) etter Brøndby-kall. Svaret skal være 200. Hvis du ser 401 eller 403 (`deny`), betyr det at payloaden er avvist av kvalitetskontrollen. Rapporter da feilteksten, og ikke endre kontrollene.

## Ikke gjør
- Ikke deploy eller endre `ministaut-koteng-ingest` eller `ministaut-ingest` (Lerkendal).
- Ikke endre andre rader enn Brøndby, og ikke slett noe.
- Ikke endre RLS, skjema, indekser, kapasiteter eller kvalitetskrav.
- Ikke legg inn skanninger manuelt. Bare operatør-PC-ens verifiserte målinger skal inn.
- Ikke be om eller vis `.ministaut-token` eller service-role-nøkler, og ikke skriv dem i Git, logger eller chat.

## Tilbakerulling
Hvis kampen må skjules igjen:
```sql
update ministaut_koteng_matches set is_published=false where event_key='6ac390963b28cba4d656278f';
```
Skanneren får da 503 igjen og holder målingene i utboksen uten å miste dem.

## Rapporter tilbake
Rapporten skal inneholde:
- Brøndby-raden slik den står i databasen, med `id`, `title`, `kickoff_at`, `venue_id`, `team_category` og `is_published`.
- Utdraget fra REST-kallet i steg 4.
- Siste rader fra steg 5, både Brøndby og Røa.
- Eventuelle avvik fra denne manualen, og hvorfor.

Skriv rapporten som kommentar på PR #27.
