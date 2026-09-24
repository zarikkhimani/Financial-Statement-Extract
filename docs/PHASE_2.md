# Phase 2: automatic PDF sections and corroborating HTML

## Planned improvement: table-of-contents guidance for 10-K and 10-Q filings

User requirement recorded September 21, 2026; not yet implemented.

Auto should first locate and read the filing's table of contents (including an
index to financial statements) in both HTML and PDF 10-K and 10-Q filings. Use
the section names and page numbers provided there to locate the financial
statements and other supported sections.

- **PDF:** Map the printed page numbers in the contents to the actual PDF pages;
  cover pages and numbering restarts can make those numbers differ.
- **HTML:** Follow local contents links/anchors to their sections when available,
  and use the listed page numbers and section labels as additional guidance.
- Verify the destination headings and tables, and follow statement continuations.
  The contents is navigation guidance, not a financial table to extract.
- If the contents is missing, incomplete, or inconsistent, use the existing
  section detection and flag unresolved ambiguity for review.

## Behavior

- Detects balance sheets, operating/income statements, cash flows, changes in net assets/partners' capital, stockholders' equity, and investment schedules.
- Recognizes split headings and repeated SEC navigation links without changing source titles.
- Follows table continuations and title-only pages across up to two conversion blanks. Blank pages are excluded; selected ranges remain discrete. It never fills the entire span between distant financial statements.
- Long investment schedules have no fixed length cap or 15-page proximity requirement. Derivative tables, related commitment tables, and single-percentage columns provide data evidence. Explanatory schedule-only prose remains section context rather than table input.
- TOCs, auditor reports, notes, and narrative section headings end the active section. Notes starting below a statement on the same page are excluded from parser input without discarding the statement above them.
- Selects the best-supported statement section using coverage of core statement types, other statement types, and HTML corroboration. Equally supported alternatives or unreadable pages between statement pages require review before table extraction. Missing core statements produce explicit completeness warnings.
- The PDF text scan is reused by the parser; auto mode no longer scans every page once for discovery and then scans the selected pages again for text.

## Matching HTML

Only local HTML siblings are considered. A same-stem companion is preferred but must still match financial row labels **and values**; filenames or similar statement titles alone do not establish identity. If no same-stem candidate exists, at most eight siblings are considered with a stronger cross-statement match requirement. Ambiguous, mismatched, or unreadable companions produce a warning and PDF-only detection. There are no network requests.

Core-statement evidence establishes identity when available, so a very long, differently wrapped investment schedule cannot overwhelm the identity check. Matched HTML rows can corroborate a PDF table whose heading is not recognized. HTML wording is never substituted for a PDF source title.

HTML extraction now groups adjacent continuation tables for all supported statement types, rather than retaining only the largest individual table. Nearby notes boundaries prevent supporting tables from becoming primary statements.

## Evidence and limitations

The returned page plan contains evidence for selected and rejected pages, every detected statement type on a shared page, warnings, and `guidance_source` when HTML was accepted. Confidence values are heuristic scores, not calibrated probabilities.

Regression fixtures cover long schedules, distant sections, title/blank/continuation pages, running navigation links, notes, derivative and percentage tables, equity, ambiguous companions, scan gaps, and source-title fidelity. Read-only checks against the ADS and ARCC June 2026 PDFs were compared with their existing core-page notes. Representative pages were also rendered for visual inspection; these checks do not constitute validation of every page in the Loan Files collection.

The ARCC check recovered balance sheet page 4, operations page 5, equity page 255, and cash flows page 256, with the intervening schedule represented as discrete data pages rather than the full 6-254 span. The ADS check recovered core pages 4-7 and 9-10. These checks also drove fixes for running navigation links and footnoted derivative tables. The actual PDF-engine smoke test runs in a subprocess to avoid a Windows native-library interaction with later Tcl initialization in the test process.

Known limitations remain explicit:

- OCR is not implemented. No-text pages with images or substantial vector graphics are treated as unreadable, not confirmed blank pages.
- Layout-heavy rows can still be misread or misclassified. Review warnings and source reconciliation remain necessary.
- Full stockholders' equity worksheet output remains Phase 3; Phase 2 selects those pages and warns about the output limitation.
- Table-aware output organization and expensive table-engine optimization remain Phase 3. Selecting a legitimate 200-page schedule can still take substantially longer than extracting a handful of core statement pages.
- Manual page selections retain Phase 1's exact/suggested/review behavior.

No Loan Files notes or existing workbooks were changed, and the Loan Files batch was not regenerated.

### Validation handoff

Phase 2's focused detection, HTML, PDF-pipeline, source-fidelity, and controller suite passes (56 tests). Lint, dependency checks, and package build passed. A complete run passed 157 tests before concurrent UI edits landed; after adding the numeric-only safeguard and those UI edits, the full run reported 151 passes and seven UI-test failures. The failures concern newly required view state, changed placeholder behavior, and new file-existence validation in the concurrently edited workspace UI. Those UI changes were preserved rather than reverted. Full-suite green status should be re-established when that UI work and its fixtures are synchronized.

## Read-only diagnostic

```powershell
.\.venv\Scripts\python.exe scripts/check_page_detection.py "C:\Filings\fund.pdf" "tmp\fund-page-plan.json"
```

This writes a local diagnostic report with page evidence and source text, not an Excel workbook. Keep reports containing financial source text outside version control.
