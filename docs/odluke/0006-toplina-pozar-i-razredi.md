# ADR 0006: Toplina, požar i razredi poplava po ćeliji

- **Status:** prihvaćeno
- **Datum:** 2. 11. 2026.

## Kontekst

ECDE daje klimatske pokazatelje na mreži ERA5 od 0,25° (oko 25 km). Provjera na stvarnim mjestima pokazala je da to nije dovoljno za obalu: ćelija kod Splita prosječno leži visoko na Mosoru i Biokovu, pa je dala 2 vruća dana godišnje, a DHMZ-ova postaja Split Marjan bilježi oko 44. Interpolacija samo preko kopnenih točaka nije pomogla, jer uzrok nije more nego reljef.

SPEC §5.3 ne definira ni razred poplava za ćeliju, nego samo za točku.

## Odluka

1. **Vrući dani:** ERA5 za 1991.–2020. plus IDW korekcija razlika prema DHMZ postajama (`klima.hr/k1`, 21 postaja, najviše 5 susjeda, do 100 km). Zavižan je izostavljen jer je na 1.594 m. Postaja nema koordinate, pa dobiva točku naselja (`config/crosswalks/dhmz_k1_stations.yaml`).
2. **Tropske noći i dani opasnosti od požara:** bilinearno iz ECDE-a. Za njih nema podataka po postajama.
3. **Površinska temperatura (LST):** medijan po scenama srednje vrijednosti ćelije, umjesto medijana po pikselu, jer je obrada 432 scene tako izvediva na prijenosnom računalu. Koriste se pregledi rastera od oko 120 m.
4. **Razred poplava po ćeliji:** granice `H_flood` 0 / 0,03 / 0,25 / 0,55 u `config/index.yaml`. Izabrane su tako da cijela ćelija samo u RP500 dobije razred 3, samo u RP100 razred 4, a u RP10 razred 5, kao i kod točke.
5. **Popunjavanje PM2,5:** ćelije bez vrijednosti uz obalu preuzimaju najbližu vrijednost do 3 km i dobivaju oznaku `gap_filled`.

## Posljedice

- Greška vrućih dana na postajama, metodom izostavljanja jedne postaje, pada s 13,8 na 8,8 dana godišnje. To je mjerena, ali još uvijek velika nesigurnost, pa je navedena u ograničenjima.
- Postaje imaju dulje razdoblje (npr. 1948.–2024.) od referentnog 1991.–2020.
- Dani opasnosti od požara ostaju grubi na obali (npr. Split 1,3 i Zadar 52 dana), što je izravno navedeno u ograničenjima.
- E-OBS (0,1°) bio bi bolji izvor, ali traži zasebnu licencu na računu korisnika. Naveden je u daljnjem razvoju.
