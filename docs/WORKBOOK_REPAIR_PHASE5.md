# Workbook repair, phase 5: balance-sheet recovery

GBDC's physical page 3 is titled `Consolidated Statements of Financial Condition`.
That title was missing from the balance-sheet aliases. Parsing began at `Assets`,
after the reporting dates, and rejected the statement for having no periods.
Both the old and the original new workbook therefore omitted the balance sheet.

## Repair

Singular and plural financial-condition titles now identify a balance sheet in
page selection and parsing. Statement ownership changes only at a standalone
heading or an explicit page-plan hint. A cash reconciliation's narrative reference
to the financial-condition statement must not switch it into the balance sheet.

Recognizing the title alone was insufficient: the selected Camelot grid combines
labels with amounts and merges several adjacent rows. The PDF's native ruled
table preserves the complete wrapped preferred/common-stock labels. A bounded
display recovery now uses those cells and their coordinates, collapsing currency
and spacer cells into one stable amount column per source date.

The `Balance Sheet` tab retains:

- June 30, 2026 in column B and September 30, 2025 in column C.
- The `(unaudited)` note under the June 2026 date only.
- The source unit note, including the share/per-share exception.
- Full stock disclosures, including authorization and outstanding-share counts
  within the labels, separate from the reported stock amounts.
- Source dashes, two-decimal NAV, section headings, totals and the notes reference.

The existing cash-flow renderer now also handles these dated balance-sheet grids.
Cash-flow contents, formatting and dimensions are unchanged. No freeze panes are
created on any worksheet.

## Recovery checks and limits

Recovery requires one unambiguous balance-sheet page with a complete ruled body,
distinct source dates above its amount columns, and a reliably bounded source
body from Assets to the notes reference. Each cell must fit within one logical
column and agree with the independently extracted words in its bounding box.
Amount cells must contain a single value or an explicit missing token. Every
body token, including wrapped label details and repeated values, must be present
with the same multiplicity as the page text. This checks text below the detected
table as well as inside it.

Missing dates, lost cells/rows, conflicting words, crossed columns, incomplete
period cells, multi-page statements and ambiguous ownership retain the original
grids and issue an explicit `Balance sheet layout` warning on Review. This
recovery does not claim general support for unruled or multi-page balance sheets.
Raw extraction records and method selection are unchanged. Existing analytical
parsing remains separate from the recovered display; broader validation belongs
to phase 6.

## GBDC acceptance

Reran physical PDF pages 3-9 against the frozen source, then checked every
balance-sheet label and amount against the independent phase-1 transcription.

- All **31 financial rows and 59 numeric values** match, in source order.
- No missing, changed, excess duplicate, unstructured or extra-label rows.
- Every amount remains in its date column and every source total is emphasized.
- Investment, asset, debt, liability and net-asset subtotals reconcile.
- NAV equals net assets times 1,000 divided by shares, rounded to two decimals.

Amounts below are in the source's thousands:

| Date | Assets | Liabilities | Net assets | Difference |
|---|---:|---:|---:|---:|
| June 30, 2026 | 8,339,566 | 4,634,697 | 3,704,869 | 0 |
| September 30, 2025 | 8,978,299 | 4,995,732 | 3,982,567 | 0 |

Income, cash flow, equity, investment schedule and all four raw/experimental tabs
have unchanged cell values, types, formats, merges and dimensions relative to
phase 4. The schedule's automatic name changes from `Statement 4` to `Statement 5`
because the recovered balance sheet adds a worksheet. All raw extraction records
also match the phase-2 saved records exactly. Every worksheet has no freeze panes.

Across the full selected source, the comparator matches **255 financial rows and
720 numeric values**. Its exit code remains 1 for the previously documented
income-label diagnostic and two cash explanatory footnotes matched as financial
labels. Those diagnostics are unchanged; they do not indicate a missing amount.
Phase 6 addresses broader review/validation, and phase 7 remains final acceptance.

The program's existing analytical audit still marks the balance-sheet equation
`NOT_TESTED`: its corporate-equity mappings do not recognize these fund net-asset
totals. It also reports duplicate mapped concepts and a footer alignment warning.
The reconciliations above were executed independently on the recovered workbook
cells; they are not claims that those internal audit limitations are fixed.
These mapping/review limitations are recorded for phase 6.

## Evidence

Workbook:
`outputs/GBDC-phase5-verified-pages-3-9/FY26_10Q_Golub_Capital_BDC_Inc_and_Subsidiaries.xlsx`

Evidence directory: `outputs/GBDC-phase5-verified-comparison/`:

- `comparison.md` / `comparison.json`: source comparisons and frozen file hashes.
- `acceptance.json`: complete coverage, date assignments, reconciliations,
  preservation checks and workbook hash.
- `balance-provenance.json`: recovered cells and original PDF coordinates.
- `balance-top.png` / `balance-bottom.png`: visually reviewed workbook renders.

Local acceptance script: `tmp/repair-phase5/verify_acceptance.py`.

Validation: **343 tests passed**, including 13 new balance-sheet cases. Ruff,
dependency consistency and source/wheel builds passed. Phase-specific diffs were
reviewed against copies taken before phase 5 to preserve existing uncommitted work.
