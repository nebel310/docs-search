.PHONY: up down logs migrate import test test-unit test-integration test-e2e load docs venv install

up:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f api

venv:
	cd backend && uv venv

install:
	cd backend && uv sync

migrate:
	docker compose run --rm api alembic upgrade head

import:
	docker compose --profile cli run --rm import

test: test-unit test-integration test-e2e

test-unit:
	cd backend && uv run pytest tests/unit -q

test-integration:
	cd backend && uv run pytest tests/integration -q

test-e2e:
	cd backend && uv run pytest tests/e2e -q

load:
	cd backend && uv run locust -f tests/load/locustfile.py --host http://localhost:8000

docs:
	cd backend && uv run python -m app.cli.dump_openapi