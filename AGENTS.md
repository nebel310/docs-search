# AGENTS.md

Проект использует agentic-разработку. Этот файл — единая точка инструкций для AI-агентов (Codex, Cursor, Copilot, Claude Code, Gemini CLI и др.), поддерживающих стандарт `AGENTS.md`[reference:1].

## Стек

- Python 3.12, `uv` для зависимостей
- FastAPI + uvicorn (async)
- PostgreSQL + PgBouncer + SQLAlchemy 2.0 async + asyncpg
- Elasticsearch (async client)
- Redis (async client)
- Docker Compose
- pytest, pytest-asyncio, pytest-cov, testcontainers, httpx, Locust

## Структура

- `backend/app/api` — HTTP-слой, только валидация и вызов сервисов
- `backend/app/services` — бизнес-логика
- `backend/app/repositories` — доступ к данным (PG, ES)
- `backend/app/core` — конфиг, логирование, исключения
- `backend/app/db` — модели, сессии, Alembic
- `backend/app/search` — Elasticsearch
- `backend/app/cache` — Redis
- `backend/app/rate_limit` — middleware и Lua
- `backend/tests/unit` — unit-тесты
- `backend/tests/integration` — интеграционные тесты
- `backend/tests/e2e` — e2e-тесты
- `backend/tests/load` — Locust

## Правила кода

- `async/await` везде, где есть I/O
- Никаких комментариев через `#`; только докстринги
- Под каждой функцией — докстринг в одну строку, без точки на конце
- Между блоками кода — две пустые строки
- Зависимости: `uv add`, `uv add --dev`; lock-файл коммитится
- Миграции: Alembic, `alembic revision --autogenerate -m "..."`

## Тесты

- Для каждой функции: позитивный, негативный, corner cases
- Цель: 100% покрытие по `app/`
- Unit → integration → e2e → load
- Запуск: `make test-unit`, `make test-integration`, `make test-e2e`, `make load`

## Инфраструктура

- `docker compose up -d --build`
- PgBouncer в `transaction` mode; в asyncpg `statement_cache_size=0`[reference:2]
- Rate limiter отключается через `RATE_LIMIT_ENABLED=false` (для нагрузки)
- `docs.json` генерируется командой `make docs`

## Ограничения

- Не добавлять микросервисы, Kafka, gRPC — это оверархитектура для данного ТЗ
- Не кэшировать поисковые запросы в Redis — только документы по id
- Не использовать Django/DRF