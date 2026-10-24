"""Unit tests for the dataset analysis package.

Run from ``reports/dataset_report``:

    python -m pytest tests -q

These tests use small in-memory frames only; they never read or modify the raw
datasets and they assert the *definitions* of the derived metrics.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analysis import olist, online_retail
from analysis.profiling import exact_duplicates, key_check, numeric_stats, temporal_profile


# ---------------------------------------------------------------------------
# Missing-value handling
# ---------------------------------------------------------------------------
def test_clean_code_preserves_missing_values():
    s = pd.Series([85123.0, "85123A", None, np.nan, "C489449", "  "])
    out = online_retail._clean_code(s)
    assert out.iloc[0] == "85123"
    assert out.iloc[1] == "85123A"
    assert pd.isna(out.iloc[2]) and pd.isna(out.iloc[3]) and pd.isna(out.iloc[5])
    assert out.iloc[4] == "C489449"
    assert not (out.astype("string").fillna("").str.lower() == "nan").any()


def test_strip_nullable_preserves_na():
    s = pd.Series(["  hello ", None, "world"])
    out = online_retail._strip_nullable(s)
    assert out.iloc[0] == "hello"
    assert pd.isna(out.iloc[1])
    assert out.iloc[2] == "world"


# ---------------------------------------------------------------------------
# Duplicates: raw vs cleaned
# ---------------------------------------------------------------------------
def test_exact_duplicates_counts():
    df = pd.DataFrame({"a": [1, 1, 2, 2, 2], "b": ["x", "x", "y", "y", "z"]})
    d = exact_duplicates(df)
    assert d["n_rows"] == 5
    assert d["n_exact_duplicate_rows"] == 2  # second (1,"x") and second (2,"y")
    assert d["exact_duplicate_pct"] == pytest.approx(40.0)


# ---------------------------------------------------------------------------
# Key checks / referential integrity
# ---------------------------------------------------------------------------
def test_key_check_composite_unique():
    df = pd.DataFrame({"order_id": ["a", "a", "b"], "item": [1, 2, 1]})
    res = key_check(df, "ds", "t", ["order_id", "item"], "order_id+item")
    assert res["is_unique_among_keyed_rows"] is True
    assert res["duplicate_excess_rows"] == 0


def test_key_check_detects_duplicates_and_missing_components():
    df = pd.DataFrame({"k": ["a", "a", "b", None]})
    res = key_check(df, "ds", "t", ["k"], "k")
    assert res["n_rows_with_missing_key_component"] == 1
    assert res["duplicate_excess_rows"] == 1
    assert res["is_unique_among_keyed_rows"] is False


def test_referential_integrity_reports_orphans_both_directions():
    left = pd.DataFrame({"fk": ["a", "b", "zzz", None]})
    right = pd.DataFrame({"pk": ["a", "b", "c"]})
    res = olist.referential_integrity(left, "fk", right, "pk", "left.fk->right.pk", "left", "right")
    assert res["left_rows_checked"] == 3
    assert res["left_orphan_rows"] == 1  # "zzz"
    assert res["right_rows_orphan"] == 1  # "c" has no children


# ---------------------------------------------------------------------------
# Numeric stats / signs
# ---------------------------------------------------------------------------
def test_numeric_stats_counts_signs():
    df = pd.DataFrame({"q": [-5, 0, 10, 20, 1000]})
    ns = numeric_stats(df, "ds", "t")
    row = ns[ns["column"] == "q"].iloc[0]
    assert row["n_negative"] == 1
    assert row["n_zero"] == 1
    assert row["min"] == -5
    assert row["max"] == 1000


# ---------------------------------------------------------------------------
# Temporal profiles
# ---------------------------------------------------------------------------
def test_temporal_profile_unique_columns():
    df = pd.DataFrame({"d1": pd.to_datetime(["2020-01-01", None, "2020-03-01"])})
    tp = temporal_profile(df, "ds", "t")
    assert list(tp["column"]) == ["d1"]
    assert tp.iloc[0]["n_missing"] == 1
    assert str(tp.iloc[0]["min_timestamp"]).startswith("2020-01-01")


# ---------------------------------------------------------------------------
# Online Retail II business signal definitions
# ---------------------------------------------------------------------------
def _retail_frame():
    return pd.DataFrame(
        {
            "Invoice": ["10001", "10001", "10002", "C10003", "A10004"],
            "StockCode": ["1", "2", "3", "1", "POST"],
            "Description": ["a", "b", "c", "a", "postage"],
            "Quantity": [-2, 5, 0, -3, 1],
            "InvoiceDate": pd.to_datetime(
                ["2010-12-01", "2010-12-01", "2010-12-02", "2010-12-03", "2010-12-03"]
            ),
            "Price": [1.0, 2.0, 5.0, 2.0, 18.0],
            "Customer ID": [100.0, 100.0, np.nan, 100.0, np.nan],
            "Country": ["UK", "UK", "UK", "UK", "UK"],
        }
    )


def test_cancellation_detection_and_negative_quantities():
    df = online_retail._clean(_retail_frame(), "synthetic")
    q = online_retail._sheet_quality("synthetic", df, n_raw_duplicates=0)
    assert q["n_cancellation_rows"] == 1  # C10003
    assert q["n_cancellation_invoices"] == 1
    assert q["n_negative_quantity_rows"] == 2  # -2 and -3
    assert q["n_negative_qty_non_cancellation"] == 1  # only the -2 line
    assert q["n_zero_quantity_rows"] == 1
    # A10004 is non-numeric and not a cancellation.
    assert q["n_non_numeric_non_cancel_invoice_rows"] == 1


def test_line_value_and_revenue_definitions():
    df = online_retail._clean(_retail_frame(), "synthetic")
    q = online_retail._sheet_quality("synthetic", df, n_raw_duplicates=0)
    # line values: -2, +10, 0, -6, +18  -> net = 20
    assert q["net_revenue"] == pytest.approx(20.0)
    assert q["gross_sales_positive"] == pytest.approx(28.0)
    assert q["all_negative_line_value"] == pytest.approx(-8.0)
    # cancellation invoice C10003 line value = -6
    assert q["cancellation_invoice_value"] == pytest.approx(-6.0)


def test_missing_customer_id_not_counted_as_string():
    df = online_retail._clean(_retail_frame(), "synthetic")
    q = online_retail._sheet_quality("synthetic", df, n_raw_duplicates=0)
    assert q["n_missing_customer_id"] == 2
    assert q["missing_customer_id_pct"] == pytest.approx(40.0)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------
def test_olist_schema_validation_flags_mismatch():
    good = pd.DataFrame(columns=olist.EXPECTED_COLUMNS["olist_sellers_dataset.csv"])
    bad = pd.DataFrame(columns=["seller_id", "wrong_col"])
    tables = {f: pd.DataFrame(columns=cols) for f, cols in olist.EXPECTED_COLUMNS.items()}
    tables["olist_sellers_dataset.csv"] = bad
    report = olist.validate_schema(tables)
    row = report[report["table"] == "olist_sellers_dataset.csv"].iloc[0]
    assert row["schema_ok"] is False or row["schema_ok"] == False  # noqa: E712
    assert "seller_zip_code_prefix" in row["missing_columns"]
    assert good is not None


def test_retail_clean_rejects_wrong_columns():
    df = pd.DataFrame({"Invoice": ["1"]})
    with pytest.raises(ValueError):
        online_retail._clean(df, "bad")
