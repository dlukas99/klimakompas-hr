# KlimaKompas HR

[![CI](https://github.com/dlukas99/klimakompas-hr/actions/workflows/ci.yml/badge.svg)](https://github.com/dlukas99/klimakompas-hr/actions/workflows/ci.yml)

> **Nacrt.** Projekt je u izradi i javni demo još ne postoji.

KlimaKompas HR je web-aplikacija otvorenog koda koja za svaku 1-km ćeliju, naselje, općinu i grad u Hrvatskoj procjenjuje izloženost poplavama, toplini, požarima i onečišćenju zraka. Tu izloženost križa s ranjivošću stanovništva iz Popisa 2021. u Indeks klimatskog rizika (IKR).

Izrađuje je tim Požega s FERIT-a Osijek za Datathon Portala otvorenih podataka 2026., izazov B – Okoliš i održivi prostor.

## Brzi start

Potrebni su Docker s Composeom, `make`, [uv](https://docs.astral.sh/uv/) i Node (verzija u `.nvmrc`).

```bash
make setup            # ovisnosti, .env iz predloška i pre-commit
make up               # PostGIS i Martin
make check            # testovi i provjere koda
make sources-verify   # provjera izvora, rezultat u docs/izvori-provjera.md
```

## Izvori podataka

Registar svih izvora je `config/sources.yaml`, a zadnji rezultat provjere `docs/izvori-provjera.md`.

## Ograničenje odgovornosti

KlimaKompas HR informativni je alat izrađen na Datathonu Portala otvorenih podataka 2026. Procjene se temelje na otvorenim podacima i modelima. One nisu službena procjena rizika niti zamjena za upozorenja DHMZ-a, Hrvatskih voda i civilne zaštite. U hitnoj situaciji nazovite 112.

## Licence

Kod je objavljen pod licencom [EUPL-1.2](LICENSE), a izvedeni podaci pod CC BY 4.0. Popis alata je u `docs/alati-i-licence.md`.
