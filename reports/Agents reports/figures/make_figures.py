"""Generate diagrams for Agent_Report.tex.

All diagrams are schematic representations of the PROPOSED governed
multi-agent architecture described in the report. They are drawings, not
measured data, and they deliberately distinguish implemented components
(solid borders) from proposed components (dashed borders).

Run from this directory:

    python make_figures.py

Outputs high-resolution PNG files in the same directory.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = Path(__file__).resolve().parent

# Consistent colour scheme.
C_IMPL = "#cfe8d5"       # implemented (solid)
C_PROP = "#e8eef7"       # proposed (dashed)
C_GOV = "#fbe6c8"        # governance
C_RISK = "#f7d9d9"       # risk
C_AUDIT = "#e3d7f0"      # audit
C_DATA = "#e6e6e6"       # data / tool interfaces
C_HUMAN = "#fff3b0"      # human approval
EDGE = "#34495e"
ARROW = "#5b6b7b"


def _new_axes(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
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
    fontsize=9,
    bold=False,
    textcolor="#1b2a38",
):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.6,rounding_size=1.5",
        linewidth=1.4,
        edgecolor=edgecolor,
        facecolor=facecolor,
        linestyle="--" if dashed else "-",
        mutation_scale=1.0,
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        fontweight="bold" if bold else "normal",
        color=textcolor,
        wrap=True,
    )
    return patch


def arrow(ax, p_from, p_to, color=ARROW, style="-|>", lw=1.4, dashed=False, rad=0.0):
    ax.add_patch(
        FancyArrowPatch(
            p_from,
            p_to,
            arrowstyle=style,
            mutation_scale=12,
            linewidth=lw,
            color=color,
            linestyle="--" if dashed else "-",
            connectionstyle=f"arc3,rad={rad}",
            shrinkA=2,
            shrinkB=2,
        )
    )


def legend(ax):
    handles = [
        ("Implemented", C_IMPL, "-"),
        ("Proposed", C_PROP, "--"),
        ("Governance", C_GOV, "-"),
        ("Risk", C_RISK, "-"),
        ("Audit", C_AUDIT, "-"),
        ("Human approval", C_HUMAN, "-"),
        ("Data / tools", C_DATA, "-"),
    ]
    x0, y0 = 2, 2
    ax.text(x0, y0 + 2.2, "Legend", fontsize=8, fontweight="bold", color=EDGE)
    xx = x0
    for label, color, ls in handles:
        ax.add_patch(
            FancyBboxPatch(
                (xx, y0 - 1.2),
                4,
                2.2,
                boxstyle="round,pad=0.1,rounding_size=0.4",
                facecolor=color,
                edgecolor=EDGE,
                linewidth=1.0,
                linestyle=ls,
            )
        )
        ax.text(xx + 4.8, y0 - 0.1, label, fontsize=7, va="center", color="#1b2a38")
        xx += 4 + 0.8 + len(label) * 1.55


def architecture():
    fig, ax = _new_axes(13, 8.6)

    box(ax, 34, 92, 32, 6, "External request / business user", facecolor=C_DATA, bold=True)

    box(ax, 32, 79, 36, 8, "Agent 1 - Orchestrator / Coordination\n(task planning, state, failure handling)",
        facecolor=C_PROP, dashed=True, bold=True, fontsize=8.5)

    ops = [
        (3, "Agent 2\nE-Commerce\nOperations", C_PROP),
        (26, "Agent 3\nInventory\nManagement", C_PROP),
        (49, "Agent 4\nAccounting", C_PROP),
        (72, "Agent 5\nRisk / Anomaly\nDetection", C_RISK),
    ]
    for x, label, col in ops:
        box(ax, x, 60, 21, 11, label, facecolor=col, dashed=(col != C_RISK), bold=True, fontsize=8.5)

    box(ax, 2, 44, 62, 10,
        "Agent 6 - Governance & Policy Enforcement\n"
        "policy checks: allow / block / escalate",
        facecolor=C_GOV, dashed=True, bold=True, fontsize=8.2)
    box(ax, 68, 44, 30, 10, "Human approval\n(high-impact actions)",
        facecolor=C_HUMAN, dashed=True, bold=True, fontsize=8.2)
    box(ax, 2, 30, 96, 8,
        "Agent 7 - Audit & Traceability  |  append-only audit events, evidence references, decision reasons",
        facecolor=C_AUDIT, dashed=True, bold=True, fontsize=8.2)

    box(ax, 2, 18, 44, 8,
        "Agent 6 INPUTS: explicit prototype policies\n(thresholds, permissions, approval rules)",
        facecolor=C_GOV, dashed=True, fontsize=7.5)

    box(ax, 3, 1.5, 62, 8,
        "IMPLEMENTED ingestion & validation layer\nanalysis/ loaders, schema & key checks, profiles (read-only)",
        facecolor=C_IMPL, bold=True, fontsize=7.5)
    box(ax, 68, 1.5, 30, 8,
        "Raw datasets\nOlist CSV (9)\nOnline Retail II XLSX",
        facecolor=C_DATA, bold=True, fontsize=7.5)

    # arrows
    # request -> orchestrator
    arrow(ax, (50, 92), (50, 87))
    # orchestrator -> operational agents
    for x in (13.5, 36.5, 59.5, 82.5):
        arrow(ax, (50, 79), (x, 71), dashed=True, rad=0.0)
    # operational agents -> governance (E-Commerce, Inventory, Accounting)
    for x in (13.5, 36.5, 59.5):
        arrow(ax, (x, 60), (x, 54), color="#c9922e", dashed=True)
    # Risk agent -> governance (escalation)
    arrow(ax, (82.5, 60), (82.5, 54), color="#b23b3b", dashed=True)
    # governance -> human approval
    arrow(ax, (64, 49), (68, 49), color="#c9922e", dashed=True)
    # operational agents -> audit
    for x in (13.5, 36.5, 59.5, 82.5):
        arrow(ax, (x, 60), (x, 38), color="#8e6fb0", dashed=True)
    # policy inputs -> governance
    arrow(ax, (24, 26), (24, 44), color="#c9922e", dashed=True)
    # audit -> orchestrator (traceability feedback)
    arrow(ax, (96, 34), (66, 79), color="#8e6fb0", dashed=True, rad=-0.28)
    # ingestion/validation layer -> operational agents
    arrow(ax, (30, 9.5), (13.5, 60), color="#3f7f57", dashed=True, rad=0.28)
    arrow(ax, (40, 9.5), (59.5, 60), color="#3f7f57", dashed=True, rad=-0.22)
    # raw data -> ingestion/validation
    arrow(ax, (68, 5.5), (65, 5.5), color="#3f7f57")

    legend(ax)
    fig.suptitle("Figure 1 - Proposed governed multi-agent architecture (dashed = proposed, solid = implemented)",
                 fontsize=10.5, fontweight="bold", y=0.99)
    fig.savefig(HERE / "fig_architecture.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def status_matrix():
    fig, ax = _new_axes(12, 5.4)
    rows = [
        ("Agent 1 Orchestrator", 0.0),
        ("Agent 2 E-Commerce", 0.0),
        ("Agent 3 Inventory", 0.0),
        ("Agent 4 Accounting", 0.0),
        ("Agent 5 Risk / Anomaly", 0.0),
        ("Agent 6 Governance", 0.0),
        ("Agent 7 Audit", 0.0),
        ("Ingestion & validation layer", 1.0),
        ("Dataset inspector (Deliverable 1)", 1.0),
    ]
    n = len(rows)
    for i, (label, impl) in enumerate(rows):
        y = n - i - 1
        ax.add_patch(FancyBboxPatch((0, y + 0.15), 60, 0.7, boxstyle="round,pad=0.05",
                                    facecolor="#f4f6f8", edgecolor="#d0d7de", linewidth=1))
        ax.text(0.7, y + 0.5, label, fontsize=9, va="center", color="#1b2a38")
        if impl:
            ax.add_patch(FancyBboxPatch((61, y + 0.15), 30, 0.7, boxstyle="round,pad=0.05",
                                        facecolor=C_IMPL, edgecolor=EDGE, linewidth=1))
            ax.text(76, y + 0.5, "Implemented (data layer)", fontsize=8.2, va="center", ha="center", color="#1b2a38")
        else:
            ax.add_patch(FancyBboxPatch((61, y + 0.15), 30, 0.7, boxstyle="round,pad=0.05",
                                        facecolor=C_PROP, edgecolor=EDGE, linewidth=1, linestyle="--"))
            ax.text(76, y + 0.5, "Proposed - not implemented", fontsize=8.2, va="center", ha="center", color="#1b2a38")
    ax.text(0, n + 0.3, "Component", fontsize=9, fontweight="bold")
    ax.text(61, n + 0.3, "Status (from repository inspection)", fontsize=9, fontweight="bold")
    ax.set_xlim(-1, 92)
    ax.set_ylim(-0.5, n + 1)
    fig.suptitle("Figure 2 - Implementation status observed in the repository", fontsize=10.5, fontweight="bold", y=0.98)
    fig.savefig(HERE / "fig_status_matrix.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def governance_lifecycle():
    fig, ax = _new_axes(12, 5.2)
    steps = [
        "1. Request", "2. Task\nplanning", "3. Authorization\n& policy check",
        "4. Agent\nexecution", "5. Result\nvalidation", "6. Risk\nassessment",
        "7. Human\napproval?", "8. Audit\nrecording", "9. Final\nresponse",
    ]
    w, gap = 9.2, 1.3
    x = 1
    y = 40
    for i, s in enumerate(steps):
        col = C_GOV if i in (2, 6) else (C_AUDIT if i == 7 else C_PROP)
        box(ax, x, y, w, 16, s, facecolor=col, dashed=True, fontsize=7.6, bold=True)
        if i < len(steps) - 1:
            arrow(ax, (x + w, y + 8), (x + w + gap, y + 8))
        x += w + gap
    # feedback for blocked/escalated
    box(ax, 30, 12, 40, 12,
        "Blocked / escalated: reason recorded; request returned to orchestrator (no unsafe execution)",
        facecolor=C_RISK, dashed=True, fontsize=7.8)
    arrow(ax, (x - w / 2, y), (50, 24), color="#b23b3b", dashed=True, rad=-0.25)
    box(ax, 2, 12, 24, 12,
        "Prototype policies\n(versioned, explicit)",
        facecolor=C_GOV, dashed=True, fontsize=7.8)
    arrow(ax, (14, 24), (28, 40), color="#c9922e", dashed=True, rad=-0.2)
    fig.suptitle("Figure 3 - Proposed governance lifecycle for every agent action",
                 fontsize=10.5, fontweight="bold", y=0.98)
    fig.savefig(HERE / "fig_governance_lifecycle.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def sequence(participants, messages, title, fname):
    fig, ax = plt.subplots(figsize=(11.5, 0.62 * len(messages) + 2.2))
    ncol = len(participants)
    xs = [5 + i * (90 / max(1, ncol - 1)) for i in range(ncol)] if ncol > 1 else [50]
    top = len(messages) + 1.4
    # participant headers
    for x, name in zip(xs, participants):
        ax.add_patch(FancyBboxPatch((x - 6.2, top), 12.4, 1.0,
                                    boxstyle="round,pad=0.08,rounding_size=0.25",
                                    facecolor="#eef2f6", edgecolor=EDGE, linewidth=1.1))
        ax.text(x, top + 0.5, name, ha="center", va="center", fontsize=8, fontweight="bold", color="#1b2a38")
        ax.plot([x, x], [top - 0.15, 0.4], color="#c3ccd5", linewidth=1.0, linestyle=(0, (3, 3)), zorder=0)
    for i, (frm, to, label, kind) in enumerate(messages):
        y = top - 0.9 - i * 1.0
        x1, x2 = xs[frm], xs[to]
        if frm == to:
            ax.add_patch(FancyArrowPatch((x1, y), (x1 + 2.2, y - 0.35),
                                         arrowstyle="-|>", mutation_scale=10, color=ARROW,
                                         connectionstyle="arc3,rad=-0.8", linewidth=1.2))
            ax.text(x1 + 2.6, y - 0.15, label, fontsize=7.4, va="center", color="#1b2a38")
            continue
        dashed = kind == "response" or kind == "return"
        color = "#8e6fb0" if kind == "audit" else ("#b23b3b" if kind == "risk" else ARROW)
        ax.add_patch(FancyArrowPatch((x1, y), (x2, y), arrowstyle="-|>", mutation_scale=11,
                                     color=color, linewidth=1.3,
                                     linestyle="--" if dashed else "-",
                                     connectionstyle="arc3,rad=0.0"))
        ax.text((x1 + x2) / 2, y + 0.14, label, ha="center", fontsize=7.4, color="#1b2a38")
    ax.set_xlim(-6, 106)
    ax.set_ylim(0, top + 1.4)
    ax.axis("off")
    ax.text(50, top + 1.9, title, ha="center", fontsize=9.5, fontweight="bold", color="#1b2a38")
    fig.savefig(HERE / fname, dpi=200, bbox_inches="tight")
    plt.close(fig)


def scenarios():
    sequence(
        ["User", "Orchestrator", "E-Commerce", "Accounting", "Governance", "Audit"],
        [
            (0, 1, "order reconciliation request", "request"),
            (1, 2, "retrieve order + items", "request"),
            (2, 3, "send item totals", "response"),
            (3, 1, "reconciliation result", "response"),
            (1, 4, "policy check (mismatch > threshold)", "request"),
            (4, 1, "allow / escalate decision", "response"),
            (1, 5, "record evidence + decision", "audit"),
            (1, 0, "consolidated recommendation", "return"),
        ],
        "Figure 4 - Scenario A: order and payment reconciliation (proposed workflow)",
        "fig_scenario_a.png",
    )
    sequence(
        ["User", "Orchestrator", "Risk", "Accounting", "Governance", "Audit"],
        [
            (0, 1, "investigate transaction", "request"),
            (1, 2, "flag candidate anomaly", "request"),
            (2, 3, "check financial relationship", "request"),
            (3, 2, "supporting evidence", "response"),
            (2, 1, "confidence + explanation", "response"),
            (1, 4, "risk escalation", "risk"),
            (4, 1, "review / block", "response"),
            (1, 5, "log anomaly + evidence", "audit"),
            (1, 0, "prioritised case for review", "return"),
        ],
        "Figure 5 - Scenario B: transaction anomaly investigation (proposed workflow)",
        "fig_scenario_b.png",
    )
    sequence(
        ["User", "Orchestrator", "Inventory", "E-Commerce", "Governance", "Audit"],
        [
            (0, 1, "inventory risk question", "request"),
            (1, 2, "analyse items / quantities", "request"),
            (2, 3, "request demand context", "request"),
            (3, 2, "product / demand data", "response"),
            (2, 1, "qualified demand indicators", "response"),
            (1, 4, "check information gaps + policy", "request"),
            (4, 1, "declared data-gap limitation", "response"),
            (1, 5, "log gap + assumptions", "audit"),
            (1, 0, "recommendation with caveats", "return"),
        ],
        "Figure 6 - Scenario C: inventory risk analysis (proposed workflow; data-limited)",
        "fig_scenario_c.png",
    )
    sequence(
        ["User", "Orchestrator", "E-Commerce", "Governance", "Audit"],
        [
            (0, 1, "request a restricted action", "request"),
            (1, 2, "propose action", "request"),
            (2, 3, "submit for policy validation", "request"),
            (3, 1, "REJECT / ESCALATE + reason", "risk"),
            (1, 4, "record rejection reason", "audit"),
            (1, 0, "action refused, alternative offered", "return"),
        ],
        "Figure 7 - Scenario D: governance rejection (proposed workflow)",
        "fig_scenario_d.png",
    )


def main():
    architecture()
    status_matrix()
    governance_lifecycle()
    scenarios()
    print("Figures written to", HERE)


if __name__ == "__main__":
    main()
