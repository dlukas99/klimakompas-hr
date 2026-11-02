# Metodologija Indeksa klimatskog rizika

Svi parametri su u `config/index.yaml` i `config/thresholds.yaml`, a formule u `backend/src/klimakompas/pipeline/` s golden testovima.

## Okvir

Rizik je funkcija opasnosti (H), izloženosti (E) i ranjivosti (V):

```
R_h = H_h · (0,5 + 0,5 · V_h)
IKR = Σ w_h · R_h / Σ w_h        (w = 0,25 za poplave, toplinu, požar i zrak)
```

Ako jedna opasnost nedostaje, IKR je prosjek dostupnih. Indeks se računa za 24.464 naseljene ćelije; ostale dobivaju samo opasnosti.

## Opasnosti

**Poplave.** Udio ćelije s dubinom većom od 0 m za povratna razdoblja 10, 100 i 500 godina (JRC, oko 90 m):

```
EAF = 0,09 · (s10 + s100)/2 + 0,008 · (s100 + s500)/2 + 0,002 · s500
H_flood = min(1, EAF / 0,10)
```

**Toplina.**

```
H_heat = 0,5 · rn(vrući dani) + 0,25 · rn(tropske noći) + 0,25 · rn(ΔLST)
```

`rn` je normalizacija između 5. i 95. percentila naseljenih ćelija. Vrući dani dolaze iz ECDE-a za 1991.–2020., uz korekciju DHMZ postajama (ADR 0006). ΔLST je medijan ljetne površinske temperature ćelije (Landsat 2024.–2025., 432 scene) minus medijan ruralnih ćelija u krugu od 15 km.

**Požar.**

```
H_fire = 0,7 · rn(dani FWI > 30) · (0,3 + 0,7 · F) + 0,3 · rn(godine s požarom u krugu 2 km)
```

F je udio drveća, grmlja i travnjaka u ćeliji i prstenu od 1 km (WorldCover). Povijest požara je MODIS MCD64A1, 2001.–2025. Taj proizvod ima piksele od 500 m i bilježi samo veće opožarene površine, pa manji požari (trave, jednog polja ili okućnice) u njemu ne postoje. Nula na iskaznici zato znači „satelit nije zabilježio veći požar”, a ne „ovdje nije bilo požara”.

**Zrak.** `H_air = clamp((PM2,5 − 5) / 20, 0, 1)` iz EEA rastera od 1 km za 2023. Vrijednost 5 µg/m³ je smjernica SZO-a (2021.), a 25 µg/m³ dosadašnja granica EU-a. Od 1. 1. 2030. granica EU-a je 10 µg/m³ (Direktiva 2024/2881).

## Ranjivost

```
V_gen  = 0,7 · pr(udio 65+) + 0,3 · pr(udio mlađih od 15)
V_heat = 0,6 · V_gen + 0,4 · (1 − udio drveća)
```

`pr` je percentilni rang. Ćelije s manje od 10 stanovnika koriste udio naselja, a ako njega nema, udio općine ili grada (ADR 0005). Pretpostavljamo da su neslaganja u Census mreži posljedica zaštite povjerljivosti, ali metapodaci to ne potvrđuju.

## Razredi

- **IKR, toplina i požar:** kvintili među naseljenim ćelijama, pa su razredi relativni.
- **Poplave:** granice `H_flood` 0 / 0,03 / 0,25 / 0,55 (ADR 0006).
- **Zrak:** PM2,5 do 5, 10, 15, 25 i više od 25 µg/m³.

## Agregacije

`IKR_jls` je prosjek ćelija ponderiran stanovništvom. Broj stanovnika uzima se iz DZS-a, a izloženi su zbroj stanovnika ćelija razreda 4 ili 5.

## Matrica izvora i ključeva

| Izvor | Ključ spajanja |
|---|---|
| DGU upravne jedinice | šifra županije, JLS-a i naselja |
| DZS Popis 2021. | normalizirani naziv županije, JLS-a i naselja, uz ručnu tablicu |
| Eurostat mreža | `GRD_ID` |
| JRC, EEA, ECDE, Landsat, WorldCover, MODIS | položaj na mreži od 1 km |
| DHMZ upozorenja | naziv županije |
| DHMZ požarni indeks i klimatske tablice | naziv naselja |
| AZO | ID postaje i naziv za koordinate |

## Analiza osjetljivosti

Na 1.000 slučajnih vektora težina (Dirichlet, α = 1) medijan Spearmanova ρ ranga općina prema osnovnom rangu je 0,91, a 5. percentil 0,69. Od 20 općina s najvišim rizikom 4 ostaju među prvih 20 u barem 80 % slučajeva (Kula Norinska, Metković, Opuzen, Zažablje). Ukupni poredak je dakle stabilan, ali točan sastav vrha ovisi o težinama. Rezultati su u `docs/osjetljivost-rezultati.json`, a pokreću se naredbom `make sensitivity`.

## Ograničenja

- Karte poplava su modelirane i pokrivaju samo riječne poplave, bez bujičnih i obalnih. Za česte poplave precjenjuju područje, a nasipi možda nisu u potpunosti obuhvaćeni, pa su visoke brojke uz velike rijeke (npr. Zagreb) gornja procjena.
- Rasteri poplava uključuju i stalne vodene površine, pa ćelije s rijekom dobivaju dio udjela i bez poplavljenog kopna.
- Klimatska mreža je oko 25 km. Vrući dani nakon korekcije imaju grešku oko 8,8 dana godišnje. Dani opasnosti od požara na obali ostaju grubi.
- Korekcija postajama prenosi razliku i na obližnje planinske ćelije, pa one mogu biti precijenjene.
- ΔLST je razlika površinske, a ne temperature zraka, i ne uzima u obzir razliku nadmorske visine.
- Točkasta procjena poplava koristi rastere od oko 90 m, a ostalo je na 1 km.
- Stanovništvo je iz Popisa 2021., a registar naselja iz 2026.
- Ćelije uz granicu sa Slovenijom i Mađarskom uključuju i stanovnike susjedne zemlje.
- Izloženi stanovnici su gornja granica.
- Iskaznica za točku opisuje kvadrat od 1 km oko nje. Pretraga zato smješta naselje u njegovu najnaseljeniju ćeliju, a općinu ili grad u najnaseljeniju ćeliju najvećeg naselja. Uz točku iskaznica uvijek prikazuje i broj stanovnika te razred rizika cijelog naselja i općine iz Popisa 2021.
- Povijest požara vidi samo veće požare (MODIS, 500 m). Podaci o intervencijama vatrogasaca po naseljima nisu objavljeni kao otvoreni podaci.
- Klimatologija nije prognoza. Razredi su relativni. Indeks nije službena procjena rizika.
