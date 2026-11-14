"""Unit tests for modeled-row rules, text extraction, and flag finalisation."""

from __future__ import annotations

import pandas as pd
import pytest

from flame.ingestion.enrich import (
    apply_modeled_rules,
    extract_text_facts,
    finalize_quality_flags,
)
from flame.ingestion.errors import PipelineError
from flame.ingestion.validate import require_verified_patterns


def _rules() -> dict[str, object]:
    return {
        "version": 1,
        "rules": [
            {
                "id": "bounded",
                "dataset_family_in": ["Partial-g Bounded"],
                "gravity_condition_prefix": "Partial-g Bounded Model",
            },
            {
                "id": "reference",
                "dataset_family_in": ["LUCI / FM2"],
                "gravity_condition_prefix": "Partial-g Bounded Model",
            },
        ],
    }


def test_modeled_rules_use_family_and_gravity_not_ids() -> None:
    frame = pd.DataFrame(
        {
            "experiment_id": ["a", "b", "c", "d"],
            "dataset_family": [
                "Partial-g Bounded",
                "Partial-g Bounded",
                "LUCI / FM2",
                "Measured",
            ],
            "gravity_condition": [
                "Partial-g Bounded Model: Lunar",
                "Partial-g Bounded Model: Martian",
                "Partial-g Bounded Model: Lunar",
                "Microgravity (~0g)",
            ],
        }
    )

    enriched, stats = apply_modeled_rules(frame, _rules())

    assert enriched["is_modeled"].tolist() == [True, True, True, False]
    assert stats.rule_counts == {"bounded": 2, "reference": 1}
    assert stats.total == 3
    assert ("a", "bounded") in stats.experiment_ids


def test_modeled_prefix_must_match_too() -> None:
    frame = pd.DataFrame(
        {
            "experiment_id": ["a", "b"],
            "dataset_family": ["Partial-g Bounded", "Partial-g Bounded"],
            "gravity_condition": ["Partial-g Bounded Model: Lunar", "Microgravity (~0g)"],
        }
    )

    enriched, stats = apply_modeled_rules(frame, _rules())

    assert enriched["is_modeled"].tolist() == [True, False]
    assert stats.total == 1


def test_text_facts_are_extracted_and_counted() -> None:
    frame = pd.DataFrame(
        {
            "experiment_id": ["saf", "saf2", "grc", "bass"],
            "dataset_family": ["SAFFIRE-II", "SAFFIRE-I", "GRC Drop Tower", "BASS-II"],
            "sample_description": [
                "Dimensions: 40.0cm x 10.0cm x 1.0cm (Flow: Concurrent)",
                "Dimensions: Nonecm x Nonecm x Nonecm (Flow: nan)",
                "Ethanol Droplet",
                "100 micron PMMA film",
            ],
            "notes": [
                "ordinary note",
                "ordinary note",
                "Microgravity duration: 3.87 s.",
                "PI: Bhattacharjee. Sample #147.",
            ],
        }
    )

    enriched, stats = extract_text_facts(frame)

    lengths = enriched["specimen_length_cm"].tolist()
    assert lengths[0] == 40.0
    assert pd.isna(lengths[1])
    assert enriched["specimen_width_cm"].tolist()[0] == 10.0
    assert enriched["specimen_thickness_cm"].tolist()[0] == 1.0
    flows = enriched["flow_direction"].tolist()
    assert flows[0] == "Concurrent"
    assert pd.isna(flows[1])
    assert enriched["microgravity_duration_s"].tolist()[2] == pytest.approx(3.87)
    assert enriched["pi_name"].tolist()[3] == "Bhattacharjee"

    assert stats.specimen_dimensions.candidate_rows == 2
    assert stats.specimen_dimensions.matched_rows == 1
    assert stats.specimen_dimensions.documented_exceptions
    assert stats.specimen_dimensions.verified
    assert stats.flow_direction.candidate_rows == 2
    assert stats.flow_direction.matched_rows == 1
    assert stats.flow_direction.verified
    assert stats.microgravity_duration.candidate_rows == 1
    assert stats.microgravity_duration.matched_rows == 1
    assert stats.pi_name.matched_rows == 1


def test_unverified_pattern_fails_the_build() -> None:
    frame = pd.DataFrame(
        {
            "experiment_id": ["grc"],
            "dataset_family": ["GRC Drop Tower"],
            "sample_description": ["Ethanol Droplet"],
            "notes": ["Microgravity duration: unknown s."],
        }
    )

    _, stats = extract_text_facts(frame)

    assert not stats.microgravity_duration.verified
    with pytest.raises(PipelineError, match="failed verification"):
        require_verified_patterns(stats)


def test_finalize_flags_sorts_and_counts() -> None:
    frame = pd.DataFrame(
        {
            "experiment_id": ["a", "b", "c"],
            "_flags": [["B", "A"], [], ["A"]],
        }
    )

    finalized, counts = finalize_quality_flags(frame)

    assert "_flags" not in finalized.columns
    assert finalized["data_quality_flags"].tolist() == [["A", "B"], [], ["A"]]
    assert counts == {"A": 2, "B": 1}


def test_finalize_flags_without_internal_column() -> None:
    finalized, counts = finalize_quality_flags(pd.DataFrame({"experiment_id": ["a"]}))

    assert finalized["data_quality_flags"].tolist() == [[]]
    assert counts == {}
