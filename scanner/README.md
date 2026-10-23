# RBK Billettmonitor V21 – automatisk 3-timerskontroll, ledighetsgraf og kampstartprognose

**Bygget på den brukerbekreftede stabile V19.1.** Vi beholder muse-/hover-skanneren, 60 faste sittefelt, kampavhengige bekreftet låste bortefelt og kvalitetssperrene fra V18. De to knappene **Ny sjekk** og **Bytt kamp** som ble rettet i V19.1 er bevart.

## Start på Windows

1. Avslutt V19.1 (Python-vinduet og skannerens separate Edge-vindu) før du starter V20.
2. Pakk ut hele ZIP-filen i **en ny mappe**.
3. Kopier dine egne data fra den gamle installasjonen om du har nye: **`historikk/`**, **`kampoppsett/`**, `lagrede_feltposisjoner.json`, `bekreftede_treff_v16.json`. Kopier kun nyere historikkfiler over demo/bundlet historikk. Ta sikkerhetskopi først.
4. Kjør `INSTALLER.bat` ved første installasjon i ny mappe (installerer også Python-tidssoneregisteret `tzdata` for Oslo-tid), deretter `START_BILLETTMONITOR.bat`.
5. Lim inn `https://billett.rbk.no/checkout/<kamp-id>`. Når stadionkartet er ferdig lastet, trykk ENTER **én gang** i kommandovinduet.
6. Første sjekk kjøres som i V19.1. **Deretter er automatisk sjekk hver tredje time PÅ som standard.** Resultater fra fullstendige kontroller lagres automatisk. Programmet beholder Edge-sesjonen og fortsetter å skanne inntil du velger «Avslutt sesjon» eller stopper programmet.
7. Bruk **«Åpne detaljert historikkgraf»** i Edge-panelet for en større, offline HTML-graf og måletabell. Bruk **«Ny sjekk»** eller **«Bytt kamp»** som før når det passer.

## Kontinuerlig drift: viktig begrensning

Automatisk tre-timerskontroll kjører **bare mens Python-prosessen, Edge og PC-en er åpne og våkne**. PC i dvale, lukket skannerprogram, nettverksfeil, Edge-feil eller et nytt innloggings-/billettflyt-vindu stopper eller forsinker sjekker. Etter en lang dvale vil programmet forsøke **én** ny måling når sesjonen fortsetter (ingen bølge av «innhentings»-sjekker). Ved feil under sidenavigering forsøkes ny sjekk etter rundt 15 minutter. Ingen skyserver, Windows-tjeneste eller planlagt oppgave installeres.

Bruk **scannerens dedikerte Edge-vindu** kun til overvåkning. Automatiske sideoppdateringer skal ikke avbryte en aktiv billettkjøpsprosess; bruk et annet nettleservindu til eventuelle kjøp. Programmet klikker ikke billetter og foretar ingen reservasjoner.

En ny periode på tre timer begynner **når en automatisk eller manuell skanning er avsluttet**. Panelet viser når neste sjekk er planlagt. Du kan slå automatikk av/på direkte i panelet. Dette valget lagres i `monitorinnstillinger.json` og beholdes ved neste oppstart. Manuell sjekk fungerer uavhengig av automatikk.

## Hva lagres etter hver sjekk?

Kun komplette kvalitetssikrede målinger legges i den godkjente historikken. Hver kjøring har `output/<dato_klokkeslett>/` med alle felt, feilrapport, offentlig PNG/HTML dersom godkjent, og en ny **`billettutvikling.html`**. En oppdatert lenke finnes også i `historikk/grafer/<kamp-id>/billettutvikling.html`. Upresise eller ufullstendige målinger lagres internt som feilrapport, men påvirker **ikke** prognosen eller grafen.

En historikk beholdes **separat per kamp-ID**. Prognosen tar også hensyn til bortefeltoppsett: en telling med to stengte bortefelt blir ikke blandet med en telling hvor bortefeltene er åpne. Eldre importerte målinger uten dokumentert bortefelt-/ståplassomfang holdes utenfor prognosegrunnlaget. Denne begrensningen er tilsiktet.

## Ledige og estimert solgte

- **Ledige** = antall sitteplasser som faktisk kunne kjøpes og ble avlest i offentlig kart. Dette er hovedtallet og brukes i grafen.
- **Estimert solgte / ikke tilgjengelige** = brukeroppgitt fast kapasitet **21 423** minus dokumentert ledige sitteplasser. Det er **ikke et bekreftet salgstall**. Reservasjoner, bortefelt og ukjent ståplassledighet inngår i differansen.
- Ståplassene `SB` og `ØVRE ØST` har ennå ukjent gjenværende ledighet; de blir ikke automatisk regnet som tilgjengelige.

## Prognosen

- Grønn linje = tidligere godkjente, observerte ledige sitteplasser.
- Oransje stiplet linje = **grovt ekstrapolert scenario**, ikke faktisk avlesning.
- Minst **4 sammenlignbare** historikkpunkter over minst **6 timer** kreves for å vise kampstartprognose.
- Mer enn **14 dager til kampstart** = vis historisk utvikling, men **ikke et tall for avspark**, fordi ekstern etterspørsel, billetter i nye kvoter og lag-/kamphendelser kan endre salget dramatisk.
- Innenfor 14 dager brukes en robust median trend fra tidligere punkter, maks 14 dager tilbake. Resultatet begrenses til en fysisk gyldig ledighet og gis et bredt scenariointervall. Båndet er **ikke et statistisk validert konfidensintervall**.
- Prognosen er for **ledige sitteplasser**, ikke antall faktiske solgte billetter. Intervall og prognose skal ikke brukes som garanti.
- Hvis kampstart ikke kan fastslås, måledata er få, eller kampen er avviklet, vises tydelig status i stedet for prognose.

## Grafen

Det grønne Edge-panelet har en kompakt graf, et scenariofelt, bryteren «Automatisk hver 3. time» og knappen «Åpne detaljert historikkgraf». Den detaljerte HTML-grafen viser tidskorrekte punkter, tilgjengelighetstabell, eventuelt prognose, og bruker norsk tidssone. Den fungerer uten internett når filen først er generert.

Det følger med `forhandsvisning/DEMO_historikk_og_prognose.png` og HTML med **syntetiske** tall slik at du kan vurdere layout. Disse tallene er ikke ekte billettstatus.

## Tester og oppgraderinger

Test med `python -m unittest discover -s tests -v`. Lokal test med `python hurtigkart.py --local-test --url file:///.../fixtures/demo_60_verified.html --test-cycles 2 --max-points 110` sjekker gjentatt skanning uten å lese RBKs nettside eller legge inn syntetiske data i godkjent historikk. Tidsplanen testes med simulert monotontid (ikke ved å vente tre reelle timer).

**V20 er ikke prøvd på din faktiske Windows Edge-installasjon eller gjennom en reell tre-timersperiode ennå.** Den eksisterende V19.1-motoren er beholdt, og en tilbakekopi av V19.1 anbefales. Det er tilsiktet at ingen offentlig graf publiseres dersom datakvaliteten ikke er bekreftet.


## GitHub-sikkerhet
Skannernokkelen ma opprettes lokalt. Bruk miljovariabel MINISTAUT_TOKEN eller .ministaut-token i scanner-mappen. Aldri commit nodler.