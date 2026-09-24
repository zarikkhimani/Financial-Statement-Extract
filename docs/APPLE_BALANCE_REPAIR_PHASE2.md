# Apple balance sheet repair: phase 2

Recovered the complete balance sheet from physical PDF page 34. The output for
pages 32-36 is `outputs/apple-phase2-pages-32-36/FY25_10K_Apple_Inc.xlsx`.

## Change

Apple's horizontal shading produces full-width detected cells containing both
the description and both amounts. The existing recovery expected those cells to
fit within distinct amount-column boundaries, so it rejected the page and left
the incomplete selected table as the displayed balance sheet.

`financial_statement_extract/balance_layout.py` now recognizes this geometry and
uses independently dated header underlines to establish non-overlapping amount
columns. Physical row boundaries retain wrapped descriptions; word coordinates
assign amounts and currency symbols to their source dates. Share counts and par
value in the description remain label text. Whole-width section headings remain
separate rows. No company names, dates or amounts are hardcoded into recovery.

The new path checks detected cell text against positioned source words, rejects
missing/ambiguous amounts and crossing column boundaries, and compares the full
source body's token multiplicity. It reuses the existing source-grid writer.
Ordinary cell-based recovery retains its previous checks. Body-boundary detection
now accepts both `Assets` and `ASSETS:`.

## Verification

- Apple: all 27 financial labels and 54 amounts match the frozen reference in
  source order. All 15 missing rows and 30 amounts are restored.
- All eight section/disclosure rows and the source footnote are preserved.
- All 18 source arithmetic controls also pass against the exported cells.
- Other Apple statement and raw tabs retain their cell values and formatting.
- All tabs preserve the spacing, width, no-merge, no-hide and no-freeze rules.
- Rendered the complete balance sheet and reviewed the resulting image.
- Full suite: 392 tests passed. Seven new tests exercise successful recovery,
  missing dates, crossing words, missing amounts, duplicate amounts, changed cell
  text and a truncated source table. Ruff and whitespace checks passed.
- GBDC pages 3-9: independent source comparator still passes all 255 rows and
  720 amounts. A run with the saved pre-phase-2 balance module and a run with the
  repaired module produce identical `xl/` workbook parts, including raw tabs.

An older GBDC output differs in the Experiential tab because of changes already
present before this repair. The isolated before/after module comparison prevents
that unrelated difference being mistaken for a phase-2 regression.

## Evidence and remaining work

`comparison.json`, `acceptance.json`, and `balance-preview.png` accompany the
Apple output. GBDC source comparison is in
`outputs/apple-phase2-gbdc-regression/validation/`. The frozen phase-1 manifest
still verifies; its source PDF, workbook, and reference were not modified.

Existing source-grid formatting also resolves the split date headings,
comma-formatted years and missing total emphasis. The source units note is fully
visible. However, analytical unit metadata still labels the mixed
millions/thousands note incorrectly; displayed source amounts are not rescaled.
Phase 3 should verify presentation and correct that metadata distinction.
Other Apple statement warnings and incomplete-output handling remain outside
this phase. Phase 4 still needs the stronger completeness/failure behavior.

The earlier phase-1 glyph warning was a console display issue: the PDF text
contains U+2019 apostrophes. Phase 2 preserves them without replacement. The
frozen reference's raw labels already contain the correct character, so its
declared replacement mapping has no effect and no baseline revision is needed.
