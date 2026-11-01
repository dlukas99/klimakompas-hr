# ADR 0003: Licenca izvedenog sloja poplava

- **Status:** prihvaćeno (odluka korisnika); konačna licenca čeka odgovor JRC-a
- **Datum:** 1. 11. 2026.

## Kontekst

Za `jrc_efas_flood` `copyright.txt` navodi CC BY 4.0, a README i JRC Data Catalogue ODbL 1.0. SPEC
§15.3 za izvedene skupove predviđa CC BY 4.0. Upit JRC-u je u `docs/dopisi/jrc-licenca.md`.

## Odluka

1. Karte JRC-a koristimo za izračun poplavnog sloja.
2. Licencu izvedenog sloja poplava određuje konačni odgovor JRC-a.
3. Ako do predaje ostane nejasno, zadana licenca izvedenog sloja poplava je **ODbL 1.0**.

## Posljedice

ODbL ima obvezu dijeljenja pod istim uvjetima, a `ikr-celije-1km` i `ikr-jls` u sebi sadrže
vrijednosti izvedene iz poplavnog sloja. Odluka izričito ne govori o njima, pa do odgovora JRC-a
primjenjujemo oprezno pravilo:

- Izvozi imaju licencu **po skupu** u `dct:license`, a ne jednu za cijeli katalog.
- Skupovi sa stupcima izvedenima iz JRC-a (`h_flood`, `r_flood`, `ikr` i razredi) nose istu licencu
  kao poplavni sloj. Ostali izvedeni skupovi nose CC BY 4.0.
- Ako JRC potvrdi CC BY 4.0, svi izvedeni skupovi prelaze na CC BY 4.0 bez promjene koda.
- Licenca se bira na jednom mjestu u konfiguraciji izvoza, a konačna vrijednost upisuje se u
  `config/sources.yaml`, `docs/izvori-podataka.md` i stranicu /podaci.

OSM i dalje ne ulazi u izvedene skupove.
