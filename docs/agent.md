# AI asistent

Asistent odgovara na pitanja o klimatskim rizicima na hrvatskom. Činjenice dolaze isključivo iz alata, uz citat izvora. Razgovori se ne spremaju.

## Kako radi

Zadani način rada je strukturirani (ADR 0008):

1. Model `granite4:3b` (Apache 2.0, preko OpenAI-kompatibilnog API-ja) pitanje pretvara u strukturirani zahtjev: namjeru, mjesto, opasnost i mjeru.
2. Zaštite provjeravaju zahtjev: mjesto se mora spominjati u pitanju i imati stvarno podudaranje naziva.
3. Kod poziva alat i sastavlja odgovor iz predložaka, s citatima `[n]`.
4. Provjera utemeljenosti još jednom usporedi sve brojeve s rezultatima alata.

Bez modela i dalje rade **brza pitanja** (`/api/v1/agent/quick`), a stranica sama provjerava je li model dostupan.

Način `LLM_MODE=tools` uključuje petlju alata iz koje model sam piše odgovor, s provjerom brojki, jednim ponovnim pokušajem i uklanjanjem neutemeljenih rečenica. Namijenjen je većim modelima.

## Alati

`geocode`, `get_place_card`, `get_jls_profile`, `rank_areas`, `get_active_warnings`, `get_air_quality` i `search_open_data`. Svi su samo za čitanje i vraćaju podatke, izvore i vrijeme.

## Sigurnost i privatnost

Ograničenje je 10 zahtjeva u minuti po klijentu, brojač je samo u memoriji, ulaz je do 1.000 znakova, a razgovori i upiti se ne bilježe. Naredbe u pitanju ne mogu promijeniti podatke, jer tekst odgovora ne dolazi iz modela.

## Evaluacija

Skup ima 64 pitanja: rangiranja, iskaznice, općine, upozorenja, zrak, pretraga podataka, teme izvan opsega i zamke. Pokretanje: `kk agent eval`. Mjereno na RTX 3050 Ti s 4 GB VRAM-a.

| Mjera | Neviđena pitanja (14) | Svih 64 |
|---|---|---|
| Točan odabir alata | 79 % | 86 % |
| Provjere sadržaja (zamke, odbijanja) | 93 % | 97 % |
| Utemeljene brojke | 100 % | 100 % |
| Odgovori s izvorom, kad je korišten alat | 77 % | 83 % |
| Latencija p50 / p95 | 0,9 s / 2,3 s | 1,0 s / 3,4 s |

**Mjerodavan je prvi stupac.** Prvih 50 pitanja koristilo se pri doradi prompta i zaštita, pa je drugi stupac optimističan. Neviđenih 14 pitanja dodano je nakon zadnje dorade i nakon njih ništa nije mijenjano.

Odgovori s alatom bez izvora su odgovori tipa „nisam pronašao to mjesto”, gdje nema podatka koji bi se citirao.

### Poznate greške na neviđenim pitanjima

- „Trebam li se brinuti zbog požara u Zadru?” → Aktivna upozorenja DHMZ-a: Narančasto upozorenje za vjetar; Žuto upozorenje za vjetar. Područja: Zadarska [1].…
- „Kakva je sada kvaliteta zraka u Rijeci?” → Za mjesto Rijeka ukupni klimatski rizik je Umjeren, veći od 54 % naseljenih područja u Hrvatskoj [1]. Zrak: Um…
- „Koliko je glavni grad Francuske udaljen od Zagreba?” → Nisam pronašao to mjesto u Hrvatskoj. Provjerite naziv ili upišite adresu.…

Takve greške daju siguran neuspjeh ili točan odgovor na srodno pitanje. Provjerena je i petlja alata s istim modelom: 91 % točnih alata, ali samo 69 % utemeljenih brojki i izmišljene tvrdnje, zbog čega nije zadani način (ADR 0008).

## Ograničenja

- Podržane su formulacije bliske primjerima u `agent/prompts/intent_hr.md`.
- Mali model griješi u razumijevanju, pa asistent uvijek pokazuje na što odgovara i navodi izvor.
- Model na poslužitelju bez GPU-a bit će sporiji; ako je prespor, ostaju brza pitanja.

Detaljni rezultati su u `docs/agent-rezultati.json`.
