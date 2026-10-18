# backend

Техническая документация бэкенда сервиса `docs-search`. Продуктовое описание и инструкция по запуску — в корневом `README.md`.

## Слои приложения

```
backend/app/
├── main.py            # create_app + lifespan
├── api/               # HTTP-слой
│   ├── deps.py        # DI-провайдеры
│   └── routers/       # documents, health, search
├── services/          # бизнес-логика
├── repositories/      # доступ к данным
│   ├── pg/            # PostgreSQL
│   └── es/            # Elasticsearch
├── schemas/           # Pydantic-схемы
├── core/              # config, logging, exceptions
├── db/                # модели, сессии, Base
├── search/            # ES-клиент и операции с индексом
├── cache/             # Redis-клиент и кэш документов
├── rate_limit/        # middleware + Lua-скрипт
└── cli/               # import_csv, init_es, dump_openapi
```

Правило зависимостей — строго в одну сторону: `api → services → repositories → (db | search | cache)`. Обратных импортов нет.

### API

Тонкий слой. Валидирует вход через Pydantic/Query, вызывает сервис, маппит доменные исключения в JSON. Бизнес-логики нет.

- `deps.py` — все DI-провайдеры: клиенты (`get_es_client`, `get_redis`), фабрика сессий (`get_session_factory`), репозитории (`get_document_repository`, `get_search_repository`), сервисы (`get_document_service`, `get_search_service`). Плюс `get_session` — открывает сессию, коммитит при успехе, откатывает при исключении.
- `routers/documents.py` — `GET /documents/{id}`, `DELETE /documents/{id}`.
- `routers/search.py` — `GET /search`. Валидация `q` и `limit` живёт здесь же (границы в `schemas/search.py`).

### Services

Оркестрация. Знают про репозитории и кэш, не знают про HTTP.

- `DocumentService.get` — кэш → PG → кэш. `delete` — PG → кэш → ES.
- `SearchService.search` — ES даёт `search_candidates` id → PG возвращает документы по этим id (уже отсортированные по `created_date desc`) → обрезка до `search_result_limit`.

Кэш описан протоколом `DocumentCacheProtocol`, чтобы сервис не зависел от конкретной реализации Redis-кэша и легко мокался в юнит-тестах.

### Repositories

Единственное место, где живут SQL-запросы и вызовы ES.

- `pg/document.py` — `get_by_id`, `get_by_ids` (с `ORDER BY created_date DESC` и `IN (...)`), `delete`. Пустой список id не уходит в БД.
- `es/document.py` — обёртка над функциями из `app/search/index.py`: `search`, `index`, `bulk_index`, `delete`.

### Search

- `client.py` — фабрика `AsyncElasticsearch` с `request_timeout=5`.
- `index.py` — операции с индексом: `index_exists`, `create_index` (идемпотентно), `delete_index`, `index_document`, `bulk_index_documents`, `refresh_index`, `delete_document`, `search_documents`. Маппинг — константа `DOCUMENTS_INDEX_MAPPING`.

### Cache

- `redis_client.py` — фабрика `Redis` с `decode_responses=True`.
- `document_cache.py` — `DocumentCache` с ключом `doc:{id}` и TTL из настроек. Хранит JSON `DocumentOut`.

Кэшируются только документы по `id`. Поисковые запросы не кэшируются.

### DB

- `base.py` — `Base(DeclarativeBase)`.
- `models.py` — `Document`: `id` (BIGINT PK), `rubrics` (`TEXT[]`), `text`, `created_date` (`TIMESTAMPTZ`).
- `session.py` — фабрики `create_engine` и `create_session_factory`.

### Rate_limit

`RateLimitMiddleware` реализует sliding-window на Redis через Lua-скрипт `SLIDING_WINDOW_SCRIPT` (ZSET: `ZREMRANGEBYSCORE` → `ZCARD` → `ZADD` → `PEXPIRE`). Ключ — `rl:{client_host}:{path}`. Skip-пути: `/health`, `/ready`, `/docs`, `/openapi.json`, `/redoc`. Fail-open при недоступности Redis или ошибке `eval` — запрос пропускается, ошибка логируется.

### Core

- `config.py` — `Settings` (pydantic-settings), кэшируется через `@lru_cache` в `get_settings`.
- `logging.py` — structlog с JSON-рендером в stdout.
- `exceptions.py` — иерархия `AppError` и наследники (`DocumentNotFoundError` 404, `SearchUnavailableError` 503, `RateLimitExceededError` 429). Маппинг в JSON-ответ — обработчик в `main.py`.

### main.py

`create_app` собирает приложение: регистрирует middleware, роутеры и обработчик `AppError`. `lifespan` создаёт engine, фабрику сессий, ES-клиент, Redis-клиент, кэш и `clock`, а в `finally` закрывает Redis, ES и engine.

## Схемы данных

### PostgreSQL (`documents`)

| Колонка | Тип | Ограничения |
|---------|-----|-------------|
| `id` | `BIGINT` | PK, autoincrement |
| `rubrics` | `TEXT[]` | NOT NULL |
| `text` | `TEXT` | NOT NULL |
| `created_date` | `TIMESTAMPTZ` | NOT NULL |

Миграция — `alembic/versions/0001_create_documents.py`. Alembic настроен на async (`alembic/env.py`, `run_async_migrations`). URL берётся из `Settings`, а не из `alembic.ini`.

### Elasticsearch (`documents`)

```json
{
  "mappings": {
    "properties": {
      "id":   {"type": "keyword"},
      "text": {"type": "text"}
    }
  }
}
```

`id` — keyword, чтобы работал `int(hit["_id"])` и не терялась точность. `text` — text, стандартный анализатор.

### Redis

| Ключ | Значение | TTL |
|------|----------|-----|
| `doc:{id}` | JSON `DocumentOut` | `CACHE_TTL_SECONDS` |
| `rl:{host}:{path}` | ZSET (score = timestamp ms) | `RATE_LIMIT_WINDOW_SECONDS` |

## Инфраструктурные решения

### PgBouncer + asyncpg

Приложение подключается к `pgbouncer:6432`, а не к `postgres:5432`. PgBouncer работает в `transaction` mode — соединение отдаётся на время транзакции и возвращается в пул после коммита.

**Проблема:** в `transaction` mode PgBouncer не гарантирует, что клиент попадёт на то же серверное соединение между транзакциями. Prepared statements, которые asyncpg кэширует на клиенте, становятся невалидными, и запросы падают с `prepared statement "__asyncpg_stmt_N__" does not exist`.

**Решение:** в `create_engine` передаётся `connect_args={"statement_cache_size": 0}` — asyncpg не кэширует prepared statements. Плата за это — план запроса не переиспользуется, но это корректно и предсказуемо.

Пул соединений: `POOL_SIZE=5`, `MAX_OVERFLOW=20`, `pool_pre_ping=True`. При `WEB_CONCURRENCY=4` максимум соединений к PgBouncer — `4 * (5 + 20) = 100`, что совпадает с лимитом `MAX_CLIENT_CONN=1000` у PgBouncer с запасом.

### Пул ES и Redis

Один клиент на процесс uvicorn, создаётся в `lifespan`, живёт до остановки воркера. Закрывается в `finally` — `await es_client.close()`, `await redis_client.aclose()`.

### Удаление документа — best-effort по ES

Удаление задевает три хранилища (PG, Redis, ES), единой транзакции между ними нет. Порядок в `DocumentService.delete`:

1. `DELETE FROM documents WHERE id = ...` в PG;
2. инвалидация `doc:{id}` в Redis;
3. удаление в ES.

Если шаг 1 вернул `rowcount == 0` — документ не найден, `DocumentNotFoundError` (404), шаги 2 и 3 не выполняются.

Если падает шаг 3 (ES недоступен, timeout, `NotFoundError` и т.п.) — исключение ловится, пишется `logger.warning("es_delete_failed", doc_id=..., error=...)`, клиенту всё равно возвращается 204.

**Последствие:** в ES может остаться «висячий» id, которого в PG уже нет. При поиске такой id придёт из ES, но `DocumentRepository.get_by_ids` его не вернёт (в PG его нет) — клиент мусорного документа не увидит. Индекс будет содержать мусор до переиндексации.

**Почему так, а не строго наоборот:** если удалять сначала из ES, а потом из PG, то при падении ES клиент получит 5xx и документ останется в PG, хотя мог бы быть удалён. Выбран вариант «источник истины — PG, ES — поисковый кэш»: удаление из PG считается успешным, если прошло в PG, а расхождение в ES чинится переиндексацией.

**Возможное решение — периодическая сверка через cron:** отдельный CLI-скрипт (`app.cli.reconcile_es`) собирает id из PG, проходит scroll-запросом по ES, делает `bulk delete` по разнице и логирует количество удалённых. Запускается строкой в `/etc/cron.d/` раз в сутки. Airflow для одной ночной задачи избыточен, cron даёт тот же эффект без обслуживания отдельного сервиса; при этом cron — это лечение последствий, а не замена транзакционности, и если расхождение должно устраняться в реальном времени, нужен outbox pattern с гарантированной доставкой удалений в ES. В текущем проекте я не реализововал эту систему.

### Импорт CSV

`app/cli/import_csv.py` читает CSV пачками (`--chunk-size`, по умолчанию 500). Для каждой пачки:

1. `session.add_all(...)` + `flush()` — получаем `id` из PG;
2. `bulk_index_documents(..., refresh=False)` — грузим в ES;
3. `commit()`.

При ошибке ES — `rollback()` в PG, пачка не сохраняется ни там, ни там. В конце — `refresh_index` один раз на весь импорт, чтобы не дёргать ES на каждой пачке.

### Логирование

structlog в JSON, уровень из `LOG_LEVEL`. `merge_contextvars` включён — можно обогащать контекст через `structlog.contextvars.bind_contextvars` (сейчас не используется, но инфраструктура на месте). Логи идут в stdout, `logging.basicConfig` настроен с `force=True`, чтобы uvicorn не перехватывал.

### Обработка исключений

- Доменные ошибки (`AppError` и наследники) — обработчик в `main.py`, формат `{"error": {"code", "message"}}`. `status_code` и `code` — атрибуты класса исключения.
- Валидация FastAPI — стандартный 422.
- Всё остальное — 500 от FastAPI, детали в логах.

## Конфигурация

`Settings` (pydantic-settings, `case_sensitive=False`, `extra="ignore"`) — единственный источник конфигурации. Читает `.env` и переменные окружения. Кэшируется через `@lru_cache` — в тестах после смены env вызывается `get_settings.cache_clear()`.

Ключевые поля, не описанные в корневом README:

| Поле | Default | Смысл |
|------|---------|-------|
| `search_candidates` | `200` | Сколько id брать из ES до фильтрации по PG |
| `search_result_limit` | `20` | Сколько документов возвращать клиенту |
| `cache_ttl_seconds` | `300` | TTL кэша документа |

`SEARCH_CANDIDATES > SEARCH_RESULT_LIMIT` — обязательное условие, иначе обрезка до лимита теряет смысл. Значение по умолчанию (200 vs 20) даёт запас на случай, когда часть id из ES «протухла» и не нашлась в PG.

## Тесты

| Каталог | Что тестирует | Docker |
|---------|---------------|--------|
| `tests/unit` | изолированно, всё через моки | не нужен |
| `tests/integration` | реальные PG/ES/Redis через testcontainers | поднимается сам |
| `tests/e2e` | HTTP против запущенного api | нужен запущенный стек |
| `tests/load` | Locust | нужен запущенный стек |

**Integration.** Testcontainers поднимают `postgres:16-alpine`, `elasticsearch:8.15.0`, `redis:7-alpine`. Миграции накатываются `alembic upgrade head` до всех тестов и откатываются `downgrade base` после. Сессионные фикстуры (`pg_container`, `es_container`, `redis_container`) переиспользуются между тестами — экономия времени. Состояние чистится между тестами: `TRUNCATE documents RESTART IDENTITY CASCADE`, пересоздание ES-индекса, `FLUSHDB` в Redis.

**E2E.** По умолчанию бьёт в `http://localhost:8000` (`E2E_BASE_URL`). Перед каждым тестом — `await asyncio.sleep(E2E_RATE_LIMIT_WINDOW)`, чтобы окно rate limiter успело истечь и тест не получил 429 «с прошлого запроса». Отдельный тест `test_rate_limit_exceeded` намеренно стреляет 150 запросами параллельно и ждёт 429 — он требует `RATE_LIMIT_ENABLED=true`. Остальные e2e-тесты проходят и при выключенном лимитере.

**Load.** Два класса Locust: `SearchUser` (вес 8) и `DocumentUser` (вес 2). Соотношение 80/20 — соответствует продовому профилю «много поиска, мало точечных чтений». `HIT_QUERIES` / `MISS_QUERIES` в пропорции 80/20. Rate limiter обязательно выключать перед `make load` — иначе 429 забивает статистику.

**Покрытие.** `pytest.ini`: `--cov=app --cov-report=term-missing`, `asyncio_mode = auto`, сессионные loop-scope для тестов и фикстур.

## Alembic

- `alembic/env.py` использует `async_engine_from_config` + `run_sync` — полностью async.
- URL берётся из `Settings.database_url`, а не из `alembic.ini` (там заглушка `driver://user:pass@localhost/dbname`).
- `target_metadata = Base.metadata` — автогенерация видит модели.
- В `versions/` пока одна миграция: `0001_create_documents.py`.

## Dockerfile

Multi-stage:

- **builder** — `python:3.12-slim-bookworm` + `uv sync --locked --no-install-project --no-dev` (сначала зависимости по lock-файлу) + `uv sync --locked --no-dev` (потом сам проект). Кэш `uv` монтируется как BuildKit cache-mount, повторные сборки не перекачивают зависимости.
- **runtime** — `python:3.12-slim-bookworm`, копируется только `.venv`, `app/`, `alembic/`, `alembic.ini`. Без `uv` и без исходников тестов. `curl` ставится для `HEALTHCHECK`.
- `HEALTHCHECK` бьёт в `/health`, интервал 10с, `start-period` 20с — API с 4 воркерами и подключениями к PG/ES стартует за это время.
- `CMD` запускает uvicorn с `--workers ${WEB_CONCURRENCY:-4}`.

## Ограничения архитектуры

- Бэкенд не масштабируется горизонтально без внешнего слоя для rate limiter: ключи считаются в Redis, а не в памяти процесса, поэтому несколько экземпляров api работают корректно, но только если у них общий Redis.
- `WEB_CONCURRENCY=4` в одном контейнере — это 4 независимых пула соединений к PgBouncer и 4 клиента ES. Для реальной нагрузки контейнеров должно быть несколько, а `WEB_CONCURRENCY` — 1 на контейнер.
- Импорт CSV не идемпотентен: повторный запуск создаст дубликаты в PG (у `id` autoincrement), а в ES они перезапишутся по `_id`. Перед повторным импортом нужен `docker compose down -v` или чистка PG.

## Возможные улучшения

- **Outbox для удалений в ES** — закрывает единственную реальную дыру в консистентности: при падении ES в индексе остаётся осиротевший id (в выдаче отфильтруется, но мусор живёт до переиндексации). Намерение удалить пишется в outbox-таблицу в одной транзакции с `DELETE` в PG, отдельный воркер гарантированно доносит его до ES с ретраями. Одна таблица и простой воркер убирают окно рассинхрона полностью.
- **Ночная сверка PG↔ES через cron** — дешёвая страховка, если outbox пока не нужен. CLI-скрипт собирает id из PG, scroll-запросом проходит по ES, делает `bulk delete` по разнице и логирует результат. Запускается строкой в crontab через `docker compose run --rm api` — тот же образ и `.env`, ничего дополнительно поднимать не нужно.
- **Идемпотентный импорт CSV** — сейчас повторный `make import` создаёт дубликаты в PG и перезаписывает их в ES. `UNIQUE` на хэш строки или на `(text, created_date)` плюс `ON CONFLICT` в `persist_batch` решают проблему, и `down -v` перед импортом больше не нужен.
- **Non-root в Dockerfile** — `USER app` после `COPY` в runtime-стадии плюс `--read-only` rootfs в compose. Снимает стандартное замечание на ревью, ничего не ломает.
- **CI (ruff + pytest)** — GitHub Actions: линт, unit, integration, проверка `alembic upgrade head` на чистой БД. Полчаса работы, снимает вопрос «а тесты правда проходят» и отлавливает регрессии до ревью.