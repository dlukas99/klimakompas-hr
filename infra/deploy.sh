#!/usr/bin/env bash
# Deploys everything to a server with Docker, in one command, from the repository root.
#   DEPLOY_HOST=root@203.0.113.7 infra/deploy.sh [public host]
# Without a public host it uses <server IP>.sslip.io, which resolves to the server and gets HTTPS.
# The local .env is never copied: the server makes its own, with a new database password.
set -euo pipefail
: "${DEPLOY_HOST:?set DEPLOY_HOST, for example root@203.0.113.7}"
DEPLOY_DIR="${DEPLOY_DIR:-/opt/klimakompas}"
SERVER_IP="${DEPLOY_HOST#*@}"
PUBLIC_HOST="${1:-$SERVER_IP.sslip.io}"
URL="https://$PUBLIC_HOST"
export PATH="$HOME/.local/bin:$PATH"

# The catalogue carries the public address, so the exports are written for this deploy.
(cd backend && PUBLIC_BASE_URL="$URL" uv run kk export all)
make -s db-dump

ssh "$DEPLOY_HOST" "command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh; mkdir -p $DEPLOY_DIR"
rsync -az --delete --exclude .git --exclude .env --exclude data --exclude node_modules \
  --exclude .venv --exclude dist ./ "$DEPLOY_HOST:$DEPLOY_DIR/"
rsync -az --mkpath data/processed/ "$DEPLOY_HOST:$DEPLOY_DIR/data/processed/"
rsync -az --mkpath data/export/ "$DEPLOY_HOST:$DEPLOY_DIR/data/export/"
rsync -az --mkpath data/backups/klimakompas.dump "$DEPLOY_HOST:$DEPLOY_DIR/data/backups/"
ssh "$DEPLOY_HOST" "cd $DEPLOY_DIR && infra/server_start.sh $PUBLIC_HOST"

# Caddy may need a moment for its first certificate.
for _ in $(seq 1 30); do
  curl -fsS --max-time 10 -o /dev/null "$URL/api/v1/health" && break
  sleep 10
done
infra/smoke.sh "$URL"
echo "Deployed: $URL"
