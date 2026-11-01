# Projektna dokumentacija

## Problem

Podaci o klimatskim rizicima u Hrvatskoj postoje, ali su razasuti: upozorenja su kod DHMZ-a, kvaliteta zraka kod ministarstva, karte poplava kod Hrvatskih voda i JRC-a, stanovništvo kod DZS-a i Eurostata, a granice kod DGU-a. Građanin ne može jednostavno saznati što to znači za njegovu adresu, a općina nema jednu sliku rizika za svoje stanovnike.

Što pokazuju naši izračuni (gornja procjena iz ćelija od 1 km, vidi ograničenja):

- oko 628.000 stanovnika živi u ćelijama visokog razreda opasnosti od riječnih poplava (model JRC);
- oko 1,5 milijuna stanovnika živi u ćelijama s godišnjim prosjekom PM2,5 iznad 15 µg/m³, što je tri puta iznad smjernice SZO-a od 5 µg/m³ (EEA, 2023.).

## Cilj

Besplatan alat otvorenog koda koji za svaku adresu, naselje, općinu i grad na jednom mjestu pokazuje izloženost poplavama, toplini, požarima i onečišćenju zraka, uz izvor svake brojke.

## Korisnici

| Korisnik | Što treba | Gdje to dobiva |
|---|---|---|
| Građanin | razumjeti rizik za svoju adresu i što može učiniti | iskaznica |
| Službenik općine ili grada | koliko je ljudi izloženo i gdje, usporedba | JLS ploča, CSV |
| Civilna zaštita | brz pregled i živa upozorenja | karta, rang-liste |
| Novinar ili istraživač | izvorni i izvedeni podaci | /podaci, API, DCAT-AP |

## Opseg

- 1-km mreža INSPIRE, 6.759 naselja, 556 općina i gradova, 21 županijska jedinica.
- Četiri opasnosti i Indeks klimatskog rizika (IKR).
- Živi slojevi: upozorenja DHMZ-a, kvaliteta zraka, požarni indeks, zaštićena područja.
- Asistent koji koristi isključivo rezultate svojih alata.

Izvan opsega: službena procjena rizika, prognoza pojedinih događaja, projekcije klimatskih promjena.

## Tijek rada

1. Provjera svih izvora stvarnim dohvatom (`docs/izvori-provjera.md`).
2. Prostorni temelj i stanovništvo, s kontrolama prema Popisu 2021.
3. Statičke opasnosti, indeks, API i karta.
4. Živi podaci, JLS ploča, asistent i nowcast.
5. Kvaliteta podataka, izvozi, pristupačnost i dokumentacija.

Odluke koje odstupaju od početne specifikacije zapisane su kao ADR-ovi u `docs/odluke/`.

## Uloge

- **Tim Požega (FERIT Osijek):** razvoj, provjera podataka, video.
- **Mentor dr. sc. Matej Džijan:** vođenje i predaja.

## Rizici

| Rizik | Kako je riješen |
|---|---|
| Ispad izvora | zadnja dobra vrijednost, vrijeme osvježavanja i poruka umjesto greške |
| Proturječna licenca karata poplava | izvedeni skupovi pod ODbL dok JRC ne odgovori (ADR 0003) |
| Gruba klimatska mreža | korekcija mjerenjima DHMZ-a i izmjerena greška (ADR 0006) |
| Nepouzdani dobni podaci malih ćelija | prag od 10 stanovnika i udio naselja (ADR 0005) |
| Nedostupan LLM | brza pitanja bez modela |

## Rezultati

- Javni kod pod EUPL-1.2, izvedeni skupovi s opisom u DCAT-AP.
- Sve kontrole prolaze: 3.871.833 stanovnika prema DZS-u, mreža unutar +0,45 %, 556 JLS-ova.
- Rang općina stabilan je na promjene težina: medijan Spearmanova ρ je 0,91 na 1.000 slučajnih težina.

## Održivost

Sustav se može preuzeti bez nas, jer je sav izračun ponovljiv iz `config/` i javnih izvora. Prirodni nositelji su općine i gradovi, ministarstvo nadležno za okoliš i podatkovna infrastruktura uz Portal otvorenih podataka. Troškovi su jedan poslužitelj; skup podataka zauzima oko 1,4 GB.
