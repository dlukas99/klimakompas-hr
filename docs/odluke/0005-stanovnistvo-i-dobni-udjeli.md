# ADR 0005: Stanovništvo i dobni udjeli po ćeliji

- **Status:** prihvaćeno (odluka korisnika)
- **Datum:** 1. 11. 2026.

## Kontekst

Provjera stvarnih datoteka u Fazi 1 pokazala je tri stvari koje SPEC ne predviđa:

1. **Dobne vrijednosti u Census mreži nisu usklađene.** U 18.708 od 24.464 naseljene ćelije `M + F`
   nije jednako `T`, a u 452 ćelije `Y_GE65` je veći od `T`. RH nema vrijednosti označenih kao
   povjerljive (`-8888`, `-9999`), pa pravilo iz SPEC §5.4 („zamjena kad je vrijednost NULL”) nikad
   ne bi djelovalo.
2. **Tablica DZS-a nema šifre**, samo nazive županija, JLS-ova i naselja.
3. **Registar DGU-a je noviji od Popisa**, pa se dio naziva i naselja razlikuje.

**Pretpostavka, ne utvrđena činjenica:** odstupanja `M + F ≠ T` vjerojatno su posljedica zaštite
povjerljivosti (dodani šum). Metapodaci za RH uz Census mrežu ne opisuju takvu metodu.

## Odluka

### Dobni udjeli po ćeliji

Čista funkcija `pipeline/population.py: age_shares`, a prag je u `config/thresholds.yaml`
(`population.min_cell_pop_for_age_shares = 10`):

| Stanje ćelije | Izvor udjela | `age_share_source` |
|---|---|---|
| `pop_total ≥ 10`, dobne vrijednosti postoje | sama ćelija, udio ograničen na najviše 1 | `cell` |
| manje od 10 stanovnika ili prikrivena vrijednost | naselje iz DZS-a | `naselje` |
| naselje nema stanovnika ili nije u Popisu | JLS iz DZS-a | `jls` |
| ćelija bez stanovnika | nema udjela | prazno |

Tablica starosti po naseljima postoji (list „1.” u `popis_2021-stanovnistvo_po_naseljima.xlsx`), pa
je udio naselja prvi izbor. Vrijednosti `naselje` i `jls` u Fazi 3 postaju `v_imputed = true`.

Stanje nakon učitavanja:

| Izvor | Ćelija | Stanovnika |
|---|---|---|
| `cell` | 17.824 | 3.861.486 |
| `naselje` | 6.608 | 27.594 |
| `jls` | 32 | 97 |

Zamjena dira 27 % naseljenih ćelija, ali samo 0,7 % stanovništva.

### Spajanje DZS-a i DGU-a

Spajamo normalizirane nazive unutar županije i JLS-a. Normalizacija izjednačava veličinu slova, vrstu
crtice i razmake, a dvojezični nazivi spajaju se po hrvatskom dijelu. Svako naselje koje se ne spoji
i nije navedeno u ručnoj tablici `config/crosswalks/dzs_dgu_naselja.yaml` ruši učitavanje.

Od 11 naziva koji se nisu spojili u prvoj provjeri:

- 4 („… – dio”) rješava normalizacija;
- 2 rješava preimenovanje JLS-a Murter-Kornati u Murter;
- 5 nema para u registru DGU-a: Martinska Ves (Vrbovec, 451 st.), Međedi, Mlinari, Radočaj i Tomići
  (Vrbovsko, 19 st.). Ti se stanovnici broje samo u JLS-u, pa državni i JLS zbrojevi ostaju točni.

Sedam naselja postoji samo u registru DGU-a jer su novija od Popisa: šest u Vrbovcu (2026.) i Korana
u Rakovici (2024.). Nemaju podatke Popisa, pa njihove ćelije koriste udio JLS-a.

### Zbrojevi

Stanovništvo JLS-a i naselja uzimamo iz DZS-a, a ne zbrajanjem ćelija. Ćelije zajedničke sa
Slovenijom i Mađarskom (`HR-SI`, `HR-HU`) uključuju i stanovnike susjedne zemlje: zbroj mreže je
3.889.177, odnosno +0,45 % prema Popisu, a primjerice Cestica ima 5.425 stanovnika u DZS-u i 8.001 u
ćelijama. Mreža služi za prikaz i izračun po ćeliji.

## Posljedice

- Uz ćeliju se ne prikazuje točan dobni broj kao činjenica, nego udio i njegov izvor.
- Agregacije po JLS-u u Fazi 3 za broj stanovnika koriste DZS, a izloženost računaju iz ćelija, pa se
  na granici može pojaviti razlika koju treba objasniti u metodologiji.
- Vrijednost praga je procjena, a ne rezultat analize; može se mijenjati u konfiguraciji.
