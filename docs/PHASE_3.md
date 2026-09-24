# Phase 3: source tables, equity output, and adaptive PDF extraction

## Implemented behavior

- Selected source grids now drive Excel presentation. Each table keeps its own source title, captions, column positions, headers, and order. Different schedule schemas or dates remain separate blocks instead of being forced into one shared value-column layout.
- HTML colspan/rowspan positions are preserved. Empty spacing rows are omitted from presentation only. Source grids remain available unchanged in `ExtractionResult.statement_tables` and `raw_table_cells`.
- Stockholders' equity is exported for both PDF and HTML. Dates within balance-row labels are not mistaken for period columns. HTML leaf headers define equity components; currency and spacing subdivisions can be combined without renaming their source headers. If those boundaries are uncertain, the physical grid is retained with a warning.
- Ruled PDF equity tables can recover open headers and rows between rule boxes. This geometry path is deliberately equity-specific, not an assumed schema for all investment tables.
- Source labels, punctuation, note references, component names and captions remain source-derived. Accounting identifiers and mappings are not display labels. A title unsuitable for an Excel tab still uses a neutral `Statement N` tab, with the full title inside.
- Numeric source cells remain numeric, including values within HTML spans. Currency, precision, percentages, sign style, and real zeros are retained. Dashes and NA/NM remain literal missing-status tokens. Ambiguous multiple amounts in one cell remain text with a warning instead of being concatenated into a number.
- Empty extraction fails before workbook creation. Detected equity without an extractable column grid also fails clearly rather than silently omitting that statement.

## PDF performance and review

The default `table_strategy="adaptive"` runs PDFPlumber first. Camelot lattice and stream run only on pages not meeting the numeric-token coverage screen. The screen uses token multiplicities (so repeated numbers cannot conceal omitted rows), requires reporting-year tokens, and requires at least 97% numeric-token coverage. This is a fallback trigger, **not proof of correct accounting or column alignment**.

Use `--table-strategy all` or API `table_strategy="all"` to run all methods for comparison. A sufficiently covered PDFPlumber result remains selected even in comparison mode; additional candidates remain in the raw method tabs. The returned extraction audit records attempted fallback pages and strategy. Raw tabs without candidates explicitly state that no tables were extracted with that method; consult the audit to distinguish skipped methods from attempted ones.

Unresolved coverage, ambiguous table association, character-decoding problems, and ambiguous numeric cells create a `Review` tab as the last worksheet. Raw candidates remain available. Page selection and manual exact/suggested/review policies are unchanged.

## API and analytical boundaries

`result.statement_tables` contains source table IDs, physical PDF page numbers (HTML has none), statement associations, titles, captions, cell grids, spans, and extraction method. Frames reference their blocks through `frame.attrs["source_tables"]`.

Existing text-derived analytical frames, internal IDs and financial audits remain available for compatibility. They are **not** a validated structured analytical model of every source grid, and financial checks on those frames do not certify displayed grid completeness. New equity output requires the source grid; the text-only parser reports that component checks were not tested rather than guessing columns. General table-to-concept analytical mapping and equity rollforward reconciliation remain limitations.

## Validation

- 163 non-native-UI regression tests passed, including source spans, separate schedule schemas, literal labels, typed amounts, percent cells, explicit equity failure, token coverage, PDF geometry, source order across engine batches, and method scheduling.
- All 10 native UI integration tests passed in a separate process. A combined run encountered the existing Windows Tcl/native-library initialization interaction; splitting native UI execution avoids it without changing the UI implementation.
- Ruff, dependency checks, and package build passed.
- Real ARCC June 2026 HTML generated all five statement categories and 164 source tables in approximately 24–26 seconds. Representative equity output was compared with the source and rendered for visual inspection; this is not an exhaustive audit of all 164 tables.
- Real ARCC PDF equity page 255 completed in approximately 1.8 seconds with no Camelot fallback, compared with 2.5 seconds in all-method mode on the same page. The four core/equity pages (4, 5, 255, 256) completed in approximately 4.5 seconds; page 4 retained an explicit numeric-coverage warning. These local measurements are illustrative, not a full-filing speed guarantee.

Test artifacts are under ignored `tmp/phase3-*` directories. Loan Files source documents, notes, and existing workbooks were not modified. No full PDF batch was regenerated.

For a bounded local check:

```powershell
.\.venv\Scripts\python.exe scripts/check_phase3_layout.py "C:\Filings\fund.pdf" "tmp\layout-check" --pages "4,5,255,256"
```

OCR remains unimplemented. Unruled/ambiguous layouts and genuinely long schedules still require source review and may trigger slower fallback extraction.
