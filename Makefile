SHELL := /bin/bash

# Prefer the user-level uv and the nvm Node. On WSL a Windows npm may otherwise win on PATH.
NVM_NODE_BIN := $(lastword $(sort $(wildcard $(HOME)/.nvm/versions/node/v*/bin)))
export PATH := $(HOME)/.local/bin:$(NVM_NODE_BIN):$(PATH)

UV := uv --directory backend run
NPM := npm --prefix frontend

.PHONY: setup up down test-db migrate sources-verify etl etl-all index sensitivity quality export worker ml-train tiles api web gen-api e2e check check-backend check-frontend licenses db-dump db-restore prod-up smoke screenshots docs-sources docs-pdf

setup:
	test -f .env || cp .env.example .env
	uv --directory backend sync
	$(NPM) ci
	$(UV) pre-commit install

up:
	docker compose up -d --wait db martin

down:
	docker compose down

test-db:
	docker compose --profile test up -d --wait db-test

migrate:
	cd backend && uv run alembic upgrade head

sources-verify:
	$(UV) kk sources verify

etl:
	$(UV) kk etl run $(SOURCE)

etl-all:
	$(UV) kk etl run-all

index:
	$(UV) kk index compute

sensitivity:
	$(UV) kk index sensitivity

quality:
	$(UV) kk quality report

export:
	$(UV) kk export all

worker:
	$(UV) kk worker

ml-train:
	$(UV) kk ml backfill
	$(UV) kk ml train

db-dump:
	mkdir -p data/backups
	docker compose exec -T db sh -c 'pg_dump -Fc -U "$$POSTGRES_USER" "$$POSTGRES_DB"' > data/backups/klimakompas.dump

# Replaces the database contents on the server with the prepared dump.
db-restore:
	docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_restore --clean --if-exists --no-owner -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" /backups/klimakompas.dump'

prod-up:
	docker compose -f docker-compose.prod.yml up -d --build

smoke:
	infra/smoke.sh $(URL)

screenshots:
	mkdir -p docs/images
	cp infra/screenshots.mjs frontend/.screenshots.mjs && (cd frontend && node .screenshots.mjs); rm -f frontend/.screenshots.mjs

docs-pdf:
	cp infra/docs_pdf.mjs frontend/.docs_pdf.mjs && (cd frontend && node .docs_pdf.mjs); rm -f frontend/.docs_pdf.mjs

docs-sources:
	$(UV) kk docs sources

# Martin finds new views only at start, so it restarts after a refresh.
tiles:
	$(UV) kk tiles refresh
	docker compose restart martin

# No access log: the geocoder query is in the URL and must not be logged (SPEC §9.7).
api:
	$(UV) uvicorn klimakompas.api.app:app --reload --no-access-log --port 8000

web:
	$(NPM) run dev

gen-api:
	$(UV) python -c "import json; from klimakompas.api.app import app; print(json.dumps(app.openapi()))" > frontend/openapi.json
	$(NPM) run gen:api

e2e:
	$(NPM) run e2e

check: check-backend check-frontend

check-backend: test-db
	$(UV) ruff check .
	$(UV) ruff format --check .
	$(UV) mypy
	$(UV) pytest

check-frontend:
	$(NPM) run lint
	$(NPM) run typecheck
	$(NPM) run test

licenses:
	$(UV) pip-licenses --format=markdown --order=license --output-file=$(CURDIR)/data/licenses-python.md
	cd frontend && npx license-checker-rseidelsohn --excludePrivatePackages --markdown --out $(CURDIR)/data/licenses-node.md
	$(UV) python $(CURDIR)/infra/update_licenses.py
