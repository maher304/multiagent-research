"""Olist Brazilian E-Commerce dataset analysis.

Design decisions (see report Section 6-8):

* ``load_tables`` records exact-duplicate counts on the *raw* values as read
  from disk, then parses the known timestamp columns. This keeps
  "original-data duplicates" and "parsed duplicates" distinguishable.
* Timestamp columns are listed once in ``DATE_COLUMNS`` and parsed in a single
  place; the generic profile loop therefore emits each temporal profile
  exactly once (no duplication).
* ``referential_integrity`` is a pure, module-level function so it can be
  unit-tested independently of the datasets.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .profiling import (
    categorical_stats,
    column_profile,
    exact_duplicates,
    key_check,
    numeric_stats,
    temporal_profile,
    value_counts_table,
)

DATASET = "Olist"

# Expected columns per file, used for schema validation (review requirement 1).
EXPECTED_COLUMNS: dict[str, list[str]] = {
    "olist_customers_dataset.csv": [
        "customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city", "customer_state",
    ],
    "olist_geolocation_dataset.csv": [
        "geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng", "geolocation_city", "geolocation_state",
    ],
    "olist_orders_dataset.csv": [
        "order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_approved_at",
        "order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date",
    ],
    "olist_order_items_dataset.csv": [
        "order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price", "freight_value",
    ],
    "olist_order_payments_dataset.csv": [
        "order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value",
    ],
    "olist_order_reviews_dataset.csv": [
        "review_id", "order_id", "review_score", "review_comment_title", "review_comment_message",
        "review_creation_date", "review_answer_timestamp",
    ],
    "olist_products_dataset.csv": [
        "product_id", "product_category_name", "product_name_lenght", "product_description_lenght",
        "product_photos_qty", "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm",
    ],
    "olist_sellers_dataset.csv": ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"],
    "product_category_name_translation.csv": ["product_category_name", "product_category_name_english"],
}

DATE_COLUMNS: dict[str, list[str]] = {
    "olist_orders_dataset.csv": [
        "order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
        "order_delivered_customer_date", "order_estimated_delivery_date",
    ],
    "olist_order_reviews_dataset.csv": ["review_creation_date", "review_answer_timestamp"],
    "olist_order_items_dataset.csv": ["shipping_limit_date"],
}


def load_tables() -> tuple[dict[str, pd.DataFrame], dict[str, int]]:
    """Read all Olist CSVs read-only.

    Returns the parsed tables and a mapping file -> exact duplicate row count
    *before* timestamp parsing (original-data duplicates).
    """
    tables: dict[str, pd.DataFrame] = {}
    raw_duplicates: dict[str, int] = {}
    for fname in config.OLIST_FILES:
        df = pd.read_csv(config.OLIST_DIR / fname, low_memory=False)
        raw_duplicates[fname] = int(df.duplicated(keep="first").sum())
        for col in DATE_COLUMNS.get(fname, []):
            before = df[col].copy()
            df[col] = pd.to_datetime(df[col], errors="coerce")
            # Parsing must not silently create NaT that were not missing before
            # for non-empty source strings.
            newly_missing = int((before.notna() & df[col].isna()).sum())
            if newly_missing:
                raise ValueError(f"{fname}:{col}: {newly_missing} values failed timestamp parsing")
        tables[fname] = df
    return tables, raw_duplicates


def validate_schema(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for fname, expected in EXPECTED_COLUMNS.items():
        actual = list(tables.get(fname, pd.DataFrame()).columns)
        rows.append(
            {
                "dataset": DATASET,
                "table": fname,
                "expected_columns": len(expected),
                "actual_columns": len(actual),
                "missing_columns": ";".join([c for c in expected if c not in actual]),
                "unexpected_columns": ";".join([c for c in actual if c not in expected]),
                "schema_ok": set(expected) == set(actual),
            }
        )
    return pd.DataFrame(rows)


def referential_integrity(
    left_df: pd.DataFrame,
    lcol: str,
    right_df: pd.DataFrame,
    rcol: str,
    relation: str,
    left_name: str,
    right_name: str,
) -> dict:
    """Distinct-value containment check for an FK relationship.

    ``left_orphan_rows`` = rows in the left table whose key value is absent
    from the referenced right-table key set. ``right_rows_orphan`` = right rows
    whose key is absent from the left key set (e.g. parents with no children).
    """
    left_vals = left_df[lcol].dropna()
    right_set = set(right_df[rcol].dropna().unique())
    n_left = int(left_vals.shape[0])
    n_orphan_rows = int((~left_vals.isin(right_set)).sum())
    left_set = set(left_vals.unique())
    right_vals = right_df[rcol].dropna()
    n_right_orphan = int((~right_vals.isin(left_set)).sum())
    return {
        "relation": relation,
        "left_table": left_name,
        "right_table": right_name,
        "left_key": lcol,
        "right_key": rcol,
        "left_rows_checked": n_left,
        "left_rows_matched": n_left - n_orphan_rows,
        "left_orphan_rows": n_orphan_rows,
        "left_orphan_pct": round(100.0 * n_orphan_rows / n_left, 4) if n_left else np.nan,
        "right_rows_orphan": n_right_orphan,
    }


def _join_expansion(
    left: pd.DataFrame, right: pd.DataFrame, left_key: str, right_key: str, name: str
) -> dict:
    """Measure how many rows an inner join produces (duplication risk)."""
    merged = left[[left_key]].merge(right, left_on=left_key, right_on=right_key, how="inner")
    return {
        "join": name,
        "left_rows": int(len(left)),
        "right_rows": int(len(right)),
        "inner_join_rows": int(len(merged)),
        "row_inflation_factor": round(len(merged) / len(left), 4) if len(left) else np.nan,
    }


def run(tables: dict[str, pd.DataFrame], raw_duplicates: dict[str, int]) -> dict:
    results: dict[str, pd.DataFrame] = {}
    facts: dict = {}

    # ---------------- schema validation ----------------
    results["schema_validation"] = validate_schema(tables)

    # ---------------- generic profiles (single pass, no duplication) ----------------
    col_profiles, dups, num_stats, cat_stats, temp_profiles = [], [], [], [], []
    for fname, df in tables.items():
        short = fname.replace("olist_", "").replace("_dataset.csv", "").replace(".csv", "")
        col_profiles.append(column_profile(df, DATASET, short))
        d = exact_duplicates(df)
        d.update({"dataset": DATASET, "table": short, "n_exact_duplicate_rows_raw": raw_duplicates.get(fname, np.nan)})
        dups.append(d)
        ns = numeric_stats(df, DATASET, short)
        if not ns.empty:
            num_stats.append(ns)
        cs = categorical_stats(df, DATASET, short)
        if not cs.empty:
            cat_stats.append(cs)
        tp = temporal_profile(df, DATASET, short)
        if not tp.empty:
            temp_profiles.append(tp)

    results["column_profile"] = pd.concat(col_profiles, ignore_index=True)
    results["duplicate_rows"] = pd.DataFrame(dups)[
        ["dataset", "table", "n_rows", "n_exact_duplicate_rows_raw", "n_exact_duplicate_rows", "exact_duplicate_pct"]
    ]
    results["numeric_stats"] = pd.concat(num_stats, ignore_index=True) if num_stats else pd.DataFrame()
    results["categorical_stats"] = pd.concat(cat_stats, ignore_index=True) if cat_stats else pd.DataFrame()
    results["temporal_profile"] = pd.concat(temp_profiles, ignore_index=True) if temp_profiles else pd.DataFrame()

    orders = tables["olist_orders_dataset.csv"]
    reviews = tables["olist_order_reviews_dataset.csv"]
    items = tables["olist_order_items_dataset.csv"].copy()
    customers = tables["olist_customers_dataset.csv"]
    payments = tables["olist_order_payments_dataset.csv"]
    products = tables["olist_products_dataset.csv"]
    sellers = tables["olist_sellers_dataset.csv"]
    geoloc = tables["olist_geolocation_dataset.csv"]
    translation = tables["product_category_name_translation.csv"]

    # ---------------- key checks ----------------
    key_rows = [
        key_check(customers, DATASET, "customers", ["customer_id"], "customer_id"),
        key_check(customers, DATASET, "customers", ["customer_unique_id"], "customer_unique_id"),
        key_check(orders, DATASET, "orders", ["order_id"], "order_id"),
        key_check(items, DATASET, "order_items", ["order_id", "order_item_id"], "order_id+order_item_id"),
        key_check(payments, DATASET, "order_payments", ["order_id", "payment_sequential"], "order_id+payment_sequential"),
        key_check(reviews, DATASET, "order_reviews", ["review_id"], "review_id"),
        key_check(reviews, DATASET, "order_reviews", ["order_id"], "order_id"),
        key_check(products, DATASET, "products", ["product_id"], "product_id"),
        key_check(sellers, DATASET, "sellers", ["seller_id"], "seller_id"),
        key_check(translation, DATASET, "product_category_translation", ["product_category_name"], "product_category_name"),
        key_check(geoloc, DATASET, "geolocation", ["geolocation_zip_code_prefix"], "geolocation_zip_code_prefix"),
    ]
    results["primary_key_checks"] = pd.DataFrame(key_rows)

    # ---------------- referential integrity ----------------
    fk_rows = [
        referential_integrity(orders, "customer_id", customers, "customer_id",
                              "orders.customer_id -> customers.customer_id", "orders", "customers"),
        referential_integrity(items, "order_id", orders, "order_id",
                              "order_items.order_id -> orders.order_id", "order_items", "orders"),
        referential_integrity(items, "product_id", products, "product_id",
                              "order_items.product_id -> products.product_id", "order_items", "products"),
        referential_integrity(items, "seller_id", sellers, "seller_id",
                              "order_items.seller_id -> sellers.seller_id", "order_items", "sellers"),
        referential_integrity(payments, "order_id", orders, "order_id",
                              "order_payments.order_id -> orders.order_id", "order_payments", "orders"),
        referential_integrity(reviews, "order_id", orders, "order_id",
                              "order_reviews.order_id -> orders.order_id", "order_reviews", "orders"),
    ]
    results["referential_integrity"] = pd.DataFrame(fk_rows)

    # ---------------- join cardinality (of join keys) ----------------
    card_rows = []
    for name, child, parent, parent_key in [
        ("orders -> order_items", items, orders, "order_id"),
        ("orders -> order_payments", payments, orders, "order_id"),
        ("orders -> order_reviews", reviews, orders, "order_id"),
        ("products -> order_items", items, products, "product_id"),
        ("sellers -> order_items", items, sellers, "seller_id"),
    ]:
        counts = child.groupby(parent_key).size()
        parent_distinct = int(parent[parent_key].nunique())
        card_rows.append(
            {
                "relationship": name,
                "cardinality": "one-to-many",
                "parent_distinct": parent_distinct,
                "child_rows": int(len(child)),
                "max_children_per_parent": int(counts.max()) if len(counts) else 0,
                "mean_children_per_parent": round(float(counts.mean()), 4) if len(counts) else 0.0,
                "parents_with_zero_children": int(parent_distinct - counts.shape[0]),
            }
        )
    orders_per_customer = orders.groupby("customer_id").size()
    card_rows.append(
        {
            "relationship": "customers -> orders",
            "cardinality": "one-to-one on customer_id",
            "parent_distinct": int(customers["customer_id"].nunique()),
            "child_rows": int(len(orders)),
            "max_children_per_parent": int(orders_per_customer.max()),
            "mean_children_per_parent": round(float(orders_per_customer.mean()), 4),
            "parents_with_zero_children": int(customers["customer_id"].nunique() - orders_per_customer.shape[0]),
        }
    )
    results["join_cardinality"] = pd.DataFrame(card_rows)

    # ---------------- join row inflation (duplication on merge) ----------------
    inflation = [
        _join_expansion(orders, items[["order_id"]], "order_id", "order_id", "orders INNER JOIN order_items ON order_id"),
        _join_expansion(orders, payments[["order_id"]], "order_id", "order_id", "orders INNER JOIN order_payments ON order_id"),
        _join_expansion(orders, reviews[["order_id"]], "order_id", "order_id", "orders INNER JOIN order_reviews ON order_id"),
        _join_expansion(items, products[["product_id"]], "product_id", "product_id", "order_items INNER JOIN products ON product_id"),
        _join_expansion(items, sellers[["seller_id"]], "seller_id", "seller_id", "order_items INNER JOIN sellers ON seller_id"),
    ]
    results["join_expansion"] = pd.DataFrame(inflation)

    # ---------------- distributions ----------------
    vc_frames = [
        value_counts_table(orders["order_status"], DATASET, "orders", "order_status"),
        value_counts_table(payments["payment_type"], DATASET, "order_payments", "payment_type"),
        value_counts_table(reviews["review_score"], DATASET, "order_reviews", "review_score"),
        value_counts_table(customers["customer_state"], DATASET, "customers", "customer_state"),
        value_counts_table(sellers["seller_state"], DATASET, "sellers", "seller_state"),
        value_counts_table(products["product_category_name"].fillna("<missing>"), DATASET, "products", "product_category_name"),
    ]
    results["value_counts"] = pd.concat(vc_frames, ignore_index=True)

    # ---------------- temporal integrity ----------------
    facts["temporal_integrity"] = {
        "orders_approved_before_purchase": int((orders["order_approved_at"] < orders["order_purchase_timestamp"]).sum()),
        "orders_delivered_before_purchase": int((orders["order_delivered_customer_date"] < orders["order_purchase_timestamp"]).sum()),
        "orders_delivered_before_carrier": int((orders["order_delivered_customer_date"] < orders["order_delivered_carrier_date"]).sum()),
        "order_purchase_min": str(orders["order_purchase_timestamp"].min()),
        "order_purchase_max": str(orders["order_purchase_timestamp"].max()),
    }

    # ---------------- monetary summary ----------------
    # All values are in Brazilian Reais (BRL) as recorded in the source file.
    items["line_total"] = items["price"] + items["freight_value"]
    facts["monetary"] = {
        "items_total_price": round(float(items["price"].sum()), 2),
        "items_total_freight": round(float(items["freight_value"].sum()), 2),
        "items_total_value": round(float(items["line_total"].sum()), 2),
        "payments_total_value": round(float(payments["payment_value"].sum()), 2),
        "avg_payment_value": round(float(payments["payment_value"].mean()), 4),
        "n_negative_price_lines": int((items["price"] < 0).sum()),
        "n_zero_price_lines": int((items["price"] == 0).sum()),
        "n_negative_freight_lines": int((items["freight_value"] < 0).sum()),
    }

    # payment vs item reconciliation proxy (order level)
    pay_sum = payments.groupby("order_id")["payment_value"].sum()
    item_sum = items.groupby("order_id")["line_total"].sum()
    both = pd.concat([pay_sum.rename("pay"), item_sum.rename("items")], axis=1).dropna()
    diff = (both["pay"] - both["items"]).abs()
    facts["reconciliation_proxy"] = {
        "orders_with_both_payment_and_items": int(len(both)),
        "orders_match_within_1_cent": int((diff <= 0.01).sum()),
        "match_pct_within_1_cent": round(100.0 * (diff <= 0.01).sum() / len(both), 4) if len(both) else np.nan,
        "mean_abs_difference": round(float(diff.mean()), 4) if len(both) else np.nan,
    }

    # product category translation coverage
    prod_cat = products["product_category_name"].dropna()
    covered = int(prod_cat.isin(set(translation["product_category_name"])).sum())
    facts["category_coverage"] = {
        "products_with_category": int(prod_cat.shape[0]),
        "products_missing_category": int(products["product_category_name"].isna().sum()),
        "distinct_categories_in_products": int(prod_cat.nunique()),
        "categories_covered_by_translation": covered,
        "coverage_pct": round(100.0 * covered / prod_cat.shape[0], 4) if prod_cat.shape[0] else np.nan,
        "translation_rows": int(len(translation)),
    }

    repeat = customers["customer_unique_id"].value_counts()
    facts["customers"] = {
        "distinct_customer_id": int(customers["customer_id"].nunique()),
        "distinct_customer_unique_id": int(customers["customer_unique_id"].nunique()),
        "customer_unique_ids_with_multiple_rows": int((repeat > 1).sum()),
        "max_rows_per_customer_unique_id": int(repeat.max()),
    }

    geo_agg = geoloc.groupby("geolocation_zip_code_prefix").size()
    facts["geolocation"] = {
        "n_rows": int(len(geoloc)),
        "distinct_zip_prefix": int(geoloc["geolocation_zip_code_prefix"].nunique()),
        "max_rows_per_zip_prefix": int(geo_agg.max()),
        "mean_rows_per_zip_prefix": round(float(geo_agg.mean()), 4),
    }

    # ---------------- series for figures ----------------
    orders = orders.copy()
    orders["month"] = orders["order_purchase_timestamp"].dt.to_period("M").astype(str)
    results["monthly_orders"] = orders.groupby("month").size().reset_index(name="n_orders")

    results["review_score_distribution"] = value_counts_table(
        reviews["review_score"], DATASET, "order_reviews", "review_score"
    ).sort_values("value")

    items_cat = items.merge(products[["product_id", "product_category_name"]], on="product_id", how="left")
    cat_rev = items_cat.groupby("product_category_name")["line_total"].sum().sort_values(ascending=False)
    results["category_revenue"] = cat_rev.reset_index(name="total_item_value").head(20).assign(dataset=DATASET)

    results["_items"] = items
    results["_orders"] = orders
    results["_payments"] = payments
    results["_reviews"] = reviews
    results["_products"] = products
    results["_customers"] = customers

    facts["n_tables"] = len(tables)
    return {"frames": results, "facts": facts}
