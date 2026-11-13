"""Typed exceptions for query planning, compilation, and execution."""

from __future__ import annotations


class RetrievalError(Exception):
    """Base exception for all retrieval operations."""


class PlanValidationError(RetrievalError, ValueError):
    """Raised when a query plan fails semantic or contract validation."""


class UnknownFieldError(PlanValidationError):
    """Raised when an unwhitelisted field name is requested."""


class UnknownOperatorError(PlanValidationError):
    """Raised when an unsupported comparison or filter operator is requested."""


class QueryCompilationError(RetrievalError):
    """Raised when a query plan cannot be compiled to parameterized SQL."""


class ExecutionError(RetrievalError):
    """Raised when query execution encounters an unexpected database failure."""


__all__ = [
    "ExecutionError",
    "PlanValidationError",
    "QueryCompilationError",
    "RetrievalError",
    "UnknownFieldError",
    "UnknownOperatorError",
]
