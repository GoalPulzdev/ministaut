# ministaut — RBK billettstatus

Goalpulz-prosjektet viser tilgjengelige RBK-billetter med separate historikker per kamp. Kilde: Windows-skanner basert pa V20/V21 (Playwright + Edge). Webdelen leser godkjente målinger fra Supabase GoalPulz Sql.

## Struktur
- `web/`: Vercel statisk kampstatusside. Vercel **Root Directory = web**, framework Other, ingen build-kommando.
- `scanner/`: Windows/Edge skanneren og testene. Installer med `INSTALLER.bat`, start med `START_BILLETTMONITOR.bat`.
- `supabase/`: dokumentasjon og source til Supabase funksjonen. Databasen er allerede opprettet under GoalPulz Sql.

## Sikkerhet
Dette repoet er offentlig. **ALDRI commit private tokens** (`.ministaut-token`, `.env`, secrets, browser profiler eller historikk fra den lokale maskinen). Etter kloning settes `MINISTAUT_TOKEN` i Windows-miljo eller i `scanner/.ministaut-token` lokalt. Funksjonen verifiserer en SHA-256 tokenhash registrert i Supabase; nylige tall vises offentlig kun ved is_published=true og accepted.

## Vercel
Import `GoalPulzdev/ministaut`, velg Root Directory `web`, framework Other. Publiserbar API key til Supabase er innebygd i statisk klient og er ikke hemmelig; Row Level Security styrer SELECT. Ikke legg secret/service_role keys i nettleseren.

## Tall og datakvalitet
- Ledige sitteplasser er antallet verifisert kjøpbare seter i målingen.
- Estimert utilgjengelige = 21423 - ledige sitteplasser; det inkluderer ikke-avleste staaplasser og eventuelt laaste felt og **er ikke bekreftet solgte**.
- 60 faste sittefelt, 19015 seter i kartet. SB og Ovre Ost er staaplasser som ikke er inkludert i avlest ledighet.
- Ingen demodata publiseres som ekte målinger. Statusfelt viser tidspunkt for forrige aksepterte måling.

## Status
GoalPulz Sql tabeller og Edge Function er opprettet. Publiseringsstatus i Vercel avhenger av kobling til GitHub. Skannerens opplasting må prøves fra den faktiske Windows-installasjonen.