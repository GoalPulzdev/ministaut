# Ministaut — samlet utviklings-, leveranse- og statusrapport

**Dato:** 24. oktober 2026  
**Eier:** Goalpulz AS  
**Repository:** [GoalPulzdev/ministaut](https://github.com/GoalPulzdev/ministaut)  
**Publikumsside:** [tipspanelet.no/ministaut](https://tipspanelet.no/ministaut)  
**Status:** Avsluttede leveranser til og med PR #16 er brukerakseptert/lukket. Videre produktutvikling fortsetter etter [masterplanen](MASTERPLAN_MINISTAUT_2026.md).

## 1. Sammendrag

Ministaut er bygget som en RBK-fokusert billettpuls for Lerkendal. Systemet måler **faktisk tilgjengelige sitteplasser** i Rosenborgs billettkart og viser det offentlig med historikk, kampvalg, endringshastighet, en forsiktig prognose og et interaktivt stadionkart.

Prosjektet er nå et samlet system med lokal Windows/Edge-skanner, Supabase-lagring og statisk Vercel-frontend. De to aktuelle kampene i perioden er Rosenborg–Start og Rosenborg–Molde. Målinger holdes separat per kamp. Automatisk kontroll er konfigurert for omtrent **hver time** når Windows-PC-en og skanneren er i drift.

Det siste avsluttede utviklingssteget er **PR #16: feltvise endringer, varmekart og målte rekorder**. Coop VIP-justeringen og kartets geometri ble lukket før denne leveransen.

**Grunnregel:** «Ledige sitteplasser» er primærmålet. `21 423 - ledige` er *estimert utilgjengelig kapasitet*, **ikke verifisert solgte billetter**. Differansen kan omfatte sperrede områder, reserverte seter, ståplasser og andre ikke-kjøpbare plasser.

## 2. Teknisk arkitektur

| Komponent | Implementasjon | Ansvar |
| --- | --- | --- |
| Lokal innsamlingsmotor | Python / Playwright / Microsoft Edge, fra kjent fungerende V19.1-baseline videreført i V20/V21 | Lese billettkartet, måle og kontrollere setefelt |
| Automatikk | Lokal scan-scheduler, standard én time | Starte nye kontroller når PC/prosess/Edge er tilgjengelig |
| Opplasting | `scanner/sync_ministaut.py` og Supabase Edge Function `ministaut-ingest` | Sende godkjente hele målinger, beholde kø ved nettverksfeil |
| Database | Supabase GoalPulz Sql | Separate kamper, tellinger, 60 feltdetaljer per hel måling |
| Nettside | Statisk `web/index.html` på Vercel | Kampvalg, pulsgraf, prognoser, feltkart, varmekart og rekorder |
| Regresjonstester | `web/stadium-layout.test.cjs`, `web/section-insights.test.cjs`, scannerens tester | Kontroll av geometri og innsiktsberegninger |

**Datamodell:** `ministaut_matches`, `ministaut_scans` og `ministaut_section_measurements`. En godkjent telling for fullt åpent kart inneholder 60 sittefelt. De 60 faste feltene representerer **19 015 seter**. `SB` og `ØVRE ØST` er ståplassområder og inngår ikke i den målte ledigheten.

Databasen skal ikke få demodata som ekte billetttellinger. Offentlig visning er avgrenset til publiserte kamper og godkjente tellinger; gjennomgå RLS ved senere API-endringer. Hemmelige skannertokens skal aldri legges i Git.

## 3. Bygget og levert — kronologisk

### 3.1. Grunnlag, PC-skanner og to-kamps drift — 23. oktober

- Opprettet eget `ministaut`-repo, web-, scanner- og Supabase-komponenter.
- Beholdt fungerende V19.1-baseline for Windows/Edge og kontrollene **Ny sjekk** / **Bytt kamp**.
- Etablert timeplan for automatiske tellinger, forutsatt at lokal PC er våken og skanneren kjører.
- Opprettet opplastingsflyt for godkjente hele målinger med `source_run_id` for duplikatkontroll og lokal ventekø for sending.
- Bygget offentlig kampoversikt med separate tellinger/historikk for **Rosenborg–Start** og **Rosenborg–Molde** samt automatisk frontend-oppdatering omtrent hvert minutt.
- Publisert via Vercel med statisk frontend og Supabase som datakilde.

**Viktig driftsavgrensning:** PC-en kan gå i dvale, restarte ved sikkerhetsoppdateringer eller bli lukket. Da stopper lokale kontroller; ingen nye målinger skal konstrueres for manglende perioder. Brukeren identifiserte en lokal sikkerhetsoppdatering som årsaken til nattoppholdet 23.–24. oktober og lukket driftsfeilpunktet.

### 3.2. Publikumstilpasset web, V3/V4 og billettpuls

Implementert gjennom [PR #1–#6](https://github.com/GoalPulzdev/ministaut/pulls?q=is%3Apr+is%3Aclosed):

- Rent, kompakt RBK-inspirert mørkt uttrykk med bedre typografi og mobilvisning.
- Store kampkort som eneste kampvelger; riktige motstandermerker der tilgjengelig.
- Hovedtall: ledige sitteplasser i valgt kamp; endring fra første og forrige relevante telling.
- Direkte billettknapp til korrekt kamp.
- Interaktiv historikkgraf med mus, tastatur og mobil/touch; tydelige tidspunkt og endringer.
- Små trendgrafer i kampkort.
- Bevaring av valgt kamp, delbar `?kamp=`-lenke, racetolerant datahenting og skånsom oppdatering.
- Fjernet dupliserende historikktabell og unødvendige forklaringer.
- «Siste telling»-indikator med stale-varsel dersom oppdateringen er mer enn omtrent 95 minutter gammel.

### 3.3. Prognose og usikkerhet — PR #7–#11

- Konservativ modell for **forventet antall ledige sitteplasser ved avspark**, ikke verifisert salg.
- Kvalitetskriterier for ferske og sammenlignbare målinger før tall vises.
- Tidligscenarioer kan vises langt før avspark, inntil 60 dager, men skal være tydelig merket som usikre.
- Historikk vises med heltrukket grønn kurve; estimert framtid med stiplet kurve og scenarioområde.
- Modellens prognose og spenn begrenses til intervallet fra null til sist observerte ledighet i den konservative modellen.
- Reduksjonstakt og scenariointervall ble justert for å unngå overdrevent brede eller urealistiske scenarioer.

**Ikke ferdig:** Full prognoselogging og etterprøvbar backtesting mot senere målinger. Nåværende prognose er en heuristisk framskriving, ikke en statistisk kalibrert sannsynlighet for utsolgt stadion.

### 3.4. Fase 1 — døgnpuls, ukespuls og tempo — PR #12–#13

- Opprettet [`MASTERPLAN_MINISTAUT_2026.md`](MASTERPLAN_MINISTAUT_2026.md), med seks produktfaser.
- **Døgnpuls:** beregner endring mellom målinger med cirka 18–30 timers avstand; viser virkelig antall timer.
- **Ukespuls:** utvikling målt over omkring sju dager når slik historikk finnes.
- **Tempo:** sammenligner observasjonstakt i påfølgende tidsvinduer, med nøkterne etiketter om raskere, langsommere eller stabil reduksjon.
- Viser «for få målinger» ved utilstrekkelig grunnlag; aldri fiktive salgstall.

### 3.5. Fase 2A — interaktivt Lerkendal-kart — PR #14–#15 og etterfølgende kartpatcher

- Offentlig visning av **alle 60 sittefelt** med målte ledige seter og feltkapasitet.
- Feltbaserte data fra samme godkjente scanrunde; sjekk mot både felttall og total målt ledighet.
- Skjematisk SVG-kart med Lerkendals fire tribunekanter; tilpasset mobil, klikk, tastatur og skjermleseretiketter.
- Tydelig merking av låste/ukjente felt og separat kontekst for ståplassene `SB` og `ØVRE ØST`.
- Stadiongeometrien ble bygget om til felles `pitchBox` / `stadiumFrame`, med sentrerte nord-/sørtribunerekker og pressefelt.
- **Coop VIP U/V/W** ble flyttet til egen korrekt stripe mellom øvrige Coop-feltnivåer, uten geometriske overlapp.
- `web/stadium-layout.test.cjs` kontrollerer 60 unike felt, kartgrenser, feltrekkefølge, riktig Coop VIP-topologi og null kollisjoner.
- Tribunedelen ble flyttet nedenfor billettgrafen, og de 60 feltkortene ble komprimert.

Utvalgte commits:
- [SVG-kart etablert](https://github.com/GoalPulzdev/ministaut/commit/e96532329c41f2cc6febd786b7a4593d742975ed)
- [Felles geometrisk forankring](https://github.com/GoalPulzdev/ministaut/commit/9b6cd719e677c0e4c27ebd69956ff176fdc4727a)
- [Coop VIP korrigert](https://github.com/GoalPulzdev/ministaut/commit/6eba1978f31bd5f1c1fc80e7506883200f72a245)
- [Coop-kartets regresjonstest](https://github.com/GoalPulzdev/ministaut/commit/599a6a82a00820300dc9df83b0f8486ec763cb68)

**Presisering:** Kartrektanglene er skjematiske feltposisjoner, ikke oppmålte setepolygoner fra den offisielle billettleverandøren.

### 3.6. Historisk import og begge kampene

Tidlige komplette og dokumenterte testsnapshots fra 23. oktober ble lagt inn i den faktiske Supabase-historikken, ikke simulert:

| Kamp | Måletid Europe/Oslo | Ledige sitteplasser |
| --- | --- | ---: |
| Rosenborg–Start | 23.10.2026 07:58 | 12 121 |
| Rosenborg–Molde | 23.10.2026 08:05 | 6 594 |
| Rosenborg–Molde | 23.10.2026 08:33 | 6 551 |
| Rosenborg–Molde | 23.10.2026 17:03 | 6 024 |

De tre første var verifiserte JSON-tester med komplett feltavlesning; kl. 17:03 var allerede registrert. Ytterligere godkjente målinger for begge kamper kom etterpå. Databasekontrollen 24. oktober viste blant annet:

- Rosenborg–Start: **11 990 ledige**, 24.10 kl. **09:49**.
- Rosenborg–Molde: **5 583 ledige**, 24.10 kl. **09:48**.
- Begge med **60 av 60 avleste sittefelt** og ingen låste felt i akkurat disse kontrollene.

Dette er **historiske observasjoner per tidspunkt**, ikke liveverdier eller bekreftede salg. Gamle filer fra **22. oktober** er identifisert som mulig ekstra historikk, men ikke dokumentert fullt kvalitetssikret/importert. De skal ikke behandles som godkjente før feltdekning og tidspunkt kan verifiseres.

### 3.7. Fase 2B / 4A-del: feltendringer, døgnvarmekart og rekorder — PR #16

[**PR #16: Feltvis endring, varmekart og målte rekorder**](https://github.com/GoalPulzdev/ministaut/pull/16) er slått sammen til `main` med merge-commit **`fc0453eea8dbff16a273b7a9887b805e566e8092`**.

Implementert på frontend:
1. **Klikk på et felt:** tilgjengelig antall nå, endring fra forrige sammenlignbare telling, endring fra en godkjent måling cirka 24 timer tidligere.
2. **Varmekart:** bytt mellom «Ledige nå» og «Endring siste døgn». Rød/oransje markering betyr størst *fall i tilgjengelighet*, blått betyr økt tilgjengelighet, nøytral grå/ukjent betyr utilstrekkelig sammenligning. Ingen tolkning som bekreftet billettsalg.
3. **Rekordkort:** laveste målte ledighet, største målte døgnreduksjon og raskeste målte reduksjon per time i et dokumentert 18–30 timers vindu.

Kvalitet:
- Samme kamp, godkjente målinger og identisk konfigurasjon av låste/utelatte felt.
- Kontrollerte feltrader, felt-IDer, kapasiteter og sum.
- Manglende historiske snapshots vises som manglende grunnlag.
- Frontend-endringer berører **ikke** scanner, Supabase-skjema eller historiske målinger.
- JavaScript-syntaks, snapshotvalg og seks varmekart-tilstander ble kontrollert i utviklingsøkten.
- Ny regresjonsfil: [`web/section-insights.test.cjs`](web/section-insights.test.cjs).

Brukeren godkjente og lukket leveransen i samtalen etter merge. **Det foreligger ikke dokumentert full visuell produksjons-/mobilaudit av PR #16** i den avsluttede arbeidsøkten. Ved siste konkrete sjekk etter merge viste Vercel fortsatt den *forrige* produksjonscommitten; dette må ikke tolkes som verifisert publisering av PR #16 før ny kontroll.

## 4. Sikkerhet, målekvalitet og sentrale prinsipper

- Publiser kun `reading_status=accepted` fra publiserte kamper.
- Ikke sammenlign forskjellige låste felt/andre dekningskonfigurasjoner som om de er like.
- Bare komplette, kontrollerte snapshots; feil ved lesing, ufullstendige felt eller sumavvik må ikke forurense historikk eller prognoser.
- Ikke omtal `21 423 - tilgjengelig` som faktisk solgte billetter.
- Vær tydelig på at ståplasser faller utenfor de 60 verifiserte sittefeltene.
- Webklienten har kun publiserbar Supabase-nøkkel; hemmelige skanner-/servernøkler må forbli private.
- Ved planlagte/uforutsette stopp på lokal PC blir det **hull i historikken**; disse skal ikke «fylles» med antatte målinger.
- Varmekartets fargeskala er en visuell kategorisering av målte differanser, ikke en kalibrert prosentmodell.
- Bruk målte faktiske tidsintervaller i grafer og rekorder.

## 5. Hva er ferdig, og hva står igjen?

| Del | Status 24.10.2026 | Merknad |
| --- | --- | --- |
| Windows/Edge-skanner og 60-felts avlesning | Levert og brukerprøvd | Avhengig av lokal PC/Edge |
| Timeskanning og to-kamps opplasting | Aktivert; observerte godkjente målinger | PC-oppdatering ga nattopphold; sak lukket etter kjent årsak |
| Supabase-lagring, grunnleggende kvalitetssperrer | Levert | Gamle 22.10-filer krever fortsatt audit |
| Offentlig Vercel-side, kampkort og interaktiv historikk | Levert | Ferskhet og kampvalg implementert |
| Fase 1A: døgnpuls | Levert | PR #12 |
| Fase 1B: ukespuls/tempo | Levert | PR #13 |
| Prognosescenarioer og graf | Levert som tidlige heuristikker | Backtesting mangler |
| Fase 2A: 60-felts stadionkart | Levert; Coop VIP lukket | Skjematisk geometrisk kart |
| Fase 2B: feltendring og varmekart | Levert i kode, PR #16 lukket | Full visuell QA bør dokumenteres |
| Fase 4A: enkle målte rekordkort | Levert i kode, PR #16 lukket | Mer historikk trengs for bredde |
| Fase 3A: mønstre per dager til avspark | Ikke levert | Neste anbefalte utviklingsfase |
| Fase 5A: prognoselogging/backtesting | Ikke levert | Krever evaluering over tid |
| Fase 6A: supporter-varsler | Ikke levert | Krever samtykke/avmelding og kontroll |

## 6. Anbefalt neste arbeidspakke

**Fase 3A — kjøpsmønstre/historiske sammenligninger**, men med disiplin rundt historikkmengde:

1. Sammenlign registrert tilgjengelighet mot antall dager til avspark per kamp.
2. Ikke gi en samlet «normal salgskurve» basert på bare én eller to kamper.
3. Støtt forklarlige målevinduer (siste 24/72 timer) når tilstrekkelig reell historikk finnes.
4. Kontroller dekning og kildekonfigurasjoner først; filtrer ufullstendige historikkpunkter.
5. Etabler etter hvert en sammenlignbar kampdatabase slik at fase 4-rekorder og fase 5-prognose kan kvalitetssikres.
6. Ta visuell QA av PR #16 på mobil og desktop når riktig Vercel-commit er bekreftet publisert.

Dette er neste leveranseforslag, ikke arbeid som hevdes ferdig.

## 7. Nyttige repo-referanser

- [Masterplan](MASTERPLAN_MINISTAUT_2026.md)
- [Webklient](web/index.html)
- [PC-skanner / dokumentasjon](scanner/README.md)
- [Opplastingsrutine](scanner/sync_ministaut.py)
- [Stadiongeometri-test](web/stadium-layout.test.cjs)
- [Seksjons-/varmekart-test](web/section-insights.test.cjs)
- [PR #12: døgnpuls](https://github.com/GoalPulzdev/ministaut/pull/12)
- [PR #13: ukespuls](https://github.com/GoalPulzdev/ministaut/pull/13)
- [PR #14: seksjonskart](https://github.com/GoalPulzdev/ministaut/pull/14)
- [PR #15: kompakt layout](https://github.com/GoalPulzdev/ministaut/pull/15)
- [PR #16: feltendringer, varmekart, rekorder](https://github.com/GoalPulzdev/ministaut/pull/16)

---

**Overleveringsstatus:** Fasen fram til og med PR #16 er lukket av produkteier. Dokumentet er en historisk statusrapport, ikke en bekreftelse på at samtlige fremtidige deler av masterplanen er implementert. Neste arbeidsøkt kan starte med fase 3A.
