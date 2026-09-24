# Apple balance sheet repair: phase 4

Incomplete PDF balance sheets now receive an explicit completeness failure in
the workbook and desktop results. The normal output is
`outputs/apple-phase4-pages-32-36/FY25_10K_Apple_Inc.xlsx`.

## Coverage check

`audit_balance_completeness` checks the source tables actually used by the
workbook, including unrecovered fallback grids. A complete analytical DataFrame
or a matching total cannot override missing displayed source content.

The check independently bounds the extracted source text between a unique
Assets heading and the accompanying Notes line. It requires identifiable assets,
liabilities and equity/net assets in both the source and the exported rows, and
checks source-body token coverage with occurrence counts. This includes section
headings, wrapped descriptions, share counts and amounts. Only case, whitespace
and currency-symbol separation are normalized. Repeated content must retain its
source multiplicity; numeric zero is not treated as blank.

Missing content is FAIL. Unsupported, ambiguous or missing source boundaries are
NOT_TESTED, explicitly described as completeness unverified. A missing table on
a selected balance-sheet page is FAIL. On balance-sheet pages this replaces the
older single-line amount coverage check, which excluded unrecovered grids and
could misclassify wrapped labels.

## Workbook and app

- The balance-sheet title retains the original title and adds a prominent red
  INCOMPLETE BALANCE SHEET warning when coverage fails; the tab is red.
- The Review headline and desktop results headline state the same failure.
- Unverified coverage receives a distinct completeness-unverified message.
- Successful coverage checks remain visible in Review. Other warnings and
  unperformed financial checks remain visible and still require review.
- Desktop startup remains lazy; the shared status helper loads only when a
  result is summarized.

## Verification

- Reran Apple pages 32–36: all 27 balance rows and 54 amounts match the frozen
  source reference. All 173 balance-body tokens are covered.
- Forced the actual PDF recovery path to fail. The original fallback exports
  the same 12 asset rows and omits the same 15 liability/equity rows as the
  frozen original. It now fails completeness, identifying both missing sections
  and 106 missing source tokens. Workbook and app warnings were verified;
  balance-sheet and Review previews were rendered and visually inspected.
- The incomplete demonstration is in
  `outputs/apple-phase4-incomplete-demonstration/`, clearly separate from the
  accepted output. Its appended warning changes the exact title cell, so its
  evidence comparison reads the known worksheet directly rather than using the
  baseline comparator's exact-title locator.
- All eight Apple statement/raw tabs retain their phase-3 cell values, styles,
  row dimensions and column dimensions.
- GBDC pages 3–9 still match all 255 reference rows and 720 amounts; all nine
  statement/raw tabs retain their phase-3 content and formatting. Its balance
  passes coverage of all 260 body tokens.
- Three blank top rows, two width-1 left columns, no merged cells, no hidden
  rows/columns and no freeze panes pass on every tab of all three outputs.
- Frozen Apple evidence hashes remain intact. Comparison and acceptance JSON
  accompany the new outputs.
- Added 21 cases covering recovered/fallback grids, missing sections/details,
  duplicated replacements, wrapped shares, zeros, unsupported source boundaries,
  missing sheets and workbook/app status presentation. Final full suite:
  **424 passed**. Ruff and whitespace checks pass.

## Limits and next phase

This is a content-coverage check. It does not certify amount-to-label/period
alignment, row order, surplus duplicates or arithmetic; those require separate
checks and the independent row/amount and arithmetic validation in phase 5.
Unbounded or continued balance-sheet layouts remain unverified rather than
receiving a false completeness pass. Existing non-balance-sheet extraction and
unknown-unit warnings are outside this phase.
