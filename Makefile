# Prosper Challenge — run everything from the repo root.

VENV := backend/.venv
PYTHON := $(VENV)/bin/python
FRONTEND := frontend

.PHONY: help install install-frontend run run-api run-all dev clean sync-flow \
        db-up db-down db-seed db-reset test

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Create the venv, install Python deps, and install frontend deps
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r backend/requirements.txt
	$(MAKE) install-frontend

install-frontend: ## Install frontend npm dependencies
	cd $(FRONTEND) && npm install

test: ## Run the backend test suite
	cd backend && $(PYTHON) -m pytest -v

run: ## Run the voice agent backend (http://localhost:7860/client)
	$(PYTHON) backend/bot.py

run-api: ## Run the agent REST API (http://localhost:8000) — required for Save/Connect
	$(PYTHON) backend/api.py

run-all: ## Start DB + Redis, then run backend and frontend concurrently
	$(MAKE) db-up
	$(PYTHON) backend/bot.py & $(PYTHON) backend/api.py & cd $(FRONTEND) && npm run dev

dev: ## Run the frontend dev server (http://localhost:3000)
	cd $(FRONTEND) && npm run dev

sync-flow: ## Copy backend/example_flow.json into frontend/public (keeps UI in sync)
	cp backend/example_flow.json $(FRONTEND)/public/example_flow.json

clean-dev: ## Remove frontend node_modules
	rm -rf $(FRONTEND)/node_modules $(FRONTEND)/dist

db-up: ## Start PostgreSQL + Redis via Docker Compose
	docker compose up -d --wait

db-down: ## Stop and remove Docker Compose services
	docker compose down

db-seed: ## Populate the DB from catalog.json and calendar.json
	$(PYTHON) backend/db/seed.py

db-reset: ## Tear down, rebuild schema, and re-seed
	docker compose down -v
	docker compose up -d --wait
	$(PYTHON) backend/db/seed.py

clean: ## Remove the venv, Python caches, and frontend node_modules
	rm -rf $(VENV)
	find backend -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf $(FRONTEND)/node_modules $(FRONTEND)/dist
