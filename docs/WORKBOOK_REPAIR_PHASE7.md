# Workbook repair, phase 7: final acceptance

The GBDC pages 3-9 repair passes the frozen-source acceptance comparison with
exit code **0**. All **255 financial rows and 720 numeric values** match, with no
missing rows, changed amounts, excess duplicates, ordering changes, missing
headings, inconsistent amount columns or remaining extra-label diagnostics.

## Final presentation repair

The source's standalone `Per Common Share Data` heading was being joined to the
following earnings-per-share label. The parser now recognizes `Per Common Share
Data` and `Per Share Data` as section headings. The source wording and note
reference remain on the EPS row, its values retain two decimals, and weighted
average share counts remain integers. A four-period regression test covers this.

This is the only phase-7 runtime change: two lines in the structural-heading
recognizer. No concepts, values, extraction methods or financial checks changed.

## Acceptance evidence

| Statement | Source rows matched | Numeric values matched |
|---|---:|---:|
| Balance sheet | 31 | 59 |
| Income statement | 40 | 152 |
| Cash flow and reconciliation | 49 | 93 |
| Changes in net assets | 39 | 126 |
| Selected investment schedule | 96 | 290 |
| Total | 255 | 720 |

Beyond the comparator's numeric fields, all 93 investment rows were checked for
investment type, interest rate, maturity, spread and its reference marker against
the frozen source text. Mixed cash/PIK text remains in the interest column, and
no PIK suffix appears in maturity. Genuine repeated holdings remain separate.

Both balance-sheet equations, both cash rollforwards including FX, all 20 equity
component rollforwards and movement subtotals, and the supported cross-statement
comparisons still pass. Final Review has **79 passes, 11 warnings, 4 not tested,
and no failures**. Its income source-row check now matches all 40 labels.

Cash flow, balance sheet, equity, schedule and all four raw/experimental sheets
retain their phase-6 contents, types, formats, merges and dimensions. Source
grids and raw extraction records are identical. Only Income's section separation
and the resulting Review diagnostics change. **Every worksheet has no freeze
panes.** Source and frozen-baseline hashes were verified.

Representative views of all five statement sheets and Review were rendered and
visually inspected, including full dates, wrapped stock disclosures, per-share
precision, supplemental cash rows, equity component headers and cash/PIK rates.

## Additional real-file regression checks

Three additional local sources were executed twice: once with the copied
pre-phase-7 parser and once with the final parser. Outputs went to separate local
directories; source files and existing workbooks were untouched. All `xl/`
workbook parts were compared byte for byte, covering cells, shared strings,
styles, worksheet structures and Review.

| Source | Selected scope | Source tables | Changed workbook parts |
|---|---|---:|---:|
| ARCC 2025 annual PDF | Physical pages 119-122, 271-273 | 8 | 0 of 15 |
| ARCC June 2026 quarterly PDF | Physical pages 4, 5, 255, 256 | 4 | 0 of 14 |
| ARCC June 2026 quarterly HTML | Full HTML extraction | 164 | 0 of 11 |

All three executions completed, retained their statement categories, preserved
their source hashes and produced no freeze panes. No phase-7 regression was
found. These are regression checks, not a source-completeness certification.

Existing ARCC limitations remain material:

- The annual PDF's balance-sheet date geometry is unsupported, so original grids
  remain with an explicit warning. Selected schedule page 271 has ambiguous
  ownership and remains available in raw output. Full structured coverage of
  this sample is not established.
- The quarterly PDF still flags wrapped labels and source-token coverage; some
  equity/financial checks lack supported source-defined periods or labels.
- The HTML export still reports ambiguous table cells and analytical mappings.
  Its 164 tables were checked for regression, not exhaustively transcribed from
  source. No claim is made that those layouts are ready for unattended use.

Those limitations existed in the pre-phase-7 outputs and were not hidden or
converted to passing statuses. Wider layout support is separate from acceptance
of the repaired GBDC pages.

## Remaining GBDC review limits

The 11 warnings concern the text-only parser, an ambiguous exact income mapping,
and raw-candidate quality/coverage. The recovered workbook has been independently
checked against the frozen source; those diagnostics remain visible.

The four untested checks cover two schedule-page text-coverage checks, full
portfolio completeness, and the unavailable June 2025 cash reconciliation.
Pages 8-9 are only a partial investment schedule. September 2025 is not substituted
for June 2025. These limits do not disappear when the selected-page comparison
passes.

## Files and validation

Accepted workbook:
`outputs/GBDC-phase7-final-pages-3-9/FY26_10Q_Golub_Capital_BDC_Inc_and_Subsidiaries.xlsx`

Accepted evidence: `outputs/GBDC-phase7-acceptance/`:

- `comparison.md` / `comparison.json`: clean frozen-reference result.
- `acceptance.json`: counts, reconciliations, preservation checks and workbook hash.
- `schedule-field-checks.json`: all 93 rate, spread/reference, type and maturity checks.
- `other-samples.json`: exact scopes, hashes, regressions and remaining limitations.
- Statement/Review PNG previews and `phase7-existing-files.diff`.

Local acceptance scripts are in `tmp/repair-phase7/`. Additional sample outputs
are under `tmp/repair-phase7/samples/` and remain development evidence.

All **368 tests** passed. Ruff, dependency consistency, source/wheel builds and
diff checks passed. Existing uncommitted work was preserved; nothing was pushed.
