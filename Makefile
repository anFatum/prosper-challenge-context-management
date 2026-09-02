# Prosper Challenge — run everything from the repo root.

VENV := backend/.venv
PYTHON := $(VENV)/bin/python
FRONTEND := frontend

.PHONY: help install install-frontend run dev clean sync-flow

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

run: ## Run the voice agent backend (http://localhost:7860/client)
	$(PYTHON) backend/bot.py

dev: ## Run the frontend dev server (http://localhost:3000)
	cd $(FRONTEND) && npm run dev

sync-flow: ## Copy backend/example_flow.json into frontend/public (keeps UI in sync)
	cp backend/example_flow.json $(FRONTEND)/public/example_flow.json

clean: ## Remove the venv, Python caches, and frontend node_modules
	rm -rf $(VENV)
	find backend -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf $(FRONTEND)/node_modules $(FRONTEND)/dist
