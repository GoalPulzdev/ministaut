# Ministaut — masterplan 2026–2027

Oppdatert 24.10.2026 · Eies av Goalpulz AS · Repository: GoalPulzdev/ministaut

## Formål og viktigste prinsipp
Bygg Ministaut trinnvis fra en korrekt offentlig måler av **faktisk tilgjengelige sitteplasser** til en interessant supporterside med historikk, stadionkart, prognoser og varsler. Dataene kommer fra godkjente, sammenlignbare skanninger av RBKs billettkart. **Redusert tilgjengelighet er ikke det samme som bekreftede salg.** Ikke presenter utilgjengelig kapasitet som solgte billetter. Verifiser begge kamper og alle 60 relevante sittefelt før en telling publiseres.

## Arbeidsregler for hver fase
- Én liten leveranse, egen branch og PR, datatest og kontroll av frontend; deretter merge til main.
- Bevar PC-skanneren, automatiske timesjekker, opplasting, Supabase og eksisterende nettside. Ingen omskriving av skannermotor ved frontendarbeid.
- Tidsstempler i Europe/Oslo i UI; bruk UTC i database. Ferskhetsindikator når tellinger er forsinket.
- Hver kurve og endringsberegning må sammenligne samme kamp og samme konfigurasjon av låste/utelatte felt.
- Før datadrevne konklusjoner: kontroller hull i måleserien, skannerfeil, større feltendringer og eventuelle tilgjengelighetsøkninger.
- Ikke legg inn abonnements-/kontaktinnsamling eller offentlige «utsolgt»-påstander før samtykke, sikkerhet og prediksjonsvalidering er på plass.

## Fase 1 — Billettpuls (START HER)
**Minste leveranse:** Vis endring i tilgjengelige sitteplasser omtrent siste døgn i kampdetaljen. Bruk reelle godkjente tellinger; vis faktisk målt tidsintervall, og vis «For få målinger» i stedet for å dikte en 24-timers verdi. Ingen ny API eller database.
**Senere i fase 1:** Mål endring per døgn over 7 dager, tempoøkning/nedgang, korte statusetiketter som kalibreres mot egen historikk; ikke kalle verdien salgstakt uten forklaring.
**Godkjenningskrav:** Korrekt kamp, riktig tidsgap, kildekonfigurasjon og null/no-data; nye data oppdaterer UI uten race conditions; mobil fungerer.

## Fase 2 — Interaktivt tribunekart
**Minste leveranse:** Oversikt over 60 sittefelt med tall for ledige seter per felt, sortert/stedsplassert etter faktisk stadiumsoppsett. Klikk på felt viser siste måling og historisk endring. Bevar totaltall fra samme skannerunde.
**Senere:** Vis 24t-animasjon og endringer per seksjon.
**Godkjenningskrav:** 60 av 60 korrekte felt; ingen sammenblanding av kamp-ID, felt-ID, ståplass eller ulike snapshots; mobil/tastatur; manglende felt skjules/merkes, ikke settes lik null.

## Fase 3 — Kjøpsmønstre
**Minste leveranse:** En enkel graf med gjennomsnittlig målt reduksjon i tilgjengelighet etter «dager til avspark», basert på flere kamper med sammenlignbare dekninger.
**Senere:** Måle endringer før/etter billettslipp, siste 72/24 timer, helg/ukedag, motstander og tabellplassering.
**Godkjenningskrav:** Tydelig skille mellom tilgjengelighetsendringer og salg; minstekrav til datagrunnlag og rens av skannerfeil.

## Fase 4 — Rekorder og kampsammenligninger
**Minste leveranse:** Rekordoversikt fra faktisk registrerte skanninger: største fall i tilgjengelighet over et dokumentert døgn, laveste målte ledighet, raskeste målte reduksjon. Sammenligning bare ved samme dager til avspark.
**Senere:** Historiske serie-/motstandermønstre.
**Godkjenningskrav:** Riktige tidsvinduer, samme feltsammensetning, ingen bekreftet tilskuertall/salg uten separat kilde.

## Fase 5 — Bedre prognosemotor
**Minste leveranse:** Logg hver utstedt prognose og test den mot senere faktiske tellinger. Skill kortsiktig trend fra kampdagsscenario, merk usikkerhet og maksimer ikke over siste tilgjengelige tall i den konservative modellen.
**Senere:** Kombiner 6/12/24/72t, historiske kampkurver, monotone tilgjengelighetsscenarioer og kalibrert prognoseintervall. Først når feilene er målt kan vi bruke ordet «sannsynlighet».
**Godkjenningskrav:** Backtesting mot hold-out-tidsperioder, rapport om medianfeil og dekning i intervall, robusthet mot lite/hullet datagrunnlag; aldri øvre verdi > siste måling.

## Fase 6 — Supportervarsler
**Minste leveranse:** Opt-in varsel om en kamp når tilgjengelige sitteplasser faller under en valgt terskel, kun på nye godkjente målinger. Start med enkel e-post og avmelding.
**Senere:** Seksjonsvarsler, aktivitetsvarsler og push.
**Godkjenningskrav:** Samtykke/personvern, avmelding, rate limit, deduplisering, robust datakvalitet og ingen varsler ved skannerfeil.

## Prioritert backlog
1. Fase 1A — døgnendring i kampdetalj (kan bygges umiddelbart)
2. Fase 1B — tempo/aktivitet etter nok historikk
3. Fase 2A — feltoversikt med data-audit
4. Fase 3A — kjøpsmønstergraf med minimum antall kamper
5. Fase 4A — rekorder
6. Fase 5A — prognoselogging og backtest
7. Fase 6A — enkelt opt-in varsel

## Utenfor scope nå
Ingen separat mobilapp, ekstra dashboards, betalte abonnement eller endring i Sportmonks-/fotballplattformene i dette prosjektet.

Status: Masterplan besluttet. Fase 1A startes nå; senere faser er ikke implementert.
