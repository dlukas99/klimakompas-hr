# PROGRESS — KlimaKompas HR
Zadnje ažuriranje: 1. 11. 2026. · Trenutna faza: 1 · Rok: pon 9. 11. 2026. 24:00 (freeze 16:00)

## Faze
- [x] F0 Bootstrap i provjera izvora (ned 1. 11.)
- [ ] F1 Prostorni temelj, stanovništvo, kostur weba (pon 2. 11.)
- [ ] F2 Statičke opasnosti (uto 3. 11.)
- [ ] F3 Indeks, API, karta (sri 4. 11.)
- [ ] F4 Živi podaci, JLS ploča (čet 5. 11.)
- [ ] F5 AI, ML, prvi deploy (pet 6. 11.)
- [ ] F6 Kvaliteta, standardi, pristupačnost (sub 7. 11.)
- [ ] F7 Dokumentacija, video (ned 8. 11.)
- [ ] F8 Freeze i predaja (pon 9. 11.)

## Trenutni zadaci
- [x] F1 priprema: polja, šifre i kontrolni zbrojevi potvrđeni na stvarnim datotekama (`config/sources.yaml`).
- [ ] F1: plan predan korisniku; čeka potvrdu jer mijenja shemu baze.
- [ ] F2 priprema: složiti ECDE zahtjev iz javnog opisa CDS procesa, čim token bude u `.env`.

## Čeka korisnika
| # | Što | Zašto | Rok | Status |
|---|---|---|---|---|
| 1 | Upisati `CDSAPI_KEY` u `.env` | ECDE je ulaz za P0 sloj topline, a zahtjevi čekaju u redu | pon 2. 11. | račun i licenca gotovi, token čeka |
| 2 | Dodati Fabija kao suradnika na GitHubu | §21; suradnik je trenutno samo `dlukas99` | pon 2. 11. | otvoreno |
| 3 | Mentor: tko šalje predaju, pitanja organizatoru (`docs/dopisi/organizator-pitanja.md`), postoji li FERIT poslužitelj ili GPU | §21 | pon 2. 11. | otvoreno |
| 4 | Poslati dopis Hrvatskim vodama (`docs/dopisi/hrvatske-vode.md`) | vektori i potvrda za WMS (P1) | pon 2. 11. | otvoreno |
| 5 | Poslati upit o licenci JRC-u (`docs/dopisi/jrc-licenca.md`) | odgovor određuje licencu izvedenog sloja poplava; bez odgovora ostaje ODbL (ADR 0003) | pon 2. 11. | otvoreno |
| 6 | Odluka: hosting i domena | potrebno za P0.7 | uto 3. 11. | otvoreno |
| 7 | Potvrda plana Faze 1 i praga za udjele 65+ | plan mijenja shemu baze i odstupa od SPEC §5.4 | pon 2. 11. | otvoreno |

## Odluke (ADR)
- [0001](docs/odluke/0001-korekcije-izvora-nakon-verifikacije.md) Korekcije izvora nakon verifikacije.
- [0002](docs/odluke/0002-open-meteo-prema-uvjetima-api-ja.md) Open-Meteo prema uvjetima API-ja.
- [0003](docs/odluke/0003-licenca-izvedenog-sloja-poplava.md) Licenca izvedenog sloja poplava.
- [0004](docs/odluke/0004-zamjena-za-nedostajuci-pm25.md) Zamjena kad lokalna postaja nema PM2,5.

## Problemi / bilješke
- F0 gotova: `make up` diže PostGIS i Martin, `make check` prolazi, verifikacija je u `docs/izvori-provjera.md`.
- AZO vraća HTTP 429 kod brzih poziva, pa worker u F4 mora razmaknuti zahtjeve. Osijek u provjerenom razdoblju nema trenutni PM2,5, pa F4 provodi ADR 0004.
- Toplinski val izvan sezone nema strukture aktivnog upozorenja, pa parser aktivnog stanja ostaje `TODO(verify)`.
- Licence s oznakom `TODO(verify)` u `config/sources.yaml` treba potvrditi prije objave izvedenih skupova.

## Izrezano (lista rezanja)
- Ništa.
