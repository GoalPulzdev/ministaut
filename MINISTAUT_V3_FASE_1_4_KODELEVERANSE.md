# Ministaut V3 fase 1–4 — første kodeleveranse

Dato: 24.10.2026
Status: **implementert grunnlag, ikke produksjonsklar integrasjon**
Branch: `feat/ministaut-v3-phase1-foundation-20261024`

## Hva er faktisk bygget?
1. **Stabil Lerkendal-baseline**: eksisterende `scanner/hurtigkart.py`, `scanner/match_config.py`, `scanner/publication.py` og `web/index.html` forblir helt uendret. Testene for V3 er isolert.
2. **Felles stadionprofil og validering**: `scanner/v3/profiles.py` definerer versjonerte stadionprofiler med vilkårlig antall sittefelt, kapasitet og lærte skanneankre. Ubekreftede og ufullstendige profiler blokkerer publikasjon. `candidate_from_reference` leser nåværende Lerkendal-referanse som et *utkast* til profil. **Selve opplærings-UI og migrering av alle bekreftede musepunkter er ikke integrert ennå.**
3. **Uavhengige kamper og jobber**: `scanner/v3/control.py` har egne intervaller, status og jobber per kamp; stopp ved avspark; lease, oppfølging av fullført/feilet skannejobb og JSON-persistens. Dette er en lokal kontrollplansprototype. Ikke en sentral Supabase-kø, og **ikke integrert med faktiske Playwright-skanninger ennå**.
4. **Enkel administrasjon**: `scanner/v3/admin.py` lar en lokal operatør registrere kamp/arena/avspark, liste, aktivere og pause kamper fra kommandolinjen uten å endre skannerkoden. **Ingen nettbasert admin og ingen direkte oppdatering av kjørende legacy-skanner ennå**.

## Hvorfor isolert?
PR #17 viste at innbygging av eventkø i den gamle `hurtigkart.py` gir en skjørt sammenkoblet løsning. Dette arbeidet starter på main, med egne moduler, og forandrer ikke eksisterende produksjonsløp. Ingen migrasjoner, secrets eller skannedata ble endret.

## Hvordan prøve lokalt
Fra repo-roten:

```shell
python -m unittest discover -s scanner/v3 -p 'test_foundation.py'
```

**Merk:** testmodulen bruker relative imports og må derfor kjøres som:

```shell
python -m unittest scanner.v3.test_foundation -v
```

Eksempel på lokal V3-staging:
```shell
python -m scanner.v3.admin add rbk-molde https://billett.rbk.no/checkout/6a9a7e3f3f93920b289b0675 lerkendal 2026-11-28T18:00:00+01:00 "Rosenborg - Molde"
python -m scanner.v3.admin list
python -m scanner.v3.admin activate rbk-molde
```

Dette registrerer *bare* et kontrollplansoppsett; skanner ikke billettkartet.

## Krav før neste merge / produksjonsbruk
- Kjør `python -m unittest scanner.v3.test_foundation -v` med faktisk Python på PC.
- Se over atomisitet ved flere samtidige prosesser: JSON-kontrollplanet er kun for **én lokal skriver**, ikke egnet som distribuert jobbkø.
- Implementer PostgreSQL/Supabase-baserte transaksjonelle jobblåser dersom flere workers skal dele kø.
- Skill event-/stadiumopplæring fra intern kontrollplan: lær Koteng i Edge med Lerkendals fungerende metode og verifiser alle feltnavn, kapasiteter, koordinater og gjentatte avlesninger.
- Koble V3-jobber til én isolert Lerkendal-skanneradapter og test faktisk kjøring uten dobbeltpublisering.
- Implementer administrasjon med godkjenning, logging og sikre serverkall; ikke gi public anon tilgang til admin-databasetabeller.
- Test nedetid/restart, kartendringer, feilskanning, manglende token, pågående skanning ved avspark og gjenoppretting etter avbrudd.
- Koteng- og bortearenaer må aldri publiseres før profilen er godkjent.

## Neste kodeleveranse
Fase 1B: robuste fellesprofil-tester og Lerkendal-adapter.
Fase 2B: operatørstyrt innlæring av Koteng med skjermbilder og faktiske punkter.
Fase 3B: integrasjon mot skanner/ingest + sentral transaksjonell kø.
Fase 4B: faktisk administrasjonspanel med auth og statusoversikt.
