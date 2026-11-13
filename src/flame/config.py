"""Typed application configuration loaded from environment variables and ``.env``."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

_PATH_FIELDS = (
    "data_raw_dir",
    "data_processed_dir",
    "data_reports_dir",
    "data_interim_dir",
    "canonical_dataset_path",
    "duckdb_path",
    "dataset_output_path",
    "provenance_manifest_path",
    "quality_report_path",
    "canonical_diff_path",
    "mappings_dir",
)


class Settings(BaseSettings):
    """Application settings.

    Values are read from ``FLAME_*`` environment variables first and from the
    project ``.env`` file second. Secret values use :class:`~pydantic.SecretStr`
    so they are masked in representations and logs.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="FLAME_",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )

    app_name: str = "Flame in Freefall"
    app_version: str = "0.1.0"

    data_raw_dir: Path = PROJECT_ROOT / "data" / "raw"
    data_processed_dir: Path = PROJECT_ROOT / "data" / "processed"
    data_reports_dir: Path = PROJECT_ROOT / "data" / "reports"
    data_interim_dir: Path = PROJECT_ROOT / "data" / "interim"
    canonical_dataset_path: Path = PROJECT_ROOT / "data" / "processed" / "canonical_experiments.csv"
    duckdb_path: Path = PROJECT_ROOT / "data" / "interim" / "flame.duckdb"
    dataset_output_path: Path = PROJECT_ROOT / "data" / "processed" / "experiments.parquet"
    provenance_manifest_path: Path = (
        PROJECT_ROOT / "data" / "processed" / "provenance_manifest.json"
    )
    quality_report_path: Path = PROJECT_ROOT / "data" / "reports" / "quality_report.md"
    canonical_diff_path: Path = PROJECT_ROOT / "data" / "reports" / "canonical_diff.csv"
    mappings_dir: Path = PROJECT_ROOT / "src" / "flame" / "ingestion" / "mappings"

    # Ingestion quality thresholds. Airflow above the threshold is quarantined;
    # burn times above the maximum are flagged but never altered.
    airflow_quarantine_threshold_cms: float = 1000.0
    burn_time_max_s: float = 3600.0

    log_level: LogLevel = "INFO"

    # Placeholders only. No API key is committed or defaulted.
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: SecretStr | None = None

    # API configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    rate_limit_per_minute: int = 60
    max_question_length: int = 1000
    max_log_text_length: int = 200

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> object:
        if isinstance(value, str):
            return value.upper()
        return value

    @field_validator(*_PATH_FIELDS, mode="after")
    @classmethod
    def _resolve_path(cls, value: Path) -> Path:
        """Resolve relative paths against the repository root."""
        if value.is_absolute():
            return value
        return PROJECT_ROOT / value

    @model_validator(mode="after")
    def _require_api_key_for_provider(self) -> Settings:
        if self.llm_provider and self.llm_api_key is None:
            raise ValueError("FLAME_LLM_API_KEY is required when FLAME_LLM_PROVIDER is set.")
        return self


def get_settings() -> Settings:
    """Build a fresh :class:`Settings` instance from the current environment."""
    return Settings()
