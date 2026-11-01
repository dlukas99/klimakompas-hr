# ADR 0001: Korekcije izvora nakon verifikacije

- **Status:** prihvaćeno
- **Datum:** 1. 11. 2026.

## Kontekst

Verifikacija u Fazi 0 pokazala je da se dio izvora razlikuje od opisa u SPEC §4.2.

## Odluka

| Izvor | SPEC | Stvarno stanje | Što radimo |
|---|---|---|---|
| `dgu_au`, `dgu_ad` | SHP u EPSG:3765 | INSPIRE GML 3.2.1 u EPSG:3035 | Čitamo GML. Mreža je već u EPSG:3035, pa nema dodatne reprojekcije. |
| `estat_census_grid_2021` | verzija iz siječnja 2025. | postoji V3 iz lipnja 2026. | Koristimo V3 kao najnoviju objavu. |
| `jrc_efas_flood` | v3.1.0, oko 100 m | v3.1.1, oko 90 m, WGS84 | Koristimo v3.1.1 i čitamo rastere prozorima preko HTTP Range. |
| `eea_pm25_1km` | putanja `/webdav/` | putanja `/datastore/public/` | Koristimo novu putanju. |
| `azo_aq_rest` | ugniježđen JSON, ISO vrijeme | ravan JSON, epoha u ms, HTTP 429 kod brzih poziva | Parser prati stvarni oblik, a worker razmiče pozive. |
| `landsat_lst` | asset `lwir11` ili `ST_B10` | postoji samo `lwir11` | Koristimo `lwir11`. |

Dokazi su u `docs/izvori-provjera.md` i u fiksturama `backend/tests/fixtures/`.

## Posljedice

Nazivi polja i šifri u GML-u i Census mreži potvrđuju se na podacima u Fazi 1.

Licenca `jrc_efas_flood` i korištenje `open_meteo` ostaju otvoreni i vode se u `PROGRESS.md`, jer
te odluke nisu tehničke.
