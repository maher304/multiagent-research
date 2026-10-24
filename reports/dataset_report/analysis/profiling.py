"""Generic, dataset-agnostic profiling helpers.

Every metric produced here is descriptive and derived only from the local
source files. No values are imputed or invented; missing data are reported,
not replaced.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _is_datetime_like(series: pd.Series) -> bool:
    return pd.api.types.is_datetime64_any_dtype(series)


def column_profile(df: pd.DataFrame, dataset: str, table: str, sheet: str = "") -> pd.DataFrame:
    """Per-column completeness, cardinality and inferred type.

    dtype inference follows pandas' standard inference after ``read_csv`` /
    ``read_excel``; it is descriptive and may differ from a formal schema.
    """
    n = len(df)
    rows = []
    for col in df.columns:
        s = df[col]
        non_null = int(s.notna().sum())
        missing = int(n - non_null)
        try:
            n_unique = int(s.nunique(dropna=True))
        except TypeError:
            n_unique = int(s.astype(str).nunique(dropna=True))
        rows.append(
            {
                "dataset": dataset,
                "table": table,
                "sheet": sheet,
                "column": col,
                "pandas_dtype": str(s.dtype),
                "n_rows": n,
                "n_non_null": non_null,
                "n_missing": missing,
                "missing_pct": round(100.0 * missing / n, 4) if n else np.nan,
                "n_unique": n_unique,
                "unique_pct_of_present": round(100.0 * n_unique / non_null, 4) if non_null else np.nan,
            }
        )
    return pd.DataFrame(rows)


def exact_duplicates(df: pd.DataFrame) -> dict:
    dup_mask = df.duplicated(keep="first")
    n_dup = int(dup_mask.sum())
    return {
        "n_rows": int(len(df)),
        "n_exact_duplicate_rows": n_dup,
        "exact_duplicate_pct": round(100.0 * n_dup / len(df), 4) if len(df) else np.nan,
    }


def numeric_stats(df: pd.DataFrame, dataset: str, table: str, sheet: str = "") -> pd.DataFrame:
    rows = []
    for col in df.columns:
        s = df[col]
        if _is_datetime_like(s):
            continue
        if not pd.api.types.is_numeric_dtype(s):
            continue
        present = s.dropna()
        if present.empty:
            continue
        q1 = present.quantile(0.25)
        q3 = present.quantile(0.75)
        iqr = q3 - q1
        if iqr > 0:
            lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            outliers = int(((present < lo) | (present > hi)).sum())
        else:
            lo = hi = np.nan
            outliers = 0
        rows.append(
            {
                "dataset": dataset,
                "table": table,
                "sheet": sheet,
                "column": col,
                "count": int(present.shape[0]),
                "mean": round(float(present.mean()), 6),
                "std": round(float(present.std()), 6) if present.shape[0] > 1 else np.nan,
                "min": round(float(present.min()), 6),
                "q1": round(float(q1), 6),
                "median": round(float(present.median()), 6),
                "q3": round(float(q3), 6),
                "max": round(float(present.max()), 6),
                "n_zero": int((present == 0).sum()),
                "n_negative": int((present < 0).sum()),
                "iqr_outliers_n": outliers,
                "iqr_lower_fence": round(float(lo), 6) if not np.isnan(lo) else np.nan,
                "iqr_upper_fence": round(float(hi), 6) if not np.isnan(hi) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def categorical_stats(
    df: pd.DataFrame,
    dataset: str,
    table: str,
    sheet: str = "",
    max_cardinality_for_tops: int = 50,
) -> pd.DataFrame:
    rows = []
    n = len(df)
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_numeric_dtype(s) or _is_datetime_like(s):
            continue
        present = s.dropna()
        if present.empty:
            continue
        # Normalise mixed types (e.g. object columns holding ints and strings).
        present = present.astype(str)
        counts = present.value_counts(dropna=True)
        n_unique = int(counts.shape[0])
        top1_val, top1_n = (counts.index[0], int(counts.iloc[0])) if n_unique else ("", 0)
        top2_val, top2_n = (counts.index[1], int(counts.iloc[1])) if n_unique > 1 else ("", 0)
        rows.append(
            {
                "dataset": dataset,
                "table": table,
                "sheet": sheet,
                "column": col,
                "n_present": int(present.shape[0]),
                "n_unique": n_unique,
                "top1_value": top1_val if n_unique else "",
                "top1_count": top1_n,
                "top1_pct": round(100.0 * top1_n / n, 4) if n else np.nan,
                "top2_value": top2_val if n_unique else "",
                "top2_count": top2_n,
                "top2_pct": round(100.0 * top2_n / n, 4) if n else np.nan,
                "low_cardinality": bool(n_unique <= max_cardinality_for_tops),
            }
        )
    return pd.DataFrame(rows)


def value_counts_table(series: pd.Series, dataset: str, table: str, column: str) -> pd.DataFrame:
    # Preserve missing values as an explicit "<missing>" category instead of
    # coercing them into the string "nan".
    normalised = series.astype("string").fillna("<missing>")
    counts = normalised.value_counts(dropna=False)
    total = int(counts.sum())
    out = pd.DataFrame(
        {
            "value": counts.index.astype(str),
            "count": counts.values.astype(int),
        }
    )
    out["pct"] = (100.0 * out["count"] / total).round(4)
    out.insert(0, "dataset", dataset)
    out.insert(1, "table", table)
    out.insert(2, "column", column)
    return out


def temporal_profile(df: pd.DataFrame, dataset: str, table: str, sheet: str = "") -> pd.DataFrame:
    rows = []
    for col in df.columns:
        s = df[col]
        if not _is_datetime_like(s):
            continue
        present = s.dropna()
        rows.append(
            {
                "dataset": dataset,
                "table": table,
                "sheet": sheet,
                "column": col,
                "n_non_null": int(present.shape[0]),
                "n_missing": int(s.isna().sum()),
                "min_timestamp": str(present.min()) if not present.empty else "",
                "max_timestamp": str(present.max()) if not present.empty else "",
                "span_days": round((present.max() - present.min()).total_seconds() / 86400.0, 3)
                if not present.empty
                else np.nan,
            }
        )
    return pd.DataFrame(rows)


def key_check(
    df: pd.DataFrame,
    dataset: str,
    table: str,
    key: list[str],
    label: str,
) -> dict:
    """Check whether ``key`` uniquely identifies rows in ``df``."""
    subset = df[key]
    n = len(df)
    n_missing_any = int(subset.isna().any(axis=1).sum())
    n_distinct = int(subset.dropna().drop_duplicates().shape[0])
    n_rows_keyed = int(subset.dropna().shape[0])
    # Number of rows beyond the first per duplicated key value.
    dup_excess = int(n_rows_keyed - n_distinct)
    return {
        "dataset": dataset,
        "table": table,
        "candidate_key": label,
        "key_columns": "+".join(key),
        "n_rows": n,
        "n_rows_with_missing_key_component": n_missing_any,
        "n_distinct_key_values": n_distinct,
        "duplicate_excess_rows": dup_excess,
        "is_unique_among_keyed_rows": bool(dup_excess == 0),
    }
