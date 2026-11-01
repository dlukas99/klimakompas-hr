# PROGRESS — KlimaKompas HR
Zadnje ažuriranje: 1. 11. 2026. · Trenutna faza: 0 → 1 · Rok: pon 9. 11. 2026. 24:00 (freeze 16:00)

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
- [ ] F1: DGU AU i Census grid V3 → `ref.*`, `pop.*`; prvo potvrditi polja i šifre na stvarnim podacima.
- [ ] F2 priprema: složiti ECDE zahtjev iz javnog opisa CDS procesa, čim token bude u `.env`.

## Čeka korisnika
| # | Što | Zašto | Rok | Status |
|---|---|---|---|---|
| 1 | Upisati `CDSAPI_KEY` u `.env` | ECDE je ulaz za P0 sloj topline, a zahtjevi čekaju u redu | pon 2. 11. | račun i licenca gotovi, token čeka |
| 2 | Dodati Fabija kao suradnika na GitHubu | §21; suradnik je trenutno samo `dlukas99` | pon 2. 11. | otvoreno |
| 3 | Mentor: tko šalje predaju, pitanja organizatoru (`docs/dopisi/organizator-pitanja.md`), postoji li FERIT poslužitelj ili GPU | §21 | pon 2. 11. | otvoreno |
| 4 | Poslati dopis Hrvatskim vodama (`docs/dopisi/hrvatske-vode.md`) | vektori i potvrda za WMS (P1) | pon 2. 11. | otvoreno |
| 5 | Poslati upit o licenci JRC-u (`docs/dopisi/jrc-licenca.md`) | karte poplava imaju proturječnu licencu, CC BY 4.0 ili ODbL | pon 2. 11. | otvoreno |
| 6 | Odluka: hosting i domena | potrebno za P0.7 | uto 3. 11. | otvoreno |
| 7 | Odluka: Open-Meteo unatoč `Disallow: /` u robots.txt? | P1 i rezerva za ECDE i AZO; predlažem da se ne koristi bez potvrde Open-Meteo-a | uto 3. 11. | otvoreno |

## Odluke (ADR)
- [0001](docs/odluke/0001-korekcije-izvora-nakon-verifikacije.md) Korekcije izvora nakon verifikacije.

## Problemi / bilješke
- F0 gotova: `make up` diže PostGIS i Martin, `make check` prolazi, verifikacija je u `docs/izvori-provjera.md`.
- AZO vraća HTTP 429 kod brzih poziva, pa worker u F4 mora razmaknuti zahtjeve. Osijek u provjerenom razdoblju nema trenutni PM2,5.
- Toplinski val izvan sezone nema strukture aktivnog upozorenja, pa parser aktivnog stanja ostaje `TODO(verify)`.
- Open-Meteo je trenutno blokiran robots.txt-om. Dok se to ne riješi, rezerve za ECDE i nowcast nisu dostupne.
- Licence s oznakom `TODO(verify)` u `config/sources.yaml` treba potvrditi prije objave izvedenih skupova.

## Izrezano (lista rezanja)
- Ništa.
