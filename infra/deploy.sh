#!/usr/bin/env bash
# Sends the code and prepared data to the server and starts the production stack.
# Usage: DEPLOY_HOST=user@server DEPLOY_DIR=/opt/klimakompas infra/deploy.sh
# The .env on the server is written by hand and is never copied from here.
set -euo pipefail
: "${DEPLOY_HOST:?set DEPLOY_HOST, for example user@server}"
DEPLOY_DIR="${DEPLOY_DIR:-/opt/klimakompas}"

rsync -az --delete --exclude .git --exclude .env --exclude data --exclude node_modules \
  --exclude .venv --exclude dist ./ "$DEPLOY_HOST:$DEPLOY_DIR/"
rsync -az --mkpath data/processed/ "$DEPLOY_HOST:$DEPLOY_DIR/data/processed/"
rsync -az --mkpath data/export/ "$DEPLOY_HOST:$DEPLOY_DIR/data/export/"
if [ -f data/backups/klimakompas.dump ]; then
  rsync -az --mkpath data/backups/klimakompas.dump "$DEPLOY_HOST:$DEPLOY_DIR/data/backups/"
fi
ssh "$DEPLOY_HOST" "cd $DEPLOY_DIR && docker compose -f docker-compose.prod.yml up -d --build"
