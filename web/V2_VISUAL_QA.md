# Ministaut visuell QA — 3. november 2026

Retning: sort/hvitt og dempet gull, redaksjonell typografi, kompakt kampvalg og stor, lesbar billettutvikling. Eksisterende stadionfoto og korrekt stadiongeometri beholdes; illustrerte konseptkart brukes aldri som datakilde eller feltoppsett.

## Kontroller

- Ekte offentlige lesedata: herrelag og RBK Kvinner, kommende og spilte kamper.
- Desktop 1536 × 1024, nettbrett 820 × 844, mobil 390 × 844 og 320 × 844.
- Ingen horisontal side-overflow; kampvelger og forstørret kart har avgrenset egen scrolling.
- Grafens viewBox følger tilgjengelig bredde. Aksetekst krymper ikke fra en fast 920-enheters tegning.
- Grafperioder, tastaturinspeksjon, kartets to modi, feltvalg og bevart markering.
- Kartforstørring med original geometri; feltlisten gir større trykkflater.
- Delingsdialog, Escape og lenker som følger aktuell vert.
- Arkiv har «Ledige ved siste måling» og skjuler kjøp/framtidsprognose.
- `/ministaut/` med moduler og lagvalg via query.
- Total 503-feil viser forståelig tilstand og synlig «Prøv igjen»; nytt forsøk kan hente data.
- Lint, beregningstester, geometritester, ferskhetstester og byggpakke kontrolleres i CI.

## Avgrensning

Chromium-validering erstatter ikke en siste kontroll på fysisk iPhone/Safari og Android. Varsellevering og opprettelse av abonnement er ikke utløst i QA. Ingen vilkårlig prosent- eller «10/10»-score brukes som bevis for visuell kvalitet.
