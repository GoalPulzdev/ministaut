-- Register Rosenborg–Brøndby (UEFA Women's Europa Cup, 29.10.2026 18:00 Oslo) for Koteng scans.
-- Requires the multi-match ministaut-koteng-ingest (event_key looked up in this table).
insert into ministaut_koteng_matches (event_key, title, kickoff_at, venue_id, team_category, is_published)
values ('6ac390963b28cba4d656278f', 'Rosenborg – Brøndby', '2026-10-29T17:00:00Z', 'koteng_arena', 'women', true)
on conflict (event_key) do nothing;
