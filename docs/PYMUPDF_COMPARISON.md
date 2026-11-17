# Optional PyMuPDF comparison

Install inside the project's environment:

```powershell
.\.venv\Scripts\python.exe -m pip install --editable ".[pymupdf]"
```

PyMuPDF uses AGPL or commercial licensing; it is an optional extra, not a
required dependency. See its [license documentation](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright).

The comparison now requires PyMuPDF 2.1 or newer. Version 2 includes additional
layout dependencies, so this optional installation is larger than the original
1.28.2 trial below. The comparison still uses only text and table reading.

Use the supported CLI:

```powershell
.\.venv\Scripts\python.exe -m financial_statement_extract "C:\Filings\filing.pdf" --pages "32-36" --output-dir "output\pymupdf" --compare-pymupdf
```

Or pass `compare_pymupdf=True` to `financial_statement_extract.extract_filing`.
The option requires PDF input and the optional dependency. Missing dependencies
fail clearly before page detection. The GUI continues to use the default path;
this option is currently available through the CLI and Python API.

The comparison runs on the resolved page selection after preflight review. It
extracts PyMuPDF text and runs both `lines` and `text` table strategies. It adds:

- `PyMuPDF`: literal line-strategy table grids.
- `PyMuPDF Text`: literal text-strategy table grids.
- `PyMuPDF Review`: extraction findings, per-page numeric token comparisons and timings.

Each raw table records its source page and strategy. The Python result's
`pymupdf_comparison` dictionary contains `version`, `raw_text_rows`,
`raw_table_cells`, `normalized_table_cells`, `metrics`, `timings`, and `audit_rows`.
Cell and table bounding boxes remain available in these records. Empty cells,
dashes and raw strings stay literal. No source spans become Excel merges.

Comparison cells are never selected for baseline statements, layout repair,
fallback selection or financial checks. Findings requiring review also appear
on the main `Review` sheet. The existing PDFPlumber experiment is separate.
Page errors are recorded explicitly; file-open errors propagate. No OCR is run.

For a local workbook plus JSON report and three alternating text timing runs:

```powershell
.\.venv\Scripts\python.exe scripts\compare_pymupdf.py "C:\Filings\filing.pdf" --pages "32-36" --output-dir "output\pymupdf"
```

Numeric token recall compares multisets with PDFPlumber's page text, including
dates and footnotes. Repeated amounts count repeatedly. This reference is not
independent ground truth, and the metric does not verify signs, row labels,
period alignment or financial accuracy. It measures raw extraction candidates;
the baseline's later layout repairs are excluded. Both strategies remain separate rather
than combining their tokens. Inspect the source and actual grids before choosing
an engine. More extracted rows can mean blank rows or false table detections.

Table timings are one-pass diagnostic measurements. Baseline table timings
include each extractor's document-opening costs; PyMuPDF strategies share an
open document and exclude its opening. The separate text benchmark includes
open/close and normalization for each engine on the identical selected pages.
Its median is not an end-to-end or full-document speedup.

## Initial local trial, October 7, 2026

PyMuPDF 1.28.2 was compared with the existing pipeline on these physical pages:

| Filing | Pages | PDFPlumber text median | PyMuPDF text median | Text speedup |
| --- | --- | --- | --- | --- |
| Apple FY2025 10-K | 32-36 | 0.375s | 0.097s | 3.9x |
| Ares Capital FY2025 10-K | 119-122,271-273 | 1.654s | 0.131s | 12.6x |

These are selected-page, warm-cache text benchmarks, not total extraction times.
Raw numeric token recall against PDFPlumber page text was:

| Filing | Raw PDFPlumber tables | PyMuPDF lines | PyMuPDF text |
| --- | --- | --- | --- |
| Apple | 84.0% | 43.4% | 93.2% |
| Ares Capital | 94.7% | 94.7% | 96.4% |

The line strategy found no tables on Apple pages 32, 33 and 35. On Apple's
balance sheet, it still put entire rows into one cell, including `Total assets`
and both amounts. The text strategy found more numeric tokens but split labels
and introduced extra physical columns. On Ares page 121, its first schedule row
split `ACP Avenu Midco LLC` and placed adjacent currency symbols with amount
cells; the line strategy preserved the principal, cost and fair-value positions.
The reviewed source values were 13.2, 13.0 and 13.2, respectively. Apple's
reviewed total assets were 359,241 and 364,980.

The trial supports investigating PyMuPDF for faster text scanning. It does not
justify replacing the table pipeline globally. Source inspection was limited
to sample rows on Apple page 34 and Ares pages 119 and 121; the workbooks have
not received complete financial reconciliation. The Ares baseline still reports
a balance-sheet completeness failure, and both filings retain existing warnings
and untested checks. Numeric recall is not a measure of final workbook accuracy.

Local workbooks and JSON diagnostics are under `output/pymupdf-trial/apple/`
and `output/pymupdf-trial/arcc/` (ignored by Git). All 12 Apple and 13 Ares
worksheets were checked for the required blank margins, visibility, no merged
cells and no freeze panes. The complete suite passed 447 tests; Ruff,
dependency checks and source/wheel builds also passed.
