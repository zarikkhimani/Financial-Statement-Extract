# Changelog

## Unreleased

These changes are under review. See [release readiness](docs/RELEASE_READINESS.md)
for outstanding checks and the scope of completed validation.

### Added

- An AI agent usage guide covering installation, CLI and Python workflows,
  page-selection review, output inspection, and recovery.
- A desktop workspace with contextual PDF settings, extraction-stage progress,
  statement and check summaries, and recovery guidance with Retry.
- Keyboard help, session text scaling from 100–200%, and Windows system colors.
- Automatic PDF statement discovery and a review step for manual selections
  over 50 pages. Large selections can retain the entered pages or use a
  conservative suggestion.
- Workbook checks for supported source layouts, financial relationships, and
  extraction coverage, with warnings and untested checks retained for review.
- An experimental PDF comparison worksheet, currently named `Experiential`.
  It runs separately from the baseline extraction and adds processing time.

### Improved

- PDF table extraction uses an adaptive strategy, with an option to run all
  table methods for comparison.
- Statement presentation preserves source labels, dates, equity components,
  and investment schedule fields for supported layouts.
- Setup retains draft values during a session and identifies changes since the
  last successful extraction. Results provide workbook and output-folder actions.
- Every exported sheet reserves three blank top rows and two width-1 left
  columns. Worksheets use no merged cells, hidden rows or columns, or freeze panes.

### Fixed

- Repaired selected BDC statement layouts, including amount alignment, wrapped
  disclosures, schedule fields, and separation of per-share section headings.
  Validation covers selected statement pages, not full-filing completeness.
- Recovered omitted liabilities and equity rows in a supported corporate
  balance-sheet layout and added checks for incomplete extraction. Acceptance
  remains limited to the source and page scope recorded in release readiness.
- Hardened desktop startup and shutdown behavior: the app refuses hidden-desktop
  startup, shows its main window, and warns before closing a pending extraction.

### Known limitations

- Unsupported layouts and coverage warnings remain. Successful comparisons
  for selected pages do not establish completeness for other filings.
- Screen-reader, Windows contrast-theme, and full visual acceptance remain open.
- Image-only PDFs require external OCR. Parser resource limits remain a known
  security limitation, as described in [SECURITY.md](SECURITY.md).

## 0.1.0 - 2026-09-10

- Prepared the repository for its first public release with an MIT license, a streamlined quick start, release guidance, and GitHub contribution templates.
- Added built-wheel installation smoke testing to CI and completed the package's public metadata links.
- Added an installable package, public Python API, command-line entry point, package metadata, and automated CI checks.
- Kept document-derived Excel text literal and disabled automatic formula and URL conversion.
- Rejected file URL authorities, UNC paths, and Windows device paths by default before filesystem access.
- Added contributor and architecture documentation plus security regression tests.
- Replaced the original monolithic script with focused extraction, normalization, mapping, audit, Excel, pipeline, and UI modules.
- Removed the embedded Base64 image, hardcoded desktop path, bundled Tabula JAR, and Java dependency.
- Added local PDF and HTML/iXBRL extraction, automatic statement-page detection, presentation-ready Excel output, explicit OCR-required reporting, and automated tests.
- Improved interim-statement workbook headers and recognition of banking income-statement sections.
- Preserved source values and provenance; missing values are not converted to zero and reporting periods are not invented.
