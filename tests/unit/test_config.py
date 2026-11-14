"""Tests for typed application settings."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from flame.config import PROJECT_ROOT, Settings


@pytest.fixture(autouse=True)
def _clear_flame_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.upper().startswith("FLAME_"):
            monkeypatch.delenv(name, raising=False)


def test_defaults_without_env_file() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_name == "Flame in Freefall"
    assert settings.app_version == "0.1.0"
    assert settings.data_raw_dir == PROJECT_ROOT / "data" / "raw"
    assert settings.data_processed_dir == PROJECT_ROOT / "data" / "processed"
    assert settings.data_interim_dir == PROJECT_ROOT / "data" / "interim"
    assert (
        settings.canonical_dataset_path
        == PROJECT_ROOT / "data" / "processed" / "canonical_experiments.csv"
    )
    assert settings.duckdb_path == PROJECT_ROOT / "data" / "interim" / "flame.duckdb"
    assert settings.log_level == "INFO"
    assert settings.llm_provider is None
    assert settings.llm_model is None
    assert settings.llm_api_key is None


def test_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLAME_LOG_LEVEL", "debug")
    monkeypatch.setenv("FLAME_DUCKDB_PATH", "/tmp/override.duckdb")
    monkeypatch.setenv("FLAME_LLM_PROVIDER", "openai")
    monkeypatch.setenv("FLAME_LLM_MODEL", "example-model")
    monkeypatch.setenv("FLAME_LLM_API_KEY", "test-secret-value")

    settings = Settings(_env_file=None)

    assert settings.log_level == "DEBUG"
    assert settings.duckdb_path == Path("/tmp/override.duckdb")
    assert settings.llm_provider == "openai"
    assert settings.llm_model == "example-model"
    assert settings.llm_api_key is not None
    assert settings.llm_api_key.get_secret_value() == "test-secret-value"


def test_relative_paths_resolve_against_project_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLAME_DATA_RAW_DIR", "custom/raw")

    settings = Settings(_env_file=None)

    assert settings.data_raw_dir == PROJECT_ROOT / "custom" / "raw"


def test_env_file_is_loaded(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "FLAME_LOG_LEVEL=WARNING\n"
        "FLAME_LLM_PROVIDER=example\n"
        "FLAME_LLM_MODEL=example-model\n"
        "FLAME_LLM_API_KEY=file-secret\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.log_level == "WARNING"
    assert settings.llm_model == "example-model"
    assert settings.llm_api_key is not None
    assert settings.llm_api_key.get_secret_value() == "file-secret"


def test_missing_api_key_for_provider_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLAME_LLM_PROVIDER", "openai")

    with pytest.raises(ValidationError, match="FLAME_LLM_API_KEY"):
        Settings(_env_file=None)


def test_invalid_log_level_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLAME_LOG_LEVEL", "verbose")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_secret_is_masked_in_repr() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="openai",
        llm_api_key="super-secret-value",
    )

    assert "super-secret-value" not in repr(settings)
