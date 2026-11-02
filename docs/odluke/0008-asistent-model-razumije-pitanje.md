# ADR 0008: Mali model samo razumije pitanje, a odgovor sastavlja kod

- **Status:** prihvaćeno
- **Datum:** 2. 11. 2026.

## Kontekst

SPEC §10 predviđa da LLM u petlji poziva alate i piše odgovor, a brojke provjerava kontrola utemeljenosti. Isprobali smo to s modelima koji stanu u 4 GB VRAM-a:

- **Qwen3 4b:** prije svakog odgovora generira više od 2.000 tokena razmišljanja, i uz `/no_think` i `think: false`, pa odgovor traje 1,5 do 3 minute.
- **Granite 4 3b (Apache 2.0):** brz je (p50 8 s), ali je u evaluaciji izmišljao tvrdnje bez brojki, koje provjera brojki ne može uhvatiti. Tvrdio je da Gunja nije u zoni poplave, procijenio rizik za nepostojeće mjesto i napisao recept. Samo 69 % brojki bilo je utemeljeno.

Za alat o riziku od poplava netočna umirujuća rečenica je opasna, pa takav način rada nije prihvatljiv za javni demo.

## Odluka

Zadani način je `LLM_MODE=structured`:

1. Model samo pretvara pitanje u strukturirani zahtjev (namjera, mjesto, opasnost, mjera).
2. Kod izvršava alat i sastavlja odgovor iz predložaka, s citatima.
3. Zaštite ne ovise o modelu: mjesto se mora stvarno spominjati u pitanju i imati stvarno podudaranje naziva, ista adresa u više gradova traži pojašnjenje, a rang-lista ili savjet vrijede samo ako ih pitanje stvarno traži.

Petlja s alatima iz SPEC-a ostaje kao `LLM_MODE=tools`, za veće modele koji prođu evaluaciju. Kod i dalje ne ovisi o jednom pružatelju.

## Posljedice

- Činjenicu može dati samo alat: nema izmišljenih brojki ni tvrdnji iz modela, a odgovor stiže za oko 1 s.
- Odgovori su manje prirodni i ne odgovaraju na svaku formulaciju. Pogrešna namjera najčešće daje siguran neuspjeh („nisam pronašao”, „nisam razumio”) ili odgovor na srodno pitanje, ali s točnim podacima.
- Rezultati su u `docs/agent.md`.
