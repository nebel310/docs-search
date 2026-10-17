import logging
import sys

import structlog
from structlog.contextvars import merge_contextvars


def configure_logging(log_level: str = "INFO") -> None:
    """Настраивает structlog для вывода JSON-логов в stdout"""
    numeric_level = logging.getLevelNamesMapping().get(log_level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
        force=True,
    )
    structlog.configure(
        processors=[
            merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Возвращает structlog-логгер с указанным именем"""
    return structlog.get_logger(name) if name else structlog.get_logger()