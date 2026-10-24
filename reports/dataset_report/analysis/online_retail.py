"""Online Retail II (UCI) analysis.

The workbook contains two worksheets (two accounting periods). Both are
profiled independently. Appending the two sheets into one frame is performed
only as a documented, *derived* step for the combined summary; the raw source
is never modified.

Missing-value handling: genuine blanks that pandas reads as ``NaN`` are kept as
missing (``pandas.NA``), never coerced into the strings ``"nan"``/``"None"``.
Cancellation, negative-quantity, zero/negative-price and adjustment lines are
reported as *business or data-quality signals*; they are not treated as fraud.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .profiling import (
    categorical_stats,
    column_profile,
    numeric_stats,
    temporal_profile,
    value_counts_table,
)

DATASET = "OnlineRetailII"
EXPECTED_COLS = ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"]


def load_sheets() -> dict[str, pd.DataFrame]:
    return pd.read_excel(config.RETAIL_XLSX, sheet_name=None, engine="openpyxl")


def _clean_code(series: pd.Series) -> pd.Series:
    """Normalise a mixed int/string code column while preserving real missing values.

    Excel stores some codes as floats (e.g. ``85123.0``) and others as strings
    (e.g. ``"85123A"`` or ``"C489449"``). Trailing ``.0`` is stripped for whole
    floats; blanks stay missing as ``pd.NA``.
    """

    def convert(value):
        if pd.isna(value):
            return pd.NA
        if isinstance(value, (float, int)) and float(value).is_integer():
            return str(int(value))
        text = str(value).strip()
        return text if text != "" else pd.NA

    return series.map(convert).astype("object")


def _strip_nullable(series: pd.Series) -> pd.Series:
    """Trim whitespace on string-like values while preserving missing values."""
    stripped = series.astype("string").str.strip()
    return stripped.where(series.notna(), pd.NA)


def _clean(df: pd.DataFrame, sheet: str) -> pd.DataFrame:
    if list(df.columns) != EXPECTED_COLS:
        raise ValueError(f"sheet '{sheet}' columns {list(df.columns)} != expected {EXPECTED_COLS}")
    out = df.copy()
    out["Invoice"] = _clean_code(out["Invoice"])
    out["StockCode"] = _clean_code(out["StockCode"])
    out["Description"] = _strip_nullable(out["Description"])
    out["Country"] = _strip_nullable(out["Country"])
    out["InvoiceDate"] = pd.to_datetime(out["InvoiceDate"], errors="coerce")
    out["Quantity"] = pd.to_numeric(out["Quantity"], errors="coerce")
    out["Price"] = pd.to_numeric(out["Price"], errors="coerce")
    out["Customer ID"] = pd.to_numeric(out["Customer ID"], errors="coerce")
    return out


def _invoice_kind(invoices: pd.Series) -> pd.Series:
    """'cancellation' when the invoice number starts with C (case-insensitive)."""
    return invoices.astype("string").str.upper().str.startswith("C").fillna(False)


def _sheet_quality(sheet: str, df: pd.DataFrame, n_raw_duplicates: int) -> dict:
    n = len(df)
    inv = df["Invoice"].astype("string")
    is_cancel = _invoice_kind(df["Invoice"])
    is_numeric_invoice = inv.str.match(r"^\d+$").fillna(False)
    non_numeric_non_cancel = int((~is_numeric_invoice & ~is_cancel).sum())
    qty = df["Quantity"]
    price = df["Price"]
    line_value = qty * price
    subset_cols = ["Invoice", "StockCode", "Quantity", "InvoiceDate", "Price"]
    dup_after_clean = int(df.duplicated(subset=subset_cols, keep="first").sum())
    cancellation_mask = is_cancel
    return {
        "dataset": DATASET,
        "sheet": sheet,
        "n_rows": n,
        "n_cols": df.shape[1],
        "n_distinct_invoice": int(df["Invoice"].nunique()),
        "n_cancellation_invoices": int(df.loc[cancellation_mask, "Invoice"].nunique()),
        "n_cancellation_rows": int(cancellation_mask.sum()),
        "n_non_numeric_non_cancel_invoice_rows": non_numeric_non_cancel,
        "n_distinct_stockcode": int(df["StockCode"].nunique()),
        "n_negative_quantity_rows": int((qty < 0).sum()),
        "n_zero_quantity_rows": int((qty == 0).sum()),
        "min_quantity": float(qty.min()) if qty.notna().any() else np.nan,
        "max_quantity": float(qty.max()) if qty.notna().any() else np.nan,
        "n_zero_price_rows": int((price == 0).sum()),
        "n_negative_price_rows": int((price < 0).sum()),
        "min_price": float(price.min()) if price.notna().any() else np.nan,
        "max_price": float(price.max()) if price.notna().any() else np.nan,
        "n_missing_customer_id": int(df["Customer ID"].isna().sum()),
        "missing_customer_id_pct": round(100.0 * df["Customer ID"].isna().sum() / n, 4) if n else np.nan,
        "n_distinct_customers": int(df["Customer ID"].nunique()),
        "n_distinct_country": int(df["Country"].nunique()),
        "n_missing_description": int(df["Description"].isna().sum()),
        "date_min": str(df["InvoiceDate"].min()),
        "date_max": str(df["InvoiceDate"].max()),
        "n_invalid_dates": int(df["InvoiceDate"].isna().sum()),
        "n_exact_duplicate_rows_raw": int(n_raw_duplicates),
        "n_exact_duplicate_rows_cleaned": int(df.duplicated(keep="first").sum()),
        "n_repeated_line_keys_cleaned": dup_after_clean,
        "gross_sales_positive": round(float(line_value[line_value > 0].sum()), 2),
        "all_negative_line_value": round(float(line_value[line_value < 0].sum()), 2),
        "cancellation_invoice_value": round(float(line_value[cancellation_mask].sum()), 2),
        "net_revenue": round(float(line_value.sum()), 2),
        "n_negative_qty_non_cancellation": int(((qty < 0) & (~cancellation_mask)).sum()),
        "n_cancellation_rows_positive_qty": int((cancellation_mask & (qty > 0)).sum()),
    }


def run(sheets: dict[str, pd.DataFrame]) -> dict:
    results: dict[str, pd.DataFrame] = {}
    facts: dict = {}
    cleaned: dict[str, pd.DataFrame] = {}
    col_profiles, num_stats, cat_stats, temp_profiles = [], [], [], []
    quality_rows = []

    for name, raw in sheets.items():
        raw_dup = int(raw.duplicated(keep="first").sum())
        df = _clean(raw, name)
        cleaned[name] = df
        col_profiles.append(column_profile(df, DATASET, "online_retail_II", name))
        ns = numeric_stats(df, DATASET, "online_retail_II", name)
        if not ns.empty:
            num_stats.append(ns)
        cs = categorical_stats(df, DATASET, "online_retail_II", name)
        if not cs.empty:
            cat_stats.append(cs)
        tp = temporal_profile(df, DATASET, "online_retail_II", name)
        if not tp.empty:
            temp_profiles.append(tp)
        quality_rows.append(_sheet_quality(name, df, raw_dup))

    results["column_profile"] = pd.concat(col_profiles, ignore_index=True)
    results["numeric_stats"] = pd.concat(num_stats, ignore_index=True)
    results["categorical_stats"] = pd.concat(cat_stats, ignore_index=True)
    results["temporal_profile"] = pd.concat(temp_profiles, ignore_index=True)
    results["quality_metrics"] = pd.DataFrame(quality_rows)

    vc = []
    for name, df in cleaned.items():
        vc.append(value_counts_table(df["Country"], DATASET, "online_retail_II", f"Country[{name}]").head(15))
        kind = pd.Series(np.where(_invoice_kind(df["Invoice"]), "cancellation(C)", "normal"), index=df.index)
        vc.append(value_counts_table(kind, DATASET, "online_retail_II", f"InvoiceKind[{name}]"))
    results["value_counts"] = pd.concat(vc, ignore_index=True)

    admin_codes = []
    for name, df in cleaned.items():
        nonnum = df.loc[~df["StockCode"].astype("string").str.match(r"^\d+$").fillna(False), "StockCode"]
        vc2 = nonnum.astype("string").value_counts().head(20).reset_index()
        vc2.columns = ["stock_code", "count"]
        vc2.insert(0, "sheet", name)
        admin_codes.append(vc2)
    results["admin_stock_codes"] = pd.concat(admin_codes, ignore_index=True)

    monthly_frames = []
    for name, df in cleaned.items():
        d = df.copy()
        d["month"] = d["InvoiceDate"].dt.to_period("M").astype(str)
        d["line_value"] = d["Quantity"] * d["Price"]
        d["is_cancellation"] = _invoice_kind(d["Invoice"])
        agg = d.groupby("month").agg(
            n_lines=("Invoice", "size"),
            n_invoices=("Invoice", "nunique"),
            n_customers=("Customer ID", "nunique"),
            n_cancellation_lines=("is_cancellation", "sum"),
            net_revenue=("line_value", "sum"),
        ).reset_index()
        agg.insert(0, "sheet", name)
        monthly_frames.append(agg)
    results["monthly_activity"] = pd.concat(monthly_frames, ignore_index=True)

    # Combined (derived) summary
    combined = pd.concat([df.assign(_sheet=n) for n, df in cleaned.items()], ignore_index=True)
    combined["line_value"] = combined["Quantity"] * combined["Price"]
    combined["is_cancellation"] = _invoice_kind(combined["Invoice"])
    set_a = set(cleaned[config.RETAIL_SHEETS[0]]["Customer ID"].dropna())
    set_b = set(cleaned[config.RETAIL_SHEETS[1]]["Customer ID"].dropna())
    facts["combined"] = {
        "n_rows_both_sheets": int(len(combined)),
        "n_distinct_invoice": int(combined["Invoice"].nunique()),
        "n_distinct_customers": int(combined["Customer ID"].nunique()),
        "n_missing_customer_id": int(combined["Customer ID"].isna().sum()),
        "missing_customer_id_pct": round(100.0 * combined["Customer ID"].isna().sum() / len(combined), 4),
        "n_distinct_stockcode": int(combined["StockCode"].nunique()),
        "n_distinct_country": int(combined["Country"].nunique()),
        "n_cancellation_invoices": int(combined.loc[combined["is_cancellation"], "Invoice"].nunique()),
        "n_cancellation_rows": int(combined["is_cancellation"].sum()),
        "net_revenue": round(float(combined["line_value"].sum()), 2),
        "gross_sales_positive": round(float(combined["line_value"][combined["line_value"] > 0].sum()), 2),
        "all_negative_line_value": round(float(combined["line_value"][combined["line_value"] < 0].sum()), 2),
        "date_min": str(combined["InvoiceDate"].min()),
        "date_max": str(combined["InvoiceDate"].max()),
        "n_customers_both_sheets": int(len(set_a & set_b)),
        "n_customers_only_sheet1": int(len(set_a - set_b)),
        "n_customers_only_sheet2": int(len(set_b - set_a)),
    }

    pos = combined[combined["line_value"] > 0]
    facts["value_distribution"] = {
        "n_positive_lines": int(len(pos)),
        "value_p50": round(float(pos["line_value"].quantile(0.5)), 4),
        "value_p95": round(float(pos["line_value"].quantile(0.95)), 4),
        "value_p99": round(float(pos["line_value"].quantile(0.99)), 4),
        "value_max": round(float(pos["line_value"].max()), 4),
    }

    results["_cleaned"] = cleaned  # type: ignore[assignment]
    results["_combined"] = combined  # type: ignore[assignment]
    return {"frames": results, "facts": facts}
