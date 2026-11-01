# Preduvjeti za rad i preuzimanje sustava

## Tehnički

- **Poslužitelj:** 4 vCPU i 8 GB RAM-a, oko 20 GB diska. Za LLM dodatno GPU ili barem 16 GB RAM-a.
- **Softver:** Linux, Docker s Composeom. Sve ostalo je u slikama.
- **Razvoj i obrada:** Python 3.12, `uv`, Node 26, oko 2 GB za sirove podatke.
- **Mreža:** javni HTTPS (portovi 80 i 443) i odlazni pristup izvorima. Puna obrada traje oko sat vremena, od čega je najdulji Landsat.

## Organizacijski

- **Vlasnik sustava** odgovoran za poslužitelj, ažuriranja i komunikaciju s izdavačima.
- **Održavanje:** praćenje stranice /podaci, osvježavanje statičkih slojeva jednom godišnje ili kad izdavač objavi novu verziju.
- **Suradnja s izdavačima:** vidi preporuke u `docs/kvaliteta-podataka.md`.

## Pravni

- **Licenca koda:** EUPL-1.2.
- **Izvedeni podaci:** CC BY 4.0, a skupovi izvedeni iz karata poplava JRC-a ODbL 1.0 dok JRC ne potvrdi drugačije (ADR 0003).
- **Izvori:** svaki s licencom u `docs/izvori-podataka.md`.
- **Hrvatske vode:** karte se prikazuju samo iz preglednika korisnika, jer `robots.txt` servisa ne dopušta automatizirani dohvat. Za preuzimanje vektora poslan je upit.
- **Open-Meteo:** samo za nekomercijalnu uporabu, unutar limita i uz atribuciju (ADR 0002). Komercijalna uporaba traži plaćeni plan ili vlastiti hosting.
- **GDPR:** ne obrađujemo osobne podatke korisnika. Ne bilježe se adrese, upiti ni razgovori, nema kolačića za praćenje. Javni dobavljači podloge (OpenFreeMap) i WMS-a (Hrvatske vode) vide IP adresu preglednika kao i svaki web-poslužitelj.
- **Povjerljivost podataka Popisa:** ćelije s manje od 10 stanovnika ne prikazuju broj stanovnika.
- **Pristupačnost:** vidi `docs/pristupacnost.md`.
- **Nije službeno:** ne koristimo grb RH ni logotipe tijela, a uz svaki prikaz rizika stoji izjava o ograničenju odgovornosti.
