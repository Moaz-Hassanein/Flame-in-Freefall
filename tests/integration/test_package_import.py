"""Integration smoke tests for the package layout."""

from __future__ import annotations

import importlib

import pytest

MODULE_NAMES = [
    "flame",
    "flame.config",
    "flame.schemas",
    "flame.ingestion",
    "flame.retrieval",
    "flame.rag",
    "flame.llm",
    "flame.api",
    "flame.observability",
    "flame.observability.logging",
]


@pytest.mark.integration
@pytest.mark.parametrize("module_name", MODULE_NAMES)
def test_module_imports(module_name: str) -> None:
    assert importlib.import_module(module_name) is not None


@pytest.mark.integration
def test_public_config_and_logging_symbols_are_available() -> None:
    from flame.config import Settings
    from flame.observability.logging import JsonFormatter

    assert Settings is not None
    assert JsonFormatter is not None
