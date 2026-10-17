from uuid import uuid4

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.logging import get_logger
from app.rate_limit.script import SLIDING_WINDOW_SCRIPT


logger = get_logger(__name__)

SKIP_PATHS = frozenset({"/health", "/ready", "/docs", "/openapi.json", "/redoc"})


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware скользящего окна rate limiter"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Применяет лимит к запросу и вызывает следующий обработчик"""
        settings = getattr(request.app.state, "settings", None)
        if settings is None or not settings.rate_limit_enabled:
            return await call_next(request)

        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        redis = getattr(request.app.state, "redis", None)
        if redis is None:
            return await call_next(request)

        client_host = request.client.host if request.client else "unknown"
        key = f"rl:{client_host}:{request.url.path}"
        now_ms = int(request.app.state.clock() * 1000)
        window_ms = settings.rate_limit_window_seconds * 1000
        member = uuid4().hex

        try:
            allowed = await redis.eval(
                SLIDING_WINDOW_SCRIPT,
                1,
                key,
                now_ms,
                window_ms,
                settings.rate_limit_requests,
                member,
            )
        except Exception as exc:
            logger.warning("rate_limit_failed", error=str(exc))
            return await call_next(request)

        if allowed == 1:
            return await call_next(request)

        return JSONResponse(
            status_code=429,
            content={"error": {"code": "rate_limit_exceeded", "message": "Too many requests"}},
            headers={"Retry-After": str(settings.rate_limit_window_seconds)},
        )