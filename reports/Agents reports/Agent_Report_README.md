# Agent Report — Build and Reproduction Notes

`Agent_Report.tex` is the source for **`Agent_Report.pdf`**, the comprehensive
agent design report for the MultiAgentAI-Research project. This directory is
self-contained: it holds the LaTeX source, the bibliography, the figure
generator and the generated figures.

## Contents

| File | Purpose |
| --- | --- |
| `Agent_Report.tex` | Report source (title page, 14 sections, appendix). |
| `Agent_Report.pdf` | Compiled report (26 pages). |
| `references.bib` | Bibliography (dataset sources + agent/governance references). |
| `figures/make_figures.py` | Generates all seven PNG figures with matplotlib. |
| `figures/*.png` | Generated figures (architecture, status matrix, governance lifecycle, scenarios A–D). |
| `Agent_Report.README.md` | This file. |

## Toolchain

- LaTeX: MiKTeX (`pdflatex`, `bibtex`). Uses `hyphenat` (`[htt]`) and the
  standard `longtable`, `tabularx`, `booktabs`, `graphicx`, `hyperref`.
- Python: 3.10.11 with `matplotlib` (figure generation only).

## Regenerating the figures

From this directory:

```powershell
python figures\make_figures.py
```

This writes the seven `figures\fig_*.png` files. The report includes them by
filename only, so the figures directory is where `pdflatex` is run.

## Compiling the report

From this directory, run the standard four-pass sequence:

```powershell
pdflatex -interaction=nonstopmode Agent_Report.tex
bibtex   Agent_Report
pdflatex -interaction=nonstopmode Agent_Report.tex
pdflatex -interaction=nonstopmode Agent_Report.tex
```

Expected result: `Agent_Report.pdf`, 26 pages, **no** undefined references or
citations and **no** overfull boxes. Font-shape warnings of the form
`Font shape 'T1/cmtt/...' undefined` are harmless: the T1 typewriter family
(`cmtt`) has no bold/italic/slanted variants, so LaTeX substitutes. They do not
affect output.

## Source data and evidence

The report is grounded in repository evidence only:

- Raw datasets (read-only, unmodified): `datasets/olist/` (9 CSV tables) and
  `datasets/online_retail_ii/online_retail_II.xlsx`.
- Implemented software: the dataset-analysis package
  `reports/dataset_report/analysis/` and its 13 passing tests
  (`reports/dataset_report/tests/test_analysis.py`).
- The authoritative measured numbers are those of the project's *Dataset
  Report* (`reports/dataset_report/dataset_report.tex`); the agent report
  reproduces them rather than re-deriving them.

## Assumptions and decisions (for reviewer confirmation)

1. **Output location.** The report was placed in `reports/Agents reports/`
   (under `reports/`, matching the existing `reports/dataset_report/` and
   `reports/dataset_selection_table/` convention) using the requested name
   "Agents reports". Spaces in the directory name require quoting on the
   command line.
2. **"Main Report" identification.** No file named literally `Main_Report`
   exists. `reports/dataset_selection_table/main.tex` is treated as the
   project/dataset overview (Deliverable 1) and `reports/dataset_report/`
   as Deliverable 2. This naming discrepancy is recorded as a repository
   finding. Neither was modified.
3. **Implementation status.** The repository contains **no agent
   implementation** — no orchestrator, messaging layer, policy engine or audit
   store. All seven agents are documented as **proposed / not implemented**.
   The only implemented software is the dataset-analysis package, presented as
   the prospective ingestion-and-validation layer.
4. **Figures.** Diagrams are rendered as PNGs by Python/matplotlib to match
   the existing `figures/` convention and avoid new LaTeX package
   dependencies.
5. **No fabrication.** No stock levels, ledger balances, fraud labels,
   policies or audit logs are invented; where the datasets cannot supply an
   item, it is marked absent and assigned to prototype scope.

## Integrity constraints

- Raw datasets must remain unmodified.
- All quantitative claims must trace to the Dataset Report or to the
  implemented package; the agent report adds design/architecture content only.
