# Apple balance sheet repair: phase 1

Phase 1 establishes a source-reviewed reference. No production extraction,
parsing, workbook-writing or application code was changed.

## Preserved evidence

Local evidence is in `outputs/apple-balance-baseline-20260921/`:

- `source.pdf`: unchanged copy of the locally supplied `apple.pdf`.
- `before.xlsx`: unchanged copy of the output for physical PDF pages 32-36.
- `source-page/`: rendered physical page 34 (printed page 31), extracted text
  and word coordinates.
- `expected.json`: all 27 financial rows and 54 amounts, source tokens and line
  references, all eight section/disclosure rows, body order, dates and units.
- `source-controls.json`: 18 independently calculated source checks, all passing.
- `comparison.json`: current missing rows, cell references, formatting findings,
  raw-tab evidence, and existing Review warnings.
- `report.md`: readable findings and complete missing-row list.
- `manifest.json`: SHA-256 hashes for preserved evidence.
- `working-source.zip`, `working-tree.patch`, `comparator.py`: development state
  at phase-1 start. This does not reconstruct historical uncommitted code for
  the original workbook run. Existing user changes were preserved.
- `build_baseline.py`: independent reference construction record. It uses explicit
  reviewed PDF line groups, not the production statement parser.

## Results

| Measure | Source | Current workbook | Missing |
|---|---:|---:|---:|
| Financial rows | 27 | 12 | 15 |
| Monetary amounts | 54 | 24 | 30 |

The current sheet ends at Total assets. All missing rows belong to liabilities
and shareholders' equity. The exported asset amounts match the source; there
are no detected changed amounts or excess duplicate financial rows. All missing
labels are present in the raw PDFPlumber or Experiential tabs, but this does not
certify correct raw-tab parsing or amount placement.

The dates are September 27, 2025 and September 28, 2024. Monetary amounts are in
millions, share counts in thousands, and par value is $0.00001 per share. The
common-stock label spans two lines and contains share counts that must stay
separate from its monetary amounts. The four negative values retain their
parenthetical source tokens. Repeated Marketable securities and Term debt labels
retain distinct row IDs, positions and section context.

Four PDF text lines contain a replacement glyph where the rendered page shows
an apostrophe. Both raw text and the visually reviewed apostrophe are retained
in the reference; no silent source-text replacement occurs.

Source controls cover both periods' current/non-current subtotals, total assets,
total liabilities, equity, liabilities plus equity, and equality with assets.
These checks supplement row-by-row comparison; equal totals alone cannot prove
completeness.

Presentation issues are recorded separately: comma-formatted years, a clipped
units note, separate currency columns, missing total emphasis, and absent lower
sections. All standing workbook rules remain required: three blank top rows,
two width-1 left columns, no merges, no hidden rows/columns and no freeze panes.

## Repeat or evaluate a later candidate

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m scripts.compare_apple_balance_baseline `
  outputs/apple-balance-baseline-20260921 `
  outputs/apple-balance-baseline-20260921/before.xlsx
```

Replace the final path with a later candidate workbook. The command verifies
evidence hashes and reads the candidate without modifying it. Exit 1 is expected
for the preserved incomplete workbook. Exit 0 means no differences detected by
the existing bounded row/layout comparator, not full visual or semantic approval;
exit 2 indicates invalid inputs or changed evidence. Full output is JSON.

This phase covers only Apple's balance sheet on physical page 34. Income,
cash-flow and equity-statement repairs and changes to production behavior belong
to later work. Phase 2 can now be evaluated against an independent reference.
