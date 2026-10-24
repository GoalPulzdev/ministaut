# Koteng Arena – kontrollrapport og neste lokale prøve, 24.10.2026

Status: Første faktiske opplæringsrapport mottatt fra bruker + skjermbilde. **Ingen automatiske livepubliseringer.** Kun første prøvemåling; `map_full_coverage_verified=false`.

## Verifiserbare funn fra første PC-forsøk
Arrangement: Rosenborg–Røa, Toppserien, 1. november 2026 kl. 14:30 (vises på skjermbildet).
URL: https://billett.rbk.no/checkout/6aaceecebfe408c38e1712dd
Rapport: `20261024T133127Z_training.json` (sendt i chatten).
Opplæring: 450 hoverpunkter; SVG/canvas-detektor; ingen rapporterte kapasitetskonflikter.

| Felt | Avlest ledig | Kapasitet |
| --- | ---: | ---: |
| FELT-1 | 48 | 49 |
| FELT-2 | 125 | 160 |
| FELT-3 | 76 | 120 |
| FELT-4 | 138 | 152 |
| FELT-5 | 0 | 49 |
| VIP | 49 | 71 |
| **Totalt, observerte sitteområder** | **436** | **601** |

Skjermbildet viser også **Ståplass A**. Dette er **ikke** innhentet som verifiserte sitteplasser og skal ikke adderes, settes til null eller tolkes som salg. FELT-5 rapporterte 0 tilgjengelige, *ikke* 49 bekreftet solgte.

## Oppdagede feil/risikoer
1. Den generiske kartdetektoren returnerte `[5,423.75,1590,950]` på et 1600x960-bilde. Det er for bredt (inkluderer deler av høyre betalingspanel), og starter under toppfelt/VIP som vises fra ca. y316.
2. Samtykkebanneret «Sikkerheten til dataene dine» lå over nedre del av kartet. Operatøren må lukke det selv, før læring starter.
3. De første 450 musepunktene var ikke garantert romlig fordelt over hele arenaen, så en nedre ståplass kan gå tapt.
4. `verified=false` fra opplæringen er korrekt. Seks observerte sittefelt er ikke bevis på komplett kartdekning eller korrekt ståplassbeholdning.

## Rettelser som er implementert på V3-branchen
- Kun for Koteng: avgrens inspeksjon til venstre billettkart med toppfeltet inkludert; påvirker ikke Lerkendal.
- Del opp prøvepunkter i SVG-kandidater og jevnt fordelte rutenettpunkter over hele den synlige kartflaten.
- Blokker læring hvis det oppdagede samtykkebanneret fortsatt dekker kartet. Samtykke gis aldri automatisk.
- Les eventuelle ståplasstooltips separat fra sitteplasser; tell dem aldri inn i sitteplasser.
- Lagre en **Koteng profil v2** (`scanner/v3_profiles/koteng_arena.v2.json`). Behold gammel v1 urørt, siden koordinatnormaliseringen er endret.
- Rapportér eventuelle mangler blant seks seksjoner vi har sett, og behold `map_full_coverage_verified=false`.
- Nye kildekode-tester i `scanner/v3/test_koteng_training.py`.

## Neste Windows-test
1. Avslutt Koteng-Edge/opplæringsprosess og behold gammel mappe som sikkerhetskopi.
2. Last ned ny ZIP fra `feat/ministaut-v3-phase1-foundation-20261024`.
3. Pakk ut til ny mappe og kjør `scanner/INSTALLER.bat` hvis nødvendig.
4. Kjør **`scanner/START_KOTENG_OPPLAERING.bat`**.
5. I Edge: åpne kart, lukk banner manuelt («Bare nødvendig»), se Felt 1–5, VIP og Ståplass A.
6. Trykk ENTER i konsollen. Vent til rapporten er ferdig.
7. Del **ny `v3_learning/koteng_arena/*_training.json` og skjermbildet**. Sjekk om seks sittefelt finnes igjen, uten kapasitetskonflikter, og om Ståplass A kan gi egen tilgjengelighetsavlesning.
8. Endre ikke `verified` til `true` manuelt; to uavhengige målinger og fullstendighetskontroll kommer før aktivering.

## Begrensning
Dette er fortsatt et læringsverktøy, ikke en komplett skanner med timeskanning/opplasting. Den faktiske Edge-kjøringen av rettelsene må verifiseres lokalt av brukeren. Testene som er lagt i GitHub er heller ikke rapportert kjørt av Windows.

Lokale Python-tester (fra `scanner`):
```
py -3 -m unittest v3.test_koteng_training v3.test_foundation -v
```

Husk at en ZIP allerede lastet ned **ikke** oppdateres når vi committer endringer.
