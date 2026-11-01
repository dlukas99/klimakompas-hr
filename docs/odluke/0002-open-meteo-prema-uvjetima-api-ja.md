# ADR 0002: Open-Meteo koristimo prema uvjetima API-ja

- **Status:** prihvaćeno (odluka korisnika)
- **Datum:** 1. 11. 2026.

## Kontekst

Faza 0 pokazala je da API hostovi Open-Meteo-a (`api`, `archive-api`, `air-quality-api`) u
`robots.txt` imaju `Disallow: /`, dok stranica `open-meteo.com` ima `Allow: /`. Isti izdavač API
javno dokumentira za programski pristup i objavljuje ograničenja poziva.

Pravilo 5 u `CLAUDE.md` traži poštivanje `robots.txt` i uvjeta korištenja, pa je za ovo odstupanje
potrebna izričita odluka.

## Odluka

Open-Meteo je dopušten. `robots.txt` tih hostova tumačimo kao pravilo za crawlere, a ne za pozive
dokumentiranog API-ja. Ovo vrijedi samo za Open-Meteo i nije presedan za druge izvore. Hrvatske vode
ostaju samo WMS u pregledniku korisnika, kako je u SPEC §4.2.

Uvjeti ([terms](https://open-meteo.com/en/terms), [pricing](https://open-meteo.com/en/pricing),
provjereno 1. 11. 2026.):

- **Namjena:** samo nekomercijalna. Uvjeti u to ubrajaju neprofitne stranice bez pretplate i oglasa.
- **Limiti:** 600 poziva u minuti, 5.000 na sat, 10.000 na dan i 300.000 na mjesec. Mjesečni limit
  nije bio u SPEC-u. Primjenjuju se po IP adresi i aplikaciji.
- **Težina poziva:** `lokacije × (dani / 14) × (varijable / 10)`. Više modela povećava težinu.
  Veliki posao dijelimo u batcheve ispod satnog limita.
- **Atribucija:** „Weather data by Open-Meteo.com (CC BY 4.0)”, a za CAMS još i Copernicus navod iz
  SPEC §4.3.

U `config/sources.yaml` izvor ima `verify.policy: api_terms`: provjera čita i prijavljuje
`robots.txt`, a na svaki host šalje po jedan najmanji poziv. Polje `robots_allowed` ostaje `false`
jer opisuje stvarno stanje.

## Posljedice

- Značajke nowcasta, CAMS rezerva i rezerva za ECDE ponovo su dostupne.
- Izdavač može blokirati aplikaciju bez najave. Žive vrijednosti zato imaju spremnik zadnje dobre
  vrijednosti, a nijedan P0 sloj ne ovisi samo o ovom izvoru.
- Ako projekt postane komercijalan, treba plaćeni plan ili vlastiti hosting (`daljnji-razvoj.md`).
