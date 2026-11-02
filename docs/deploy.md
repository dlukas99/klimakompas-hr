# Deploy

## Što treba

Poslužitelj s Linuxom (npr. Ubuntu 24.04), 4 vCPU, 8 GB RAM-a i oko 40 GB diska, otvoreni portovi 80 i 443 te SSH pristup s ovog računala. Domena nije obavezna: bez nje se koristi `<IP>.sslip.io`, koji također dobiva HTTPS.

## Jedna naredba

Lokalno moraju raditi `make up` i učitani podaci.

```bash
DEPLOY_HOST=root@203.0.113.7 infra/deploy.sh                 # adresa 203.0.113.7.sslip.io
DEPLOY_HOST=root@203.0.113.7 infra/deploy.sh demo.primjer.hr # vlastita domena usmjerena na poslužitelj
```

Skripta:

1. napravi izvoze i DCAT-AP s javnom adresom te dump baze;
2. instalira Docker na poslužitelju ako ga nema i kopira kod i podatke;
3. na poslužitelju napravi `.env` s novom nasumičnom lozinkom baze, koja ne izlazi s poslužitelja;
4. vrati bazu, pokrene stack, a Caddy sam dobije HTTPS certifikat;
5. pokrene smoke test.

Lokalni `.env` se nikad ne kopira, pa CDS token ostaje na ovom računalu. Poslužitelju treba samo za ponovni izračun klimatskih slojeva, a to se radi lokalno.

Nakon deploya pokrenite e2e na javnoj adresi:

```bash
cd frontend && E2E_BASE_URL=https://ADRESA npx playwright test
```

## LLM (neobavezno)

Bez modela rade brza pitanja. Na poslužitelju bez GPU-a prvo izmjerite brzinu:

```bash
docker compose -f docker-compose.prod.yml --profile llm up -d ollama
docker compose -f docker-compose.prod.yml exec ollama ollama pull granite4:3b
```

U `.env` zatim postavite `LLM_BASE_URL=http://ollama:11434/v1` i `LLM_MODEL=granite4:3b` te ponovno pokrenite `api`. Ako je odgovor predug, ostavite `LLM_BASE_URL` prazan.

## Rad

- **Nowcast:** `make ml-train` lokalno pa ponovni deploy; prognozu svakog sata radi worker.
- **Sigurnosna kopija:** `pg_dump` na poslužitelju jednom dnevno.
- **Nadzor:** `/api/v1/health` i stranica /podaci.
- **Osvježavanje statičkih slojeva:** lokalno `make etl-all index` pa ponovni deploy.
