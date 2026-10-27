# START HER — OPPDRAG TIL LOKAL PC-AGENT (Ministaut)

**Arbeidssted:** Windows-PC med Microsoft Edge, Git, Python 3.12, og tilgang til de tre aktive billettskannerinstallasjonene. GitHub: `GoalPulzdev/ministaut`.

## Kopier dette som oppdrag til agenten

> Du skal bygge grunnlaget for **én komplett Ministaut Scanner Control**, med støtte for alle lag og kamper via versjonerte arenaadaptere. Dette er ikke en frontend-oppgave. Les `docs/SCANNER_AGENT_MASTERPLAN_20261027.md` og `docs/SCANNER_BASELINES_20261027.md` i sin helhet før du endrer kode.
>
> **Start kun FASE 0**: Arkiver og verifiser originale skannere. Den fungerende Lerkendal-koden ligger i `scanner/`. Koteng V2.4 kommer som en original 455 KB ZIP i samme PC-mappe som agenten har tilgang til. Bruk `tools/import_koteng_v24_to_repo.py` og verifiser SHA256 `b0ea10aacd80da2d2acf323dc2aadb5268cd9c6c8e0476bc6afa9cd0401d5d6a`. Importer alle filer til `baselines/koteng/v2.4/`.
>
> Sjekk de **to øvrige scannerinstallasjonene fysisk på PC**. Identifiser om de begge bruker Lerkendal-motoren eller om én av dem har egne modifikasjoner for cup. Registrer kildefilhash, aktiv kamp-ID, konfigurasjon (kun ikke-hemmelige felt), versjon og testresultater. Ingen gjettede versjoner eller kamp-ID-er.
>
> IKKE endre produksjonskoden, ikke stopp eksisterende scanner, ikke publiser testsnapshots, ikke endre Supabase/Vercel og ikke bruk GitHub Actions. Ikke les eller commit token, Edge-profil, cookies, hemmeligheter eller lokal historikk. Hvis en aktiv scanner ikke kan leses uten driftsavbrudd, dokumenter det og be om en kontrollert kopi først.
>
> Lever `docs/SCANNER_BASELINE_AUDIT.md`, komplette kildekodebaselines i Git, beståtte lokale tester, identifiserte forskjeller, og forslag til adaptergrensesnitt. Lag egen PR. **Fortsett ikke til fase 1 før baseline-auditen er kontrollert.**

## Første kommandoer (PowerShell)

Kjør i en mappe der du har lov til å lagre prosjektkode:

```powershell
git clone https://github.com/GoalPulzdev/ministaut.git
cd ministaut
git switch -c feat/scanner-platform-baseline
py -3 tools/import_koteng_v24_to_repo.py --zip "C:\sti\til\RBK_Koteng_V2_4_NY_SKJERM_KOMPLETT.zip"
py -3 tools/import_koteng_v24_to_repo.py --zip "C:\sti\til\RBK_Koteng_V2_4_NY_SKJERM_KOMPLETT.zip" --apply
git status --short
```

**Bytt ut eksempelfilstien med den virkelige ZIP-plasseringen.** Første kommando er «dry run». Ingen Git push gjøres automatisk.

Kjør så eksisterende lokale tester fra riktig skannerkatalog:

```powershell
cd scanner
py -3 -m unittest discover -s tests -v
cd ..\baselines\koteng\v2.4
py -3 -m unittest discover -s tests -v
```

Om Playwright/Pillow mangler, kjør den respektive skannerens installasjonsrutine i eget miljø først. Testene må ikke starte en ekte timevis livejobb eller sende data.

## Bevar «stabil drift» mens agenten jobber
- Eksisterende scanner-Python- og Edge-vinduer skal fortsette urørt.
- Git-arbeidskopien og nye avhengigheter må ligge i en **egen** mappe.
- GitHub Actions brukes ikke.
- Ingen migrering, ingen opplasting av gamle/kunstige data.
- Alle endringer i `scanner/`, `web/`, `supabase/` behandles som nye separate produksjonsoppgaver.

## Overordnet fremtidig mål
Én oppstartsfil, automatisk timeskanning for flere kamp-ID-er, kun én aktiv produsent per kamp, robust offline-kø, profilsjekk per arena, kamp- og kategorispesifikk historikk, datakvalitetsgate og RBK/RBK Kvinner-fanen som rendrer riktig kamp. Ny leverandør/arena introduseres gjennom ny adapter, ikke kopiering av hele programmet.
