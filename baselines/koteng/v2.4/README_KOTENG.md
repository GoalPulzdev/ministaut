## Koteng V2.4 på ny Windows-skjerm

Bruk 07_SJEKK_SKJERM.bat og deretter 02_TEST_EN_GANG.bat. Edge åpnes med låst innholdsvindu på 1294 x 642 CSS-piksler også ved annen skjermoppløsning. De seks ankerpunktene og profillåsen endres ikke. En for liten skjerm eller endret kart stopper skanningen før publisering. Se V2_4_NY_SKJERM.txt.

# RBK Billettmonitor – Koteng Arena V1.8 (LÅST LOKALPROFIL)

**Status 26. oktober 2026:** Bruker har bekreftet at tellingen i Rosenborg–Røa
(1. november kl. 14.30) er korrekt. Siste medfølgende kontroll ble tatt
2026-10-26T15:26:28Z: 6/6 felt i **begge** uavhengige skannepass, uten
konflikter, og **424 observerte ledige seter**. Det er et historisk referansetall,
IKKE en hardkodet verdi som vises som live. Nye tellinger kommer utelukkende fra
ferske, synlige tooltip-avlesninger.

## Låst referanse

| Område | Seter i kartet | Ledige 26.10 | Bekreftet Edge-anker (CSS) |
|---|---:|---:|---|
| VIP | 71 | 45 | 436, 225 |
| FELT-1 | 49 | 48 | 244, 242 |
| FELT-2 | 160 | 125 | 314, 244 |
| FELT-3 | 120 | 70 | 407, 248 |
| FELT-4 | 152 | 136 | 522, 244 |
| FELT-5 | 49 | 0 | 616, 244 |
| **Sum** | **601** | **424** | |

Referanse-Edge hadde 1294 × 642 CSS-piksler, kartområde
[0, 201.6, 863.3, 577.8] og sidezoom 0.90. VIP-ankeret kan bruke en annen
lokal posisjon i første kontrollpass; rapporten bekrefter 2/2 korrekte tooltip-avlesninger.

**Dette låses:** feltnavn, seksjonskapasiteter, manuelt verifiserte hover-ankere,
viewport, kartområde, zoom og arrangements-ID. SHA256 sjekker at profil og
ankere ikke er utilsiktet endret. Avvik medfører STOPP, ikke automatisk
ny opplæring eller påstått 0 tilgjengelige.

**Dette låses ikke som påstått verifisert:** billettkategori (fortsatt ukjent),
VIP-/HC-salgsregler, om Felt 5 er låst eller bare viser null, totalt antall
stående eller all kjøpbar beholdning for alle kategorier. Ståplass A/B er
ikke sitteplasser og er holdt utenfor sitteplasstallet.
Ingen "estimert solgte" vises for Koteng.

## Lokal bruk

1. Ta sikkerhetskopi av den fungerende V1.7-mappen. Ikke installer over den.
2. Pakk ZIP ut i en **ny mappe** på Windows.
3. `INSTALLER_KOTENG.bat` første gang. Deretter `KONTROLLER_PROFIL.bat`:
   den skal vise «KOTENG-PROFIL LÅST OG KONTROLLERT».
4. Kjør `START_KOTENG.bat`. Skanneren åpner sin egen Edge-profil og bruker
   kun de seks bekreftede ankerpunktene. Ingen manuell opplæring nødvendig.
5. Kontroller `diagnostikk/<kamp-ID>/<UTC-tid>/diagnostikk.json` og
   `kontrollpunkter.png` i hver kjøring.

**Viktig:** Samme Edge-geometri må gjelde som den låste referansen. Hvis
vindusstørrelse, sidezoom eller kartets plassering endres utover toleransen,
stopper skanneren med forklaring. IKKE overskriv `ankerpunkter_koteng.json`.
For et nytt skjermoppsett eller en annen kamp må det opprettes en separat
profilversjon, som kontrolleres og godkjennes på nytt.

`LAER_OPP_KOTENG.bat` er deaktivert i denne låste pakken. Et uttrykkelig
`--teach`-forsøk avvises av skanneren. Endre ikke digest for å omgå kontrollene.

## Datakvalitet / ingen produksjonsendringer

- Alltid to uavhengige, samsvarende avlesninger per seksjon.
- Uavleste felt forkastes – de telles aldri som null.
- Kapasitetsendring eller ukjente områder utløser kvalitetsfeil.
- Korrekte ferske feltavlesninger får lokal status `LOCKED_LOCAL_VERIFIED`.
- `complete=false`, `publishable=false` og `public_approved=false` til
  offentlig salgbart inventar og billettkategorier er særskilt validert.
- Ingen timeplan, Supabase-skriving eller offentlig visning er aktivert.
- **Lerkendal-koden og eksisterende offentlige data er ikke endret.**

## Tests

`python -m unittest discover -s tests -v`

Tester verifiserer blant annet SHA256-endringskontroll, feil arrangement,
endret geometri, uavhengige pass, og at `--teach` ikke kan overskrive en låst profil.
