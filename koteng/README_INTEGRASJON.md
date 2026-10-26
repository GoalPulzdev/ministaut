# Ministaut – Koteng Arena: sikker V2-integrasjon

## Isolasjon
**Ikke rør den fungerende Lerkendal-skanneren.** Kopier `sync_koteng.py`, `hourly_koteng.py` og de to START_KOTENG_TIMEVIS*.bat-filene fra denne mappen inn i samme mappe som **den eksisterende fungerende V1.8** (`koteng_scanner.py`, `profile_lock.py`, `koteng_profile.json` og `ankerpunkter_koteng.json`). Ikke kopier over eller erstatt de låste filene. Koteng V1.8 er fortsatt eneste skannemotor.

## Driftsmodus
* `START_KOTENG_TIMEVIS.bat`: privat lokal skanning hver time, stopper ved avspark, ingen overføring.
* `START_KOTENG_TIMEVIS_PRIVAT.bat`: samme skanning, lagrer komplette V1.8-resultater i egne Supabase-Koteng-tabeller med `reading_status=observed` (offentlig, kontrollert observasjon, ikke salg eller full kategoriinventarkontroll). Krever konfigurert lokal `MINISTAUT_TOKEN` i miljøet eller privat `.ministaut-token` i Koteng-mappen (aldri commit).
* `py -3 sync_koteng.py diagnostikk\\6aaceecebfe408c38e1712dd\\<run>\\diagnostikk.json`: kontroller én diagnostikk lokalt uten opplasting. Legg til `--send` for offentlig, kvalitetskontrollert observasjon.

Nye målinger må ha to samsvarende pass i alle seks felt, uendret kapasitetsmodell, korrekt låst profil og SHA-kontroll. Skanneren åpner Edge og kjører `--no-pause`; første timekjøring bør overvåkes på PC. Hvis siden endrer kart, skal skanneren feile og ikke lagre feilverdier.

## Backend
`ministaut-koteng-ingest` er en **separat** autentisert Supabase-funksjon. Den bruker samme administrerte skannertokenordning, men skriver bare til `ministaut_koteng_*`-tabeller. Den gamle Lerkendal-ingestfunksjonen og tabellene er urørt. Data skrives som `observed` kun ved låst profil og to samsvarende pass; aldri som bekreftet salg.

## Offentlig visning
RBK/RBK Kvinner byttes i Ministaut. Røa-kampen er synlig når frontendendringen blir publisert, men avlesningskortet viser «venter på første godkjente telling» til en administrator manuelt godkjenner kategori/inventar og skanning. Ikke sett `reading_status=accepted` før VIP/HC/Felt 5 og billettkategorier er kontrollert. Ståplass A/B inngår ikke.

## Neste Koteng-kamp
En annen arrangements-ID er ikke automatisk låst. Opprett egen profil/anker-kontroll for ny kamp, og utvid en separat ingest-versjon etter godkjenning. Det er **ikke** trygt å gjenbruke profillåsen på tvers av kamp-ID uten ny verifikasjon.

## Live publisering 26. oktober 2026
Rosenborg–Røa er autorisert som kamp i RBK Kvinner-visningen. Nye gyldige V1.8-tellinger sendes via Koteng-ingest med status `observed`. Dette er et offentlig målt antall fra den valgte billettkategorien, **ikke** verifiserte salg eller en garanti for at hver kategori har samme ledighet. Status `accepted` er reservert for særskilt godkjent inventar/kategori. Nettleseren viser `observed`/`accepted` for RBK Kvinner og bare `accepted` for RBK. En ny dato for målingen er obligatorisk; referansebildets 424 skal aldri brukes som oppdatert live-tall.
