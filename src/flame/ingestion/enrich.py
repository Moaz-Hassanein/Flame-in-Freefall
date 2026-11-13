"""Deterministic enrichment: modeled-row marking, flags, and text facts.

The text extraction patterns are intentionally narrow. A pattern is implemented
only after it has been verified against every row that declares the fact in the
canonical artifact. The quality report prints the candidate and matched counts.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import pandas as pd
import yaml

from flame.ingestion.errors import PipelineError

_DIMENSIONS = re.compile(
    r"Dimensions:\s*(?P<length>\d+(?:\.\d+)?)cm\s*x\s*"
    r"(?P<width>\d+(?:\.\d+)?)cm\s*x\s*(?P<thickness>\d+(?:\.\d+)?)cm"
)
_FLOW_DIRECTION = re.compile(r"\(Flow:\s*(?P<direction>Concurrent|Opposed)\)")
_MICROGRAVITY_DURATION = re.compile(
    r"Microgravity duration:\s*(?P<seconds>\d+(?:\.\d+)?)\s*s\b", re.IGNORECASE
)
_PI_NAME = re.compile(r"\bPI:\s*(?P<name>[A-Za-z][A-Za-z .'-]*?)\.")

_DIMENSION_FAMILIES = frozenset(
    {
        "SAFFIRE-I",
        "SAFFIRE-II",
        "SAFFIRE-III",
        "SAFFIRE-IV",
        "SAFFIRE-V",
        "SAFFIRE-VI",
    }
)
_MICROGRAVITY_FAMILY = "GRC Drop Tower"
_PI_FAMILY = "BASS-II"


@dataclass(frozen=True)
class PatternStats:
    """Verification and match counts for one extraction pattern."""

    name: str
    pattern: str
    candidate_rows: int
    matched_rows: int
    unmatched_values: dict[str, int] = field(default_factory=dict)
    documented_exceptions: dict[str, int] = field(default_factory=dict)
    verified: bool = True


@dataclass(frozen=True)
class ExtractionStats:
    """All extraction statistics produced by :func:`extract_text_facts`."""

    specimen_dimensions: PatternStats
    flow_direction: PatternStats
    microgravity_duration: PatternStats
    pi_name: PatternStats


@dataclass(frozen=True)
class ModeledRuleStats:
    """Counts produced by :func:`apply_modeled_rules`."""

    rule_counts: dict[str, int]
    total: int
    experiment_ids: tuple[tuple[str, str], ...]


def load_modeled_rules(path: Path) -> dict[str, Any]:
    """Load and minimally validate the modeled-row rule file."""

    with path.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise PipelineError(f"{path}: modeled rules must be a mapping")
    rules = payload.get("rules")
    if not isinstance(rules, list) or not rules:
        raise PipelineError(f"{path}: 'rules' must be a non-empty list")
    for rule in rules:
        if not isinstance(rule, dict) or not isinstance(rule.get("id"), str):
            raise PipelineError(f"{path}: every rule needs a string 'id'")
    return cast(dict[str, Any], payload)


def apply_modeled_rules(
    frame: pd.DataFrame, config: dict[str, Any]
) -> tuple[pd.DataFrame, ModeledRuleStats]:
    """Set ``is_modeled`` from family and gravity rules, never from row IDs."""

    enriched = frame.copy()
    is_modeled = pd.Series(False, index=enriched.index, dtype=bool)
    rule_counts: Counter[str] = Counter()
    matched_ids: list[tuple[str, str]] = []

    for rule in cast(list[dict[str, Any]], config["rules"]):
        rule_id = str(rule["id"])
        mask = pd.Series(True, index=enriched.index, dtype=bool)
        families = rule.get("dataset_family_in", [])
        if families:
            if not isinstance(families, list):
                raise PipelineError(f"modeled rule {rule_id!r}: dataset_family_in must be a list")
            mask &= enriched["dataset_family"].isin(families)
        prefix = rule.get("gravity_condition_prefix")
        if prefix is not None:
            mask &= enriched["gravity_condition"].astype(str).str.startswith(str(prefix))
        new_matches = mask & ~is_modeled
        rule_counts[rule_id] = int(new_matches.sum())
        for experiment_id in enriched.loc[new_matches, "experiment_id"]:
            matched_ids.append((str(experiment_id), rule_id))
        is_modeled |= mask

    enriched["is_modeled"] = is_modeled
    stats = ModeledRuleStats(
        rule_counts=dict(sorted(rule_counts.items())),
        total=int(is_modeled.sum()),
        experiment_ids=tuple(sorted(matched_ids)),
    )
    return enriched, stats


def extract_text_facts(frame: pd.DataFrame) -> tuple[pd.DataFrame, ExtractionStats]:
    """Extract verified text facts into new nullable columns.

    A row that does not declare the fact stays null. No value is inferred from a
    neighboring row or from a family default.
    """

    enriched = frame.copy()
    descriptions = enriched["sample_description"].fillna("").astype(str)
    notes = enriched["notes"].fillna("").astype(str)
    families = enriched["dataset_family"].astype(str)

    dimension_stats = _extract_dimensions(enriched, descriptions)
    flow_stats = _extract_flow_direction(enriched, descriptions, families)
    duration_stats = _extract_microgravity_duration(enriched, notes, families)
    pi_stats = _extract_pi_name(enriched, notes, families)

    stats = ExtractionStats(
        specimen_dimensions=dimension_stats,
        flow_direction=flow_stats,
        microgravity_duration=duration_stats,
        pi_name=pi_stats,
    )
    return enriched, stats


def _extract_dimensions(frame: pd.DataFrame, descriptions: pd.Series) -> PatternStats:
    candidate_mask = descriptions.str.contains("Dimensions:", regex=False)
    numeric_mask = candidate_mask & ~descriptions.str.contains("Nonecm", regex=False)
    extracted = descriptions.str.extract(_DIMENSIONS)

    matched_mask = numeric_mask & extracted["length"].notna()
    skipped = descriptions[candidate_mask & ~numeric_mask]

    frame["specimen_length_cm"] = pd.to_numeric(extracted["length"], errors="coerce")
    frame["specimen_width_cm"] = pd.to_numeric(extracted["width"], errors="coerce")
    frame["specimen_thickness_cm"] = pd.to_numeric(extracted["thickness"], errors="coerce")

    unmatched = descriptions[numeric_mask & ~matched_mask]
    unmatched_counts = Counter(unmatched.tolist())
    exception_counts = Counter(skipped.tolist())
    verified = int(numeric_mask.sum()) == int(matched_mask.sum())

    return PatternStats(
        name="specimen_dimensions",
        pattern=_DIMENSIONS.pattern,
        candidate_rows=int(candidate_mask.sum()),
        matched_rows=int(matched_mask.sum()),
        unmatched_values=dict(sorted(unmatched_counts.items())),
        documented_exceptions=dict(sorted(exception_counts.items())),
        verified=verified,
    )


def _extract_flow_direction(
    frame: pd.DataFrame, descriptions: pd.Series, families: pd.Series
) -> PatternStats:
    candidate_mask = descriptions.str.contains("(Flow:", regex=False)
    exception_mask = candidate_mask & descriptions.str.contains("(Flow: nan)", regex=False)
    extracted = descriptions.str.extract(_FLOW_DIRECTION)
    matched_mask = candidate_mask & extracted["direction"].notna()
    frame["flow_direction"] = extracted["direction"]

    unmatched = descriptions[candidate_mask & ~matched_mask & ~exception_mask]
    unmatched_counts = Counter(unmatched.tolist())
    exception_counts = Counter(descriptions[exception_mask].tolist())
    in_family = families.isin(_DIMENSION_FAMILIES)
    verified = (
        int(matched_mask.sum()) + int(exception_mask.sum())
        == int((candidate_mask & in_family).sum())
    )

    return PatternStats(
        name="flow_direction",
        pattern=_FLOW_DIRECTION.pattern,
        candidate_rows=int(candidate_mask.sum()),
        matched_rows=int(matched_mask.sum()),
        unmatched_values=dict(sorted(unmatched_counts.items())),
        documented_exceptions=dict(sorted(exception_counts.items())),
        verified=verified,
    )


def _extract_microgravity_duration(
    frame: pd.DataFrame, notes: pd.Series, families: pd.Series
) -> PatternStats:
    in_family = families == _MICROGRAVITY_FAMILY
    candidate_mask = in_family & notes.str.contains("Microgravity duration:", regex=False)
    extracted = notes.str.extract(_MICROGRAVITY_DURATION)
    matched_mask = candidate_mask & extracted["seconds"].notna()
    frame["microgravity_duration_s"] = pd.to_numeric(extracted["seconds"], errors="coerce")

    unmatched = notes[candidate_mask & ~matched_mask]
    unmatched_counts = Counter(unmatched.tolist())
    verified = int(matched_mask.sum()) == int(candidate_mask.sum())

    return PatternStats(
        name="microgravity_duration",
        pattern=_MICROGRAVITY_DURATION.pattern,
        candidate_rows=int(candidate_mask.sum()),
        matched_rows=int(matched_mask.sum()),
        unmatched_values=dict(sorted(unmatched_counts.items())),
        verified=verified,
    )


def _extract_pi_name(
    frame: pd.DataFrame, notes: pd.Series, families: pd.Series
) -> PatternStats:
    in_family = families == _PI_FAMILY
    candidate_mask = in_family & notes.str.contains("PI:", regex=False)
    extracted = notes.str.extract(_PI_NAME)
    matched_mask = candidate_mask & extracted["name"].notna()
    frame["pi_name"] = extracted["name"]

    unmatched = notes[candidate_mask & ~matched_mask]
    unmatched_counts = Counter(unmatched.tolist())
    verified = int(matched_mask.sum()) == int(candidate_mask.sum())

    return PatternStats(
        name="pi_name",
        pattern=_PI_NAME.pattern,
        candidate_rows=int(candidate_mask.sum()),
        matched_rows=int(matched_mask.sum()),
        unmatched_values=dict(sorted(unmatched_counts.items())),
        verified=verified,
    )


def finalize_quality_flags(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Move internal ``_flags`` into a sorted ``data_quality_flags`` list column."""

    finalized = frame.copy()
    if "_flags" in finalized.columns:
        raw_flags = finalized.pop("_flags").tolist()
    else:
        raw_flags = [[] for _ in range(len(finalized))]

    flags_column: list[list[str]] = []
    counts: Counter[str] = Counter()
    for value in raw_flags:
        flags = sorted(str(item) for item in value) if isinstance(value, list) else []
        flags_column.append(flags)
        counts.update(flags)

    finalized["data_quality_flags"] = flags_column
    return finalized, dict(sorted(counts.items()))
