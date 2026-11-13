"""JSON structured logging with request correlation and secret redaction."""

from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any, TextIO

from flame.config import LogLevel

REQUEST_ID: ContextVar[str | None] = ContextVar("request_id", default=None)

_REDACTED = "[REDACTED]"
_SENSITIVE_MARKERS = (
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "authorization",
    "credential",
)
_KEY_VALUE_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|token|secret|password|authorization)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_API_KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")
_RESERVED_RECORD_KEYS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
}


def set_request_id(request_id: str | None) -> Token[str | None]:
    """Bind a request identifier to the current context."""
    return REQUEST_ID.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    """Restore the previous request identifier."""
    REQUEST_ID.reset(token)


def get_request_id() -> str | None:
    """Return the request identifier bound to the current context, if any."""
    return REQUEST_ID.get()


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in _SENSITIVE_MARKERS)


def redact_text(text: str) -> str:
    """Redact common secret shapes from a free-form string."""
    redacted = _KEY_VALUE_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{_REDACTED}",
        text,
    )
    redacted = _BEARER_PATTERN.sub(f"Bearer {_REDACTED}", redacted)
    return _API_KEY_PATTERN.sub(_REDACTED, redacted)


def redact_value(value: Any) -> Any:
    """Recursively redact secrets in structured log values."""
    if isinstance(value, dict):
        return {
            key: _REDACTED
            if isinstance(key, str) and _is_sensitive_key(key)
            else redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


class _FlameJsonHandler(logging.StreamHandler[TextIO]):
    """Stream handler tagged so reconfiguration can replace only our handler."""


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(record.getMessage()),
            "request_id": get_request_id(),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_KEYS or key == "request_id":
                continue
            payload[key] = _REDACTED if _is_sensitive_key(key) else redact_value(value)
        if record.exc_info:
            payload["exception"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)


def _level_value(level: str) -> int:
    normalized = level.upper()
    levels = logging.getLevelNamesMapping()
    if normalized not in levels:
        raise ValueError(f"Unknown log level: {level!r}")
    return levels[normalized]


def configure_logging(level: LogLevel | str = "INFO", stream: TextIO | None = None) -> None:
    """Configure root JSON logging, replacing any handler installed previously."""
    level_value = _level_value(level)

    root = logging.getLogger()
    for handler in tuple(root.handlers):
        if isinstance(handler, _FlameJsonHandler):
            root.removeHandler(handler)

    handler = _FlameJsonHandler(stream or sys.stderr)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level_value)
