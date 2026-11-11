# Koteng Arena – første lokale stadionopplæring i Ministaut V3

**24. oktober 2026.** Verktøyet er en kontrollert **opplæringspilot**. Ikke en godkjent live-skanner.

## Filer du skal bruke
- **`scanner/START_KOTENG_OPPLAERING.bat`** – åpner en separat Edge-sesjon og lærer Koteng-felt fra synlige tooltip-verdier.
- `scanner/v3/learn_koteng.py` – selve opplæringsmotoren.
- `scanner/v3_profiles/koteng_arena.v1.json` – ny, *ikke-godkjent* Koteng-profil etter kjøringen.
- `scanner/v3_learning/koteng_arena/` – lokale rapporter og skjermbilder fra læring.
- `scanner/START_MINISTAUT_V3_TEST.bat` – eget kontrollpanel for lokal registrering og testplanlegging, **ikke** stadionopplæring.
- `scanner/START_BILLETTMONITOR.bat` – gammel **Lerkendal-skanner**; ikke bruk denne på Koteng.

## Fremgangsmåte for Windows
1. Avslutt eksisterende scanner og ta vare på den fungerende installasjonen.
2. Last ned fersk ZIP fra `feat/ministaut-v3-phase1-foundation-20261024` etter commit `db54647a`, pakk ut i egen mappe.
3. Kjør `scanner/INSTALLER.bat` hvis Playwright mangler.
4. Dobbeltklikk **`scanner/START_KOTENG_OPPLAERING.bat`**.
5. Ny Microsoft Edge med isolert opplæringsprofil åpner `https://billett.rbk.no/checkout/6aaceecebfe408c38e1712dd`.
6. Naviger i den nye Edge-sesjonen til **det synlige stadionkartet** og sørg for at felt kan gi tooltip når du holder musen over.
7. Klikk i kommandovinduet og trykk **ENTER** én gang når kartet er klart.
8. Programmet forsøker bekreftede hover-avlesninger for SVG-punkter og reservegrid; det klikker aldri seter.
9. Etter skanning les loggen, `v3_learning/koteng_arena/*_training.json` og kontrollér mot Edge-kartet.
10. Gjenta ved behov (eksempel `python -m v3.learn_koteng --max-points 900 --step 28`). Utkastet kan utvides; konflikt i kapasitet stopper oppdatering.

## Sikkerhets- og kvalitetsbegrensning
- Opplæring bruker **samme grunnmetode** som Lerkendal: hover + synlig ledig/kapasitet + flere stabile lesninger + lagrede koordinater.
- For Koteng er det ennå ikke bevist at alle felter kan leses på denne måten. Ingen telling eller full stadiondekning er garantert.
- Koordinater normaliseres til den oppdagede kartregionen. Dette er en ny profilegenskap; Lerkendal bruker banerelative referansekoordinater, som ikke skal konverteres blindt.
- Parseren for treningen tillater også nummererte sektorer, men andre tooltip-formater kan trenge tilpasning.
- Opplæringsresultat er **alltid `verified=false`**. Krever menneskelig stadfesting av alle felt/kapasiteter og ny verifikasjon før automatisk telling kan kobles til.
- Ingen Supabase-opplasting, billettkjøp, billettreservasjoner eller endringer i gammel Lerkendal-kode.
- En godkjent profil overskrives ikke fra læringsverktøyet.

## Status mot V3 fase 1–4
- Lerkendal: gammel scanner bevart; import av 60 faktiske felt og bekreftede punkter til V3 som *utkast*.
- Koteng: nå eget operatørstyrt hoveropplæringsverktøy. Ikke fysisk kjørt mot Koteng i Edge av utviklingsagenten.
- Ny fler-kampplanlegger: isolert testkode; ikke koblet til faktisk Playwright-telling.
- Lokal admin: grafisk `START_MINISTAUT_V3_TEST.bat` (staging); ikke full publiseringsadmin.

Slik at Koteng kan godkjennes, trengs minst komplette opplæringsrapporter, sammenligning med billettkartets faktiske feltliste, og integrert lesemotor som tester alle profilfelter.
