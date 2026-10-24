"""Figure generation from the analysed datasets.

All figures are produced from the real local datasets; no illustrative or
synthetic values are plotted.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from . import config

sns.set_theme(style="whitegrid", context="notebook")
PALETTE = sns.color_palette("deep")


def _save(fig, name: str) -> str:
    path = config.FIGURES_DIR / name
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return str(path)


def olist_figures(frames: dict) -> list[str]:
    produced = []
    orders = frames["_orders"]
    payments = frames["_payments"]
    reviews = frames["_reviews"]

    # 1. Monthly order volume
    monthly = frames["monthly_orders"]
    monthly = monthly[monthly["n_orders"] > 0]
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(pd.to_datetime(monthly["month"]), monthly["n_orders"], marker="o", ms=3, color=PALETTE[0])
    ax.set_title("Olist: orders by purchase month")
    ax.set_xlabel("Purchase month")
    ax.set_ylabel("Orders")
    fig.autofmt_xdate()
    produced.append(_save(fig, "fig_olist_orders_monthly.png"))

    # 2. Order status
    vc = orders["order_status"].value_counts()
    fig, ax = plt.subplots(figsize=(8, 3.6))
    sns.barplot(x=vc.values, y=vc.index, ax=ax, color=PALETTE[1])
    ax.set_title("Olist: order status distribution")
    ax.set_xlabel("Orders")
    ax.set_ylabel("")
    produced.append(_save(fig, "fig_olist_order_status.png"))

    # 3. Payment types
    vc = payments["payment_type"].value_counts()
    fig, ax = plt.subplots(figsize=(7, 3.4))
    sns.barplot(x=vc.index, y=vc.values, ax=ax, color=PALETTE[2])
    ax.set_title("Olist: payments by payment type")
    ax.set_xlabel("Payment records")
    ax.set_ylabel("")
    produced.append(_save(fig, "fig_olist_payment_types.png"))

    # 4. Review scores
    vc = reviews["review_score"].value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    sns.barplot(x=vc.index.astype(str), y=vc.values, ax=ax, color=PALETTE[3])
    ax.set_title("Olist: review score distribution")
    ax.set_xlabel("Review score")
    ax.set_ylabel("Reviews")
    produced.append(_save(fig, "fig_olist_review_scores.png"))

    # 5. Top categories by item value
    cat = frames["category_revenue"].dropna(subset=["product_category_name"]).head(15)
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(x=cat["total_item_value"], y=cat["product_category_name"], ax=ax, color=PALETTE[4])
    ax.set_title("Olist: top 15 categories by item value (price + freight)")
    ax.set_xlabel("Total item value (BRL)")
    ax.set_ylabel("")
    produced.append(_save(fig, "fig_olist_category_revenue.png"))

    # 6. Missingness across tables
    cp = frames["column_profile"]
    top_missing = cp[cp["missing_pct"] > 0].sort_values("missing_pct", ascending=False).head(20)
    fig, ax = plt.subplots(figsize=(9, 6))
    labels = top_missing["table"] + "." + top_missing["column"]
    sns.barplot(x=top_missing["missing_pct"], y=labels, ax=ax, color=PALETTE[5])
    ax.set_title("Olist: columns with missing values (top 20)")
    ax.set_xlabel("Missing values (%)")
    ax.set_ylabel("")
    produced.append(_save(fig, "fig_olist_missingness.png"))

    return produced


def retail_figures(frames: dict) -> list[str]:
    produced = []
    monthly = frames["monthly_activity"]
    cleaned = frames["_cleaned"]
    combined = frames["_combined"]

    # 1. Monthly transaction lines (both sheets as separate series)
    fig, ax = plt.subplots(figsize=(9, 3.6))
    for i, (sheet, grp) in enumerate(monthly.groupby("sheet")):
        grp = grp.sort_values("month")
        ax.plot(pd.to_datetime(grp["month"]), grp["n_lines"], marker="o", ms=3, label=sheet, color=PALETTE[i])
    ax.set_title("Online Retail II: transaction lines per month")
    ax.set_xlabel("Month")
    ax.set_ylabel("Transaction lines")
    ax.legend()
    fig.autofmt_xdate()
    produced.append(_save(fig, "fig_retail_monthly_lines.png"))

    # 2. Monthly net revenue
    fig, ax = plt.subplots(figsize=(9, 3.6))
    for i, (sheet, grp) in enumerate(monthly.groupby("sheet")):
        grp = grp.sort_values("month")
        ax.plot(pd.to_datetime(grp["month"]), grp["net_revenue"], marker="o", ms=3, label=sheet, color=PALETTE[i])
    ax.set_title("Online Retail II: net revenue per month")
    ax.set_xlabel("Month")
    ax.set_ylabel("Net revenue")
    ax.legend()
    fig.autofmt_xdate()
    produced.append(_save(fig, "fig_retail_net_revenue_monthly.png"))

    # 3. Top countries (combined)
    vc = combined["Country"].value_counts().head(10)
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.barplot(x=vc.values, y=vc.index, ax=ax, color=PALETTE[1])
    ax.set_title("Online Retail II: top 10 countries by transaction lines (both periods)")
    ax.set_xlabel("Transaction lines")
    ax.set_ylabel("")
    produced.append(_save(fig, "fig_retail_top_countries.png"))

    # 4. Line value distribution (positive lines, log scale)
    val = combined.loc[combined["line_value"] > 0, "line_value"].astype(float)
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.hist(np.log10(val), bins=60, color=PALETTE[2])
    ax.set_title("Online Retail II: distribution of log10 line value (positive lines)")
    ax.set_xlabel("log10(Quantity x Price)")
    ax.set_ylabel("Lines")
    produced.append(_save(fig, "fig_retail_value_distribution.png"))

    # 5. Data-quality signals per sheet
    q = frames["quality_metrics"]
    metrics = ["n_negative_quantity_rows", "n_cancellation_rows", "n_zero_price_rows", "n_missing_customer_id"]
    long = q.melt(id_vars="sheet", value_vars=metrics, var_name="metric", value_name="count")
    fig, ax = plt.subplots(figsize=(9, 4))
    sns.barplot(data=long, x="metric", y="count", hue="sheet", ax=ax)
    ax.set_title("Online Retail II: data-quality / business-process signals per period")
    ax.set_xlabel("")
    ax.set_ylabel("Rows")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    produced.append(_save(fig, "fig_retail_quality_signals.png"))

    # 6. Cancellation rate per month
    fig, ax = plt.subplots(figsize=(9, 3.6))
    canc = []
    for sheet, df in cleaned.items():
        d = df.copy()
        d["month"] = d["InvoiceDate"].dt.to_period("M").astype(str)
        d["is_cancel"] = d["Invoice"].astype(str).str.upper().str.startswith("C")
        g = d.groupby("month").agg(n=("is_cancel", "size"), c=("is_cancel", "sum")).reset_index()
        g["rate"] = 100.0 * g["c"] / g["n"]
        g["sheet"] = sheet
        canc.append(g)
    canc = pd.concat(canc, ignore_index=True)
    for i, (sheet, grp) in enumerate(canc.groupby("sheet")):
        grp = grp.sort_values("month")
        ax.plot(pd.to_datetime(grp["month"]), grp["rate"], marker="o", ms=3, label=sheet, color=PALETTE[i])
    ax.set_title("Online Retail II: cancellation-line rate per month")
    ax.set_xlabel("Month")
    ax.set_ylabel("Cancellation lines (%)")
    ax.legend()
    fig.autofmt_xdate()
    produced.append(_save(fig, "fig_retail_cancellation_rate.png"))

    return produced


def comparison_figure(olist_frames: dict, retail_frames: dict) -> str:
    """Side-by-side completeness of key columns across both datasets."""
    ol = olist_frames["column_profile"].copy()
    ol["label"] = ol["table"] + "." + ol["column"]
    ol = ol.sort_values("missing_pct", ascending=False).head(10)

    rt = retail_frames["column_profile"].copy()
    rt["label"] = rt["sheet"].str.replace("Year ", "", regex=False) + " | " + rt["column"].astype(str)
    rt = rt.sort_values("missing_pct", ascending=False).head(10)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    sns.barplot(x=ol["missing_pct"], y=ol["label"], ax=axes[0], color=PALETTE[0])
    axes[0].set_title("Olist: highest missing-value columns")
    axes[0].set_xlabel("Missing (%)")
    axes[0].set_ylabel("")
    sns.barplot(x=rt["missing_pct"], y=rt["label"], ax=axes[1], color=PALETTE[3])
    axes[1].set_title("Online Retail II: highest missing-value columns")
    axes[1].set_xlabel("Missing (%)")
    axes[1].set_ylabel("")
    return _save(fig, "fig_completeness_comparison.png")
