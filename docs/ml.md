# Nowcast PM2,5

Model predviđa PM2,5 na postajama 3, 6, 12 i 24 sata unaprijed, s rasponom nesigurnosti. Ne ulazi u Indeks klimatskog rizika, nego se prikazuje na iskaznici uz oznaku modela.

## Podaci

- **Mjerenja:** satni PM2,5 iz AZO servisa, zadnje dvije godine, 19 postaja s barem 2.000 sati podataka. Servis vraća najviše 1.000 zapisa po zahtjevu, pa se povijest puni u dijelovima od 40 dana.
- **Meteorologija:** Open-Meteo, povijest za trening i prognoza za serviranje: temperatura, vlaga, vjetar, oborina i tlak.
- **CAMS PM2,5:** Open-Meteo, kao značajka i kao usporedba.

## Model

LightGBM s horizontom kao značajkom. Uči promjenu u odnosu na trenutnu vrijednost, što je za kratke horizonte točnije nego učenje apsolutne vrijednosti. Raspon daju kvantilni modeli za 10. i 90. percentil.

**Značajke:** lagovi 1, 2, 3, 6, 12 i 24 h, pomični prosjeci 3, 6 i 24 h, sat, dan u tjednu, mjesec, sezona grijanja, državni praznik, meteorologija i CAMS za ciljni sat te postaja.

Značajke povijesti koriste samo vrijednosti poznate u trenutku izdavanja, što provjeravaju testovi u `tests/unit/test_ml_features.py`.

## Validacija

Vremenska, rolling-origin, s tri uzastopna testna razdoblja od 30 dana: od 2026-08-03 do 2026-11-01. Model se za svako razdoblje uči samo na ranijim podacima. Ukupno je 191.910 predviđanja.

| Horizont | MAE modela | RMSE | Perzistencija | t−24 h | CAMS | Dobitak prema perzistenciji | Pokrivenost raspona |
|---|---|---|---|---|---|---|---|
| 1 h | 1,397 | 2,725 | 1,166 | 3,536 | 3,907 | -20 % | 78 % |
| 3 h | 2,109 | 3,887 | 2,333 | 3,542 | 3,911 | 10 % | 77 % |
| 6 h | 2,618 | 4,567 | 3,297 | 3,547 | 3,91 | 21 % | 76 % |
| 12 h | 2,921 | 4,885 | 3,89 | 3,549 | 3,909 | 25 % | 75 % |
| 24 h | 3,004 | 4,947 | 3,585 | 3,585 | 3,883 | 16 % | 76 % |
| **Ukupno** | **2,401** | 4,272 | 2,841 | 3,552 | 3,904 | 16 % | 76 % |

Vrijednosti su u µg/m³. Raspon je namijenjen pokrivenosti od 80 %.

## Što iz toga slijedi

- Model je bolji od perzistencije, vrijednosti od jučer i sirovog CAMS-a na horizontima od 3 do 24 sata, pa se prikazuje on, a ne CAMS.
- **Na 1 sat model je lošiji od perzistencije, pa se taj horizont ne prikazuje.** Prikazuju se samo horizonti s pozitivnim dobitkom, a pravilo se primjenjuje automatski nakon svakog treninga.
- Raspon pokriva nešto manje od nominalnih 80 %, pa je malo preuzak.
- Greška se razlikuje po postajama: najmanja MAE je 1,102 (postaja 224), a najveća 4,614 µg/m³ (postaja 162). Najteže su industrijske i gradske postaje.

## Ograničenja

- Testna razdoblja su od kolovoza do listopada, pa zimske epizode onečišćenja nisu ocijenjene na najnovijim podacima.
- Podaci AZO servisa nisu označeni kao validirani.
- Model radi samo za postaje koje imaju svježe mjerenje; bez njega nema prognoze.
- Zadnjih tjedan dana treninga nema arhivske meteorologije; takve retke model obrađuje kao nedostajuće vrijednosti.

Pokretanje: `make ml-train`. Rezultati su u `docs/ml-rezultati.json`.
