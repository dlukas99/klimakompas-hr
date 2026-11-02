# Izjava o pristupačnosti

Cilj je sukladnost s WCAG 2.1 na razini AA.

## Što je napravljeno

- Sve je dostupno tipkovnicom, uključujući pretragu (combobox s ARIA oznakama) i slojeve karte.
- Razina rizika uvijek je prikazana bojom, brojem i riječju, pa ne ovisi samo o boji.
- Kontrast teksta je najmanje 4,5:1, a provjerava ga axe-core na svakoj stranici.
- Paleta rizika (YlOrRd) ima monotonu svjetlinu.
- Karta ima tablični prikaz, a podaci s karte dostupni su i na stranicama iskaznice i općina.
- Jezik stranice je označen (`lang="hr"`), a postoji i poveznica za preskakanje na sadržaj.
- Stranice rade na širini od 360 px.

## Kako provjeravamo

`make e2e` pokreće Playwright i axe-core na svim stranicama, na 1280 px i 360 px.

Lighthouse (mobilni profil, 2. 11. 2026., lokalni produkcijski stack):

| Stranica | Pristupačnost | Performanse |
|---|---|---|
| Početna | 100 | 95 |
| Iskaznica | 100 | 93 |
| Karta | 100 | 64–68 |

Karta je ispod cilja od 80 za performanse. Mjerena je uz softverski WebGL, koji je sporiji od grafike stvarnog mobitela, a najveći dio čini biblioteka karte od oko 1 MB. Stvarni uređaj treba provjeriti nakon deploya.

## Poznata ograničenja

- Sama karta je grafički prikaz: čitač zaslona ne može čitati pojedine ćelije, zato postoje iskaznica, pretraga i tablice.
- Klik na kartu traži pokazivač. Isti podaci dostupni su pretragom.
- Službene karte Hrvatskih voda su slike s vanjskog servisa, bez opisa.

## Povratne informacije

Probleme s pristupačnošću prijavite kao issue u [GitHub repozitoriju](https://github.com/dlukas99/klimakompas-hr/issues).
