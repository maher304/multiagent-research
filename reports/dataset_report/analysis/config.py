"""Shared configuration and helpers for the dataset analysis package.

The package inspects the two raw datasets read-only and writes derived
artifacts (CSV/JSON summaries and figures) under ``reports/dataset_report``.
Raw data files are never modified.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
# config.py -> analysis/ -> dataset_report/ -> reports/ -> repository root
PACKAGE_DIR = Path(__file__).resolve().parent
REPORT_DIR = PACKAGE_DIR.parent
REPO_ROOT = REPORT_DIR.parent.parent

OLIST_DIR = REPO_ROOT / "datasets" / "olist"
RETAIL_XLSX = REPO_ROOT / "datasets" / "online_retail_ii" / "online_retail_II.xlsx"

RESULTS_DIR = REPORT_DIR / "analysis_results"
FIGURES_DIR = REPORT_DIR / "figures"

OLIST_FILES = [
    "olist_customers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
]

# Stable ordering used in report tables.
OLIST_TABLE_ORDER = {
    "olist_customers_dataset.csv": 1,
    "olist_orders_dataset.csv": 2,
    "olist_order_items_dataset.csv": 3,
    "olist_order_payments_dataset.csv": 4,
    "olist_order_reviews_dataset.csv": 5,
    "olist_products_dataset.csv": 6,
    "olist_sellers_dataset.csv": 7,
    "olist_geolocation_dataset.csv": 8,
    "product_category_name_translation.csv": 9,
}

RETAIL_SHEETS = ["Year 2009-2010", "Year 2010-2011"]


def ensure_dirs() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(df: pd.DataFrame, name: str, float_fmt: str = "%.6g") -> Path:
    """Write a DataFrame to ``analysis_results/<name>`` deterministically."""
    ensure_dirs()
    out = RESULTS_DIR / name
    df.to_csv(out, index=False, float_format=float_fmt)
    return out


def write_json(payload: dict, name: str) -> Path:
    ensure_dirs()
    out = RESULTS_DIR / name
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, default=str)
    return out


def round_pct(value: float) -> float:
    return round(float(value), 4)
