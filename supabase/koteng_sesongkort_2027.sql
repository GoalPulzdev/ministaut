-- Sesongkort Koteng Arena 2027 (RBK Kvinner). Vises på nettsiden uten avspark,
-- som sesongkortet for Lerkendal. Hvis kickoff_at er NOT NULL i tabellen, bruk
-- '2026-12-31T23:00:00Z' (salgsstart oppgitt på billettsiden) i stedet for null.
insert into ministaut_koteng_matches (event_key, title, kickoff_at, venue_id, team_category, is_published)
values ('6acc9e4a3549bc0f9595cfb4', 'Sesongkort Koteng Arena 2027', null, 'koteng_arena', 'women', true)
on conflict (event_key) do nothing;
