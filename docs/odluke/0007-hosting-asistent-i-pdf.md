# ADR 0007: Hosting, asistent na javnom demu i PDF dokumentacije

- **Status:** prihvaćeno (hosting čeka odluku korisnika)
- **Datum:** 2. 11. 2026.

## Odluka

1. **Hosting:** korisnik ga još nije odabrao. Sve je pripremljeno za bilo koji poslužitelj s Dockerom: `docker-compose.prod.yml`, `infra/deploy.sh`, `infra/smoke.sh` i `docs/deploy.md`.
2. **Asistent:** na javnom demu uvijek rade brza pitanja bez LLM-a. Mali open-weight model uključuje se samo ako izmjereno odgovara dovoljno brzo; stranica sama provjerava je li model dostupan.
3. **PDF dokumentacije:** umjesto Pandoca i WeasyPrinta koristi se Chromium iz Playwrighta, jer ne traži sistemske pakete, a već je dio razvojnih alata.
4. **OGC API:** pygeoapi čita poglede u shemi `ogc`, u EPSG:4326. Ćelije s manje od 10 stanovnika nemaju objavljen broj stanovnika.

## Posljedice

Bez poslužitelja nema javnog URL-a, a on je obavezan dio predaje. Ta stavka je u `PROGRESS.md` pod „Čeka korisnika”.
