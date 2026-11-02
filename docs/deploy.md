# Deploy

Treba poslužitelj s Dockerom, 4 vCPU i 8 GB RAM-a te, za HTTPS, domena usmjerena na njega.

## 1. Pripremite podatke lokalno

```bash
make up migrate etl-all index quality sensitivity export db-dump
```

Prije `make export` postavite `PUBLIC_BASE_URL` u `.env` na javnu adresu, jer ulazi u DCAT-AP katalog.

## 2. Pripremite poslužitelj

Na poslužitelju ručno napravite `/opt/klimakompas/.env` prema `.env.example`, nikad ne kopirajte lokalni. Važno je:

```bash
POSTGRES_PASSWORD=<nova nasumična lozinka>
SITE_ADDRESS=demo.primjer.hr        # domena: Caddy sam dobiva HTTPS certifikat
PUBLIC_BASE_URL=https://demo.primjer.hr
CORS_ORIGINS=https://demo.primjer.hr
WEB_PORT=80
LLM_BASE_URL=                       # prazno: rade samo brza pitanja
```

## 3. Pokrenite

```bash
DEPLOY_HOST=korisnik@server infra/deploy.sh
ssh korisnik@server 'cd /opt/klimakompas && make db-restore && docker compose -f docker-compose.prod.yml restart martin api'
make smoke URL=https://demo.primjer.hr
```

## LLM (neobavezno)

```bash
docker compose -f docker-compose.prod.yml --profile llm up -d ollama
docker compose -f docker-compose.prod.yml exec ollama ollama pull granite4:3b
```

U `.env` zatim postavite `LLM_BASE_URL=http://ollama:11434/v1` i `LLM_MODEL=granite4:3b`. Na CPU-u izmjerite brzinu; ako je odgovor predug, ostavite `LLM_BASE_URL` prazan.

## Rad

- **Sigurnosna kopija:** `make db-dump`, ili `pg_dump` na poslužitelju jednom dnevno.
- **Nadzor:** `/api/v1/health` i stranica /podaci.
- **Osvježavanje statičkih slojeva:** ponoviti korak 1 i prenijeti bazu.
