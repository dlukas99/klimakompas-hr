SHELL := /bin/bash

# Prefer the user-level uv and the nvm Node. On WSL a Windows npm may otherwise win on PATH.
NVM_NODE_BIN := $(lastword $(sort $(wildcard $(HOME)/.nvm/versions/node/v*/bin)))
export PATH := $(HOME)/.local/bin:$(NVM_NODE_BIN):$(PATH)

UV := uv --directory backend run
NPM := npm --prefix frontend

.PHONY: setup up down sources-verify check check-backend check-frontend licenses

setup:
	test -f .env || cp .env.example .env
	uv --directory backend sync
	$(NPM) ci
	$(UV) pre-commit install

up:
	docker compose up -d --wait db martin

down:
	docker compose down

sources-verify:
	$(UV) kk sources verify

check: check-backend check-frontend

check-backend:
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
