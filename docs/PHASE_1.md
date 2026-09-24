# Phase 1: page-selection preflight and source terminology

Historical Phase 1 implementation notes. Automatic-discovery limitations below are superseded by [Phase 2](PHASE_2.md); manual-selection behavior remains unchanged.

## Implemented

- Every PDF run builds a `StatementPagePlan` before Camelot or PDFPlumber table extraction. The plan records the source path, selection mode, requested/selected/suggested physical PDF pages, original detected headings, page roles, evidence, and warnings. It is returned as `ExtractionResult.page_plan` and in result metadata; it is not a new workbook worksheet.
- Manual selections longer than 50 pages require explicit review. Fifty is a review threshold, not a maximum statement length. Schedules may legitimately exceed it.
- The desktop offers suggested pages, exact entered pages, or cancel. Cancel is the default. The CLI stops with exit code 2 and instructions; the Python API raises `PageSelectionReviewRequired`, carrying the plan.
- `page_policy="exact"` keeps every requested page. `page_policy="suggested"` removes only pages containing no text, separator rules, or a standalone number matching the physical page. Pages without readable extraction, scanned pages, other numeric-only pages, title pages, uncertain continuations, notes, and investment schedules are retained. This is conservative cleanup, **not yet accurate financial-statement-range discovery**.
- Invalid, reversed, or out-of-bounds manual ranges fail explicitly. Manual page numbers always refer to the PDF viewer, not printed filing numbers.
- PDF and HTML statement titles and item terminology are kept separate from classification. Note references and section colons remain visible; unnamed inferred totals keep their values without an invented display label. HTML superscript text and duplicate source rows are retained.
- The exact extracted statement title is used inside Excel. If it is not a legal, unique Excel tab name, a neutral `Statement N` tab is used. Missing titles stay missing rather than being fabricated. Schedule column headings retain source spelling and order instead of standardized replacements.
- `RawItem` remains authoritative for display/export. `StandardItem`, `InternalID`, `AnalyticalFamily`, and `MappingRelationship` are internal metadata, not replacement display labels. Related mappings and inferred labels cannot satisfy exact-concept value lookups in financial audits.
- Investment-company changes in net assets from operations and corporate net income have distinct identifiers. They share the analytical family `period_result`, not a claim of literal accounting equivalence.

## Usage

```powershell
.\.venv\Scripts\financial-extract.exe "C:\Filings\fund.pdf" --pages "20-60"
# After reviewing the proposed selection, explicitly choose one:
.\.venv\Scripts\financial-extract.exe "C:\Filings\fund.pdf" --pages "20-60" --page-policy exact
.\.venv\Scripts\financial-extract.exe "C:\Filings\fund.pdf" --pages "20-60" --page-policy suggested
```

The API accepts the same `page_policy` values: `review` (default), `exact`, and `suggested`. HTML uses the source-fidelity changes but has no PDF page-selection policy.

## Deliberately remaining for subsequent phases

- Automatic PDF selection still uses the existing three-core-statement detector. Reliable investment-schedule/equity discovery, blank-gap continuation, section boundaries, and matching local HTML guidance belong to Phase 2. The result and desktop summary warn about that limitation.
- Investment schedules are in scope for both PDF and HTML. Phase 1 never trims them for length, but does not promise to discover all of them automatically.
- Full stockholders' equity output and table-aware extraction/performance changes remain later work. Stockholders' equity headings currently act as section boundaries.
- Source fidelity means preserving extracted terminology, not reproducing page layout: existing text extraction still collapses whitespace and joins wrapped lines, and period detection still assembles multilevel date headings. OCR is not implemented. Missing or misread source text cannot be reconstructed by this phase.
- Accepting a review currently repeats the lightweight text scan; it does not run table extraction twice. No Loan Files batch or notes were modified during this implementation.

## Verification

Regression tests cover range validation, review before expensive extraction, exact/suggested propagation into both PDF table engines, CLI review handling, desktop cancellation and both choices, serialized page-plan evidence, schedule retention, source titles/labels/notes, unnamed totals, schedule headers, and distinct accounting concepts. Existing extraction and UI tests remain in the suite.
