from unittest.mock import AsyncMock, MagicMock

import pytest

from app.cli.init_es import run
from app.core.config import Settings


def _patch(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    """Подменяет клиент и операции с индексом"""
    es_client = MagicMock()
    es_client.close = AsyncMock()
    create = AsyncMock()
    delete = AsyncMock()
    monkeypatch.setattr("app.cli.init_es.create_es_client", MagicMock(return_value=es_client))
    monkeypatch.setattr("app.cli.init_es.create_index", create)
    monkeypatch.setattr("app.cli.init_es.delete_index", delete)
    return es_client, create, delete, MagicMock()


async def test_run_creates_index(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет создание индекса без удаления"""
    es_client, create, delete, _ = _patch(monkeypatch)
    await run(Settings(_env_file=None))
    create.assert_awaited_once()
    delete.assert_not_awaited()
    es_client.close.assert_awaited_once()


async def test_run_with_drop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет удаление и создание индекса"""
    es_client, create, delete, _ = _patch(monkeypatch)
    await run(Settings(_env_file=None), drop=True)
    delete.assert_awaited_once()
    create.assert_awaited_once()
    es_client.close.assert_awaited_once()


async def test_run_passes_index_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет передачу имени индекса"""
    es_client, create, _, _ = _patch(monkeypatch)
    settings = Settings(_env_file=None, elasticsearch_index="custom")
    await run(settings)
    create.assert_awaited_once_with(es_client, "custom")


async def test_run_closes_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет закрытие клиента при ошибке"""
    es_client, create, _, _ = _patch(monkeypatch)
    create.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError):
        await run(Settings(_env_file=None))
    es_client.close.assert_awaited_once()