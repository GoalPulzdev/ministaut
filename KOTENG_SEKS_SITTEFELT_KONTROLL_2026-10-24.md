# Koteng er ferdig kartlagt: kun 6 sitteområder

Dato: 24.10.2026 · Sted: Koteng Arena · Miljø: Ministaut V3 lokal Windows-test
Brukeren har bekreftet at **Felt 1–5 og VIP er samtlige sitteområder**.
**Vi skal ikke utføre mer generell stadionkartlegging på Koteng.**
Ståplass A er en separat kategori, og holdes utenfor sitteplasstallet.

| Sitteområde | Ledige, første observasjon | Feltkapasitet |
| --- | ---: | ---: |
| FELT-1 | 48 | 49 |
| FELT-2 | 125 | 160 |
| FELT-3 | 76 | 120 |
| FELT-4 | 138 | 152 |
| FELT-5 | 0 | 49 |
| VIP | 49 | 71 |
| **SUM** | **436** | **601** |

Tallene gjelder kun den første lokale opplæringsmålingen og er **ikke** dokumenterte solgte billetter eller hele Kotengs stadionkapasitet.

## Endring i programflyten
- **`scanner/START_KOTENG_OPPLAERING.bat`** kaller nå `START_KOTENG_KONTROLL.bat`.
- **`scanner/START_KOTENG_KONTROLL.bat`** kjører `python -m v3.verify_koteng`.
- `scanner/v3/verify_koteng.py` åpner Koteng-kartet i Edge, leser **kun lagrede punkter fra de seks bekreftede feltene**, kontrollerer tooltip mot referansekapasitet og gjør to feltkontrollrunder.
- Lokale `*.json`-rapporter under `scanner/v3_learning/koteng_arena/`. Manglende felt regnes aldri som null. Ingen opplasting til Supabase, ikke automatisk timeskanning.
- Profilkilde **`scanner/v3_profiles/koteng_arena.v1.json`** fra første fungerende opplæring eller `koteng_arena.v2.json` hvis en oppdatert profil er fullstendig.
- Profilen er fortsatt `verified=false`; det er korrekt inntil kontrollrunden på Windows har bestått. Ikke endre dette manuelt.

## VIKTIG ved ny nedlasting
ZIP fra GitHub inkluderer **ikke** lokalt innlærte hoverpunkter. Kopier følgende fra den forrige testmappen før du starter:
`scanner/v3_profiles/koteng_arena.v1.json`

Valgfritt hvis finnes: `scanner/v3_profiles/koteng_arena.v2.json`.

Behold begge profiler når du kopierer. Kontrollprogrammet velger nyeste **komplette** profil. V1-ankre brukes mot opprinnelig skjermgeometri fra den mottatte treningsrapporten (1600×960 px), mens V2 bruker den nye avgrensningen. Bland aldri koordinatsystemene.
Hvis profilen ikke finnes, gir programmet en forklarende feilmelding, i stedet for å starte nye 450 hoverpunkter.

## Lokal test
1. Last ned ny ZIP av `feat/ministaut-v3-phase1-foundation-20261024`, og pakk ut i ny mappe.
2. Kopier ovennevnte lokal profilfil inn i den nye mappen.
3. Åpne `scanner/START_KOTENG_KONTROLL.bat` (eller gammel `START_KOTENG_OPPLAERING.bat`).
4. I Edge: vis billettkart, avvis/lukk samtykkebanneret selv, trykk Enter i kommandovinduet.
5. To avlesningsrunder blir kjørt over de seks feltene, uten kjøp/reservasjon.
6. Send `scanner/v3_learning/koteng_arena/*_six_fields_verification.json` for datakontroll.

## QA-kriterier før ekte timeskanning
- 6/6 felt korrekt lest i begge runder.
- Alle kapasiteter stemmer med den bekreftede referansen.
- Ingen store motstridende ledighetstall mellom de to rundene.
- Ingen falske tilskrivninger fra hengende/foreldede tooltip-verdier.
- Kun etter godkjent QA kobler vi Koteng til planlegger, historikk og publisering.

Kode og nye tester er committet. **Ingen fysisk Windows/Edge-verifikasjon av ny kode er gjennomført av assistenten.**
