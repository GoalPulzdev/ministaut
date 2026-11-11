-- Lerkendal: inngang per sittefelt, til presentasjon (f.eks. «Inngang 15 og 17»).
-- Kilde: billett.rbk.no (feltets infoboks), lest av Lerkendal-motoren og stabil
-- i 200 av 200 skanninger t.o.m. 11.11.2026. PRESSE har ingen oppgitt inngang.
-- Feltet brukes bare til visning; ingest og kvalitetskontroll bruker det ikke.

alter table public.ministaut_sections add column if not exists entrance text;
comment on column public.ministaut_sections.entrance is
  'Inngang(er) for feltet til visning, f.eks. "15 og 17". Kilde: billett.rbk.no. Null = ikke oppgitt.';

update public.ministaut_sections s
set entrance = v.entrance
from (values
  ('A', '5'),
  ('AA', '2 og 6'),
  ('AB', '1'),
  ('B', '5'),
  ('BA', '2 og 6'),
  ('BB', '1'),
  ('C', '5'),
  ('CA', '2 og 6'),
  ('CB', '1 og 7'),
  ('D', '5'),
  ('DA', '3'),
  ('DB', '1 og 7'),
  ('E', '5'),
  ('EA', '2 og 6'),
  ('EB', '7'),
  ('F', '5'),
  ('FA', '2 og 6'),
  ('FB', '7'),
  ('G', '5'),
  ('GA', '2 og 6'),
  ('GB', '7'),
  ('HB', '8 og 11'),
  ('I', '13'),
  ('IB', '8 og 11'),
  ('J', '13'),
  ('JB', '8 og 11'),
  ('K', '13'),
  ('KB', '8 og 11'),
  ('LB', '8 og 11'),
  ('MA', '15'),
  ('MB', '14'),
  ('N', '16'),
  ('NA', '15'),
  ('NB', '14'),
  ('O', '16'),
  ('OA', '15 og 17'),
  ('OB', '14'),
  ('P', '16'),
  ('PA', '15 og 17'),
  ('PB', '14'),
  ('PRESSE', null),
  ('Q', '16'),
  ('QA', '15 og 17'),
  ('QB', '14'),
  ('RA', '17'),
  ('RB', '18'),
  ('SA', '17'),
  ('TA', '21 og 22'),
  ('TB', '24'),
  ('U', '23'),
  ('UA', '21 og 22'),
  ('UB', '24'),
  ('V', '23'),
  ('VA', '21 og 22'),
  ('VB', '24'),
  ('W', '23'),
  ('WA', '21 og 22'),
  ('WB', '24'),
  ('XA', '21 og 22'),
  ('XB', '24')
) as v(section_code, entrance)
where s.section_code = v.section_code;

-- Kontroll: forventet 60 felt totalt, 59 med inngang, 1 uten (PRESSE).
select count(*) as felt, count(entrance) as med_inngang from public.ministaut_sections;

-- Offentlig lesing av referansedata for nettsiden: bare disse tre kolonnene.
grant select (section_code, capacity, entrance) on public.ministaut_sections to anon, authenticated;
do $$ begin
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='ministaut_sections'
                 and policyname='ministaut_public_sections_read') then
    create policy ministaut_public_sections_read on public.ministaut_sections
      for select to anon, authenticated using (true);
  end if;
end $$;
