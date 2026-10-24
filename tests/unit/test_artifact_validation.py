"""Unit tests for post-generation artifact validation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from governed_multiagent.validation import (
    ArtifactValidationError,
    validate_analysis_artifacts,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_RESULTS = REPO_ROOT / "reports" / "dataset_report" / "analysis_results"
REAL_FIGURES = REPO_ROOT / "reports" / "dataset_report" / "figures"


def _copy_artifacts(tmp_path: Path) -> tuple[Path, Path]:
    results = tmp_path / "analysis_results"
    figures = tmp_path / "figures"
    shutil.copytree(REAL_RESULTS, results)
    shutil.copytree(REAL_FIGURES, figures)
    return results, figures


def _messages(report) -> str:
    return "\n".join(str(issue) for issue in report.issues)


def test_real_artifacts_validate_cleanly():
    report = validate_analysis_artifacts(REAL_RESULTS, REAL_FIGURES)
    assert report.ok, report.format_lines()
    assert len(report.checked) == 40  # 26 CSV + summary.json + 13 figures


def test_missing_csv_is_reported(tmp_path):
    results, figures = _copy_artifacts(tmp_path)
    (results / "olist_monthly_orders.csv").unlink()
    report = validate_analysis_artifacts(results, figures)
    assert not report.ok
    assert "olist_monthly_orders.csv" in _messages(report)


def test_unparseable_csv_is_reported(tmp_path):
    results, figures = _copy_artifacts(tmp_path)
    (results / "olist_monthly_orders.csv").write_text("", encoding="utf-8")
    report = validate_analysis_artifacts(results, figures)
    assert not report.ok
    assert "could not be parsed" in _messages(report)


def test_wrong_columns_and_non_numeric_values_are_reported(tmp_path):
    results, figures = _copy_artifacts(tmp_path)
    (results / "olist_monthly_orders.csv").write_text(
        "month,wrong_column\n2017-01,not-a-number\n", encoding="utf-8"
    )
    report = validate_analysis_artifacts(results, figures)
    messages = _messages(report)
    assert "missing expected column(s): n_orders" in messages
    assert "unexpected extra column(s): wrong_column" in messages
    assert "cross-check skipped; missing column(s): n_orders" in messages


def test_corrupt_cross_check_artifact_does_not_crash_validation(tmp_path):
    results, figures = _copy_artifacts(tmp_path)
    (results / "olist_primary_key_checks.csv").write_text(
        "dataset,table\nOlist,orders\n", encoding="utf-8"
    )
    report = validate_analysis_artifacts(results, figures)
    assert not report.ok
    assert "cross-check skipped; missing column(s)" in _messages(report)


def test_non_numeric_cross_check_value_is_reported(tmp_path):
    results, figures = _copy_artifacts(tmp_path)
    (results / "olist_monthly_orders.csv").write_text(
        "month,n_orders\n2017-01,oops\n", encoding="utf-8"
    )
    report = validate_analysis_artifacts(results, figures)
    messages = _messages(report)
    assert "column 'n_orders' contains 1 non-numeric value(s)" in messages
    assert "cross-check could not be evaluated" in messages


def test_non_finite_numeric_value_is_reported(tmp_path):
    results, figures = _copy_artifacts(tmp_path)
    (results / "olist_monthly_orders.csv").write_text(
        "month,n_orders\n2017-01,inf\n", encoding="utf-8"
    )
    report = validate_analysis_artifacts(results, figures)
    assert "non-finite" in _messages(report)


def test_invalid_summary_json_is_reported(tmp_path):
    results, figures = _copy_artifacts(tmp_path)
    (results / "summary.json").write_text("{not json", encoding="utf-8")
    report = validate_analysis_artifacts(results, figures)
    assert "JSON could not be parsed" in _messages(report)


def test_summary_dimension_mismatch_is_reported(tmp_path):
    results, figures = _copy_artifacts(tmp_path)
    summary_path = results / "summary.json"
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    payload["dimensions"]["olist"]["total_rows"] += 1
    summary_path.write_text(json.dumps(payload), encoding="utf-8")
    report = validate_analysis_artifacts(results, figures)
    assert "does not match table_dimensions sum" in _messages(report)


def test_invalid_png_is_reported(tmp_path):
    results, figures = _copy_artifacts(tmp_path)
    (figures / "fig_olist_orders_monthly.png").write_bytes(b"not a png")
    report = validate_analysis_artifacts(results, figures)
    assert "not a valid PNG" in _messages(report)


def test_missing_figure_is_reported(tmp_path):
    results, figures = _copy_artifacts(tmp_path)
    (figures / "fig_olist_orders_monthly.png").unlink()
    report = validate_analysis_artifacts(results, figures)
    assert "required figure is missing" in _messages(report)


def test_raise_for_errors_raises_with_actionable_text(tmp_path):
    results, figures = _copy_artifacts(tmp_path)
    (results / "summary.json").unlink()
    report = validate_analysis_artifacts(results, figures)
    with pytest.raises(ArtifactValidationError) as excinfo:
        report.raise_for_errors()
    assert "summary.json" in str(excinfo.value)
