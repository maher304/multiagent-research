"""Entry point: ``python -m analysis`` from ``reports/dataset_report``.

Runs the full reproducible analysis over the two raw datasets and writes:
  * analysis_results/*.csv and analysis_results/summary.json
  * figures/*.png

Raw datasets are read-only.
"""

from __future__ import annotations

import json

import pandas as pd

from . import compare, config, figures, olist, online_retail


def _dimensions(olist_tables: dict, retail_sheets: dict) -> tuple[pd.DataFrame, dict, dict]:
    rows = []
    total_rows = total_cols = 0
    for fname, df in olist_tables.items():
        rows.append(
            {
                "dataset": "Olist",
                "table": fname,
                "n_rows": int(len(df)),
                "n_cols": int(df.shape[1]),
            }
        )
        total_rows += len(df)
        total_cols += df.shape[1]
    ol_dim = {"total_rows": int(total_rows), "total_cols": int(total_cols), "n_tables": len(olist_tables)}
    rt_rows = rt_cols = 0
    for name, df in retail_sheets.items():
        rows.append(
            {
                "dataset": "OnlineRetailII",
                "table": f"online_retail_II.xlsx[{name}]",
                "n_rows": int(len(df)),
                "n_cols": int(df.shape[1]),
            }
        )
        rt_rows += len(df)
        rt_cols += df.shape[1]
    rt_dim = {"total_rows": int(rt_rows), "total_cols": int(rt_cols), "n_sheets": len(retail_sheets)}
    return pd.DataFrame(rows), ol_dim, rt_dim


def main() -> None:
    config.ensure_dirs()
    print("Loading Olist tables ...")
    olist_tables, olist_raw_dups = olist.load_tables()
    print("Analysing Olist ...")
    ol = olist.run(olist_tables, olist_raw_dups)

    print("Loading Online Retail II workbook (this can take about a minute) ...")
    retail_sheets = online_retail.load_sheets()
    print("Analysing Online Retail II ...")
    rt = online_retail.run(retail_sheets)

    dims, ol_dim, rt_dim = _dimensions(olist_tables, retail_sheets)

    # ---- write machine-readable outputs ----
    config.write_csv(dims, "table_dimensions.csv")
    config.write_csv(compare.dataset_inventory(), "dataset_inventory.csv")
    config.write_csv(ol["frames"]["schema_validation"], "olist_schema_validation.csv")
    config.write_csv(ol["frames"]["column_profile"], "olist_column_profile.csv")
    config.write_csv(ol["frames"]["duplicate_rows"], "olist_duplicate_rows.csv")
    config.write_csv(ol["frames"]["numeric_stats"], "olist_numeric_stats.csv")
    config.write_csv(ol["frames"]["categorical_stats"], "olist_categorical_stats.csv")
    config.write_csv(ol["frames"]["temporal_profile"], "olist_temporal_profile.csv")
    config.write_csv(ol["frames"]["primary_key_checks"], "olist_primary_key_checks.csv")
    config.write_csv(ol["frames"]["referential_integrity"], "olist_referential_integrity.csv")
    config.write_csv(ol["frames"]["join_cardinality"], "olist_join_cardinality.csv")
    config.write_csv(ol["frames"]["join_expansion"], "olist_join_expansion.csv")
    config.write_csv(ol["frames"]["value_counts"], "olist_value_counts.csv")
    config.write_csv(ol["frames"]["category_revenue"], "olist_category_revenue.csv")
    config.write_csv(ol["frames"]["monthly_orders"], "olist_monthly_orders.csv")

    config.write_csv(rt["frames"]["column_profile"], "retail_column_profile.csv")
    config.write_csv(rt["frames"]["numeric_stats"], "retail_numeric_stats.csv")
    config.write_csv(rt["frames"]["categorical_stats"], "retail_categorical_stats.csv")
    config.write_csv(rt["frames"]["temporal_profile"], "retail_temporal_profile.csv")
    config.write_csv(rt["frames"]["quality_metrics"], "retail_quality_metrics.csv")
    retail_dups = rt["frames"]["quality_metrics"][
        ["dataset", "sheet", "n_rows", "n_exact_duplicate_rows_raw",
         "n_exact_duplicate_rows_cleaned", "n_repeated_line_keys_cleaned"]
    ]
    config.write_csv(retail_dups, "retail_duplicate_rows.csv")
    config.write_csv(rt["frames"]["value_counts"], "retail_value_counts.csv")
    config.write_csv(rt["frames"]["admin_stock_codes"], "retail_admin_stock_codes.csv")
    config.write_csv(rt["frames"]["monthly_activity"], "retail_monthly_activity.csv")

    config.write_csv(compare.dataset_comparison(ol["facts"], rt["facts"], ol_dim, rt_dim), "dataset_comparison.csv")
    config.write_csv(compare.agent_suitability(), "agent_suitability.csv")

    # ---- figures ----
    print("Generating figures ...")
    fig_paths = []
    fig_paths += figures.olist_figures(ol["frames"])
    fig_paths += figures.retail_figures(rt["frames"])
    fig_paths.append(figures.comparison_figure(ol["frames"], rt["frames"]))

    # ---- summary ----
    summary = {
        "olist": ol["facts"],
        "online_retail_ii": rt["facts"],
        "dimensions": {
            "olist": ol_dim,
            "online_retail_ii": rt_dim,
        },
        "figures": [p.replace("\\", "/") for p in fig_paths],
    }
    config.write_json(summary, "summary.json")

    print(json.dumps(summary, indent=2, default=str)[:4000])
    print("\nDone. Results in", config.RESULTS_DIR)
    print("Figures in", config.FIGURES_DIR)


if __name__ == "__main__":
    main()
