"""Regression tests for the Olist review-count parsing bug.

The inspector used to rely on ``csv.Sniffer`` including its inferred
``doublequote`` flag. On the Olist review file the sniffer inferred
``doublequote=False``, which misread doubled quotes inside quoted comments and
over-counted records. These tests reproduce that failure and verify the fix.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
import pytest

import inspect_datasets as inspector

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "olist_reviews_sample.csv"
REAL_REVIEWS = (
    Path(__file__).resolve().parents[2]
    / "datasets"
    / "olist"
    / "olist_order_reviews_dataset.csv"
)


def _read_with_doublequote(path: Path, doublequote: bool) -> list[list[str]]:
    dialect = inspector.ExplicitCsvDialect()
    dialect.delimiter = ","
    dialect.doublequote = doublequote
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle, dialect=dialect))


def test_fixed_parser_preserves_quoted_newlines_and_escaped_quotes():
    headers, rows, stats = inspector.read_csv_records(FIXTURE)
    assert len(headers) == 7
    assert stats["doublequote"] is True
    assert stats["delimiter"] == "','"
    assert stats["raw_records"] == 4
    assert stats["parsed_records"] == 4
    assert stats["rejected_records"] == 0
    assert rows[1]["review_comment_message"] == 'He said "excellent" and bought again'
    assert "first line\nsecond line" in rows[2]["review_comment_message"]


def test_old_doublequote_false_parsing_reproduces_the_bug():
    raw = _read_with_doublequote(FIXTURE, doublequote=False)
    fixed = _read_with_doublequote(FIXTURE, doublequote=True)

    assert len(raw) > len(fixed)
    header_width = len(fixed[0])
    assert any(len(row) != header_width for row in raw)


def test_malformed_records_are_reported_not_silently_skipped(tmp_path):
    path = tmp_path / "malformed.csv"
    path.write_text(
        "a,b,c\n"
        "1,2,3\n"
        "4,5\n"
        "6,7,8,9\n"
        "10,11,12\n",
        encoding="utf-8",
    )
    headers, rows, stats = inspector.read_csv_records(path)
    assert headers == ["a", "b", "c"]
    assert stats["raw_records"] == 4
    assert stats["parsed_records"] == 2
    assert stats["rejected_records"] == 2
    assert [item["observed_fields"] for item in stats["rejected_examples"]] == [2, 4]


@pytest.mark.skipif(not REAL_REVIEWS.is_file(), reason="real Olist review file is not available")
def test_real_olist_review_file_counts_match_pandas():
    headers, rows, stats = inspector.read_csv_records(REAL_REVIEWS)
    pandas_count = len(pd.read_csv(REAL_REVIEWS))

    assert len(headers) == 7
    assert stats["doublequote"] is True
    assert stats["rejected_records"] == 0
    assert stats["parsed_records"] == pandas_count
    assert stats["parsed_records"] == 99_224
    assert stats["raw_records"] == 99_224
    assert len(rows) == pandas_count
