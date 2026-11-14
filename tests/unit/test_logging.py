"""Tests for JSON logging, request correlation, and secret redaction."""

from __future__ import annotations

import json
import logging
from io import StringIO
from typing import Any

import pytest

from flame.observability.logging import (
    configure_logging,
    get_request_id,
    reset_request_id,
    set_request_id,
)

_LOGGER_NAME = "flame.tests"


def _emit(stream: StringIO, message: str = "hello", **extra: Any) -> dict[str, Any]:
    logger = logging.getLogger(_LOGGER_NAME)
    if extra:
        logger.info(message, extra=extra)
    else:
        logger.info(message)
    lines = stream.getvalue().strip().splitlines()
    payload: dict[str, Any] = json.loads(lines[-1])
    return payload


def test_json_payload_shape() -> None:
    stream = StringIO()
    configure_logging("INFO", stream)

    payload = _emit(stream)

    assert {"timestamp", "level", "logger", "message", "request_id"} <= payload.keys()
    assert payload["level"] == "INFO"
    assert payload["logger"] == _LOGGER_NAME
    assert payload["message"] == "hello"
    assert payload["request_id"] is None


def test_request_id_is_included() -> None:
    stream = StringIO()
    token = set_request_id("req-42")
    try:
        configure_logging("DEBUG", stream)
        payload = _emit(stream)
        assert payload["request_id"] == "req-42"
        assert get_request_id() == "req-42"
    finally:
        reset_request_id(token)

    assert get_request_id() is None


def test_message_secrets_are_redacted() -> None:
    stream = StringIO()
    configure_logging("INFO", stream)

    payload = _emit(
        stream,
        "api_key=supersecret123 Bearer abc.def.ghi sk-1234567890abcdef",
    )

    message = payload["message"]
    assert "supersecret123" not in message
    assert "abc.def.ghi" not in message
    assert "sk-1234567890abcdef" not in message
    assert message.count("[REDACTED]") >= 3


def test_structured_secrets_are_redacted() -> None:
    stream = StringIO()
    configure_logging("INFO", stream)

    payload = _emit(
        stream,
        "auth",
        password="hunter2",
        nested={"token": "tok-123", "safe": "ok"},
        safe="visible",
    )

    assert payload["password"] == "[REDACTED]"
    assert payload["nested"]["token"] == "[REDACTED]"
    assert payload["nested"]["safe"] == "ok"
    assert payload["safe"] == "visible"


def test_exception_secrets_are_redacted() -> None:
    stream = StringIO()
    configure_logging("INFO", stream)

    try:
        raise RuntimeError("api_key=leaked-secret")
    except RuntimeError:
        logging.getLogger(_LOGGER_NAME).exception("failure")

    payload = json.loads(stream.getvalue().strip().splitlines()[-1])
    assert "leaked-secret" not in payload["exception"]
    assert "[REDACTED]" in payload["exception"]


def test_reconfigure_does_not_duplicate_handlers() -> None:
    stream = StringIO()
    configure_logging("INFO", stream)
    configure_logging("INFO", stream)

    _emit(stream)

    assert len(stream.getvalue().strip().splitlines()) == 1


def test_unknown_level_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown log level"):
        configure_logging("verbose", StringIO())
