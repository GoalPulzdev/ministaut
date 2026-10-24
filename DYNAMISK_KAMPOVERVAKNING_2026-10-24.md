# Ministaut: dynamisk kampliste, timeskanning og arkivering

Status: implementert på branch/PR for lokal Windows/Edge-verifisering. **Ikke slå på Koteng-skanning før ny stadionprofil er målt og validert.**

## Mål
Legg til kamper mens monitoren er åpen. Hver verifiserte kamp med framtidig avspark skal automatisk skannes etter samme timesintervall; ingen kamp skal bli liggende igjen som aktiv etter avspark. Historikk per kamp beholdes. Nye kamper skal ikke erstatte eksisterende kamper eller slette historikk.

## Bruk i skannerpanelet
1. Under kamper: Lim inn `https://billett.rbk.no/checkout/<kamp-id>`.
2. Velg **Lerkendal** eller **Koteng Arena** basert på arrangementet. Trykk **Legg til**. Den pågående tellingen fortsetter.
3. Velg lagret kamp i **Mine kamper**. Angi korrekt lokal dato/klokkeslett under **Avspark for valgt kamp (norsk tid)** og trykk **Lagre**.
4. Kamper med kjent avspark i framtiden og **verifisert Lerkendal-profil** går inn i automatisk overvåkning. Flere forfalte kamper skannes sekvensielt i samme Edge-sesjon, uten omstart.
5. På og etter avspark går kampen over til **avsluttet**. Ingen nye kontroller/publisering; all historikk beholdes.
6. Koteng-kamper forblir **avventer kart**. De kan lagres med avspark nå, men teller ikke før stadiondata, hoverankre og kapasitet er bekreftet.

## Kjernefiler
- `scanner/event_registry.py`: `monitor_kamper.json` og kick-off-status: `awaiting_kickoff`, `scheduled`, `awaiting_map`, `finished`.
- `scanner/panel.js`: input, arena, kampliste og lagring av avspark.
- `scanner/hurtigkart.py`: registrering, kampbytte, round-robin over aktiverte kamper, publiseringssperre etter avspark.
- `scanner/test_event_registry.py`: regresjonstester.

## Eksisterende kamper
- Rosenborg–Start: avspark 07.11.2026 kl. 18:00 norsk tid.
- Rosenborg–Molde: avspark 28.11.2026 kl. 18:00 norsk tid.
- RBK Kvinner: `6aaceecebfe408c38e1712dd` lagt inn som **avventer Koteng-kart**. Arrangementets faktiske navn, arena og starttid må kontrolleres i RBKs billettsystem.

## Sikkerhet
- Hovedscanner, Lerkendal 60-felt, validert opplasting, eksisterende Supabase-historikk og prognoser skal ikke endres.
- Ukjent kampstart betyr **ikke automatisk telling**. Brukeren registrerer korrekt tidspunkt.
- Ved Windows-dvale kan tidsplanen forskyves; det skapes ikke syntetiske tellinger for manglende perioder.
- Nye kampoppsett er lagret lokalt i `scanner/monitor_kamper.json`; filen kan beholdes mellom programoppgraderinger.
- PC-agenten må teste med to samtidige Lerkendal-kamper og måle at hver får egen skanning omtrent én gang i timen, at en kamp med avspark like etter neste telling automatisk fjernes fra aktiv kø, og at kampregistrering ikke avbryter annen telling.
- Kjør `python -m unittest discover -s scanner -p 'test_event_registry.py' -v` fra repo-roten; kjør dessuten eksisterende scanner-tester.
- Vær ekstra oppmerksom på at en gammel monitorinstans må restartes **én gang ved installasjon av ny programkode**. Etter den oppgraderingen kan nye kamper legges inn uten omstart. Endringen oppdaterer ikke en allerede kjørende Python-prosess automatisk.

## Neste eget utviklingssteg
Kartlegg Koteng-sittekartet fra ekte checkout, implementer en arena-spesifikk skannerprofil og Supabase-validering, og vis kvinner/herre-kamper med respektive arenaer på web. Ukjent Koteng-kapasitet skal aldri erstattes med Lerkendal-tall.
