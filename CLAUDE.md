# KlimaKompas HR — upute za Claude Code

Ovo je jezgra koja se učitava u svaku sesiju. Sve detalje drži **`docs/SPEC.md`**: izvore podataka, metodologiju, API, UX, plan po danima i predaju.
SPEC čitaj samo po odjeljcima. Sadržaj je na vrhu dokumenta, a odjeljak pronađi grepom za naslov `## §N`.

## 1. Što gradimo i zašto
- **KlimaKompas HR** je web-aplikacija otvorenog koda. Sastoji se od karte, „klimatske iskaznice” za bilo koju adresu, ploče za općine i gradove (JLS) i AI asistenta.
- Za svaku 1-km ćeliju, naselje i JLS u RH procjenjuje izloženost **poplavama, toplini, požarima i onečišćenju zraka**. Tu izloženost križa s **ranjivošću stanovništva** (Popis 2021.) u **Indeks klimatskog rizika (IKR)**.
- Natjecanje: **Datathon Portala otvorenih podataka 2026.** (MPUDT), **izazov B – Okoliš i održivi prostor**. Tim Požega, FERIT Osijek.
- **Rok predaje: ponedjeljak 9. 11. 2026. u 24:00.** Interni freeze je 9. 11. u 16:00, a mentor šalje predaju do 20:00.
- Ocjenjuje se samo ono što predamo: kod, dokumentacija, demo i video do 3 min. Usmene obrane nema. Kriteriji i što iz njih slijedi: SPEC §2.
- Prioritet je **dovršen, stabilan, javno hostan demo s izvrsnim UX-om**, a ne broj značajki.

## 2. Zlatna pravila (vrijede uvijek)
1. **Nikad ne izmišljaj** URL-ove, nazive slojeva ili polja, ID-jeve, šifre, brojke, licence ni citate. Sve o vanjskim izvorima provjeri stvarnim dohvatom. Neprovjereno označi `TODO(verify)` i javi mi.
2. **Prioriteti idu P0 → P1 → P2** (SPEC §3). Ne počinji P2 dok P0 nije gotov i deployan.
3. **Demo nikad ne smije biti prazan ni srušen.** Svaki živi izvor ima spremnik „zadnje dobre vrijednosti” i prikazuje vrijeme osvježavanja. Ispad izvora znači degradaciju s porukom, a ne grešku.
4. **Svaki skup podataka** upiši u `config/sources.yaml` prije korištenja. Iz tog zapisa nastaju atribucije, `docs/izvori-podataka.md` i stranica /podaci.
5. **Poštuj izvore.** Provjeri robots.txt i uvjete korištenja. Šalji najviše 2 paralelna zahtjeva po hostu, ponavljaj s backoffom i koristi User-Agent iz `.env`. Sirove odgovore spremaj u `data/raw/`. Gdje automatizirani pristup nije dopušten (npr. `servisi.voda.hr`), WMS se smije samo prikazivati u pregledniku korisnika, bez masovnog preuzimanja (SPEC §4).
6. **Privatnost:** ne spremaj i ne logiraj adrese, upite ni razgovore korisnika. Nema analitike ni kolačića za praćenje. Fontove hostamo sami.
7. **Samo softver otvorenog koda** (OSI licence). Svaku novu ovisnost i AI alat upiši u `docs/alati-i-licence.md`. Licenca koda je **EUPL-1.2**, a izvedenih podataka CC BY 4.0. OSM nikad ne ulazi u izvedene skupove.
8. **Jezik:** kod, identifikatori, komentari i commit poruke pišu se na engleskom. UI, dokumentacija i README pišu se na hrvatskom: jednostavnim jezikom, s ispravnim dijakriticima i brojevima u formatu `hr-HR`.
9. Ne koristimo grb RH ni logotipe tijela javne vlasti. Ništa ne smije sugerirati službeni status. Uz svaki prikaz rizika ide izjava o ograničenju odgovornosti (SPEC §9.6).
10. **Tajne** drži samo u `.env`, a predložak u `.env.example`. Nikad ih ne ispisuj, ne logiraj i ne commitaj.
11. **Pitaj prije** sljedećih radnji: brisanje podataka ili tablica, destruktivne migracije, plaćeni servisi, promjena licence, `git push --force`, slanje bilo čega izvan repozitorija.

## 3. Kako radimo (svaka sesija)
1. Pročitaj `PROGRESS.md`: trenutnu fazu, otvorene zadatke i odjeljak „Čeka korisnika”. Ako `PROGRESS.md` ne postoji, kreni s **Fazom 0** (SPEC §3.2).
2. Pročitaj odjeljak SPEC-a koji pokriva zadatak.
   - Kad posao dira više od 3 datoteke, mijenja shemu baze ili odstupa od SPEC-a, najprije napiši kratki plan (koraci, datoteke, rizici) i čekaj moju potvrdu.
   - Svako odstupanje zapiši kao ADR u `docs/odluke/NNNN-naslov.md`.
3. Radi u malim, testiranim koracima. Prije svakog commita `make check` mora proći.
4. Commitaj često po Conventional Commits, npr. `feat(etl): add AZO air-quality connector`. Pushaj nakon svake gotove stavke. Nikad ne commitaj `.env`, tajne ni sadržaj `data/`.
5. Na kraju zadatka ažuriraj `PROGRESS.md` (✅, bilješka, sljedeći korak), pripadnu dokumentaciju i `config/sources.yaml`.
6. Ako ti treba nešto što može samo čovjek (račun, e-mail, odluka, snimanje):
   - upiši to u `PROGRESS.md` → „Čeka korisnika”,
   - odmah mi javi,
   - nastavi s drugim zadatkom.
7. Neovisne provjere (npr. više izvora odjednom) smiješ paralelizirati subagentima. Nalaze zapiši u `docs/izvori-provjera.md`.
8. Ako kasnimo za planom, primijeni listu rezanja (SPEC §3.3) i reci mi što je izrezano.

## 4. Stog (detalji i licence: SPEC §6)
- **Backend:**
  - jezik i alati: Python 3.12 + `uv`
  - API i baza: FastAPI, Pydantic v2, SQLAlchemy 2 + GeoAlchemy2, Alembic
  - HTTP: httpx + tenacity
  - geo: GeoPandas, Shapely 2, pyproj, rasterio/rioxarray, OWSLib, lxml
  - podaci: pandas, pyarrow, DuckDB
  - ostalo: LightGBM, Typer (CLI `kk`), APScheduler (worker), structlog
- **Baza:** PostgreSQL 16 + PostGIS 3.4.
  - Mreža i izračuni idu u EPSG:3035, a nacionalni podaci stižu u EPSG:3765.
  - API vraća GeoJSON u EPSG:4326, a vrijeme se u bazi drži u UTC-u.
- **Kartografija:** Martin (vektorske pločice), pygeoapi (OGC API – Features), MapLibre GL JS.
- **Frontend:** React + TypeScript (strict) + Vite, Tailwind CSS, shadcn/ui (Radix), TanStack Query, React Router, Recharts.
- **AI:**
  - LLM se poziva preko OpenAI-kompatibilnog API-ja (`LLM_BASE_URL`, `LLM_MODEL`).
  - Zadano je lokalni Ollama s open-weight modelom pod licencom Apache 2.0 (npr. Qwen3).
  - Kod ne smije ovisiti o jednom pružatelju.
- **Infra:** Docker Compose, Caddy (HTTPS, reverse proxy), GitHub Actions.
- **Testovi:** pytest (+ vcrpy), Vitest + Testing Library, Playwright + axe-core.
- Na Windowsima razvijaj u **WSL2** uz Docker Desktop. Repozitorij drži unutar Linux datotečnog sustava, a ne na `/mnt/c`.

## 5. Struktura (puna: SPEC §7)
```text
backend/src/klimakompas/{core,sources,pipeline,live,ml,agent,api,worker}/   backend/tests/
frontend/src/{pages,components,features,lib,i18n}/                          frontend/tests/
config/{sources.yaml,index.yaml,thresholds.yaml,advice/}   infra/   docs/   data/ (u .gitignore)
```

## 6. Naredbe (Makefile; dodaj cilj kad gradiš funkcionalnost)
| Naredba | Što radi |
|---|---|
| `make setup` | `uv sync`, `npm ci`, pre-commit hookovi |
| `make up` / `make down` | Docker Compose servisi (db, martin, …) |
| `make sources-verify` | provjera svih izvora → `docs/izvori-provjera.md` |
| `make etl SOURCE=<id>` / `make etl-all` | dohvat i obrada izvora |
| `make index` | izračun IKR-a (ćelije, JLS, naselja) |
| `make api` / `make web` | razvojni poslužitelji |
| `make check` | ruff, mypy, pytest, eslint, tsc, vitest |
| `make e2e` | Playwright + axe na pokrenutom stacku |
| `make export` | izvedeni skupovi + DCAT-AP |
| `make screenshots` / `make docs-pdf` | snimke zaslona i PDF dokumentacije za predaju |

## 7. Arhitektura ukratko (SPEC §8)
Tok podataka ide ovim redom:
1. Izvori.
2. Konektori u `sources/`; sirovi odgovori idu u `data/raw/`.
3. Normalizacija na zajedničke ključeve: `cell_id` (INSPIRE 1 km), šifre JLS-a i naselja, vrijeme u UTC-u.
4. PostGIS sheme `ref`, `pop`, `haz`, `live`, `idx`, `meta` i `ml`.
5. Izračun IKR-a prema `config/index.yaml`.
6. FastAPI `/api/v1`, Martin i pygeoapi.
7. Web i AI asistent.

Statičke slojeve (poplave, toplina, požar, kronični zrak) računamo batchom. Žive slojeve osvježava worker po rasporedu iz `sources.yaml`: upozorenja DHMZ-a, kvalitetu zraka i metapodatke Portala.

## 8. Ključne odluke (mijenjaju se samo ADR-om)
- **Prostorne jedinice:** INSPIRE 1-km mreža (EPSG:3035, `GRD_ID`) te JLS i naselja iz DGU-a.
- **Rizik:**
  - Rizik po opasnosti računa se kao `R = H × (0,5 + 0,5 · V)`, a IKR je ponderirani prosjek tih rizika.
  - Ponderi i pragovi stoje isključivo u `config/index.yaml` i `config/thresholds.yaml` (SPEC §5).
- **Poplave:**
  - Računski sloj su karte dubina JRC/EFAS.
  - Službene karte Hrvatskih voda prikazujemo samo kao WMS sloj u pregledniku. GetFeatureInfo ide iz preglednika, ako to CORS dopušta.
  - Vektori HV-a ulaze samo ADR-om.
- **Zrak:**
  - kronični: EEA PM2,5 na 1 km
  - trenutni: REST servis `iszz.azo.hr`
  - prognoza: LightGBM nowcast, a CAMS je rezerva
- **Toplina:** ECDE (vrući dani, tropske noći) + Landsat LST (urbani toplinski otok) + ESA WorldCover (zelenilo).
- **Požar:** ECDE dani s FWI > 30 + gorivo (WorldCover) + povijest opožarenih površina. DHMZ indeks služi samo kao živi sloj u sezoni.
- **AI asistent** koristi isključivo rezultate svojih alata. Svaka brojka mora biti utemeljena i citirana (SPEC §10).

## 9. Definicija gotovog (za svaku značajku)
- Radi na stvarnim podacima, na mobitelu (360 px) i na desktopu.
- Ima testove: parsere na snimljenim fiksturama, izračune na „golden” primjerima i API ugovor.
- Uz svaki broj stoje izvor i datum zadnje izmjene. Postoje stanja učitavanja, greške i praznog rezultata.
- Pristupačno je:
  - tipkovnica, ARIA, `lang="hr"`
  - kontrast ≥ 4,5:1
  - svi tekstovi su u `frontend/src/i18n/hr.json`
- Dokumentirano je, `make check` prolazi i `PROGRESS.md` je ažuriran.

## 10. Kad nešto zapne
- **Izvor je nedostupan ili promijenjen:**
  - prijeđi na fallback iz SPEC §4.2
  - zapiši to u `docs/izvori-provjera.md` i u `PROGRESS.md`
- **Zahtjev je nejasan:** postavi jedno konkretno pitanje s predloženom zadanom opcijom.
- **Parametri API-ja:** ne pogađaj ih (npr. CDS zahtjeve ili `tipPodatka` AZO servisa). Utvrdi ih empirijski ili me pitaj.
- **Velike rastere** obrađuj u prozorima ili blokovima izrezanim na granicu RH. Nikad ne učitavaj cijelu Europu u memoriju.
