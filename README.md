# docs-search

Поисковик по текстам документов: принимает произвольный текстовый запрос, ищет по тексту в Elasticsearch и возвращает первые 20 документов с полями из БД, упорядоченные по дате создания. Документы можно получать по `id` и удалять из БД и индекса.

## Возможности

- **Поиск** — `GET /search?q=...&limit=...`. Текст ищется по индексу Elasticsearch, полные карточки документов достаются из PostgreSQL, результат сортируется по `created_date` (desc) и ограничивается 20 записями.
- **Получение документа по `id`** — `GET /documents/{id}` с кэшированием в Redis.
- **Удаление документа** — `DELETE /documents/{id}` из PostgreSQL, Redis и Elasticsearch.
- **Импорт CSV** — CLI-команда для загрузки исходного массива данных в БД и индекс.
- **Health-check** — `/health` (liveness) и `/ready` (readiness по PG и ES).
- **OpenAPI-документация** — `docs.json` в корне репозитория, генерируется командой.

## Соответствие ТЗ

| Требование ТЗ | Реализация |
|---------------|------------|
| Поиск по тексту, первые 20 документов, сортировка по дате | `GET /search`, `match` в ES → выборка из PG → `ORDER BY created_date DESC` → `LIMIT 20` |
| Удаление из БД и индекса по `id` | `DELETE /documents/{id}` |
| Любой фреймворк кроме Django/DRF | FastAPI |
| `README` с гайдом по поднятию | этот файл |
| `docs.json` (OpenAPI) | лежит в корне репозитория |
| Функциональные тесты | `backend/tests/e2e` |
| Docker | `docker-compose.yaml` |
| Асинхронные вызовы | FastAPI + SQLAlchemy async + asyncpg + async-клиенты ES и Redis |

**Структура БД (`documents`):** `id`, `rubrics`, `text`, `created_date`.

**Структура индекса (`documents`):** `id` (keyword), `text` (text).

## Стек

- Python 3.12, `uv`
- FastAPI + uvicorn
- PostgreSQL 16 + PgBouncer + SQLAlchemy 2.0 async + asyncpg
- Elasticsearch 8.15 (async client)
- Redis 7 (async client)
- Docker Compose
- pytest (unit / integration / e2e), Locust

## Быстрый старт

### Требования

- Docker и Docker Compose v2
- Свободные порты: `8000`, `5432`, `6432`, `9200`, `6379`
- Менеджер пакетов `uv`

Перед первым запуском подготовь окружение:

```bash
cp .env.example .env
```

В репозитории уже лежит `data/posts.csv`. Если нужен свой набор — положи CSV с тем же именем по тому же пути (`data/posts.csv`); других изменений не требуется.

Дальше выбери один из двух путей — с `make` или без него. Результат одинаковый.

### Вариант 1 — с `make`

Нужен установленный GNU Make (`winget install GnuWin32.Make` (это команда для win11/10), после установки — добавить папку с `make.exe` в PATH и перезапустить терминал).

```bash
make up          # docker compose up -d --build
make seed        # migrate + init-es + import
```

Проверка:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl "http://localhost:8000/search?q=информации&limit=5"
```

Тесты:

```bash
make test-unit
make test-integration
make test-e2e
make test        # все три подряд
```

Нагрузка (rate limiter обязательно выключить, иначе часть запросов упрётся в 429) (если не интересно проводить нагрузочное тестирование, то этот этам можно пропустить):

```bash
# в .env: RATE_LIMIT_ENABLED=false
make rebuild
make load
# в .env обратно RATE_LIMIT_ENABLED=true
make rebuild
```

Остановка и уборка:

```bash
make down        # остановить, данные сохранить
make down-v      # остановить + снести volumes
make reset       # down -v + up (данные пропадут, нужен make seed)
make clean-cache # __pycache__, .pytest_cache, *.pyc
```

### Вариант 2 — без `make` (чистый `docker compose` + `uv`)

Те же шаги руками.

**Поднять стек**

```bash
docker compose up -d --build
```

**Миграции + индекс + данные**

```bash
docker compose run --rm api alembic upgrade head
docker compose --profile cli run --rm init-es
docker compose --profile cli run --rm import
```

**Проверка**

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl "http://localhost:8000/search?q=информации&limit=5"
curl http://localhost:8000/documents/1
```

Swagger UI: `http://localhost:8000/docs`  
OpenAPI: `http://localhost:8000/openapi.json`

**Пересборка API после правки `.env` или кода**

```bash
docker compose up -d --force-recreate --build api
```

**Тесты**

```bash
# unit — быстро, без docker
cd backend
uv run pytest tests/unit -v

# integration — testcontainers сам поднимет PG/ES/Redis
cd backend
uv run pytest tests/integration -v --no-cov

# e2e — нужен поднятый api + данные (см. выше)
cd backend
uv run pytest tests/e2e -v --no-cov

# всё сразу
cd backend
uv run pytest -v
```

`cd` действует только в текущем терминале; каждый следующий запуск начинай с `cd backend` снова (или открой новый терминал). Повторные прогоны ничего не ломают.

**Нагрузка**
*Если не интересно проводить нагрузочное тестирование, то этот этам можно пропустить*

```bash
# в .env: RATE_LIMIT_ENABLED=false
docker compose up -d --force-recreate --build api

cd backend
uv run locust -f tests/load/locustfile.py --headless --users 500 --spawn-rate 50 --run-time 3m --host http://localhost:8000 --csv=load_results --html=load_report.html

# в .env обратно RATE_LIMIT_ENABLED=true
docker compose up -d --force-recreate --build api
```

**Очистка кэшей (PowerShell)**

```powershell
Get-ChildItem -Path . -Recurse -Force -Directory -Filter __pycache__ | Where-Object { $_.FullName -notmatch '\\\.venv\\' } | Remove-Item -Recurse -Force
Get-ChildItem -Path . -Recurse -Force -Directory -Filter .pytest_cache | Remove-Item -Recurse -Force
Get-ChildItem -Path . -Recurse -Force -File -Filter *.pyc | Where-Object { $_.FullName -notmatch '\\\.venv\\' } | Remove-Item -Force
```

**Остановка**

```bash
docker compose down       # остановить, данные сохранить
docker compose down -v    # остановить + снести volumes
```

**Полный сброс (аналог `make reset`)**

```bash
docker compose down -v
docker compose up -d --build
docker compose run --rm api alembic upgrade head
docker compose --profile cli run --rm init-es
docker compose --profile cli run --rm import
```

### Про rate limiter

- По умолчанию в `.env` `RATE_LIMIT_ENABLED=false` — так удобно гонять нагрузку и e2e без случайных 429.
- Для всех «обычных» прогонов (юнит, интеграционные, ручные запросы) выставь `RATE_LIMIT_ENABLED=true` и пересоздай API — иначе e2e-тест на срабатывание лимитера будет ложно зелёным, а поведение сервиса не совпадёт с продовым. Если запустить тесты (кроме load) с `RATE_LIMIT_ENABLED=false`, то просто один из тестов упадёт.
- После правки `.env` пересоздай контейнер: `make rebuild` (с make) или `docker compose up -d --force-recreate --build api` (без make).

## API

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| `GET` | `/search` | `q` (1..500), `limit` (1..20, default 20) | `{"total", "items": [DocumentOut]}` |
| `GET` | `/documents/{id}` | — | `DocumentOut` / 404 |
| `DELETE` | `/documents/{id}` | — | 204 / 404 |
| `GET` | `/health` | — | `{"status": "ok"}` |
| `GET` | `/ready` | — | `{"status", "pg", "es"}`, 503 при недоступности |

`DocumentOut`: `id`, `rubrics`, `text`, `created_date`.

Ошибки в формате:

```json
{"error": {"code": "document_not_found", "message": "Document not found"}}
```

Коды: `document_not_found` (404), `search_unavailable` (503), `rate_limit_exceeded` (429), `internal_error` (500).

## Документация OpenAPI

`docs.json` в корне репозитория — снимок OpenAPI-схемы сервиса. Можно пересобрать:

```bash
# с make
make docs

# без make
cd backend
uv run python -m app.cli.dump_openapi
```
Документацию также можно найти по адресу ``http://localhost:8000/docs`` после запуска приложения.

## А также....
Детали реализации бэкенда (слои, схемы, инфраструктурные решения, нюансы PgBouncer и asyncpg) — в `backend/README.md`.