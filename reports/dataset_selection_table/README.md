# Dataset Selection and Suitability Analysis

## Contents

- `main.tex`: academic report for Deliverable 1.
- `references.bib`: the bibliography cited by the report.
- `dataset_inventory.csv`: observed local data files and dimensions.
- `data_quality_summary.csv`: per-field missingness, distinct counts, and numeric ranges.
- `primary_key_checks.csv`: candidate single/composite keys, duplicate excess, and missing-key counts.
- `dataset_comparison.csv` and `agent_suitability_matrix.csv`: qualitative decisions and evidence.
- `inspection_summary.json`: machine-readable file inventory and observed relationship checks.
- `scripts/inspect_datasets.py`: standard-library analysis script.

## Datasets found

The project contains nine Olist CSV files in `datasets/olist/` and `datasets/online_retail_ii/online_retail_II.xlsx` (two worksheets). The exact paths and measured sizes/dimensions are in `dataset_inventory.csv`. Source data are read-only to the script; it writes only report artifacts.

## Reproduce inspection

Requires Python 3.9 or newer. The inspector uses only the Python standard library (including `zipfile` and `xml.etree.ElementTree`) and does not require pandas or openpyxl.

From the project root:

```powershell
python reports/dataset_selection_table/scripts/inspect_datasets.py
```

Optional paths:

```powershell
python reports/dataset_selection_table/scripts/inspect_datasets.py --root . --output reports/dataset_selection_table
```

The script scans CSV and XLSX files and inventories JSON files under `datasets/`. XLSX formula results are not recalculated. Type inference and exact duplicate detection are descriptive; see the report for interpretation limits. Existing generated artifacts are retained; rerunning the inspector refreshes them from the local source files.

## Compile LaTeX

The report has been compiled successfully with MiKTeX. It requires `booktabs`, `longtable`, `tabularx`, `hyperref`, `enumitem`, and `microtype`. If a package is missing in another environment, install it with MiKTeX Console or `mpm --install=<package>`. Run from this directory:

```powershell
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

## Licensing status

The UCI Online Retail II page identifies the record, creator, DOI, and CC BY 4.0 license. The Olist Kaggle page verifies dataset title/provider and the nine-file listing; the license field was not independently confirmed from the accessible primary page during preparation. Do not assume unrestricted redistribution; recheck the current Kaggle data card before sharing raw data.

## Limitations

The datasets are analyzed independently and are not record-level merged. They contain transaction evidence, not full stock history, a general ledger, native governance policies, confirmed fraud outcomes, or agent implementation behavior. Olist joins are key-containment checks over distinct values, not proof that every business event is complete.

