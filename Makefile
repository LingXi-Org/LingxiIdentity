SHELL := pwsh.exe

PYTHON ?= python
COMPOSE := docker compose --env-file .env -f deployment/compose.yaml
BOOTSTRAP_COMPOSE := docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.bootstrap.yaml

.PHONY: install lint format-check test typecheck compose-config dev-up prod-up bootstrap smoke down logs

install:
	$(PYTHON) -m pip install -e sdk/python -e server -e bootstrap -e ".[dev]"

lint:
	$(PYTHON) -m ruff check .

format-check:
	$(PYTHON) -m ruff format --check .

typecheck:
	$(PYTHON) -m mypy sdk/python/src server/src bootstrap

test:
	$(PYTHON) -m pytest -q

compose-config:
	$(COMPOSE) config

dev-up:
	$(BOOTSTRAP_COMPOSE) up -d --build

prod-up:
	$(COMPOSE) up -d --build

bootstrap:
	$(BOOTSTRAP_COMPOSE) run --rm --no-deps bootstrap

smoke:
	$(COMPOSE) run --rm smoke

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=200
