# Collection regression: phase 2

Completed November 15, 2026. All 116 PDFs are accounted for. Source review produced
controlled page selections for 113 usable filings. Two inputs need repair or a
usable replacement, and one is the wrong document for this test suite.

The unchanged Phase 1 detector was run on every PDF, including its normal local
HTML guidance. This phase tested page coverage, not extracted amounts.

| Result | Count |
| --- | ---: |
| PDFs inventoried and scanned | 116 |
| Source PDF pages attempted | 26,015 |
| Usable filings with prepared source scopes | 113 |
| Prepared extraction jobs, including two Digital Realty entities | 114 |
| Core statement pages in those jobs | 607 |
| Full scope pages, including investment schedules and retained context | 6,070 |
| Usable filings with all confirmed core data pages selected automatically | 89 |
| Usable filings with core data pages missing from automatic selection | 24 |
| Confirmed core data pages omitted | 41 |
| Filings with investment schedule table coverage gaps | 72 |
| Schedule table pages flagged as omitted | 744 |

## Files

- [Readable coverage index](../outputs/regression-phase2-20261115/coverage.csv)
- [Detailed page map and source evidence](../outputs/regression-phase2-20261115/coverage.json)
- [Prepared Phase 3 jobs](../outputs/regression-phase2-20261115/phase3-jobs.json)
- [Reviewed exceptions](../outputs/regression-phase2-20261115/review-overrides.json)
- [Validation results](../outputs/regression-phase2-20261115/validation/integrity.json)
- [Reproduction and evidence guide](../outputs/regression-phase2-20261115/README.md)

## Material findings

Missing pages contain real amounts, including net asset value per share,
earnings per share, equity movements and cash-flow disclosures. Examples include
Bain Capital Specialty Finance's quarterly pages 6 and 11, Carlyle's annual
pages 97 and 100, and Golub's quarterly cash-flow page 9. These are coverage
defects rather than cosmetic heading differences.

The detector completed 115 scans and failed on Travelers. Its default policy
would proceed on 111 files, request review on Palmer Square's quarterly filing,
and find no pages for American Tower, DigitalBridge and the Allstate document.
A completed scan or permission to proceed does not establish full coverage.

Core coverage includes equity/net assets and comprehensive income where present.
Schedule coverage includes related investment tables within the primary schedule
section, such as derivatives and affiliate rollforwards. Titles, unit captions
and explanatory pages are retained as context. Another 188 schedule pages have
uncertain data-versus-context classification. They remain in the prepared full
scope and are not silently counted as passing or omitted from later extraction.

## Input exceptions and source distinctions

| Filing | Finding | Treatment |
| --- | --- | --- |
| DigitalBridge 2023 | Financial pages render correctly, but extracted text is garbled and loses numeric characters. | Pages 78-86 mapped visually; hold numerical extraction until a usable source or OCR workflow is available. |
| Travelers 2023 | 24 PyMuPDF page-tree errors; PDFium cannot open it; PDFPlumber fails with `Unexpected EOF`. | Financial pages 145-149 are identified, but this exact damaged input is blocked. |
| Allstate file labeled 2023 10-K | Actual document is a 2024 proxy/shareholder-report package without the complete primary financial statement set. | Retain in the inventory as a wrong-document exception; do not report it as a parser regression. |
| Digital Realty 2023 | Separate Inc. and L.P. consolidated statement sets. | Prepare separate jobs for pages 94-100 and 101-107. |
| Applied Digital | Filename says 2023; filing and statements report fiscal year ended May 31, 2024. | Use source period and pages 66-70. |
| ICMB annual | Full-dollar reporting and mixed twelve-month/six-month columns after a fiscal-year change. | Preserve exact source periods and units. |
| American Tower equity | Amounts are in millions while share counts are in thousands. | Preserve the per-column exception on page 99. |
| PennantPark annual | Source cash-flow heading is misspelled `STEATEMENTS`. | Source rows confirm cash-flow page 95; no application patch made. |

Source header excerpts and unit captions are stored with page numbers. When no
scaling caption is printed, the map explicitly retains amounts as printed; it
does not invent a thousands/millions multiplier. The six unresolved reporting
dates belonging to actual financial reports are now supported by statement
headers or rendered pages. The Allstate proxy does not get an invented 10-K date.

## Validation and limits

The source scan is independent of the production detector. Coverage was reviewed
using source headings, statement boundaries, continuation text and targeted
rendered pages. It was not a visual review of every page, nor a comparison of
every financial amount. Page roles supported only by ambiguous text remain
explicitly uncertain.

All 116 detector reports and source scans are retained. Five targeted audit
checks passed, along with Ruff and inventory/integrity validation. The Phase 1
snapshot, 153 original program files, all 369 source-library files and all 324
previous project output files remain unchanged.

Phase 3 can use the prepared exact page selections to establish a numerical
baseline, first across the 607 core pages and then the full schedule scopes.
The two blocked inputs and wrong-document exception remain visible. No Phase 3
job was executed, no workbook was changed, and no extraction logic was modified.
