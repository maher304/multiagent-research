"""Assemble inventory, comparative and agent-suitability artifacts.

The qualitative columns (interpretation, recommendation) are manually curated
and clearly separated from measured columns in the report.
"""

from __future__ import annotations

import pandas as pd

from . import config


def dataset_inventory() -> pd.DataFrame:
    rows = []
    for fname in config.OLIST_FILES:
        path = config.OLIST_DIR / fname
        rows.append(
            {
                "dataset": "Olist",
                "file": path.name,
                "format": "CSV",
                "sheet": "",
                "size_bytes": path.stat().st_size,
                "sha256": config.sha256_file(path),
            }
        )
    path = config.RETAIL_XLSX
    rows.append(
        {
            "dataset": "OnlineRetailII",
            "file": path.name,
            "format": "XLSX",
            "sheet": "Year 2009-2010",
            "size_bytes": path.stat().st_size,
            "sha256": config.sha256_file(path),
        }
    )
    rows.append(
        {
            "dataset": "OnlineRetailII",
            "file": path.name,
            "format": "XLSX",
            "sheet": "Year 2010-2011",
            "size_bytes": path.stat().st_size,
            "sha256": "",  # same workbook; single hash recorded on the first sheet row
        }
    )
    return pd.DataFrame(rows)


def dataset_comparison(olist_facts: dict, retail_facts: dict, ol_dims: dict, rt_dims: dict) -> pd.DataFrame:
    rows = [
        ("Domain / business context", "Brazilian online marketplace (Olist) covering multiple sellers", "UK-based online wholesale/gift retailer, two accounting periods"),
        ("Source / provenance", "Olist public dataset (Kaggle distribution); nine relational CSV files", "UCI Machine Learning Repository dataset 'Online Retail II'; single Excel workbook, two sheets"),
        ("Time coverage", f"{olist_facts['temporal_integrity']['order_purchase_min']} to {olist_facts['temporal_integrity']['order_purchase_max']}", f"{retail_facts['combined']['date_min']} to {retail_facts['combined']['date_max']}"),
        ("Number of files / sheets", "9 CSV files", "1 workbook, 2 worksheets"),
        ("Rows (total)", f"{ol_dims['total_rows']:,} data rows across files", f"{rt_dims['total_rows']:,} transaction lines across sheets"),
        ("Columns", "4-9 per table; relational (normalised) schema", "8 identical columns per sheet; single denormalised fact table"),
        ("Main entities / variables", "customers, orders, order items, payments, reviews, products, sellers, geolocation, category translation", "invoice lines: Invoice, StockCode, Description, Quantity, InvoiceDate, Price, Customer ID, Country"),
        ("Granularity of observations", "Multiple grains: order, order item, payment, review, product, seller", "One row per invoice line (product-level transaction)"),
        ("Missingness", f"Concentrated in delivery timestamps and review text; product category missing in {olist_facts['category_coverage']['products_missing_category']:,} products", f"Customer ID missing in {retail_facts['combined']['missing_customer_id_pct']}% of lines; Description occasionally missing"),
        ("Duplicate rows", "Exact duplicate rows negligible; keys largely unique (see key checks)", "Exact duplicate rows negligible after normalisation; repeated invoice lines occur"),
        ("Data quality / preprocessing", "Relational joins, timestamp parsing, category translation mapping, currency in BRL, no returns/refunds table", "Mixed-type invoice/stock codes, cancellations via 'C' prefix, negative quantities/prices, missing customer IDs, no product master"),
        ("Use for e-commerce operations", "Strong: order lifecycle, statuses, payments, reviews, multi-seller orders", "Strong: transaction-level sales, countries, repeat customers, cancellations"),
        ("Use for inventory analysis", "Indirect: items and product attributes support demand analysis; no stock levels", "Indirect: quantities sold support demand and stock-out proxies; no stock levels"),
        ("Use for accounting workflows", "Payments and item values support reconciliation prototypes; no general ledger", "Line values, cancellations and adjustments support reconciliation and revenue checks; no ledger"),
        ("Use for anomaly detection", "Multi-table consistency checks, delivery/price outliers, review-score anomalies", "Negative quantities, zero/negative prices, cancellations, extreme line values"),
        ("Use for governance / audit experiments", "Supports traceable evidence retrieval across linked tables; no policies", "Supports transaction-level audit trails and rule checks; no policies"),
        ("Key limitations", "No returns/refunds, no cost/margin data, no stock movement; anonymised IDs", "No product master, no order status, no cost data; missing customer IDs; no true labels for anomalies"),
        ("License / redistribution", "Distribution terms governed by the Kaggle dataset page (verify current data card)", "CC BY 4.0 per the UCI dataset record (verify current record)"),
    ]
    return pd.DataFrame(rows, columns=["criterion", "olist", "online_retail_ii"])


def agent_suitability() -> pd.DataFrame:
    rows = [
        {
            "agent": "Orchestrator / Coordination",
            "olist_evidence": "orders + order_items + order_payments + order_reviews joined by order_id",
            "retail_evidence": "Invoice/StockCode lines with InvoiceDate ordering",
            "implementable_tasks": "Simulate multi-step order-processing workflows with explicit dependencies (approve -> pick/pack -> ship -> invoice -> reconcile)",
            "example_questions": "Can a workflow coordinate order validation, payment reconciliation and audit logging end-to-end?",
            "metrics": "Workflow completion rate, step latency, dependency violation count",
            "limitations": "Dataset structure alone does not demonstrate coordination; requires prototype execution logs",
        },
        {
            "agent": "E-Commerce",
            "olist_evidence": "order_status, order_purchase_timestamp, payments, reviews, items",
            "retail_evidence": "Invoice, Quantity, Price, InvoiceDate, Country",
            "implementable_tasks": "Order/transaction analysis, status tracking, sales reporting, cancellation analysis",
            "example_questions": "What is the sales trend by month/category, and how do cancellations vary over time?",
            "metrics": "Order volume, revenue, cancellation rate, review score distribution",
            "limitations": "No marketing/session data; Retail has no order-status concept",
        },
        {
            "agent": "Inventory",
            "olist_evidence": "order_items (product_id, seller_id, quantity implicitly per line), products attributes",
            "retail_evidence": "StockCode, Quantity per invoice line",
            "implementable_tasks": "Indirect demand analysis, product velocity, low/high-demand ranking, stock-out proxies",
            "example_questions": "Which products show high demand that would warrant replenishment?",
            "metrics": "Units sold per product, demand variability, days-without-sales proxy",
            "limitations": "No real-time stock levels, warehouse stock history, replenishment events, or stock movements in either dataset",
        },
        {
            "agent": "Accounting",
            "olist_evidence": "order_payments (payment_value, payment_type, installments), items (price, freight)",
            "retail_evidence": "line value = Quantity x Price, cancellations, adjustments",
            "implementable_tasks": "Reconciliation prototypes, transaction consistency checks, revenue aggregation",
            "example_questions": "Do summed item values reconcile with summed payment values per order?",
            "metrics": "Reconciliation mismatch rate, unexplained variance",
            "limitations": "No general ledger, journal entries, tax records, or audited statements; Olist totals are payment vs item proxies only",
        },
        {
            "agent": "Risk / Anomaly Detection",
            "olist_evidence": "delivery-time outliers, price/freight outliers, review-score vs delivery anomalies, duplicate keys",
            "retail_evidence": "negative quantities, zero/cancellation prices, extreme values, missing customer IDs",
            "implementable_tasks": "Transparent rule-based and statistical anomaly flagging",
            "example_questions": "Which orders show unusual freight-to-price ratios or abnormal delivery delays?",
            "metrics": "Flag rate, precision/recall only when trustworthy labels exist (not available here)",
            "limitations": "No ground-truth fraud labels; flagged cases are candidate anomalies, not verified fraud",
        },
        {
            "agent": "Governance",
            "olist_evidence": "Structured fields usable as policy inputs (e.g., max freight ratio, allowed statuses)",
            "retail_evidence": "Transaction fields usable as policy inputs (e.g., price > 0, quantity limits)",
            "implementable_tasks": "Policy-enforcement prototype with explicitly defined experimental rules",
            "example_questions": "Which transactions violate a threshold rule, and are they blocked or escalated?",
            "metrics": "Policy violation detection rate, false-block rate",
            "limitations": "Datasets contain no governance policies, permissions, or approval workflows",
        },
        {
            "agent": "Audit",
            "olist_evidence": "Business records that can serve as evidence references",
            "retail_evidence": "Transaction records that can serve as evidence references",
            "implementable_tasks": "Record agent actions, timestamps, policy decisions, evidence references, outcomes during experiments",
            "example_questions": "Can every agent decision be traced to the source record that justified it?",
            "metrics": "Audit event coverage, evidence traceability rate",
            "limitations": "Audit logs must be generated by the prototype; they are not part of the original datasets",
        },
    ]
    return pd.DataFrame(rows)
