# Kvaliteta podataka

Provjere se pokreću naredbom `make quality`, spremaju u `meta.dq_checks`, a uživo su na `/api/v1/quality` i stranici /podaci. Kontrole iz učitavanja ruše učitavanje ako nisu zadovoljene, pa prethodni podaci ostaju.

## Što provjeravamo

| Provjera | Što mjeri |
|---|---|
| Dostupnost i svježina | status zadnjeg učitavanja i starost prema očekivanoj kadenci |
| Potpunost | udio postaja s podatkom u zadnja 3 sata, ćelije bez vrijednosti |
| Rasponi | dopuštene vrijednosti, npr. PM2,5 od 0 do 1000 µg/m³ |
| Metapodaci na Portalu | licenca prisutna, izdavač aktivan |
| Dosljednost ključeva | 556 JLS-ova, 21 županijska jedinica, naselja s podacima Popisa |

## Nalazi (2. 11. 2026.)

| Izvor | Nalaz |
|---|---|
| Natura 2000 na Portalu | zapis nema licencu, a izdavač je označen kao neaktivan (HAOP) |
| AZO postaje | od 93 navedene postaje samo 33 imale su podatke u zadnjih 7 dana; od njih 94 % ima svježe mjerenje |
| AZO dokumentacija | uputa navodi „0 Json, 1 xml” za `tipPodatka`, a stvarno je 0 satni i 4 dnevni podaci; oblik odgovora razlikuje se od upute; odgovor je bez upozorenja ograničen na 1.000 zapisa |
| DZS Popis 2021. | tablica naselja nema šifre, pa se spaja po nazivima, a 5 naselja nema para u registru |
| DGU registar | 7 naselja novija su od Popisa; opis na Portalu navodi SHP, a stvarni format je GML |
| Eurostat mreža | zbrojevi se ne slažu: u 18.708 od 24.464 naseljene ćelije M + F nije T, a u 452 ćelije 65+ je veći od T |
| DHMZ klimatske tablice | nemaju koordinate postaja |
| EEA PM2,5 | 83 ćelije nemaju vrijednost ni nakon popunjavanja do 3 km, a 914 je popunjeno |
| JRC karte poplava | licenca je proturječna: `copyright.txt` navodi CC BY 4.0, a katalog i README ODbL 1.0 |
| Hrvatske vode | `robots.txt` je 1. 11. vratio HTTP 503, pa ga tretiramo kao zabranu |

## Preporuke izdavateljima

1. **MZOZT:** uskladiti uputu AZO servisa sa stvarnim ponašanjem, objaviti popis postaja kao API s ID-jem i koordinatama te navesti uvjete ponovne uporabe i ograničenje učestalosti.
2. **DZS:** dodati službene šifre JLS-a i naselja u tablice Popisa, jer spajanje po nazivima nije pouzdano.
3. **Portal i MZOZT:** ažurirati licencu i izdavača zapisa Natura 2000.
4. **DHMZ:** dodati koordinate u klimatske tablice i objaviti broj tropskih noći.
5. **Hrvatske vode:** omogućiti automatizirani pristup ili objaviti vektore karata pod otvorenom licencom te strojno čitljive vodostaje.
6. **DGU:** uskladiti opis formata na Portalu sa stvarnim datotekama.
7. **JRC:** razjasniti licencu karata poplava.
