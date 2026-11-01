# ADR 0004: Zamjena kad lokalna postaja nema PM2,5

- **Status:** prihvaćeno (odluka korisnika)
- **Datum:** 1. 11. 2026.

## Kontekst

Postaje u Osijeku nisu vratile PM2,5 za 29. 10. – 1. 11. 2026. Provjera od 1. 11. pokazuje da
Osijek-1 (`160`) ima satni PM10, s najnovijim zapisom od istog dana. Osijek – PPI (`300`) nema ni
PM10 ni PM2,5.

## Odluka

Kad lokalna postaja nema svjež PM2,5 (prag zastarjelosti je 6 h, SPEC §4.2), prikaz ide ovim redom:

1. **PM10 lokalne postaje**, s oznakom da je to druga onečišćujuća tvar.
2. **PM2,5 najbliže postaje sa svježim podacima**, s nazivom postaje i udaljenošću.
3. Ako nema ni jednog ni drugog, poruka da trenutni podatak nije dostupan, uz vrijeme zadnjeg
   mjerenja.

Pravila:

- PM10 se ne preračunava u PM2,5 i ne ulazi u nowcast PM2,5 kao da je PM2,5.
- Razina kvalitete računa se pragovima za prikazanu tvar, a ne pragovima za PM2,5.
- Uz svaku zamjenu UI izričito navodi što se prikazuje, s koje postaje i iz kojeg vremena. Tekstovi
  su u `frontend/src/i18n/hr.json`.
- Asistent dobiva istu oznaku u rezultatu alata, pa zamjensku vrijednost ne može predstaviti kao
  lokalni PM2,5.

Ovo se odnosi samo na prikaz trenutnog stanja. Kronična komponenta IKR-a i dalje dolazi iz EEA
rastera od 1 km.

## Posljedice

Pravilo se primjenjuje na sve postaje, ne samo na osječke. Provedba je u Fazi 4 (`live`, API i UI).
Pragovi za PM10 moraju biti u `config/thresholds.yaml` i potvrđeni kod izvora; `eaqi.bands` je zasad
prazan i označen `TODO(verify)`.
