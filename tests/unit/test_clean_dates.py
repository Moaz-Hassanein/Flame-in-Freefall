"""Unit tests for date parsing and date-normalisation flags."""

from __future__ import annotations

import pandas as pd
import pytest

from flame.ingestion.clean import (
    FLAG_TEST_DATE_CAMPAIGN_RANGE,
    FLAG_TEST_DATE_MISSING,
    FLAG_TEST_DATE_UNPARSEABLE,
    clean_test_dates,
    parse_test_date,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2021-06-25", "2021-06-25"),
        ("2/19/2014", "2014-02-19"),
        ("12/1/2009", "2009-12-01"),
        ("10/24/09", "2009-10-24"),
        ("1/5/11", "2011-01-05"),
    ],
)
def test_supported_formats_become_iso(raw: str, expected: str) -> None:
    assert parse_test_date(raw) == (expected, ())


def test_two_digit_year_pivot_is_explicit() -> None:
    assert parse_test_date("1/1/68")[0] == "2068-01-01"
    assert parse_test_date("1/1/69")[0] == "1969-01-01"
    assert parse_test_date("1/1/70")[0] == "1970-01-01"
    assert parse_test_date("1/1/99")[0] == "1999-01-01"


def test_campaign_range_is_null_with_flag() -> None:
    assert parse_test_date("2017-2024") == (None, (FLAG_TEST_DATE_CAMPAIGN_RANGE,))


@pytest.mark.parametrize("value", [None, float("nan"), "", "   "])
def test_missing_dates_are_flagged(value: object) -> None:
    assert parse_test_date(value) == (None, (FLAG_TEST_DATE_MISSING,))


@pytest.mark.parametrize("value", ["not-a-date", "2021-13-01", "13/40/2020", 20210101])
def test_unparseable_dates_are_flagged(value: object) -> None:
    assert parse_test_date(value) == (None, (FLAG_TEST_DATE_UNPARSEABLE,))


def test_clean_test_dates_preserves_raw_and_counts() -> None:
    frame = pd.DataFrame(
        {
            "experiment_id": ["a", "b", "c", "d", "e"],
            "test_date": ["2021-06-25", "2/19/2014", "10/24/09", "2017-2024", None],
        }
    )

    cleaned, stats = clean_test_dates(frame)

    assert cleaned["test_date"].tolist()[:4] == [
        "2021-06-25",
        "2014-02-19",
        "2009-10-24",
        "2017-2024",
    ]
    assert cleaned["test_date"].isna().sum() == 2
    assert cleaned["test_date_raw"].tolist() == frame["test_date"].tolist()
    assert stats.total == 5
    assert stats.missing == 1
    assert stats.parsed == 3
    assert stats.converted == 2
    assert stats.campaign_ranges == {"2017-2024": 1}
    assert cleaned["_flags"].tolist() == [
        [],
        [],
        [],
        [FLAG_TEST_DATE_CAMPAIGN_RANGE],
        [FLAG_TEST_DATE_MISSING],
    ]
