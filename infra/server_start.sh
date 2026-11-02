#!/usr/bin/env bash
# Runs on the server, from the project folder. Safe to run again after every deploy.
# Usage: infra/server_start.sh <public host> [web port]
set -euo pipefail
HOST="${1:?give the public host, for example 203.0.113.7.sslip.io}"
WEB_PORT="${2:-80}"
COMPOSE=(docker compose -f docker-compose.prod.yml)

if [ ! -f .env ]; then
  # The database password is created here and never leaves the server.
  sed -e "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 24)/" .env.example > .env
  # Compose builds the real database URL itself, so the template's example must not stay.
  sed -i "/^DATABASE_URL=/d" .env
  chmod 600 .env
fi

set_value() {
  if grep -q "^$1=" .env; then
    sed -i "s|^$1=.*|$1=$2|" .env
  else
    printf '%s=%s\n' "$1" "$2" >> .env
  fi
}
if [ "$WEB_PORT" = "80" ]; then
  set_value SITE_ADDRESS "$HOST"
  URL="https://$HOST"
else
  # A test on another port has no public certificate, so it stays on plain HTTP.
  set_value SITE_ADDRESS ":80"
  URL="http://$HOST:$WEB_PORT"
fi
set_value PUBLIC_BASE_URL "$URL"
set_value CORS_ORIGINS "$URL"
set_value WEB_PORT "$WEB_PORT"
# No model on the server by default: the quick questions work without one (ADR 0007).
if ! "${COMPOSE[@]}" --profile llm ps --services --status running 2>/dev/null | grep -qx ollama; then
  set_value LLM_BASE_URL ""
fi

"${COMPOSE[@]}" up -d --build --wait db
DUMP=data/backups/klimakompas.dump
if [ -f "$DUMP" ] && [ ! "$DUMP" -ot data/backups/.restored ]; then
  "${COMPOSE[@]}" up migrate
  "${COMPOSE[@]}" exec -T db sh -c \
    'pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB" /backups/klimakompas.dump' \
    || echo "pg_restore reported warnings; the smoke test decides whether the data is usable"
  touch data/backups/.restored
fi
"${COMPOSE[@]}" up -d --build --wait --wait-timeout 180 api worker martin pygeoapi web
"${COMPOSE[@]}" restart martin
echo "Stack is up at $URL"
