"""Artifact validation for the dataset-analysis pipeline.

The data pipeline writes 26 CSV files, ``summary.json`` and 13 PNG figures.
This module validates those outputs *after* generation. It deliberately does
not assume a single schema: each artifact has its own expected columns, numeric
columns, and consistency rules.

The validation is descriptive: it reports actionable errors and never rewrites
the artifacts or the source datasets.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Artifact-specific schemas
# ---------------------------------------------------------------------------
CSV_SCHEMAS: dict[str, tuple[str, ...]] = {
    "agent_suitability.csv": (
        "agent", "olist_evidence", "retail_evidence", "implementable_tasks",
        "example_questions", "metrics", "limitations",
    ),
    "dataset_comparison.csv": ("criterion", "olist", "online_retail_ii"),
    "dataset_inventory.csv": ("dataset", "file", "format", "sheet", "size_bytes", "sha256"),
    "olist_categorical_stats.csv": (
        "dataset", "table", "sheet", "column", "n_present", "n_unique", "top1_value",
        "top1_count", "top1_pct", "top2_value", "top2_count", "top2_pct", "low_cardinality",
    ),
    "olist_category_revenue.csv": ("product_category_name", "total_item_value", "dataset"),
    "olist_column_profile.csv": (
        "dataset", "table", "sheet", "column", "pandas_dtype", "n_rows", "n_non_null",
        "n_missing", "missing_pct", "n_unique", "unique_pct_of_present",
    ),
    "olist_duplicate_rows.csv": (
        "dataset", "table", "n_rows", "n_exact_duplicate_rows_raw",
        "n_exact_duplicate_rows", "exact_duplicate_pct",
    ),
    "olist_join_cardinality.csv": (
        "relationship", "cardinality", "parent_distinct", "child_rows",
        "max_children_per_parent", "mean_children_per_parent", "parents_with_zero_children",
    ),
    "olist_join_expansion.csv": (
        "join", "left_rows", "right_rows", "inner_join_rows", "row_inflation_factor",
    ),
    "olist_monthly_orders.csv": ("month", "n_orders"),
    "olist_numeric_stats.csv": (
        "dataset", "table", "sheet", "column", "count", "mean", "std", "min", "q1",
        "median", "q3", "max", "n_zero", "n_negative", "iqr_outliers_n",
        "iqr_lower_fence", "iqr_upper_fence",
    ),
    "olist_primary_key_checks.csv": (
        "dataset", "table", "candidate_key", "key_columns", "n_rows",
        "n_rows_with_missing_key_component", "n_distinct_key_values",
        "duplicate_excess_rows", "is_unique_among_keyed_rows",
    ),
    "olist_referential_integrity.csv": (
        "relation", "left_table", "right_table", "left_key", "right_key",
        "left_rows_checked", "left_rows_matched", "left_orphan_rows",
        "left_orphan_pct", "right_rows_orphan",
    ),
    "olist_schema_validation.csv": (
        "dataset", "table", "expected_columns", "actual_columns", "missing_columns",
        "unexpected_columns", "schema_ok",
    ),
    "olist_temporal_profile.csv": (
        "dataset", "table", "sheet", "column", "n_non_null", "n_missing",
        "min_timestamp", "max_timestamp", "span_days",
    ),
    "olist_value_counts.csv": ("dataset", "table", "column", "value", "count", "pct"),
    "retail_admin_stock_codes.csv": ("sheet", "stock_code", "count"),
    "retail_categorical_stats.csv": (
        "dataset", "table", "sheet", "column", "n_present", "n_unique", "top1_value",
        "top1_count", "top1_pct", "top2_value", "top2_count", "top2_pct", "low_cardinality",
    ),
    "retail_column_profile.csv": (
        "dataset", "table", "sheet", "column", "pandas_dtype", "n_rows", "n_non_null",
        "n_missing", "missing_pct", "n_unique", "unique_pct_of_present",
    ),
    "retail_duplicate_rows.csv": (
        "dataset", "sheet", "n_rows", "n_exact_duplicate_rows_raw",
        "n_exact_duplicate_rows_cleaned", "n_repeated_line_keys_cleaned",
    ),
    "retail_monthly_activity.csv": (
        "sheet", "month", "n_lines", "n_invoices", "n_customers",
        "n_cancellation_lines", "net_revenue",
    ),
    "retail_numeric_stats.csv": (
        "dataset", "table", "sheet", "column", "count", "mean", "std", "min", "q1",
        "median", "q3", "max", "n_zero", "n_negative", "iqr_outliers_n",
        "iqr_lower_fence", "iqr_upper_fence",
    ),
    "retail_quality_metrics.csv": (
        "dataset", "sheet", "n_rows", "n_cols", "n_distinct_invoice",
        "n_cancellation_invoices", "n_cancellation_rows",
        "n_non_numeric_non_cancel_invoice_rows", "n_distinct_stockcode",
        "n_negative_quantity_rows", "n_zero_quantity_rows", "min_quantity",
        "max_quantity", "n_zero_price_rows", "n_negative_price_rows", "min_price",
        "max_price", "n_missing_customer_id", "missing_customer_id_pct",
        "n_distinct_customers", "n_distinct_country", "n_missing_description",
        "date_min", "date_max", "n_invalid_dates", "n_exact_duplicate_rows_raw",
        "n_exact_duplicate_rows_cleaned", "n_repeated_line_keys_cleaned",
        "gross_sales_positive", "all_negative_line_value", "cancellation_invoice_value",
        "net_revenue", "n_negative_qty_non_cancellation", "n_cancellation_rows_positive_qty",
    ),
    "retail_temporal_profile.csv": (
        "dataset", "table", "sheet", "column", "n_non_null", "n_missing",
        "min_timestamp", "max_timestamp", "span_days",
    ),
    "retail_value_counts.csv": ("dataset", "table", "column", "value", "count", "pct"),
    "table_dimensions.csv": ("dataset", "table", "n_rows", "n_cols"),
}

NUMERIC_COLUMNS: dict[str, tuple[str, ...]] = {
    "agent_suitability.csv": (),
    "dataset_comparison.csv": (),
    "dataset_inventory.csv": ("size_bytes",),
    "olist_categorical_stats.csv": ("n_present", "n_unique", "top1_count", "top1_pct", "top2_count", "top2_pct"),
    "olist_category_revenue.csv": ("total_item_value",),
    "olist_column_profile.csv": (
        "n_rows", "n_non_null", "n_missing", "missing_pct", "n_unique", "unique_pct_of_present",
    ),
    "olist_duplicate_rows.csv": (
        "n_rows", "n_exact_duplicate_rows_raw", "n_exact_duplicate_rows", "exact_duplicate_pct",
    ),
    "olist_join_cardinality.csv": (
        "parent_distinct", "child_rows", "max_children_per_parent",
        "mean_children_per_parent", "parents_with_zero_children",
    ),
    "olist_join_expansion.csv": ("left_rows", "right_rows", "inner_join_rows", "row_inflation_factor"),
    "olist_monthly_orders.csv": ("n_orders",),
    "olist_numeric_stats.csv": (
        "count", "mean", "std", "min", "q1", "median", "q3", "max", "n_zero",
        "n_negative", "iqr_outliers_n", "iqr_lower_fence", "iqr_upper_fence",
    ),
    "olist_primary_key_checks.csv": (
        "n_rows", "n_rows_with_missing_key_component", "n_distinct_key_values", "duplicate_excess_rows",
    ),
    "olist_referential_integrity.csv": (
        "left_rows_checked", "left_rows_matched", "left_orphan_rows",
        "left_orphan_pct", "right_rows_orphan",
    ),
    "olist_schema_validation.csv": ("expected_columns", "actual_columns"),
    "olist_temporal_profile.csv": ("n_non_null", "n_missing", "span_days"),
    "olist_value_counts.csv": ("count", "pct"),
    "retail_admin_stock_codes.csv": ("count",),
    "retail_categorical_stats.csv": ("n_present", "n_unique", "top1_count", "top1_pct", "top2_count", "top2_pct"),
    "retail_column_profile.csv": (
        "n_rows", "n_non_null", "n_missing", "missing_pct", "n_unique", "unique_pct_of_present",
    ),
    "retail_duplicate_rows.csv": (
        "n_rows", "n_exact_duplicate_rows_raw", "n_exact_duplicate_rows_cleaned",
        "n_repeated_line_keys_cleaned",
    ),
    "retail_monthly_activity.csv": (
        "n_lines", "n_invoices", "n_customers", "n_cancellation_lines", "net_revenue",
    ),
    "retail_numeric_stats.csv": (
        "count", "mean", "std", "min", "q1", "median", "q3", "max", "n_zero",
        "n_negative", "iqr_outliers_n", "iqr_lower_fence", "iqr_upper_fence",
    ),
    "retail_quality_metrics.csv": (
        "n_rows", "n_cols", "n_distinct_invoice", "n_cancellation_invoices",
        "n_cancellation_rows", "n_non_numeric_non_cancel_invoice_rows",
        "n_distinct_stockcode", "n_negative_quantity_rows", "n_zero_quantity_rows",
        "min_quantity", "max_quantity", "n_zero_price_rows", "n_negative_price_rows",
        "min_price", "max_price", "n_missing_customer_id", "missing_customer_id_pct",
        "n_distinct_customers", "n_distinct_country", "n_missing_description",
        "n_invalid_dates", "n_exact_duplicate_rows_raw", "n_exact_duplicate_rows_cleaned",
        "n_repeated_line_keys_cleaned", "gross_sales_positive", "all_negative_line_value",
        "cancellation_invoice_value", "net_revenue", "n_negative_qty_non_cancellation",
        "n_cancellation_rows_positive_qty",
    ),
    "retail_temporal_profile.csv": ("n_non_null", "n_missing", "span_days"),
    "retail_value_counts.csv": ("count", "pct"),
    "table_dimensions.csv": ("n_rows", "n_cols"),
}

EXPECTED_FIGURES: tuple[str, ...] = (
    "fig_completeness_comparison.png",
    "fig_olist_category_revenue.png",
    "fig_olist_missingness.png",
    "fig_olist_orders_monthly.png",
    "fig_olist_order_status.png",
    "fig_olist_payment_types.png",
    "fig_olist_review_scores.png",
    "fig_retail_cancellation_rate.png",
    "fig_retail_monthly_lines.png",
    "fig_retail_net_revenue_monthly.png",
    "fig_retail_quality_signals.png",
    "fig_retail_top_countries.png",
    "fig_retail_value_distribution.png",
)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    artifact: str
    message: str
    severity: str = "error"

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.artifact}: {self.message}"


@dataclass
class ValidationReport:
    """Collection of validation issues produced by one validation run."""

    checked: list[str] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)

    def add(self, artifact: str, message: str, severity: str = "error") -> None:
        self.issues.append(ValidationIssue(artifact, message, severity))

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_for_errors(self) -> None:
        if self.errors:
            raise ArtifactValidationError(self.format_lines())

    def format_lines(self) -> str:
        lines = [f"Checked {len(self.checked)} artifacts; {len(self.errors)} error(s), {len(self.warnings)} warning(s)."]
        lines.extend(str(issue) for issue in self.issues)
        return "\n".join(lines)


class ArtifactValidationError(ValueError):
    """Raised when :meth:`ValidationReport.raise_for_errors` finds errors."""


def _as_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes"})


def _check_numeric_columns(
    report: ValidationReport, name: str, frame: pd.DataFrame, columns: Iterable[str]
) -> None:
    for column in columns:
        if column not in frame.columns:
            continue
        original = frame[column]
        converted = pd.to_numeric(original, errors="coerce")
        invalid = original.notna() & converted.isna()
        if invalid.any():
            report.add(name, f"column '{column}' contains {int(invalid.sum())} non-numeric value(s)")
        finite = converted.dropna().to_numpy(dtype=float)
        if finite.size and not np.isfinite(finite).all():
            report.add(name, f"column '{column}' contains non-finite numeric value(s)")


def _validate_csv(report: ValidationReport, name: str, path: Path, expected: tuple[str, ...]) -> pd.DataFrame | None:
    if not path.is_file():
        report.add(name, "required CSV artifact is missing")
        return None
    try:
        frame = pd.read_csv(path, low_memory=False)
    except Exception as exc:  # pandas raises several concrete parser errors
        report.add(name, f"CSV could not be parsed: {exc}")
        return None
    report.checked.append(name)
    missing = [column for column in expected if column not in frame.columns]
    if missing:
        report.add(name, f"missing expected column(s): {', '.join(missing)}")
    unexpected = [column for column in frame.columns if column not in expected]
    if unexpected:
        report.add(name, f"unexpected extra column(s): {', '.join(unexpected)}", severity="warning")
    if frame.empty:
        report.add(name, "artifact contains no data rows")
    _check_numeric_columns(report, name, frame, NUMERIC_COLUMNS.get(name, ()))
    return frame


def _validate_png(report: ValidationReport, name: str, path: Path) -> None:
    if not path.is_file():
        report.add(name, "required figure is missing")
        return
    try:
        data = path.read_bytes()
    except OSError as exc:
        report.add(name, f"figure could not be read: {exc}")
        return
    report.checked.append(name)
    signature = b"\x89PNG\r\n\x1a\n"
    if len(data) < 24 or not data.startswith(signature) or data[12:16] != b"IHDR":
        report.add(name, "file is not a valid PNG (bad signature or missing IHDR)")
        return
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if width <= 0 or height <= 0:
        report.add(name, f"PNG has invalid dimensions {width}x{height}")
    if len(data) < 64:
        report.add(name, "PNG is suspiciously small")


def _validate_summary(report: ValidationReport, summary_path: Path, results_dir: Path, figures_dir: Path) -> dict | None:
    name = "summary.json"
    if not summary_path.is_file():
        report.add(name, "required JSON artifact is missing")
        return None
    try:
        text = summary_path.read_text(encoding="utf-8")
        payload = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        report.add(name, f"JSON could not be parsed: {exc}")
        return None
    report.checked.append(name)
    if not isinstance(payload, dict):
        report.add(name, "top-level JSON value must be an object")
        return None

    for key in ("olist", "online_retail_ii", "dimensions", "figures"):
        if key not in payload:
            report.add(name, f"missing top-level key '{key}'")
    if not isinstance(payload.get("dimensions"), dict):
        report.add(name, "'dimensions' must be an object")
        return payload
    if not isinstance(payload.get("figures"), list) or not payload["figures"]:
        report.add(name, "'figures' must be a non-empty list")

    for key in ("olist", "online_retail_ii"):
        if key in payload and not isinstance(payload[key], dict):
            report.add(name, f"'{key}' must be an object")

    try:
        json.dumps(payload, allow_nan=False)
    except (TypeError, ValueError) as exc:
        report.add(name, f"JSON contains non-finite or non-serialisable values: {exc}")

    # Cross-check dimensions against table_dimensions.csv.
    dims_path = results_dir / "table_dimensions.csv"
    if dims_path.is_file():
        try:
            dims = pd.read_csv(dims_path)
            for summary_key, dataset_key in (("olist", "Olist"), ("online_retail_ii", "OnlineRetailII")):
                subset = dims[dims["dataset"] == dataset_key]
                if subset.empty:
                    report.add("table_dimensions.csv", f"no rows for dataset '{dataset_key}'")
                    continue
                declared = payload.get("dimensions", {}).get(summary_key)
                if not isinstance(declared, dict):
                    report.add(name, f"dimensions.{summary_key} must be an object")
                    continue
                expected_rows = int(subset["n_rows"].sum())
                if declared.get("total_rows") != expected_rows:
                    report.add(
                        name,
                        f"dimensions.{summary_key}.total_rows={declared.get('total_rows')} "
                        f"does not match table_dimensions sum {expected_rows}",
                    )
        except Exception as exc:
            report.add("table_dimensions.csv", f"could not cross-check dimensions: {exc}")

    # Figures: every listed path should resolve to a file in the figures directory.
    figures = payload.get("figures", [])
    if isinstance(figures, list):
        for entry in figures:
            if not isinstance(entry, str) or not entry:
                report.add(name, "figure entries must be non-empty strings")
                continue
            candidate = figures_dir / Path(entry).name
            if not candidate.is_file():
                report.add(name, f"figure listed in summary is missing: {Path(entry).name}")
    return payload


def _cross_checks(report: ValidationReport, frames: dict[str, pd.DataFrame]) -> None:
    def require(name: str, frame: pd.DataFrame, columns: tuple[str, ...]) -> bool:
        missing = [column for column in columns if column not in frame.columns]
        if missing:
            report.add(name, f"cross-check skipped; missing column(s): {', '.join(missing)}")
            return False
        return True

    schema = frames.get("olist_schema_validation.csv")
    if schema is not None and "schema_ok" in schema.columns:
        if not _as_bool(schema["schema_ok"]).all():
            bad = schema.loc[~_as_bool(schema["schema_ok"]), "table"].tolist()
            report.add("olist_schema_validation.csv", f"schema validation failed for: {', '.join(map(str, bad))}")

    keys = frames.get("olist_primary_key_checks.csv")
    if keys is not None and not keys.empty and require(
        "olist_primary_key_checks.csv",
        keys,
        ("n_rows", "n_distinct_key_values", "duplicate_excess_rows"),
    ):
        try:
            if (keys["duplicate_excess_rows"] > keys["n_rows"]).any():
                report.add("olist_primary_key_checks.csv", "duplicate_excess_rows exceeds n_rows")
            if (keys["n_distinct_key_values"] > keys["n_rows"]).any():
                report.add("olist_primary_key_checks.csv", "n_distinct_key_values exceeds n_rows")
            if "is_unique_among_keyed_rows" in keys.columns:
                unique = _as_bool(keys["is_unique_among_keyed_rows"])
                if (keys.loc[unique, "duplicate_excess_rows"] != 0).any():
                    report.add("olist_primary_key_checks.csv", "a key marked unique has duplicate excess rows")
        except (TypeError, ValueError) as exc:
            report.add("olist_primary_key_checks.csv", f"cross-check could not be evaluated: {exc}")

    refs = frames.get("olist_referential_integrity.csv")
    if refs is not None and not refs.empty and require(
        "olist_referential_integrity.csv",
        refs,
        ("left_rows_checked", "left_rows_matched", "left_orphan_rows"),
    ):
        try:
            mismatched = refs[(refs["left_rows_matched"] + refs["left_orphan_rows"]) != refs["left_rows_checked"]]
            if not mismatched.empty:
                report.add("olist_referential_integrity.csv", "matched + orphan rows do not equal checked rows")
        except (TypeError, ValueError) as exc:
            report.add("olist_referential_integrity.csv", f"cross-check could not be evaluated: {exc}")

    dups = frames.get("olist_duplicate_rows.csv")
    if dups is not None and not dups.empty and require(
        "olist_duplicate_rows.csv",
        dups,
        ("n_rows", "n_exact_duplicate_rows", "n_exact_duplicate_rows_raw"),
    ):
        try:
            if (dups["n_exact_duplicate_rows"] > dups["n_rows"]).any():
                report.add("olist_duplicate_rows.csv", "duplicate rows exceed total rows")
            if (dups["n_exact_duplicate_rows_raw"] > dups["n_rows"]).any():
                report.add("olist_duplicate_rows.csv", "raw duplicate rows exceed total rows")
        except (TypeError, ValueError) as exc:
            report.add("olist_duplicate_rows.csv", f"cross-check could not be evaluated: {exc}")

    retail = frames.get("retail_quality_metrics.csv")
    if retail is not None and not retail.empty and require(
        "retail_quality_metrics.csv",
        retail,
        ("gross_sales_positive", "all_negative_line_value", "net_revenue"),
    ):
        try:
            reconciled = retail["gross_sales_positive"] + retail["all_negative_line_value"]
            # Artifacts are written with float_format="%.6g"; allow the resulting
            # six-significant-digit rounding when reconciling the three amounts.
            if not np.allclose(
                reconciled.to_numpy(dtype=float),
                retail["net_revenue"].to_numpy(dtype=float),
                rtol=1e-4,
                atol=0.5,
            ):
                report.add("retail_quality_metrics.csv", "gross_sales_positive + all_negative_line_value != net_revenue")
        except (TypeError, ValueError) as exc:
            report.add("retail_quality_metrics.csv", f"cross-check could not be evaluated: {exc}")

    monthly = frames.get("olist_monthly_orders.csv")
    if monthly is not None and not monthly.empty and require(
        "olist_monthly_orders.csv", monthly, ("n_orders",)
    ):
        try:
            if (monthly["n_orders"] < 0).any():
                report.add("olist_monthly_orders.csv", "n_orders contains negative values")
        except (TypeError, ValueError) as exc:
            report.add("olist_monthly_orders.csv", f"cross-check could not be evaluated: {exc}")


def validate_analysis_artifacts(results_dir: str | Path, figures_dir: str | Path | None = None) -> ValidationReport:
    """Validate the complete dataset-analysis output set.

    ``figures_dir`` defaults to ``<results_dir>/../figures``.
    """

    results = Path(results_dir)
    figures = Path(figures_dir) if figures_dir is not None else results.parent / "figures"
    report = ValidationReport()

    if not results.is_dir():
        report.add("analysis_results", f"results directory does not exist: {results}")
        return report
    if not figures.is_dir():
        report.add("figures", f"figures directory does not exist: {figures}")

    frames: dict[str, pd.DataFrame] = {}
    for name, expected in CSV_SCHEMAS.items():
        frame = _validate_csv(report, name, results / name, expected)
        if frame is not None:
            frames[name] = frame
    _cross_checks(report, frames)

    _validate_summary(report, results / "summary.json", results, figures)

    for figure in EXPECTED_FIGURES:
        _validate_png(report, figure, figures / figure)

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the dataset-analysis artifacts.")
    parser.add_argument(
        "--results",
        default=str(Path("reports") / "dataset_report" / "analysis_results"),
        help="directory containing the CSV/JSON artifacts",
    )
    parser.add_argument(
        "--figures",
        default=None,
        help="directory containing the PNG figures (default: <results>/../figures)",
    )
    args = parser.parse_args(argv)
    report = validate_analysis_artifacts(args.results, args.figures)
    print(report.format_lines())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
