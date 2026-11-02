# AI asistent

Asistent odgovara na pitanja o klimatskim rizicima na hrvatskom. Činjenice dolaze isključivo iz alata, uz citat izvora. Razgovori se ne spremaju.

## Kako radi

Zadani način rada je strukturirani (ADR 0008):

1. Model `granite4:3b` (Apache 2.0, preko OpenAI-kompatibilnog API-ja) pitanje pretvara u strukturirani zahtjev: namjeru, mjesto, opasnost i mjeru.
2. Zaštite provjeravaju zahtjev: mjesto se mora spominjati u pitanju i imati stvarno podudaranje naziva.
3. Kod poziva alat i sastavlja odgovor iz predložaka, s citatima `[n]`.
4. Provjera utemeljenosti još jednom usporedi sve brojeve s rezultatima alata.

Ako model nije dostupan ili vrati nečitljiv odgovor, pitanje čitaju **jednostavna pravila** (`agent/rules.py`). Ona prepoznaju ključne riječi i nazive mjesta iz registra DGU-a, uz hrvatske padeže. Ostali koraci su isti, pa slobodna pitanja rade i na poslužitelju bez modela. Uz to uvijek rade **brza pitanja** (`/api/v1/agent/quick`), gdje korisnik bira općinu ili grad, a adresu ili naselje samo unutar te općine.

Način `LLM_MODE=tools` uključuje petlju alata iz koje model sam piše odgovor, s provjerom brojki, jednim ponovnim pokušajem i uklanjanjem neutemeljenih rečenica. Namijenjen je većim modelima.

## Alati

`geocode`, `get_place_card`, `get_jls_profile`, `rank_areas`, `get_active_warnings`, `get_air_quality` i `search_open_data`. Svi su samo za čitanje i vraćaju podatke, izvore i vrijeme.

## Sigurnost i privatnost

Ograničenje je 10 zahtjeva u minuti po klijentu, brojač je samo u memoriji, ulaz je do 1.000 znakova, a razgovori i upiti se ne bilježe. Naredbe u pitanju ne mogu promijeniti podatke, jer tekst odgovora ne dolazi iz modela.

## Evaluacija

Skup ima 76 pitanja: rangiranja, iskaznice, općine, upozorenja, zrak, pretraga podataka, teme izvan opsega i zamke. Pokretanje: `kk agent eval` (model) i `kk agent eval --rules` (pravila). Model je mjeren na RTX 3050 Ti s 4 GB VRAM-a.

| Mjera | Model, neviđena (12) | Pravila, neviđena (12) | Model, svih 76 | Pravila, svih 76 |
|---|---|---|---|---|
| Točan odabir alata | 100 % | 92 % | 90 % | 95 % |
| Provjere sadržaja (zamke, odbijanja) | 100 % | 100 % | 96 % | 99 % |
| Utemeljene brojke | 100 % | 100 % | 100 % | 98 % |
| Latencija p50 / p95 | 1,3 s / 1,9 s | 0,3 s / 0,5 s | 1,2 s / 2,2 s | 0,3 s / 0,7 s |

**Mjerodavni su stupci s neviđenim pitanjima.** Prvih 64 pitanja koristilo se pri doradi prompta, zaštita i pravila, pa su stupci sa svih 76 optimistični. Zadnjih 12 pitanja napisano je prije mjerenja, a nakon njih ništa nije mijenjano osim jednog očekivanja: adresa u Puli iz pitanja ne postoji u registru DGU-a, pa je ispravan odgovor „Nisam pronašao”.

Pravila na cijelom skupu imaju jednu brojku koju provjera nije mogla potvrditi. Takve rečenice provjera utemeljenosti uklanja prije prikaza.

Odgovori s alatom bez izvora su odgovori tipa „nisam pronašao to mjesto”, gdje nema podatka koji bi se citirao.

Detaljni rezultati su u `docs/agent-rezultati.json` (model) i `docs/agent-rezultati-pravila.json` (pravila).

Provjerena je i petlja alata s istim modelom: 91 % točnih alata, ali samo 69 % utemeljenih brojki i izmišljene tvrdnje, zbog čega nije zadani način (ADR 0008).

## Ograničenja

- Podržane su formulacije bliske primjerima u `agent/prompts/intent_hr.md`.
- Mali model griješi u razumijevanju, pa asistent uvijek pokazuje na što odgovara i navodi izvor.
- Model na poslužitelju bez GPU-a bit će sporiji; ako je prespor ili ga nema, pitanja čitaju pravila.
- Pravila razumiju samo pitanja s nazivom mjesta i ključnom riječi (npr. „poplava”, „zrak”, „stanovnika”). Na neobične formulacije odgovaraju da pitanje nije u opsegu.
