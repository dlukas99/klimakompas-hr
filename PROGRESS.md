# PROGRESS — KlimaKompas HR
Zadnje ažuriranje: 1. 11. 2026. · Trenutna faza: 2 · Rok: pon 9. 11. 2026. 24:00 (freeze 16:00)

## Faze
- [x] F0 Bootstrap i provjera izvora (ned 1. 11.)
- [x] F1 Prostorni temelj, stanovništvo, kostur weba (gotovo 1. 11.)
- [ ] F2 Statičke opasnosti (uto 3. 11.)
- [ ] F3 Indeks, API, karta (sri 4. 11.)
- [ ] F4 Živi podaci, JLS ploča (čet 5. 11.)
- [ ] F5 AI, ML, prvi deploy (pet 6. 11.)
- [ ] F6 Kvaliteta, standardi, pristupačnost (sub 7. 11.)
- [ ] F7 Dokumentacija, video (ned 8. 11.)
- [ ] F8 Freeze i predaja (pon 9. 11.)

## Trenutni zadaci
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
| 7 | U Ubuntu terminalu, u mapi `frontend`: `sudo npx playwright install-deps chromium` | sistemske biblioteke za `make e2e` na tvom računalu; do tada koristim privremeno raspakirane u `~/.local/share/kk-browser-libs` | kad stigneš | otvoreno |

## Odluke (ADR)
- [0001](docs/odluke/0001-korekcije-izvora-nakon-verifikacije.md) Korekcije izvora nakon verifikacije.
- [0002](docs/odluke/0002-open-meteo-prema-uvjetima-api-ja.md) Open-Meteo prema uvjetima API-ja.
- [0003](docs/odluke/0003-licenca-izvedenog-sloja-poplava.md) Licenca izvedenog sloja poplava.
- [0004](docs/odluke/0004-zamjena-za-nedostajuci-pm25.md) Zamjena kad lokalna postaja nema PM2,5.
- [0005](docs/odluke/0005-stanovnistvo-i-dobni-udjeli.md) Stanovništvo i dobni udjeli po ćeliji.

## Problemi / bilješke
- F1 gotova: 21 županija, 556 JLS-ova (128 + 428), 6.759 naselja, 60.968 ćelija, 24.464 naseljene, 1.683.411 adresa. Sve naseljene ćelije imaju JLS. Zbroj mreže 3.889.177 (+0,45 %), zbroj DZS-a točno 3.871.833.
- Puni ETL traje oko 9 minuta; adrese 3,5 minute, pa fallback na geokoder bez adresa nije bio potreban.
- E2e (Playwright i axe) prolazi na 1280 px i 360 px, ali se zasad pokreće samo lokalno, ne u CI-ju, jer traži učitane podatke. Radix/shadcn još nisu uvedeni: dosadašnji UI koristi nativne pristupačne elemente.
- Razvojne npm ovisnosti imaju 31 umjerenu ranjivost u `npm audit`; produkcijske 0.
- Podloga: OpenFreeMap je jedini vanjski poziv iz preglednika. Ako je nedostupan, karta prelazi na praznu pozadinu s našim slojevima.
- F0 gotova: `make up` diže PostGIS i Martin, `make check` prolazi, verifikacija je u `docs/izvori-provjera.md`.
- AZO vraća HTTP 429 kod brzih poziva, pa worker u F4 mora razmaknuti zahtjeve. Osijek u provjerenom razdoblju nema trenutni PM2,5, pa F4 provodi ADR 0004.
- Toplinski val izvan sezone nema strukture aktivnog upozorenja, pa parser aktivnog stanja ostaje `TODO(verify)`.
- Licence s oznakom `TODO(verify)` u `config/sources.yaml` treba potvrditi prije objave izvedenih skupova.

## Izrezano (lista rezanja)
- Ništa.
