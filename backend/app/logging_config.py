"""Structured JSON logging configuration for the Etsy Listing Agent backend.

Call ``configure_logging()`` once at application startup (in lifespan).
After that, every ``logging.getLogger(__name__)`` call produces structured
JSON lines on stdout — compatible with log aggregators (Datadog, CloudWatch,
Loki, etc.).

The ``RequestIdMiddleware`` injects a per-request ``X-Request-ID`` header and
binds the value to ``contextvars`` so all log records emitted during a request
automatically include ``request_id``.
"""

import json
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# ── Context variable ──────────────────────────────────────────────────────────
# Stores the current request ID in async context so any logger can read it.
_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Return the request ID for the current async context (empty string if none)."""
    return _request_id_var.get()


# ── JSON log formatter ────────────────────────────────────────────────────────


class _JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects.

    Each record gets the standard fields plus ``request_id`` (when set) and
    any extra key-value pairs passed as ``extra=`` to the logger call.
    """

    # Fields that are already represented at the top level — don't duplicate them.
    _SKIP_ATTRS = frozenset(
        {
            "args",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "message",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()

        payload: dict = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
        }

        # Attach request_id when available
        rid = get_request_id()
        if rid:
            payload["request_id"] = rid

        # Include exception traceback as a string if present
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        # Include any extra key-value pairs added via extra={}
        for key, value in record.__dict__.items():
            if key not in self._SKIP_ATTRS and not key.startswith("_"):
                payload[key] = value

        return json.dumps(payload, default=str)


# ── Public configuration entry-point ─────────────────────────────────────────


def configure_logging(level: str = "INFO") -> None:
    """Replace the root logger's handlers with a single JSON-to-stdout handler.

    Should be called once during application startup, before any request
    handling begins.

    Args:
        level: Logging level string — e.g. ``"INFO"``, ``"DEBUG"``, ``"WARNING"``.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric_level)

    # Silence noisy third-party loggers that don't add value in production
    for noisy in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Structured JSON logging initialised",
        extra={"log_level": level.upper()},
    )


# ── Request ID middleware ─────────────────────────────────────────────────────


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Inject a unique ``X-Request-ID`` into every request and response.

    The ID is either taken from the incoming ``X-Request-ID`` header (so
    upstream proxies can propagate a trace ID) or generated fresh as a UUIDv4.

    The ID is bound to ``_request_id_var`` so all log records emitted during
    the request automatically include it via ``_JsonFormatter``.
    """

    def __init__(self, app: ASGIApp, header_name: str = "X-Request-ID") -> None:
        super().__init__(app)
        self._header_name = header_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Honour an existing request ID from an upstream proxy/load-balancer
        request_id = request.headers.get(self._header_name) or uuid.uuid4().hex

        token = _request_id_var.set(request_id)
        start = time.monotonic()

        try:
            response = await call_next(request)
        finally:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            _request_id_var.reset(token)

        # Echo the request ID back in the response so clients can correlate logs
        response.headers[self._header_name] = request_id

        # Structured access log (replaces uvicorn.access noise)
        logging.getLogger("app.access").info(
            "%s %s %s",
            request.method,
            request.url.path,
            response.status_code,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        return response
