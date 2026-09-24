# Workbook repair, phase 6: source-aware checks and Review

The earlier financial audit read analytical parser frames, even when the workbook
displayed repaired source grids. That left the fund balance sheet and cash flow
untested and produced duplicate-concept warnings for legitimate source sections.
Review displayed only a small selection of extraction warnings and omitted the
financial audit statuses.

## Changes

Recovered balance, cash-flow and equity statements are now audited using the same
source grids that the writer exports. These checks do not alter any statement:

- Both balance-sheet dates compare assets with the sum of liabilities and net
  assets, and independently with the reported combined total. A matching printed
  total cannot conceal an incorrect component sum.
- Cash rollforwards include the separately reported foreign-exchange effect.
  The reconciliation uses its own as-of dates, separately from cash-flow periods.
- Each source-defined equity period checks all five beginning/change/ending
  components and all five movement subtotals.
- Cross-statement source checks require exact dates/durations and matching known
  unit scales. Income's nine-month operating result is compared with the same
  cash-flow period; cash reconciliation components are compared with the same
  balance-sheet date and label. June and September are never paired just because
  they have the same year.
- Every selected, recognized statement page must have a table attached to an
  exported sheet. Supported grids check distinct headings, column widths, row
  classification/provenance lengths, numeric grammar, replacement characters and
  duplicate source positions. Equal values at distinct positions are preserved.
- Supported complete source-text rows are compared with exported labels and
  complete amount vectors, retaining multiplicity. A missing row replaced by an
  equal-value duplicate does not satisfy this check. Wrapped cash labels expand
  only through their explicit source-line references.

Missing/ambiguous totals cannot pass. Blanks and NA/NM are not zero. Explicit
source dashes contribute no movement in movement/component sums; that arithmetic
convention is disclosed in the evidence and never changes the exported cells.
Equation tolerance is one reported unit, stated in each result, rather than a
percentage that grows with balance size. A source row/column integrity failure
prevents source-grid financial checks from reporting a pass.

The legacy analytical lookup now requires exactly one exact mapped concept and a
finite value. It no longer silently chooses the first ambiguous match. Related
or fuzzy mappings do not count as duplicate exact concepts, and the remaining
duplicate warning explains that different sections can legitimately share a
concept. Legacy cross-statement matching uses the complete period label instead
of its year, and does not substitute Cash for Cash and Cash Equivalents.
Unknown unit scales no longer receive a unit-consistency pass.

## Review output

Every exported workbook now has a Review sheet with explicit status, check,
scope and evidence columns. Failed checks precede warnings, untested checks and
passes. The summary counts each status, and explains that arithmetic success is
not proof of complete extraction. Headers are filterable; **nothing is frozen**.
Financial statuses, source coverage and extraction problems are visible. No
reported checks produces `NOT_TESTED`, not a blank clean bill of health.

Raw-candidate coverage diagnostics identify their scope separately from repaired
statement checks. Text-parser diagnostics remain visible and identify that the
exported tables have separate checks. No financial statement or raw sheet is
changed to make a check pass.

The independent development comparator now excludes explicitly explanatory,
merged, amount-free notes beginning with “Includes” or “See Note”. It still checks
numbered rows with amounts, including amounts incorrectly embedded in a merged
label. This removes the two known cash-footnote false positives without hiding
financial rows or changing the frozen reference.

## GBDC acceptance

Re-extracted physical pages 3-9 and exported the final Review presentation.

- All **255 financial rows and 720 numeric values** still match the frozen source
  reference. No missing rows, changed amounts or excess duplicates were found.
- All nine non-Review sheets preserve cell values/types/formats, merges, column
  widths and row heights relative to phase 5. Source grids and raw extraction
  records are identical. All sheets have no freeze panes.
- Review reports **78 passes, 12 warnings and 4 not-tested checks; no failures**.
- Passing results include both balance equations for both dates, two cash
  rollforwards, two cash reconciliation sums, 20 equity component rollforwards,
  20 equity movement subtotals, two income/cash operating-result comparisons,
  ten same-date balance-sheet cash components, seven page-attachment checks,
  five structural checks and four supported text-row coverage checks.
- The June 2026 cash ending balance matches its same-date reconciliation. June
  2025 is explicitly untested because the supplied reconciliation is September
  2025; its year is insufficient evidence for comparison.

The source-row check deliberately still flags the income per-share label that
contains its preceding section heading (39 of 40 exact labels match). The
independent comparator matches its amounts but also retains that presentation
diagnostic, so its exit status remains 1. No source label was changed in phase 6.

The other warnings concern text-only parser passages, an ambiguous exact income
concept and raw candidate quality/coverage. They are visible limitations, not
newly changed statement values. The two schedule page row-coverage checks and
the full-portfolio check remain untested. Source-text coverage can miss wrapped
rows and omissions in PDF text extraction; it is not the independent 255-row
acceptance oracle. Phase 7 still covers broader final acceptance and other source
examples. This phase does not claim universal support for all financial layouts.

## Evidence and validation

Accepted workbook:
`outputs/GBDC-phase6-final-pages-3-9/FY26_10Q_Golub_Capital_BDC_Inc_and_Subsidiaries.xlsx`

Accepted evidence: `outputs/GBDC-phase6-acceptance/`:

- `comparison.md` / `comparison.json`: frozen-source comparison and input hashes.
- `acceptance.json`: preservation checks, coverage, status counts and file hash.
- `review-checks.json`: every displayed review result.
- `review-top.png` / `review-checks.png`: visually inspected Review previews.
- `phase6-existing-files.diff`: phase-specific changes to existing runtime files.

Local acceptance script: `tmp/repair-phase6/verify_acceptance.py`.
Other phase-6 comparison/output directories are development runs.

Regression tests include missing/duplicate/blank totals, invalid or shifted cells,
missing provenance, repeated source positions, equal-value legitimate repeats,
FX rollforwards, unmatched periods, mismatched scales, equity movement errors,
missing selected pages, equal-total row substitutions, safe literal output and
the no-freeze rule. Review expectations for existing PDF/HTML/text exports were
updated without relaxing their financial-sheet checks.

The full suite contains **367 passing tests**, including 24 new validation cases.
Ruff, dependency checks and source/wheel builds passed. Existing runtime diffs
were reviewed against pre-phase-6 copies; unrelated uncommitted work remains.
