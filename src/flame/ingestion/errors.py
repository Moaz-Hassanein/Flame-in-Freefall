"""Pipeline errors that always carry file and row context."""

from __future__ import annotations


class PipelineError(Exception):
    """Base class for deterministic, user-facing ingestion failures."""


class SourceFormatError(PipelineError):
    """A source file does not have the expected shape or columns."""

    def __init__(self, path: str, message: str, *, row: int | None = None) -> None:
        self.path = path
        self.row = row
        location = f"{path}" if row is None else f"{path} (row {row})"
        super().__init__(f"{location}: {message}")


class RowContextError(PipelineError):
    """A single record failed a hard constraint."""

    def __init__(
        self,
        *,
        path: str,
        row: int | None,
        experiment_id: str | None,
        message: str,
    ) -> None:
        self.path = path
        self.row = row
        self.experiment_id = experiment_id
        parts = [path]
        if row is not None:
            parts.append(f"row {row}")
        if experiment_id:
            parts.append(f"experiment_id={experiment_id!r}")
        super().__init__(f"{', '.join(parts)}: {message}")


class DataValidationError(PipelineError):
    """Hard dataset validation failed.

    Carries the first few concrete failures so the caller can act without
    parsing a large error object.
    """

    def __init__(self, message: str, *, failures: list[str]) -> None:
        self.failures = failures
        detail = "\n".join(f"  - {failure}" for failure in failures)
        super().__init__(f"{message}\n{detail}")
