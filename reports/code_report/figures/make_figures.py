"""Generate the diagrams for ``Code_Report.tex``.

Every diagram in this module is a *schematic* rendering of what was found by
inspecting the repository. Nothing here is measured data and nothing here
claims that a component exists: the four visual categories map directly onto
the implementation-status language used in the report.

    Implemented                -> solid, green
    Partially implemented      -> solid, amber
    Proposed / not implemented -> dashed, blue-grey
    External data source       -> solid, grey

Run from this directory:

    python make_figures.py

Writes six high-resolution PNG files next to this script:

    fig_repo_architecture.png     (Figure 1)
    fig_execution_workflow.png    (Figure 2)
    fig_data_pipeline.png         (Figure 3)
    fig_agent_interaction.png     (Figure 4)
    fig_governance_audit.png      (Figure 5)
    fig_testing_workflow.png      (Figure 6)
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Visual language
# ---------------------------------------------------------------------------
C_IMPL = "#cfe8d5"   # implemented
C_PART = "#fbe6c8"   # partially implemented
C_PROP = "#e8eef7"   # proposed / not implemented
C_DATA = "#e6e6e6"   # external data source
C_RISK = "#f7d9d9"   # validation gate / abort
C_HUMAN = "#fff3b0"  # human approval

E_IMPL = "#2f6b45"
E_PART = "#b8860b"
E_PROP = "#34495e"
E_DATA = "#4a4a4a"

TXT = "#1b2a38"
EDGE = "#34495e"
ARROW = "#5b6b7b"
ARROW_DATA = "#3f7f57"
ARROW_GOV = "#c9922e"
ARROW_RISK = "#b23b3b"
ARROW_AUDIT = "#8e6fb0"


def _axes(w, h, xlim=(0, 100), ylim=(0, 104)):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")
    return fig, ax


def box(
    ax,
    x,
    y,
    w,
    h,
    text,
    facecolor="white",
    edgecolor=EDGE,
    dashed=False,
    fontsize=8.4,
    bold=False,
    textcolor=TXT,
    rounding=1.4,
):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.35,rounding_size={rounding}",
        linewidth=1.4,
        edgecolor=edgecolor,
        facecolor=facecolor,
        linestyle="--" if dashed else "-",
        zorder=2,
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2.0,
        y + h / 2.0,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        fontweight="bold" if bold else "normal",
        color=textcolor,
        zorder=3,
        linespacing=1.35,
    )
    return patch


def arrow(ax, p_from, p_to, color=ARROW, lw=1.3, dashed=False, rad=0.0, style="-|>"):
    ax.add_patch(
        FancyArrowPatch(
            p_from,
            p_to,
            arrowstyle=style,
            mutation_scale=11,
            linewidth=lw,
            color=color,
            linestyle="--" if dashed else "-",
            connectionstyle=f"arc3,rad={rad}",
            shrinkA=1.5,
            shrinkB=1.5,
            zorder=1,
        )
    )


def legend(ax, x=2.0, y=1.5, fontsize=6.9):
    """Two-by-two legend keyed to the four implementation-status categories."""
    handles = [
        ("Implemented", C_IMPL, E_IMPL, "-"),
        ("Partially implemented", C_PART, E_PART, "-"),
        ("Proposed / not implemented", C_PROP, E_PROP, "--"),
        ("External data source", C_DATA, E_DATA, "-"),
    ]
    ax.text(x, y + 5.0, "Legend (implementation status)", fontsize=fontsize,
            fontweight="bold", color=EDGE)
    col_x = [x, x + 48.0]
    row_y = [y + 1.4, y - 1.4]
    for i, (label, fc, ec, ls) in enumerate(handles):
        r, c = divmod(i, 2)
        xx, yy = col_x[c], row_y[r]
        ax.add_patch(
            FancyBboxPatch(
                (xx, yy - 0.5),
                3.2,
                1.9,
                boxstyle="round,pad=0.08,rounding_size=0.35",
                facecolor=fc,
                edgecolor=ec,
                linewidth=1.1,
                linestyle=ls,
                zorder=2,
            )
        )
        ax.text(xx + 3.9, yy + 0.45, label, fontsize=fontsize, va="center", color=TXT)


def title(ax, text, y=103.0, fontsize=10.4):
    ax.text(50, y, text, ha="center", va="top", fontsize=fontsize,
            fontweight="bold", color=TXT)


def panel_label(ax, text, x, y, fontsize=8.4, color=EDGE):
    ax.text(x, y, text, fontsize=fontsize, fontweight="bold", color=color,
            ha="left", va="bottom")


# ---------------------------------------------------------------------------
# Figure 1 - Repository and module architecture
# ---------------------------------------------------------------------------
def repo_architecture():
    fig, ax = _axes(13.2, 8.8)
    title(ax, "Figure 1 - Repository and module architecture "
              "(solid = implemented, dashed = proposed)")

    panel_label(ax, "IMPLEMENTED SOFTWARE   (reports/)", 2, 94.5, color=E_IMPL)
    panel_label(ax, "PROPOSED   (no code found)", 64, 94.5, color=E_PROP)

    lw, lx = 60.0, 2.0
    left = [
        (85.5, 6.0, "Reporting layer (LaTeX):  main.tex -> main.pdf  |  dataset_report.tex -> .pdf  |  Agent_Report.tex -> .pdf",
         C_IMPL, E_IMPL),
        (77.0, 6.5, "Output layer:  analysis_results/*.csv (26) + summary.json  |  figures/*.png (13)  |  dataset-selection CSV/JSON",
         C_IMPL, E_IMPL),
        (68.5, 6.5, "Assembly modules:  compare.py (dataset_inventory, dataset_comparison, agent_suitability),  figures.py",
         C_IMPL, E_IMPL),
        (60.0, 6.5, "Entry point:  analysis/__main__.py :: main()      [python -m analysis]",
         C_IMPL, E_IMPL),
        (51.5, 6.5, "Analysis run:  olist.run(),  online_retail.run()",
         C_IMPL, E_IMPL),
        (43.0, 6.5, "Profiling library:  profiling.py  (7 dataset-agnostic helpers)",
         C_IMPL, E_IMPL),
        (34.5, 6.5, "Ingestion & validation:  config.py,  olist.load_tables/validate_schema,\n"
                    "online_retail.load_sheets/_clean",
         C_IMPL, E_IMPL),
        (26.0, 6.5, "Independent inspector:  scripts/inspect_datasets.py  (standard library only)",
         C_IMPL, E_IMPL),
        (17.5, 6.5, "Input provenance:  config.sha256_file -> dataset_inventory.csv  (no event log)",
         C_PART, E_PART),
        (8.5, 6.5, "External data sources (read-only):  datasets/olist/*.csv (9 files),\n"
                   "datasets/online_retail_ii/online_retail_II.xlsx (2 sheets)",
         C_DATA, E_DATA),
    ]
    for (y, h, text, fc, ec) in left:
        box(ax, lx, y, lw, h, text, facecolor=fc, edgecolor=ec, fontsize=7.0)

    for i in range(len(left) - 1):
        y_bottom = left[i][0]
        y_top = left[i + 1][0] + left[i + 1][1]
        arrow(ax, (lx + 8, y_bottom), (lx + 8, y_top), color=ARROW_DATA)

    rx, rw = 64.0, 34.0
    right = [
        (85.5, 6.0, "src/  - directory exists but is EMPTY", C_PROP, E_PROP),
        (75.5, 8.5, "Agent layer: 7 agent components\n(no class is defined anywhere in the repository)",
         C_PROP, E_PROP),
        (65.0, 8.5, "Orchestration & messaging\n(task planning, routing, retries, queues/APIs/LLM calls)",
         C_PROP, E_PROP),
        (54.5, 8.5, "Governance engine\n(policy evaluation, allow / block / escalate, human approval)",
         C_PROP, E_PROP),
        (44.0, 8.5, "Audit store\n(append-only event log, run IDs, evidence references)",
         C_PROP, E_PROP),
        (33.5, 8.5, "Typed data contracts\n(request/response, workflow state, decision records)",
         C_PROP, E_PROP),
        (23.0, 8.5, "Agent, integration and end-to-end tests",
         C_PROP, E_PROP),
    ]
    for (y, h, text, fc, ec) in right:
        box(ax, rx, y, rw, h, text, facecolor=fc, edgecolor=ec, dashed=True, fontsize=7.2)

    arrow(ax, (lx + lw, 71.25), (rx, 79.75), color=ARROW, dashed=True)
    ax.text(63.0, 75.0, "future\nintegration\npoint", fontsize=6.3, ha="center",
            va="center", color=ARROW, style="italic")

    legend(ax)
    fig.savefig(HERE / "fig_repo_architecture.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 2 - Main execution workflow
# ---------------------------------------------------------------------------
def execution_workflow():
    fig, ax = _axes(13.2, 8.4)
    title(ax, "Figure 2 - Main execution workflow: three entry points")

    panel_label(ax, "Path A - python -m analysis   (cwd: reports/dataset_report)", 3, 96.0, color=E_IMPL)
    panel_label(ax, "Path B - python reports/dataset_selection_table/scripts/inspect_datasets.py", 51, 96.0, color=E_IMPL)

    ax_lw, ax_lx, h = 44.0, 3.0, 7.0
    a_steps = [
        "config.ensure_dirs()  creates analysis_results/ and figures/",
        "olist.load_tables()   reads 9 CSV files, counts raw duplicates",
        "GATE  timestamp parsing must not create new NaT\n-> else raise ValueError(file:column) and abort",
        "olist.run()   profiles and validates, returns frames/facts",
        "online_retail.load_sheets()   reads both Excel sheets (openpyxl)",
        "GATE  sheet columns must equal EXPECTED_COLS\n-> else raise ValueError and abort",
        "online_retail.run()   cleans, profiles, derives business signals",
        "_dimensions(); write 26 CSV; render 13 PNG; write summary.json",
        "print summary size and output directories; exit 0",
    ]
    y, prev = 88.0, None
    for s in a_steps:
        gate = s.startswith("GATE")
        box(ax, ax_lx, y, ax_lw, h, s,
            facecolor=C_RISK if gate else C_IMPL,
            edgecolor=ARROW_RISK if gate else E_IMPL,
            fontsize=6.6)
        if prev is not None:
            arrow(ax, (ax_lx + 8, prev), (ax_lx + 8, y + h), color=ARROW_DATA)
        prev = y
        y -= h + 1.0

    bx_lx, bx_w = 50.0, 47.0
    b_steps = [
        "argparse: --root (default repo root), --output (default report dir)",
        "discover datasets/** for .csv / .xlsx / .xls / .json",
        "CSV branch: csv.Sniffer dialect, streamed rows, per-column profile",
        "XLSX branch: pure-Python OOXML streaming reader (zipfile + ElementTree)",
        "write dataset_inventory.csv, data_quality_summary.csv,",
        "primary_key_checks.csv, dataset_comparison.csv, agent_suitability_matrix.csv",
        "write inspection_summary.json (inventory, relationship checks, field quality)",
        "print one line per inspected file",
    ]
    y, prev = 88.0, None
    for s in b_steps:
        box(ax, bx_lx, y, bx_w, h, s, facecolor=C_IMPL, edgecolor=E_IMPL, fontsize=6.6)
        if prev is not None:
            arrow(ax, (bx_lx + 8, prev), (bx_lx + 8, y + h), color=ARROW_DATA)
        prev = y
        y -= h + 1.0

    box(ax, 3.0, 12.0, 94.0, 6.5,
        "Path C - python -m pytest tests -q   (cwd: reports/dataset_report)"
        "   ->   13 tests collected, 13 passed, 0 failed (see Figure 6)",
        facecolor=C_IMPL, edgecolor=E_IMPL, fontsize=6.9, bold=True)

    legend(ax, y=1.5)
    fig.savefig(HERE / "fig_execution_workflow.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 3 - Data pipeline
# ---------------------------------------------------------------------------
def data_pipeline():
    fig, ax = _axes(13.6, 7.8)
    title(ax, "Figure 3 - Data pipeline: discovery, validation, transformation, analysis, export")

    row1 = [
        (2.0, 74.0, 22.0, 13.0, "1. External files", C_DATA, E_DATA,
         "datasets/olist/*.csv\n(nine files)\n\ndatasets/online_retail_ii/\nonline_retail_II.xlsx\n(Year 2009-2010, 2010-2011)"),
        (26.0, 74.0, 22.0, 13.0, "2. Discovery", C_IMPL, E_IMPL,
         "config.OLIST_FILES\nconfig.RETAIL_SHEETS\nconfig.OLIST_DIR,\nconfig.RETAIL_XLSX\n(paths derived from __file__)"),
        (50.0, 74.0, 22.0, 13.0, "3. Loading", C_IMPL, E_IMPL,
         "pd.read_csv(low_memory=False)\npd.read_excel(sheet_name=None,\nengine='openpyxl')\nno usecols, no dtype hints,\nno chunking"),
        (74.0, 74.0, 24.0, 13.0, "4. Validation gates", C_RISK, ARROW_RISK,
         "olist.validate_schema: set equality\nvs EXPECTED_COLUMNS\nonline_retail._clean: exact\ncolumn list equality\n\ntimestamp parse may not create\nnew NaT -> raise ValueError"),
    ]
    for (x, y, w, hh, label, fc, ec, body) in row1:
        box(ax, x, y, w, hh, label + "\n\n" + body, facecolor=fc, edgecolor=ec, fontsize=6.3)
    for i in range(3):
        arrow(ax, (row1[i][0] + row1[i][2] + 0.3, 80.5),
              (row1[i + 1][0] - 0.3, 80.5), color=ARROW_DATA)

    row2 = [
        (2.0, 46.0, 22.0, 15.0, "5. Normalisation", C_IMPL, E_IMPL,
         "pd.to_datetime(errors='coerce')\npd.to_numeric(errors='coerce')\n_clean_code strips trailing '.0'\nand keeps blanks as pd.NA\n_strip_nullable trims strings\nmissing values are never\nimputed or stringified"),
        (26.0, 46.0, 22.0, 15.0, "6. Profiling", C_IMPL, E_IMPL,
         "column_profile (completeness,\ncardinality, pandas dtype)\nexact_duplicates (raw + cleaned)\nnumeric_stats (IQR fences,\nn_zero, n_negative)\ncategorical_stats, temporal_profile\ncategory translation coverage"),
        (50.0, 46.0, 22.0, 15.0, "7. Relational analysis", C_IMPL, E_IMPL,
         "candidate key checks\nreferential integrity (orphan rows\nin both directions)\njoin cardinality\njoin row-inflation factor\nvalue counts, monthly series\ncategory revenue ranking"),
        (74.0, 46.0, 24.0, 15.0, "8. Derived facts and signals", C_IMPL, E_IMPL,
         "line_total = price + freight\nline_value = Quantity x Price\nis_cancellation = Invoice begins 'C'\nreconciliation proxy: sum(payment)\nvs sum(item line_total) per order\ntemporal-integrity violations"),
    ]
    for (x, y, w, hh, label, fc, ec, body) in row2:
        box(ax, x, y, w, hh, label + "\n\n" + body, facecolor=fc, edgecolor=ec, fontsize=6.3)
    for i in range(3):
        arrow(ax, (row2[i][0] + row2[i][2] + 0.3, 53.5),
              (row2[i + 1][0] - 0.3, 53.5), color=ARROW_DATA)
    arrow(ax, (13, 74), (13, 61), color=ARROW_DATA)
    arrow(ax, (62, 74), (62, 61), color=ARROW_DATA)

    row3 = [
        (2.0, 24.0, 30.0, 14.0, "9. Serialisation", C_IMPL, E_IMPL,
         "config.write_csv (float_format '%.6g')\nconfig.write_json\n-> analysis_results/: 26 CSV\nfiles + summary.json (deterministic)"),
        (35.0, 24.0, 30.0, 14.0, "10. Visualisation", C_IMPL, E_IMPL,
         "matplotlib (Agg backend) + seaborn\nfigures.py -> 13 PNG at 150 dpi\nno synthetic or illustrative\nvalues are ever plotted"),
        (68.0, 24.0, 30.0, 14.0, "11. Downstream consumption", C_IMPL, E_IMPL,
         "LaTeX sources include the CSV\nnumbers and the PNG figures;\ncompiled PDFs are the human-\nreadable output"),
    ]
    for (x, y, w, hh, label, fc, ec, body) in row3:
        box(ax, x, y, w, hh, label + "\n\n" + body, facecolor=fc, edgecolor=ec, fontsize=6.3)
    for x in (17.0, 50.0, 83.0):
        arrow(ax, (x, 46.0), (x, 38.0), color=ARROW_DATA)

    box(ax, 2.0, 9.0, 96.0, 11.0,
        "Boundary of what the data can support:  the pipeline measures observed transactions only. Neither dataset carries\n"
        "stock-on-hand, inventory movements, a general ledger or chart of accounts, native governance policies, or verified fraud\n"
        "labels. Cancellations, negative quantities and IQR outliers are reported as business or data-quality signals - never as fraud.",
        facecolor=C_PART, edgecolor=E_PART, fontsize=6.4)

    legend(ax, y=1.0)
    fig.savefig(HERE / "fig_data_pipeline.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 4 - Agent interaction
# ---------------------------------------------------------------------------
def agent_interaction():
    fig, ax = _axes(13.2, 8.4, ylim=(0, 110))
    title(ax, "Figure 4 - Agent interaction: what is implemented vs. what is proposed", y=109.0)

    box(ax, 2.0, 95.0, 96.0, 9.0,
        "REPOSITORY EVIDENCE: no agent class, message schema, orchestrator, policy engine or audit store exists.\n"
        "Everything above the green band is the PROPOSED design documented in Agent_Report.tex; it is NOT implemented.",
        facecolor=C_RISK, edgecolor=ARROW_RISK, fontsize=7.4, bold=True)

    box(ax, 34.0, 84.0, 32.0, 6.0, "Business user / external request",
        facecolor=C_DATA, edgecolor=E_DATA, fontsize=7.2, bold=True)
    box(ax, 30.0, 72.0, 40.0, 7.5, "Agent 1 - Orchestrator / Coordination   (proposed)\n"
                                   "task decomposition, delegation, consolidation",
        facecolor=C_PROP, edgecolor=E_PROP, dashed=True, fontsize=7.2, bold=True)
    arrow(ax, (50, 84), (50, 79.5), color=ARROW, dashed=True)

    for x, label in [
        (2.0, "Agent 2\nE-Commerce\nOperations"),
        (26.0, "Agent 3\nInventory\nManagement"),
        (50.0, "Agent 4\nAccounting"),
        (74.0, "Agent 5\nRisk & Anomaly\nDetection"),
    ]:
        box(ax, x, 59.0, 22.0, 9.0, label, facecolor=C_PROP, edgecolor=E_PROP,
            dashed=True, fontsize=7.0, bold=True)
        arrow(ax, (50, 72), (x + 11, 68.0), color=ARROW, dashed=True)

    box(ax, 2.0, 46.0, 56.0, 8.0, "Agent 6 - Governance & Policy Enforcement   (proposed)\n"
                                   "policy checks: allow / block / escalate",
        facecolor=C_PROP, edgecolor=E_PROP, dashed=True, fontsize=7.0, bold=True)
    box(ax, 62.0, 46.0, 36.0, 8.0, "Human approval   (proposed)\nfor high-impact actions",
        facecolor=C_HUMAN, edgecolor=E_PART, dashed=True, fontsize=7.0, bold=True)
    for x in (13.0, 37.0, 61.0):
        arrow(ax, (x, 59.0), (x, 54.0), color=ARROW_GOV, dashed=True)
    arrow(ax, (85.0, 59.0), (58.0, 54.0), color=ARROW_RISK, dashed=True)
    arrow(ax, (58.0, 50.0), (62.0, 50.0), color=ARROW_GOV, dashed=True)

    box(ax, 2.0, 34.0, 96.0, 8.0, "Agent 7 - Audit & Traceability   (proposed)\n"
                                   "append-only audit events, evidence references, decision reasons",
        facecolor=C_PROP, edgecolor=E_PROP, dashed=True, fontsize=7.0, bold=True)
    arrow(ax, (30, 46), (30, 42), color=ARROW_AUDIT, dashed=True)
    arrow(ax, (98, 38), (70, 72), color=ARROW_AUDIT, dashed=True, rad=-0.22)
    ax.text(88.5, 52.0, "traceability\nfeedback", fontsize=6.2, color=ARROW_AUDIT,
            style="italic", ha="center", va="center")

    box(ax, 2.0, 13.0, 96.0, 18.0,
        "IMPLEMENTED TODAY - the only real communication mechanism in the repository\n"
        "analysis/__main__.py :: main() runs a single process, sequentially, and passes results as direct Python calls and\n"
        "shared in-memory dictionaries:  load_tables() -> run() -> _dimensions() -> write_csv()/write_json() -> figures.*().\n"
        "There is no message bus, no queue, no HTTP or tool interface, no LLM or agent call, no retry and no rollback.\n"
        "This sequential analyse-then-export order is the closest implemented analogue of an orchestrator.",
        facecolor=C_IMPL, edgecolor=E_IMPL, fontsize=6.8)

    legend(ax, y=2.0)
    fig.savefig(HERE / "fig_agent_interaction.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 5 - Governance and audit workflow
# ---------------------------------------------------------------------------
def governance_audit():
    fig, ax = _axes(13.2, 8.2)
    title(ax, "Figure 5 - Governance and audit controls: enforced by code vs. documented only")

    panel_label(ax, "CONTROLS ENFORCED BY THE CURRENT CODE", 2, 95.0, color=E_IMPL)
    panel_label(ax, "DOCUMENTED BUT NOT ENFORCED  /  PROPOSED", 52, 95.0, color=E_PROP)

    enforced = [
        (86.0, 6.5, "Read-only treatment of raw data: loaders only read; every write target is analysis_results/ or figures/"),
        (78.0, 7.0, "Schema gate: olist.validate_schema compares actual column sets with EXPECTED_COLUMNS"),
        (70.0, 7.0, "Type gate: olist.load_tables raises ValueError if timestamp parsing newly creates NaT"),
        (62.0, 7.0, "Contract gate: online_retail._clean raises ValueError unless columns == EXPECTED_COLS"),
        (54.0, 7.0, "Fail-closed behaviour: a failed gate aborts the run; nothing is silently coerced or imputed"),
        (46.0, 7.0, "Determinism: fixed float_format, no RNG, no network access; outputs byte-identical on re-run"),
    ]
    for (y, hh, text) in enforced:
        box(ax, 2.0, y, 46.0, hh, text, facecolor=C_IMPL, edgecolor=E_IMPL, fontsize=6.4)
    box(ax, 2.0, 36.0, 46.0, 8.5,
        "Input provenance: config.sha256_file records a SHA-256 per source file in\n"
        "dataset_inventory.csv  (an integrity manifest only - not an audit trail)",
        facecolor=C_PART, edgecolor=E_PART, fontsize=6.4)

    proposed = [
        (86.0, 6.5, "Authorization layer: who may request which action (no identity or roles exist in code)"),
        (78.5, 6.5, "Policy engine: versioned rules producing allow / block / escalate decisions"),
        (71.0, 6.5, "Tool and resource permissions: allow-lists for files, queries and side effects"),
        (63.5, 6.5, "Human-in-the-loop approval gate for high-impact or irreversible actions"),
        (56.0, 6.5, "Retry, timeout and rollback semantics for partially failed steps"),
    ]
    for (y, hh, text) in proposed:
        box(ax, 52.0, y, 46.0, hh, text, facecolor=C_PROP, edgecolor=E_PROP,
            dashed=True, fontsize=6.4)
    box(ax, 52.0, 46.5, 46.0, 8.5,
        "Audit event store: run ID, actor, action, input digest, decision, evidence\n"
        "reference, outcome and timestamp (schema proposed, not implemented)",
        facecolor=C_PROP, edgecolor=E_PROP, dashed=True, fontsize=6.4)
    box(ax, 52.0, 36.0, 46.0, 9.5,
        "Sensitive-data handling: Olist review text is personal data; no redaction,\n"
        "retention or access-control mechanism is implemented. Credential management\n"
        "is absent because no code requires a secret - there is no API or model client.",
        facecolor=C_PROP, edgecolor=E_PROP, dashed=True, fontsize=6.4)

    flow = [
        ("Request", C_DATA, E_DATA, False),
        ("Input validation\n(ENFORCED)", C_IMPL, E_IMPL, False),
        ("Policy check\n(PROPOSED)", C_PROP, E_PROP, True),
        ("Execution\n(data pipeline)", C_DATA, E_DATA, False),
        ("Audit event\n(PROPOSED)", C_PROP, E_PROP, True),
        ("Response", C_DATA, E_DATA, False),
    ]
    xs = [0.5 + i * 16.6 for i in range(6)]
    for (x, (label, fc, ec, dashed)) in zip(xs, flow):
        box(ax, x, 20.0, 14.0, 8.5, label, facecolor=fc, edgecolor=ec,
            dashed=dashed, fontsize=6.5, bold=True)
    for i in range(5):
        arrow(ax, (xs[i] + 14.0, 24.25), (xs[i + 1], 24.25), color=ARROW)

    ax.text(50, 15.0,
            "Only the left-hand controls exist in code. The policy, approval and audit stages of this flow are design only: "
            "no decision is\nrecorded, no actor is identified and no action is gated beyond column and type validation.",
            ha="center", va="top", fontsize=6.5, color=TXT, style="italic")

    legend(ax, y=1.0)
    fig.savefig(HERE / "fig_governance_audit.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 6 - Testing workflow
# ---------------------------------------------------------------------------
def testing_workflow():
    fig, ax = _axes(13.6, 7.6)
    title(ax, "Figure 6 - Testing workflow: what is executed today and which layers are missing")

    box(ax, 22.0, 86.0, 56.0, 8.5,
        "python -m pytest tests -q      (cwd: reports/dataset_report)\n"
        "collected 13 tests  ->  13 passed in 2.53 s   |   0 failed, 0 skipped, 0 errors",
        facecolor=C_IMPL, edgecolor=E_IMPL, fontsize=7.4, bold=True)
    ax.text(50, 84.0, "pytest 9.1.0 discovers tests/test_analysis.py; the suite inserts reports/dataset_report on sys.path "
                      "and uses in-memory frames only",
            ha="center", va="top", fontsize=6.3, color=TXT, style="italic")

    covered = [
        "exact_duplicates() - duplicate counting",
        "key_check() - single and composite keys",
        "numeric_stats() - sign counts and ranges",
        "temporal_profile() - one row per date column",
        "referential_integrity() - orphan rows",
        "olist.validate_schema() - mismatch flagging",
        "online_retail._clean_code() - preserves pd.NA",
        "online_retail._strip_nullable() - trims, keeps NA",
        "online_retail._clean() - rejects wrong columns",
        "online_retail._sheet_quality() - cancellation,",
        "    negative-quantity, revenue and line-value",
        "    definitions, missing-customer-id counting",
    ]
    box(ax, 2.0, 40.0, 46.0, 40.0,
        "COVERED - 13 unit assertions\n\n" + "\n".join(covered),
        facecolor=C_IMPL, edgecolor=E_IMPL, fontsize=6.3)
    arrow(ax, (29.0, 86.0), (22.0, 80.0), color=ARROW_DATA)

    not_covered = [
        "config.py - paths, sha256_file, write_csv/json",
        "profiling.column_profile / categorical_stats /",
        "    value_counts_table",
        "olist.load_tables (real CSV I/O)",
        "olist.run and online_retail.run (full pipeline)",
        "online_retail.load_sheets (Excel I/O)",
        "compare.py - inventory, comparison, suitability",
        "figures.py - all figure generation",
        "__main__.main() - the entry point itself",
        "scripts/inspect_datasets.py - the whole inspector",
        "Integration test on the real datasets",
        "End-to-end test of either entry point",
        "Data-contract tests for CSV/JSON outputs",
        "Agent, governance and audit behaviour tests",
    ]
    box(ax, 52.0, 40.0, 46.0, 40.0,
        "NOT COVERED (verified gaps)\n\n" + "\n".join(not_covered),
        facecolor=C_PROP, edgecolor=E_PROP, dashed=True, fontsize=6.3)
    arrow(ax, (71.0, 86.0), (78.0, 80.0), color=ARROW, dashed=True)

    box(ax, 2.0, 26.0, 96.0, 10.5,
        "Evidence of prior runs: reports/.pytest_cache/ and reports/dataset_report/.pytest_cache/ exist; the latter records node\n"
        "IDs for these same 13 tests and an empty lastfailed set. No CI configuration, no coverage measurement and no automated\n"
        "test runner were found in the repository.",
        facecolor=C_DATA, edgecolor=E_DATA, fontsize=6.4)

    box(ax, 2.0, 12.0, 96.0, 11.0,
        "Reproduction check performed while preparing this report: the full analysis pipeline was re-executed with "
        "'python -m analysis'.\nAll 27 files in analysis_results/ were regenerated with byte-identical SHA-256 digests, demonstrating that the "
        "data pipeline is\ndeterministic. This is a reproducibility check on the data layer - it is not an agent-behaviour test.",
        facecolor=C_IMPL, edgecolor=E_IMPL, fontsize=6.4)

    legend(ax, y=1.0)
    fig.savefig(HERE / "fig_testing_workflow.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def main():
    repo_architecture()
    execution_workflow()
    data_pipeline()
    agent_interaction()
    governance_audit()
    testing_workflow()
    print("Figures written to", HERE)


if __name__ == "__main__":
    main()
