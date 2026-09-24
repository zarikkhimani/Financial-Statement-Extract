# Workbook repair, phase 3: cash flow

The selected Camelot table on physical PDF page 7 begins at the cash
reconciliation, below three supplemental financial rows. The text extraction
contains those rows. Merely restoring the older analytical presentation would
lose the reconciliation total and mislabel its dates.

Phase 3 assembles cash-flow display blocks from complete source text on pages
unambiguously assigned to cash flow. Each block retains its own explicit source
period headings, labels, numeric tokens, and page/line provenance. It does not
replace the analytical concept mapper or modify raw extraction candidates.

## Changes

- Recover the cash interest, distributions declared, and dividend-reinvestment
  stock disclosures that were above the selected reconciliation table.
- Preserve the main and supplemental nine-month periods separately from the
  reconciliation's June 30, 2026 and September 30, 2025 dates.
- Join the wrapped reconciliation-total label without mistaking its reference
  to the cash-flow statement for a new statement heading.
- Export a readable `Cash Flow` tab with one description and two amount columns,
  emphasized totals and sections, full headings, source footnotes, and wrapped labels.
- Preserve zero versus missing amounts, parentheses, currency and percentage formats.

## Bounds and failure behavior

The recovery requires an unambiguous PDF cash-flow page and explicit standalone
year/date headings. It stops at the notes boundary, preserves genuine repeated
rows, and checks that every amount vector in each selected table is retained
with at least the same multiplicity. Overlapping extraction candidates are checked
individually, not added together.

Conflicting amounts, unresolved numeric lines, missing headings, or ambiguous
page ownership keep the original grids for the entire cash-flow statement and
produce an explicit `Cash flow layout` warning, including in the Review tab.
The recovery does not silently assign guessed periods or replace unresolved
numbers with prose. This is bounded recovery for supported text layouts, not a
claim that every possible cash-flow PDF is supported.

Raw coverage warnings still measure raw table extraction. Phase 6 will address
broader review reporting; this phase does not redesign that system or change
analytical DataFrame period mapping.

## GBDC acceptance

Reran the frozen PDF on physical pages 3-9. On cash-flow pages 6-7:

| Check | Result |
|---|---:|
| Financial rows matched | 49 of 49 |
| Numeric values matched | 93 of 93 |
| Missing, changed or excess duplicate financial rows | 0 |
| Main cash-flow financial rows | 40 |
| Supplemental financial rows | 3 |
| Cash reconciliation financial rows | 6 |

Restored values, in thousands:

| Disclosure | Nine months ended June 30, 2026 | Nine months ended June 30, 2025 |
|---|---:|---:|
| Cash paid during the period for interest | 171,335 | 199,922 |
| Distributions declared for the period | 275,083 | 335,228 |
| Stock issued in connection with dividend reinvestment plan | — | 33,704 |

Every financial row's source label and local period assignment was checked
independently in the saved workbook. The reconciliation components sum to
70,663 and 112,443 for their respective dates. The cash-flow rollforwards end
at 70,663 and 178,773 for their respective nine-month periods; these distinct
2025 balances were not conflated.

The income, equity, investment schedule, Lattice, Stream, PDFPlumber and
Experiential sheets retain phase-2 cell contents and cell formatting. The
investment schedule remains at 93 investment rows and three subtotals.

## Evidence and checks

Accepted workbook:
`outputs/GBDC-phase3-verified-pages-3-9/FY26_10Q_Golub_Capital_BDC_Inc_and_Subsidiaries.xlsx`

Evidence directory: `outputs/GBDC-phase3-verified-comparison/`:

- `comparison.md` and `comparison.json`: frozen-baseline comparison.
- `acceptance.json`: per-row period assignments, checks, workbook hash and limitations.
- `cash-flow-provenance.json`: complete display blocks and source line references.
- `cash-top.png`, `cash-supplemental.png`, `cash-reconciliation.png`: visually reviewed exports.

Local acceptance script: `tmp/repair-phase3/verify_acceptance.py`.
Earlier phase-3 output directories are development runs.

All 320 project tests passed, including 12 new cash-flow regression cases.
Ruff, dependency checks, and source/wheel builds passed. The frozen baseline
passed integrity checks. Final scope review compared modified files with copies
taken immediately before phase 3, preserving pre-existing uncommitted work.

The broad baseline label matcher flags two explanatory footnotes as unexpected
rows/extra label text because they mention cash. Both were checked verbatim
against the PDF; neither contains amount cells. They are retained source notes,
not extra financial rows. This comparator limitation remains visible in the
report and is recorded explicitly in the acceptance result.

The overall comparison still reports differences: the balance sheet is missing,
equity component headings/alignment need repair, and earlier minor presentation
issues remain. Phase 4 addresses equity; phase 5 addresses the balance sheet.
