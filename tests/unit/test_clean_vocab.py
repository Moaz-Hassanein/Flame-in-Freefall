"""Unit tests for explicit vocabulary normalisation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from flame.ingestion.clean import load_vocabulary_config, normalize_vocabulary


def _config() -> dict[str, object]:
    return {
        "version": 7,
        "extinction_outcome": {
            "mappings": {
                "Self-extinguished": {"to": "Self-Extinction", "reason": "case only"}
            }
        },
        "material_category": {"mappings": {}},
    }


def test_mapping_is_applied_and_original_is_preserved() -> None:
    frame = pd.DataFrame(
        {
            "extinction_outcome": ["Self-extinguished", "Extinction", None],
            "experiment_id": ["a", "b", "c"],
        }
    )

    cleaned, stats = normalize_vocabulary(
        frame, column="extinction_outcome", config=_config()
    )

    assert cleaned["extinction_outcome"].tolist() == ["Self-Extinction", "Extinction", None]
    assert cleaned["extinction_outcome_raw"].tolist() == [
        "Self-extinguished",
        "Extinction",
        None,
    ]
    assert stats.mapping_version == "7"
    assert stats.applied == (("Self-extinguished", "Self-Extinction", 1),)
    assert stats.identity == {"Extinction": 1}
    assert stats.total_non_null == 2
    assert stats.null_count == 1


def test_empty_mapping_is_identity_only() -> None:
    frame = pd.DataFrame({"material_category": ["Polymer", "Polymer"]})

    cleaned, stats = normalize_vocabulary(
        frame, column="material_category", config=_config()
    )

    assert cleaned["material_category"].tolist() == ["Polymer", "Polymer"]
    assert stats.applied == ()
    assert stats.identity == {"Polymer": 2}


def test_missing_section_raises() -> None:
    frame = pd.DataFrame({"unknown": ["x"]})

    with pytest.raises(ValueError, match="no section"):
        normalize_vocabulary(frame, column="unknown", config=_config())


def test_invalid_entry_raises() -> None:
    config = {"version": 1, "extinction_outcome": {"mappings": {"x": "not-a-mapping"}}}
    frame = pd.DataFrame({"extinction_outcome": ["x"]})

    with pytest.raises(ValueError, match="invalid mapping entry"):
        normalize_vocabulary(frame, column="extinction_outcome", config=config)


def test_load_config_requires_integer_version(tmp_path: Path) -> None:
    path = tmp_path / "vocab.yaml"
    path.write_text("version: nope\nextinction_outcome:\n  mappings: {}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="integer 'version'"):
        load_vocabulary_config(path)
