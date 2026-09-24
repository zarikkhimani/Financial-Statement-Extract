# Apple balance sheet repair: phase 6 — final acceptance

Final workbook:
`outputs/apple-phase6-pages-32-36/FY25_10K_Apple_Inc.xlsx`

The balance-sheet repair has passed final regression and delivery checks. No
additional production-code changes were necessary in this phase.

## Final runs

- Re-extracted pages 32–36 from the user's original Desktop `apple.pdf`. Its
  SHA-256 matches the frozen phase-1 source.
- Independently verified all 27 balance-sheet rows, 54 amounts and 18 exact
  arithmetic equations from the saved Excel cells. Both dates and all source
  section/disclosure labels are present. Monetary units remain millions, share
  counts thousands, and no amounts are rescaled.
- Repeated extraction with all table methods enabled. All four financial
  statement tabs remain identical to the normal adaptive run; the balance sheet
  independently passes the same source/amount/arithmetic acceptance checks.
- Built both source and wheel distributions. Ran the wheel's CLI in an isolated
  Python process that imports the application from the wheel, then independently
  validated that workbook. Its nine sheets match the normal run's cell content,
  styles and dimensions.
- Reran GBDC pages 3–9. All 255 financial rows and 720 amounts still match the
  frozen reference. All 15 `xl/` workbook parts are byte-identical to phase 5.
- Forced balance-layout recovery to fail through the real extraction path. The
  resulting assets-only sheet contains the original 12 rows and misses the
  original 15 rows. The balance sheet, Review tab and app headline all explicitly
  say INCOMPLETE BALANCE SHEET; the completeness check is FAIL.

## Preservation and visual review

All nine final Apple sheets retain phase-5 content, types, styles, row dimensions
and column dimensions, including Review. The full balance sheet and all 18
arithmetic checks were rendered and visually inspected. The long common-stock
description, full units caption, dates, four parenthetical negatives, subtotals,
liabilities/equity sections and closing note are readable.

Every sheet in all five generated workbooks passes the standing workbook rules:
three blank top rows; two blank left columns at Excel width 1; no merged cells;
no hidden or collapsed rows/columns, zero dimensions or hidden sheets; no freeze
panes. Excel's stored width includes padding, so XlsxWriter's width 1 is serialized
as 1.7109375.

## Validation and evidence

- Full suite: **442 passed**.
- Ruff: passed across application, scripts and tests.
- Dependency consistency: passed.
- Source/wheel builds and isolated packaged CLI extraction: passed.
- Frozen Apple and GBDC evidence integrity: passed.

The final output folder contains `independent-validation.json`, `acceptance.json`,
`result-checks.json`, `balance-preview.png`, `arithmetic-preview.png` and a
`manifest.json` recording workbook/evidence and relevant runtime-source hashes.
Local verification runners are `tmp/run_apple_phase6.py`,
`tmp/verify_apple_phase6.py`, and `tmp/apple_phase6_wheel_smoke.py`.
The independent acceptance command remains:

```powershell
.\.venv\Scripts\python.exe -m scripts.validate_apple_balance `
  outputs/apple-balance-baseline-20260921 `
  outputs/apple-phase6-pages-32-36/FY25_10K_Apple_Inc.xlsx
```

## Scope of completion

The Apple balance-sheet repair is complete. This does not certify the other Apple
statements or universal support for all PDF layouts. The app correctly still
says review required: its overall result has 45 passes, 14 warnings, zero
failures and 90 not-tested/unknown checks. Existing non-balance-sheet extraction
and unknown-unit warnings remain visible. Unsupported balance-sheet layouts
remain explicitly unverified rather than receiving a false completeness pass.
