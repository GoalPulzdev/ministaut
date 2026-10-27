# Ministaut V2 - visuell kvalitetskontroll mot mockbilder

Primærreferanse: første sort-hvitt-gull mockbilde av Ministaut. Sekundærreferanse: kompakt dashboard fra mockbilde 2. Ingen demonstrasjonstall fra mockbilder skal brukes; data må komme fra Supabase og godkjente skanninger.

## Kriterier for 95 prosent likhet

Dette er et mål, ikke en målt score. Det krever ekte sammenlignbare nettleser-screenshots av V2 mot bildene.

- Hero, stadionfoto, lys, typografi og kronemerke: 20 prosent
- Navigasjon, spacing og sort/hvitt/gull/grå palett: 15 prosent
- Kampkort med dato, faktiske klubbmerker, ledige plasser: 15 prosent
- Dashboardgeometri, hovedtall, graf og prognose: 25 prosent
- Stadionkart, felt og lesbar tribuneoversikt: 15 prosent
- Responsiv mobil og tilgjengelighet: 10 prosent

Hvert område vurderes 0-100. Vektet sum minst 95 av 100, pluss full funksjonskontroll, kreves før merge. Oppdiktede statistikker eller feil kampmetadata er alltid blokkere.

## Gjennomført på V2-grenen

- Autentisk Lerkendal-hero med CC BY-SA-fotokreditering, gull/krem og sort-hvitt.
- Kronemerke og premium navigasjon.
- Kompakte lagvalg, kampkort med klubbmerker.
- Billettstatus, graf med valg 24t/7d/30d/alle, prognose og interaktiv tribuneoversikt.
- Opprinnelig V1, backend og skannermotor beholdt uendret.

## Test på PC

1. Opprett Vercel preview fra feature-grenen; ikke merge rett til main.
2. Fra repo-roten: node web/qa/v2-smoke.mjs. Fra web-mappen: npm run build.
3. Ta Edge eller Chromium-screenshots ved 1440x1080, 1280x800, 768x1024, 390x844.
4. Test valgene for RBK, RBK Kvinner, kampnavn, ekte avspark i norsk tid, historikkgrafer, valgt tidsrom, alle kartsektorer, feiltilstander og billettlink.
5. Legg faktisk V2-screenshot side ved side med godkjente mockbilder. Score komponentene ovenfor.
6. Publiser først når designscoren er minst 95/100 og funksjonelle tester er bestått.

Ingen faktisk screenshot av V2 ble verifisert i denne sesjonen. Vercel ga tidligere 403/404. 95 prosent er derfor ikke meldt oppnådd.
