# Apple balance sheet repair: phase 5

Added corporate balance-sheet arithmetic and independently validated the saved
workbook against the frozen phase-1 source reference. Current output:
`outputs/apple-phase5-pages-32-36/FY25_10K_Apple_Inc.xlsx`.

## Checks in the program

The recovered-grid audit previously recognized total net assets, leaving Apple's
shareholders' equity untested. It now recognizes explicit equity captions and
checks nine equations per date:

- Current and non-current asset component sums.
- Current and non-current liability component sums.
- Total assets and total liabilities from their reported subtotals.
- Total equity from its source-defined components, including negative balances.
- Reported liabilities plus equity against its components.
- Total assets against reported liabilities plus equity.

Components come only from uniquely bounded source sections. Missing/duplicate
headings or totals, nested subtotals, unavailable amounts and competing equity
totals remain NOT_TESTED. Share counts embedded in descriptions are never added
as monetary amounts. The existing BDC/net-assets checks remain unchanged.

These 18 checks now appear in the workbook's Review tab and in the app's checks.
They retain the existing production tolerance of one reported unit. All Apple
differences are exactly zero; no tolerance was needed for this acceptance.

## Independent saved-workbook validation

`scripts/validate_apple_balance.py` imports no production extraction, parsing,
normalization, recovery or auditing code. It verifies every frozen evidence hash,
including the independent arithmetic controls, before reading the workbook.

The existing source comparator checks all 27 rows and 54 amounts, repeated-label
multiplicity, source order and basic layout. The new validator separately binds
source line groups to saved Excel rows by label occurrence, verifies literal full
dates over the amount columns, and calculates all 18 controls from numeric Excel
cells using exact decimal arithmetic. It records the input and total cell
addresses. It does not reuse the reference's precomputed arithmetic results.
Formulas, missing values, ambiguous row associations and misplaced date columns
cannot silently pass.

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m scripts.validate_apple_balance `
  outputs/apple-balance-baseline-20260921 `
  outputs/apple-phase5-pages-32-36/FY25_10K_Apple_Inc.xlsx
```

Exit 0 means the bounded checks pass; 1 means differences or unverified checks;
2 means invalid inputs/evidence. The command is read-only and prints JSON.

## Results

- 27/27 rows and 54/54 amounts match the independent source reference.
- Both full dates are correctly positioned; all 18 saved-cell calculations pass
  exactly. Total assets and liabilities plus equity are 359,241 for 2025 and
  364,980 for 2024, in the source's reported millions.
- Six deliberately damaged workbook copies were rejected: missing detail,
  duplicate replacing detail, offsetting amount errors, lost negative sign,
  swapped amount periods and swapped date headings. The offsetting-error case
  passes all arithmetic equations but fails the row/amount comparison, proving
  the two checks provide different evidence.
- The original incomplete workbook is rejected with its 15 missing rows.
- All eight Apple statement/raw tabs retain phase-4 content, styles and
  dimensions; only Review diagnostics changed. All standing workbook rules pass.
- GBDC pages 3–9 were rerun; all 15 `xl/` parts are byte-identical to phase 4.
- Added 18 tests for corporate arithmetic, ambiguous/missing sections, equity
  aliases, saved-cell arithmetic, period placement and evidence integrity.
  Full suite: **442 passed**. Ruff and whitespace checks pass.

`independent-validation.json`, `balance-arithmetic.json` and `acceptance.json`
accompany the new workbook. The frozen evidence remains unchanged.

## Remaining scope

This acceptance covers Apple's balance sheet, not the other Apple statements.
Their existing extraction/unknown-unit warnings remain visible, so the overall
app result still requires review. Phase 6 final regression/delivery remains the
next phase; the user's initial phase-6 request was corrected to phase 5.
