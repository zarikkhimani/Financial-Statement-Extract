# Phase 8 BDC review: Ares Capital 2025

Reviewed locally on 2026-09-21. **Acceptance failed on extraction fidelity.**
The bounded UI workflow completed, but the financial tables are not yet usable
without repair. No production extraction code was changed in this pass.

## Source and scope

- Ares Capital Corporation, fiscal 2025 Form 10-K: 333 PDF pages, 2,945,741 bytes.
- [Issuer-provided PDF](https://arcc.ares.com/media/document/f8d03a78-ecdf-4b26-a491-319f93216de2/assets/Q4_2025_10K.pdf?disposition=inline).
  The SEC endpoint rejected automated downloading; the issuer copy was used instead.
- SHA-256: `20D839D4F31031C0878ABDBB102761EB09A8823EDDA8DB35CB54A8FA92A4BAFD`.
- Local evidence is retained in ignored `tmp/phase8-public-review/`: original PDF,
  page-detection JSON, rendered source pages, and separate CLI/GUI workbooks.
- Windows 11 build 26200, project Python 3.12.14, Tcl/Tk 8.6.12.

The PDF skill guided source-page rendering. The spreadsheet skill's read-only
reconciliation guidance was used without repairing or restyling generated cells.
Computer use verified the actual running workspace, not a mockup.

## Bounded phases executed

1. **Text-only detection:** scanned all 333 pages. Selected 152 candidate pages:
   `119-188,190-198,200-262,264-273`, including 148 schedule pages and four core
   statements. Detector warnings were empty. This is not a page-by-page completeness
   sign-off. A process sample reached 3,353,739,264 bytes (3.12 GiB) working set.
   Final peak and exact elapsed time were not recorded.
2. **Seven-page extraction:** `119-122,271-273`, unchanged adaptive strategy.
   CLI benchmark: **5.83 seconds**, five statement types, eight source-table blocks.
   Camelot fallback ran on six pages. Coverage warnings identify `119,121-122,271`.
3. **Real GUI worker:** same seven pages, **6.266 seconds**, five statement types,
   67 checks, no Tk callback errors. Headline: **Workbook saved · review required**.
   This passes workflow completion only, not source fidelity.
4. **Live visual interaction:** 640x700 logical size, 150% application text scale.
   Ctrl+Enter starts extraction and the primary action becomes disabled while busy.
   Completion exposes Open workbook and Extract again with a persistent warning.
   F6 scrolls checks into view. Clicking a warning and scrolling its detail pane
   exposes the message beyond truncated table columns. The primary action, setup
   restore control, and warning remain visible. The header and context consume much
   of the initial viewport at this size; results require scrolling.

## Source reconciliation and failures

Workbook inspected: `bounded-output/FY25_10K_PART_I_FINANCIAL_INFORMATION.xlsx`.
Pages below are one-based PDF pages, not printed F-page labels.

| Source / workbook evidence | Result |
| --- | --- |
| Page 120, total investment income: 3,052 / 2,990 / 2,614. `Statement 1!D31,G31,J31` | Numeric values match |
| Page 120, net investment income: 1,415 / 1,436 / 1,258. `Statement 1!D42,G42,J42` | Numeric values match |
| Page 273, ending cash, equivalents and restricted cash: 924 / 860 / 564. `Statement 2!D46,G46,J46` | Numeric values match |
| Page 272, closing equity row: 718 shares, 1 common stock, 13,359 paid-in capital, 958 earnings, 14,318 equity. `Statement 5!B36:F36` | Numeric values match; source dashes elsewhere remain text |
| Page 119, total assets 31,235 / 28,254. `CONSOLIDATED BALANCE SHEET!A15:B15` | **Fail:** 2025 value embedded in label text; only 2024 is a numeric column |
| Page 121, ACP Avenu row: principal 13.2, amortized cost 13.0, fair value 13.2. `Statement 4!A6:C6` | **Fail:** issuer, rate, dates and principal collapse into A6; cost and fair value share B6 as text |
| Company identity in A1 across statement sheets and output filename | **Fail:** inferred as PART I - FINANCIAL INFORMATION rather than Ares Capital |

The Extraction Review sheet flags incomplete coverage and ambiguous cells. Raw
alternative engine outputs are retained. The unselected stream output separates
balance-sheet values better than the chosen lattice output. Candidate ranking needs
investigation; do not suppress warnings or force one engine globally.

No full 152-page table extraction was attempted after these reproducible failures.
No claim is made about all schedule rows, total portfolio reconciliation, PDF/HTML
equivalence, or unexamined cells.

## Reproduce

The review harness now accepts `--pages`. It initializes the normal page draft and
does not bypass validation or preflight approval. Omit `--smoke` for interaction.

```powershell
.\.venv\Scripts\python.exe -m financial_statement_extract.ui.review --source tmp\phase8-public-review\ARCC-2025-10K.pdf --pages 119-122,271-273 --smoke --review-dir tmp\phase8-public-review\gui-output
```

The watchdog remains 30 seconds; do not use smoke mode for a whole large filing.
Harness/page-selection regressions: **26 passed**. Scoped Ruff and `git diff --check`
passed. Installed-wheel evidence predates this new review option; no new package
was built or published.

## Pickup order

1. Fix source-column fidelity and company inference with regression fixtures for
   these failures, preserving raw alternatives and review warnings.
2. Bound the text scanner's retained page data; measure time/peak memory and prove
   its page plan and extracted text are unchanged.
3. Rerun the sample, then expand to full schedules with source-total and row/column
   reconciliation. Complete the remaining UI size/scale matrix separately.

Screen-reader and actual Windows high-contrast acceptance remain open. The fresh
accessibility snapshot still reports mostly unnamed panes. No OS settings changed,
no assistive software was installed, and no Excel workbook was opened automatically.
