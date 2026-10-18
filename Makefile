.PHONY: up down down-v reset rebuild migrate init-es import seed \
        test-unit test-integration test-e2e test load clean-cache

up:
	docker compose up -d --build

down:
	docker compose down

down-v:
	docker compose down -v

reset: down-v up

rebuild:
	docker compose up -d --force-recreate --build api

migrate:
	docker compose run --rm api alembic upgrade head

init-es:
	docker compose --profile cli run --rm init-es

import:
	docker compose --profile cli run --rm import

seed: migrate init-es import

test-unit:
	cd backend && uv run pytest tests/unit -v

test-integration:
	cd backend && uv run pytest tests/integration -v --no-cov

test-e2e:
	cd backend && uv run pytest tests/e2e -v --no-cov

test: test-unit test-integration test-e2e

load:
	cd backend && uv run locust -f tests/load/locustfile.py --headless --users 500 --spawn-rate 50 --run-time 3m --host http://localhost:8000 --csv=load_results --html=load_report.html

clean-cache:
	find . -type d -name "__pycache__" -not -path "*/.venv/*" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -not -path "*/.venv/*" -delete