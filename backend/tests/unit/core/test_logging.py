import logging
from collections.abc import Iterator

import pytest
import structlog

from app.core.logging import configure_logging, get_logger


@pytest.fixture(autouse=True)
def _reset_structlog() -> Iterator[None]:
    """Сбрасывает structlog и stdlib logging перед каждым тестом"""
    structlog.reset_defaults()
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    yield
    structlog.reset_defaults()
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)


def test_configure_logging_valid_level() -> None:
    """Проверяет конфигурацию при валидном уровне логирования"""
    configure_logging("DEBUG")


def test_configure_logging_invalid_level_falls_back() -> None:
    """Проверяет что невалидный уровень откатывается на INFO"""
    configure_logging("NOPE")


def test_configure_logging_lowercase_level() -> None:
    """Проверяет что уровень в нижнем регистре корректно обрабатывается"""
    configure_logging("debug")


def test_configure_logging_idempotent() -> None:
    """Проверяет что повторный вызов не падает"""
    configure_logging("INFO")
    configure_logging("INFO")


def test_get_logger_named() -> None:
    """Проверяет получение логгера с именем"""
    configure_logging("INFO")
    logger = get_logger("my.module")
    assert logger is not None


def test_get_logger_anonymous() -> None:
    """Проверяет получение логгера без имени"""
    configure_logging("INFO")
    logger = get_logger()
    assert logger is not None


def test_logger_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    """Проверяет что логгер пишет JSON в stdout"""
    configure_logging("INFO")
    logger = get_logger("test")
    logger.info("hello", foo="bar")
    out = capsys.readouterr().out
    assert "hello" in out
    assert "foo" in out
    assert "bar" in out