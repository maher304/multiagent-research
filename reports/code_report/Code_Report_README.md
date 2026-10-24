# Code Report — Build and Reproduction Notes

`Code_Report.tex` is the source for **`Code_Report.pdf`**, the evidence-based
software implementation report for the MultiAgentAI-Research project. This
directory is self-contained: it holds the LaTeX source, the bibliography, the
figure generator and the generated figures.

## Contents

| File | Purpose |
| --- | --- |
| `Code_Report.tex` | Report source (title page, abstract, glossary, 19 sections, appendix). |
| `Code_Report.pdf` | Compiled report (32 pages). |
| `references.bib` | Bibliography (dataset sources + software documentation + agent/governance/data-quality references; 28 entries, all cited). |
| `figures/make_figures.py` | Generates all six PNG figures with matplotlib. |
| `figures/fig_*.png` | Generated figures (repository architecture, execution workflow, data pipeline, agent interaction, governance/audit, testing workflow). |
| `Code_Report_README.md` | This file. |

## Toolchain

- LaTeX: MiKTeX (`pdflatex`, `bibtex`). Uses `hyphenat` (`[htt]`) and the
  standard `booktabs`, `longtable`, `tabularx`, `float`, `hyperref`.
- Python: 3.10.11 with `matplotlib` (figure generation only).

## Regenerating the figures

From this directory:

```powershell
python figures\make_figures.py
```

This writes the six `figures\fig_*.png` files. The report includes them by
filename only (`\graphicspath{{figures/}}`), so the figures directory is where
`pdflatex` is run.

## Compiling the report

From this directory, run the standard four-pass sequence:

```powershell
pdflatex -interaction=nonstopmode Code_Report.tex
bibtex   Code_Report
pdflatex -interaction=nonstopmode Code_Report.tex
pdflatex -interaction=nonstopmode Code_Report.tex
```

Expected result: `Code_Report.pdf`, 32 pages, **no** undefined references or
citations, **no** errors and **no** overfull boxes above 3 pt. Font-shape
warnings of the form `Font shape 'T1/cmtt/...' undefined` are harmless: the T1
typewriter family (`cmtt`) has no bold/italic/slanted variants, so LaTeX
substitutes an upright shape. They do not affect output.

Two LaTeX pitfalls are already handled in the sources (kept here so they are
not reintroduced):

- A literal `%` inside `\code{...}` starts a comment; the report writes
  `\code{float\_format="\%.6g"}` with an escaped `\%`.
- BibTeX's `plain.bst` re-cases `@article`/`@misc`/`@techreport` titles, so
  every title in `references.bib` is wrapped in double braces
  (`title = {{...}}`) to keep proper names such as `Sarbanes--Oxley`,
  `Online Retail II`, `ISO/IEC 42001` and `NumPy` intact.

## Source data and evidence

The report documents only what exists in the repository:

- Repository inspection: 2,144 lines of Python across 11 files, 65 functions,
  **0 classes**; empty `src/`; zero-byte root `README.md`.
- Implemented software: the dataset-analysis package
  `reports/dataset_report/analysis/` (7 modules, `python -m analysis` entry
  point), its 13 passing tests (`reports/dataset_report/tests/test_analysis.py`),
  the stdlib inspector `reports/dataset_selection_table/scripts/inspect_datasets.py`,
  and the figure generators.
- Verified during preparation of this report: `python -m pytest tests -q`
  → `13 passed in 1.49s`; `python -m analysis` → all 27 artifacts in
  `analysis_results/` reproduced byte-identical (SHA-256); defect D2
  (`csv.Sniffer` dialect → 99,250 vs 99,224 review rows) reproduced in
  Appendix A.3.
- Companion reports (`main.tex`, `dataset_report.tex`, `Agent_Report.tex`)
  were read for cross-reference only and were not modified.

## Assumptions and decisions (for reviewer confirmation)

1. **Output location.** The report was placed in `reports/code_report/`
   (under `reports/`, matching the `reports/dataset_report/` and
   `reports/dataset_selection_table/` convention).
2. **"Main Report" identification.** No file named literally `Main_Report`
   exists in the repository. `reports/dataset_selection_table/main.tex` is
   treated as the project/dataset overview and is cited as such; the
   discrepancy is recorded as a repository finding. It was not modified.
3. **Implementation status.** All seven conceptual agents are classified
   **designed but not implemented** from repository evidence (zero class
   definitions, empty `src/`). No agent, performance or fraud-detection figure
   is fabricated.
4. **Figures.** Diagrams are rendered as PNGs by Python/matplotlib to match
   the existing `figures/` convention of the sibling reports and to avoid new
   LaTeX package dependencies.
5. **Citations.** Every bibliography entry is cited in the text; all URLs
   resolved at the time of writing; no citation, author, year, DOI or URL was
   invented.

## Integrity constraints

- Raw datasets remain read-only: `datasets/olist/` (9 CSV tables) and
  `datasets/online_retail_ii/online_retail_II.xlsx`.
- Only `reports/code_report/` was created for this deliverable; no source file
  or sibling report was altered.
- Every implementation claim in the report carries a file path, a symbol name
  or a measured command output; anything not verifiable is labelled as such
  (see the report's glossary for the status vocabulary).
