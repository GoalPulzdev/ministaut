# Ministaut · UX-standard (Impeccable-vurdering, 2026-10-23)

**Publikum:** RBK-supportere som følger billettutviklingen på mobil og PC.  
**Oppgave:** Se hvor mange sitteplasser som faktisk er tilgjengelige, velge Rosenborg-kamp, følge endring over tid og gå direkte til RBKs billettsalg.

## Konsekvent designretning
- Mørk, stadioninspirert visning med rolig grønn fargebruk, myk kontrast og ett tydelig lyst kjøps-CTA.
- Én kampvelger: de store kampkortene. Ikke innfør en ekstra dropdown.
- Hovedmålet er `ledige sitteplasser`. Dette er bekreftede skanninger, ikke antall solgte billetter.
- Vis **færre/flere ledige sitteplasser** i stedet for negative tall uten forklaring. Skill mellom tilbakegang og økning i tilgjengelighet.
- Vis tidspunkt/relativ alder på siste godkjente måling. Etter 95 minutter vises nøytral «Ny telling avventes». Ikke antyd sanntid eller automatisk vellykkede timesjekker.
- Behold historikk kun som interaktiv graf, ikke duplisert tabell. Sammenlign bare tellinger med samme låst-felt-konfigurasjon.
- Gjør valgt kamp delbar som `?kamp=<event_key>`. Del-lenken skal aldri eksponere token/secrets.
- Bruk samme primære design på 320–1440 px; mobilvalg gir synlig overgang til detaljer. Minst 44 px trykkflater for interaktive knapper.
- Normal brødtekst 15–16 px, sekundærtekst minst 12 px med høy kontrast; tydelige tastatur-fokusrammer.
- Animasjon bare som tilstandsrespons; alltid `prefers-reduced-motion`.
- Bevar 60-felts kvalitetskontroll, Supabase, Edge-opplasting og siste 500 godkjente målinger. Web-polish endrer **ikke** datakilden.

## Impeccable-revisjon
| Område | Forbedring |
| --- | --- |
| Distill | Fjernet progressbaren som kunne forveksles med offisielle salg; beholdt én velger og én historikkgraf |
| Typeset | Justert skrifthierarki og kontrast; 44 px oppdateringsknapp |
| Layout | Samlet to endringsmålinger i én todelt flate, harmonisert spacing og border-radius |
| Clarify | Relative måletidspunkter, tydeligere retning på endringstall, stale-status uten falsk trygghet |
| Harden | Link til riktig kamp, direkte URL-valg, mobil-scroll, feilmeldinger, trygge fallback for klubbmerker |
| Optimize | Minigraf-tegning unngår unødvendig DOM-erstatning ved minuttrefresh |
| Polish | Samlet CSS i ett tokensystem, redusert doble overrides, fokus- og hover-tilstander, dark-only supporterprofil |

## Kvalitetssikring før ny merge
1. Test to kampkort, riktige Supabase-verdier, match-URL og direkte billettlenke.
2. Test ingen, én og flere målinger; endringer i låst-felt-konfigurasjon skal ikke blandes.
3. Test 75 min og over 95 min gammel skanning, inkludert nettverksfeil og tilbakekomst fra skjult fane.
4. Test i Edge/Chrome og på mobil (320/375/390 px og desktop), fokus med tastatur og graf på touch.
5. Vurder kontraster og touchmål; bekreft ingen horisontal overflow.
6. Kontroller ekte Vercel-deploy før du kaller endringen verifisert i produksjon.

Oppdatert med designprinsipper fra [Impeccable](https://impeccable.style/docs/) (audit, distill, typeset, layout, clarify, harden, optimize, polish). Dette dokumentet er prosjektets UX-kontrakt og erstatter ikke reell enhets-/nettlesertesting.
