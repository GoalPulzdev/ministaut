# Koteng Arena V2.4 – komplett Windows-installering

V2.4 er en **selvstendig installasjon**, bygget fra den brukerbekreftede Koteng V1.8 skannemotoren. Det er **ikke nødvendig** å ha V1.8 eller V2.2 på den nye PC-en. Dette gjelder **kun RBK Kvinner mot Røa 1. november 2026 kl. 14.30**, ikke nye kamper automatisk.

## Rask oppstart

1. Pakk ut `Koteng_V2.4` i en mappe du eier (for eksempel på skrivebordet).
2. Kjør `01_INSTALLER.bat` – krever nett for Playwright/Pillow og ved eventuell Python-installasjon. Python 3.12 installeres med winget dersom den mangler. Microsoft Edge må være installert.
3. Kjør `07_SJEKK_SKJERM.bat` og deretter `02_TEST_EN_GANG.bat` og kontroller at begge passene bekrefter **6/6**. Testen publiserer **ingenting**.
4. Kjør `03_KONFIGURER_TOKEN.bat`. Lim inn eksisterende RBK/Ministaut-skannertoken fra den tidligere PC-en. Du kan alternativt kopiere `.ministaut-token` fra den andre PC-en til **samme mappe som `hourly_koteng.py`**.
5. **Stopp eventuelle andre live-installasjoner for samme kamp.** Kjør `04_START_LIVE_TIMEVIS.bat`. Skanneren starter nå, og kontrollerer omtrent hver time så lenge vinduet og PC-en er aktive.
6. Se status på [Ministaut RBK Kvinner](https://tipspanelet.no/ministaut?lag=kvinner). En ny vellykket innsending gir `observed` og et tidsstemplet, dobbeltkontrollert antall ledige sitteplasser.

## Filer og modus

| Fil | Funksjon |
|---|---|
| `01_INSTALLER.bat` | Automatisk Python-oppsett, virtuell miljøisolering, Playwright/Pillow og kontroll av låsen |
| `07_SJEKK_SKJERM.bat` | Test Windows-hovedskjermens tilgjengelige størrelse før Edge åpnes |
| `02_TEST_EN_GANG.bat` | Én lokal, upublisert kontrollskanning |
| `03_KONFIGURER_TOKEN.bat` | Lagre token uten å vise input på skjermen |
| `04_START_LIVE_TIMEVIS.bat` | Sikker live-skanning hver time |
| `05_START_LOKALT_TIMEVIS.bat` | Timevis telling lokalt, uten nettverksopplasting |
| `06_KONTROLLER_LAAST_PROFIL.bat` | Sjekker SHA256 for stadionprofil og alle seks ankerpunkter |
| `diagnostikk/` | Nye lokale resultater, kontrollpunkter og referansebilder |

## Kjente begrensninger

**Låst bildegeometri:** V1.8-profilen er knyttet til et Edge-vindu på **1294 × 642 CSS-piksler**, kartregion `[0, 201.6, 863.3, 577.8]` og sidens zoom **0,9**. På en PC med en annen skjermoppløsning, Windows-zoom eller Edge-oppsett kan skanneren stoppe uten å registrere ny måling. Dette er ønsket sikkerhet. Profilen og ankrene får ikke overskrives for å omgå sperren. Ta vare på `diagnostikk.json` og `referanse_edge.png` for kontrollert ny maskinkalibrering.

**Token:** ZIP-en inneholder aldri et hemmelig token. Det finnes allerede én aktiv tokenregistrering på Ministaut; for ny maskin må tokenet kopieres fra autorisert PC eller et nytt token utstedes sikkert. Dersom det ikke finnes et gyldig token, kan lokal modus kjøres, men liveopplasting avvises. Ikke del token i chat eller GitHub.

**Metrikk:** Seksjonskapasiteter: VIP 71, Felt 1 49, Felt 2 160, Felt 3 120, Felt 4 152 og Felt 5 49. Sum 601. Ståplass A/B holdes utenfor. Avlesninger er **observerte ledige sitteplasser fra valgt kategori**, ikke offisielle salg eller et verifisert fler-kategori lager.

**Stabilitet:** Det er ingen Windows-tjeneste. CMD-vinduet må bli stående, og PC-en må ikke gå i hvilemodus. Ved skannefeil beholdes gammel måling med originalt tidspunkt, aldri null; ny time forsøkes. Programmet stopper ved avspark. Edge-profilen kan være i bruk av bare én skanneprosess av gangen.

**Isolasjon:** Lerkendals kode, database og tidsplan berøres ikke. Koteng bruker separat Supabase-funksjon, egne tabeller og et låst seksjonsoppsett. Nye kamper krever ny kampkonfigurasjon/egen kvalitetssikring.

## Feilsøking

- **Ingen Python/winget:** Installer [Python 3.12 for Windows](https://www.python.org/downloads/windows/) manuelt og kjør `01_INSTALLER.bat` igjen.
- **Microsoft Edge mangler:** Installer Edge på Windows. Skanneren bruker `channel="msedge"`; innebygd Chromium er ikke en godkjent erstatning.
- **Kartet har endret størrelse:** La være å laste opp data. Kontroller Windows-skalering, oppløsning og Edge-vindu; bruk en særskilt verifisert kalibrering ved behov.
- **`pending` i stedet for `observed`:** Det kjører gammel opplastingskode eller skanningen gjaldt en tidligere registrert kjøretid. Bruk kun V2.4-filene og en **fersk** skanning.
- **401 Unauthorized:** Token er ugyldig. Konfigurer på nytt med `03_KONFIGURER_TOKEN.bat`; ikke kopier inn API-service-nøkler.
- **Flere PC-er:** Bruk én aktiv maskin per kamp for å unngå dobbel timeshistorikk.

## Kontroller / tester

Den opprinnelige V1.8-motoren er beholdt uten endret innlesingsalgoritme, og de låste V1.8-filene kan fortsatt verifiseres med 

```
.venv\Scripts\python.exe -m unittest discover -s tests -q
```

I tillegg kjøres førstegangsprofilkontrollen automatisk i installasjonen.

## V2.4: annen fysisk skjermoppløsning

V2.4 setter Playwright Edge-innholdsvinduet til eksakt **1294 x 642 CSS-piksler** selv ved annet fysisk skjermformat. Programmet lar original V1.8-profil, SHA256 og referansekoordinater stå uendret. Det bruker ikke maksimering. Hvis Windows-hovedskjermens arbeidsflate ikke rommer vinduet, avviser skjermsjekken. Kontroller `kontrollpunkter.png` etter en vellykket lokal test. Hvis stadionkartet faktisk har endret layout, vil kartkontroll stoppe og ingen data sendes; ny manuell kalibrering krever separat godkjent profilversjon. Ikke omgå denne kontrollen.
