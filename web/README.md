# Ministaut frontend

Statisk nettleserklient for offentlige RBK-billettmålinger. Ingen skanner- eller databaseendringer er nødvendige.

## Utvikling og kontroller

Bruk Node 24. Verktøyene er kun utviklingsavhengigheter; nettleseren laster ingen rammeverk.

```sh
npm ci
npm run check
npm test
npm run build
python3 -m http.server 4173 --directory public
```

Åpne `http://localhost:4173/`. Testene kontrollerer beregninger, lagvalg, alle 60 stadionfelt, prognosenes ferskhet, DOM-referanser og produksjonspakken.

## Ansvar og kildefiler

| Fil | Ansvar |
| --- | --- |
| `index.html` | Semantisk sidestruktur; én hovedkilde |
| `assets/styles.css` | Farger, typografi, komponenter, responsivitet og fokus |
| `assets/app.mjs` | Tilstand, lesekall, renderingsflyt og interaksjoner |
| `assets/models.mjs` | Testbare beregninger uten DOM eller nettverk |
| `assets/stadium-layout.mjs` | Verifisert, uendret stadiongeometri |
| `assets/charts.mjs` | Grafdimensjoner som bevarer lesbar tekst |
| `assets/match-card.mjs` | Felles kampkort; trygg innsetting av kildetekst |

Kampkort og hovedmåling bruker samme døgnberegning. Samtidige identiske lesekall deler én forespørsel; de har 12 sekunders tidsgrense og ingen automatisk retry. Kartforstørring, grafperioder og vindusendringer gjør ikke nye datakall.

## Publisering og innbygging

`npm run build` lager `public/`, med identisk hovedside på `/` og `/v2`, samt uendret V1 på `/v1`. `v2.html` i kildekoden er kun en omdirigering som bevarer query og fragment. Rediger aldri en separat kopi av hovedsiden.

For Vercel: Root Directory `web`, Build Command `npm run build`, Output Directory `public`. For en annen statisk vert: publiser hele `public/`.

Ved innbygging på eksempelvis `/ministaut/` må **hele innholdet**, inkludert `assets/`, ikoner, manifest og service worker, ligge under den samme adressen. En tidligere løsning som bare kopierer `index.html` må oppdateres til å kopiere hele pakken. Bruk avsluttende skråstrek på katalogadressen. Relative ressursbaner, delingslenker og PWA-scope følger vertens adresse.

## Visuell kvalitetskontroll

Kontroller 1536, 820, 390 og 320 px. Hovedflyten er lag → kamp → nøkkeltall/graf → tribunefelt → billettlenke. Test også arkiv, tomme datasett, total nettverksfeil og «Prøv igjen», tastatur i graf/kart, kartforstørring, redusert bevegelse og delingsdialog.

Arkiv viser siste observerte ledighet, uten framtidsprognose eller kjøpsknapp. Målte tall og anslag skal holdes tydelig atskilt. Ledige plasser er aldri bekreftet salg, og ståplasser inngår ikke i sitteplassmålingene. Varsellevering krever eget endepunkt- og enhetstestløp; vanlige frontendtester skal ikke opprette abonnementer.
