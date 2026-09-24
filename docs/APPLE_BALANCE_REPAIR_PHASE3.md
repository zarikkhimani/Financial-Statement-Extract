# Apple balance sheet repair: phase 3

Verified the full source-based balance-sheet presentation and corrected monetary
unit classification. The current workbook is
`outputs/apple-phase3-pages-32-36/FY25_10K_Apple_Inc.xlsx`.

## Unit correction

The classifier previously searched the entire caption for thousands before
millions. Apple's caption says amounts are in millions but share counts are in
thousands, so the exception incorrectly determined the monetary metadata.

`normalization.classify_unit_note` now classifies the main clause before
`except`. It preserves the exception separately and records an explicit
share-count scale where stated. Conflicting primary scales remain unknown rather
than being resolved by keyword priority. Unspecified share units are not inferred.
`statements.py` retains this metadata in each statement's attributes.

Apple's balance and income statement metadata now identify monetary amounts in
millions and explicit share counts in thousands. Raw source captions and numeric
values are unchanged; no values are multiplied or divided. Existing per-share and
par-value exceptions remain explicit in the caption/exception metadata. The
reported statement scale is not an instruction to rescale every cell.

## Presentation and evidence

- All 27 balance-sheet rows and 54 amounts still match the frozen source.
- The full September 27, 2025 and September 28, 2024 headings are literal text.
- The complete units note is visible, including its share-count and par-value
  exceptions. The common-stock description retains both source lines' content.
- All eight totals have bold emphasis; all four negative amounts retain
  parentheses. Currency signs remain number formatting rather than extra columns.
- Three blank top rows, two width-1 left columns, no merged cells, no hidden
  rows/columns and no freeze panes remain verified on every tab.
- All eight statement/raw worksheets retain identical values, styles, row heights
  and column widths from phase 2. Their worksheet XML is also unchanged, so the
  visually reviewed phase-2 balance preview remains an exact presentation reference.
- GBDC pages 3-9 were rerun. All 15 `xl/` workbook parts are byte-identical to the
  phase-2 regression output; the existing source-comparison acceptance is preserved.
- The frozen phase-1 evidence hashes remain unchanged.

`units.json`, `comparison.json` and `acceptance.json` accompany the new output.

## Validation and limits

Eleven new cases cover mixed-scale captions, aliases, missing/conflicting primary
units, explicit versus unspecified share scales, metadata propagation, and
unchanged reported numeric values. The full suite produced 401 passes and two
UI keyboard-focus failures. Rerunning the entire UI accessibility file in
isolation passed all 25 tests, including both failures; no UI code was changed.
Ruff and whitespace checks passed.

The false millions-versus-thousands mismatch is resolved. Overall unit consistency
correctly remains NOT_TESTED because the separate equity statement has no known
unit metadata. Other Apple statement extraction warnings are not resolved by this
balance-sheet phase. Stronger handling of incomplete exports remains phase 4.
