-- Ministaut Fase 2A: allow public read of section measurements ONLY for
-- accepted scans of published matches. Reference capacities are stored in
-- every section measurement; no need to expose the sections table.
grant select on public.ministaut_section_measurements to anon, authenticated;
create policy ministaut_public_section_measurements_read
on public.ministaut_section_measurements for select to anon, authenticated
using (
  exists (
    select 1 from public.ministaut_scans s
    join public.ministaut_matches m on m.id=s.match_id
    where s.id=scan_id
      and s.reading_status='accepted'
      and m.is_published=true
  )
);
-- Applied to Supabase GoalPulz project 2026-10-24.
-- Before replaying on another environment, check pg_policies to avoid duplicates.
