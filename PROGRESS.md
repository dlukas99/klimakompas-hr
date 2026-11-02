# PROGRESS — KlimaKompas HR
Zadnje ažuriranje: 2. 11. 2026. · Trenutna faza: 7 · Rok: pon 9. 11. 2026. 24:00 (freeze 16:00)

## Faze
- [x] F0 Bootstrap i provjera izvora (ned 1. 11.)
- [x] F1 Prostorni temelj, stanovništvo, kostur weba (gotovo 1. 11.)
- [x] F2 Statičke opasnosti
- [x] F3 Indeks, API, karta
- [x] F4 Živi podaci, JLS ploča
- [~] F5 AI i ML gotovi; deploy čeka poslužitelj
- [x] F6 Kvaliteta, standardi, pristupačnost
- [~] F7 Dokumentacija gotova; video snima korisnik
- [ ] F8 Freeze i predaja (pon 9. 11.)

## Trenutni zadaci
- [ ] Deploy na poslužitelj (čeka redak 6 ispod), smoke test i e2e na produkciji.
- [ ] F8: tag `v1.0.0`, Release s izvozima i PDF-om, provjera poveznica.

## Čeka korisnika
| # | Što | Zašto | Rok | Status |
|---|---|---|---|---|
| 2 | Dodati Fabija kao suradnika na GitHubu | §21; suradnik je trenutno samo `dlukas99` | pon 2. 11. | otvoreno |
| 3 | Mentor: tko šalje predaju, pitanja organizatoru (`docs/dopisi/organizator-pitanja.md`), postoji li FERIT poslužitelj ili GPU | §21 | pon 2. 11. | otvoreno |
| 4 | Poslati dopis Hrvatskim vodama (`docs/dopisi/hrvatske-vode.md`) | vektori i potvrda za WMS (P1) | pon 2. 11. | otvoreno |
| 5 | Poslati upit o licenci JRC-u (`docs/dopisi/jrc-licenca.md`) | odgovor određuje licencu izvedenog sloja poplava; bez odgovora ostaje ODbL (ADR 0003) | pon 2. 11. | otvoreno |
| 6 | Odluka: hosting i domena; SSH pristup i `.env` na poslužitelju (`docs/deploy.md`) | bez javnog URL-a predaja nije potpuna | što prije, najkasnije 6. 11. | **blokira deploy** |
| 7 | U Ubuntu terminalu, u mapi `frontend`: `sudo npx playwright install-deps chromium` | sistemske biblioteke za `make e2e` na tvom računalu; do tada koristim privremeno raspakirane u `~/.local/share/kk-browser-libs` | kad stigneš | otvoreno |

| 8 | Snimiti i montirati video (SPEC §19) | samo čovjek | 7.–8. 11. | otvoreno |
| 9 | Upisati puno ime u README i pregledati `docs/dopisi/predaja.md`; mentor šalje predaju | samo čovjek | 9. 11. do 20:00 | otvoreno |

## Odluke (ADR)
- [0001](docs/odluke/0001-korekcije-izvora-nakon-verifikacije.md) Korekcije izvora nakon verifikacije.
- [0002](docs/odluke/0002-open-meteo-prema-uvjetima-api-ja.md) Open-Meteo prema uvjetima API-ja.
- [0003](docs/odluke/0003-licenca-izvedenog-sloja-poplava.md) Licenca izvedenog sloja poplava.
- [0004](docs/odluke/0004-zamjena-za-nedostajuci-pm25.md) Zamjena kad lokalna postaja nema PM2,5.
- [0005](docs/odluke/0005-stanovnistvo-i-dobni-udjeli.md) Stanovništvo i dobni udjeli po ćeliji.
- [0006](docs/odluke/0006-toplina-pozar-i-razredi.md) Toplina, požar i razredi poplava.
- [0007](docs/odluke/0007-hosting-asistent-i-pdf.md) Hosting, asistent i PDF.
- [0008](docs/odluke/0008-asistent-model-razumije-pitanje.md) Mali model samo razumije pitanje.

## Problemi / bilješke
- 2. 11. popravci nakon korisničkog testa:
  - Asistent: adrese se nude samo iz odabrane općine. Slobodna pitanja rade i bez modela, pomoću pravila.
  - Gumb „Otvori punu iskaznicu” više ne vraća na kartu, jer zadnji `moveend` karte više ne mijenja URL.
  - Pretraga smješta naselje i općinu u naseljenu ćeliju. Iskaznica uvijek prikazuje stanovništvo i rizik naselja i općine.
  - Poruka o živim podacima navodi koji izvor kasni.
  - Klizači težina objašnjeni su jednostavnim riječima.
  - Napomena o ograničenju MODIS-a za manje požare.
  - E2e: 48 scenarija.
- F1 gotova: 21 županija, 556 JLS-ova (128 + 428), 6.759 naselja, 60.968 ćelija, 24.464 naseljene, 1.683.411 adresa. Sve naseljene ćelije imaju JLS. Zbroj mreže 3.889.177 (+0,45 %), zbroj DZS-a točno 3.871.833.
- Puni ETL traje oko 9 minuta; adrese 3,5 minute, pa fallback na geokoder bez adresa nije bio potreban.
- E2e (Playwright i axe) prolazi na 1280 px i 360 px, ali se zasad pokreće samo lokalno, ne u CI-ju, jer traži učitane podatke. Radix/shadcn još nisu uvedeni: dosadašnji UI koristi nativne pristupačne elemente.
- Razvojne npm ovisnosti imaju 31 umjerenu ranjivost u `npm audit`; produkcijske 0.
- Podloga: OpenFreeMap je jedini vanjski poziv iz preglednika. Ako je nedostupan, karta prelazi na praznu pozadinu s našim slojevima.
- F2–F6 gotove na lokalnom stacku: svi slojevi, IKR, API, web, worker, asistent, nowcast, kvaliteta, izvozi i OGC. Dokumenti su u `docs/`.
- E2e (38 scenarija) prolazi lokalno na 1280 i 360 px. U CI-ju se ne pokreće jer traži učitane podatke.
- Nije rađeno: suša, vodostaji, validacija poplava, engleski, PWA (P2).
- F0 gotova: `make up` diže PostGIS i Martin, `make check` prolazi, verifikacija je u `docs/izvori-provjera.md`.
- AZO vraća HTTP 429 kod brzih poziva, pa worker u F4 mora razmaknuti zahtjeve. Osijek u provjerenom razdoblju nema trenutni PM2,5, pa F4 provodi ADR 0004.
- Toplinski val izvan sezone nema strukture aktivnog upozorenja, pa parser aktivnog stanja ostaje `TODO(verify)`.
- Licence s oznakom `TODO(verify)` u `config/sources.yaml` treba potvrditi prije objave izvedenih skupova.

## Izrezano (lista rezanja)
- P2 stavke nisu rađene. Ništa iz P0 ni P1 nije izrezano.
