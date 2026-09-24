# UI Phase 8: acceptance review and rollout gates

## Decision

**Local review candidate, not approved for rollout.** Automated acceptance work is
complete, but visual sign-off, real screen-reader validation, and an actual Windows
high-contrast review remain open. No version bump, push, publication, or deployment
is part of this phase.

The frontend review keeps the existing calm, results-centered composition. It adds
review tooling and evidence, not new ornamental styling or extraction behavior.

## Repeatable live review

Run `run_ui_review.bat`. This is the production workspace with an extra **Review
cases** menu and a review-session label, not the Phase 2 simulation. Select a case,
then choose **Extract to Excel**. Generated inputs and real output workbooks stay in
a fresh, ignored `tmp/ui-review/session-*` directory. Nothing is overwritten or
automatically removed. Ordinary `run.bat` remains the normal launcher.

Cases:

- **Corporate:** synthetic registrant metadata, income statement, cash flows,
  balance sheet, two reporting years, earnings per share, and financial checks.
- **Fund:** equity with merged headers, dashes and N/A, 60 long investment labels,
  and investment tables with different column schemas, including percentages.
- **Invalid:** a valid HTML document with no financial statements. Extraction must
  fail explicitly and create no workbook. Load Corporate afterward to exercise
  recovery using the same workspace.

These are realistic-shaped synthetic fixtures, **not representative public/client
filing benchmarks**. They do not establish accuracy or performance on large filings.

```powershell
.\.venv\Scripts\python.exe -m financial_statement_extract.ui.review --case fund --size 640x700 --text-scale 2
.\.venv\Scripts\python.exe -m financial_statement_extract.ui.review --case corporate --smoke
.\.venv\Scripts\python.exe -m financial_statement_extract.ui.review --case invalid --smoke
```

`--smoke` runs the real UI event loop and worker, reports JSON, and exits. It has a
30-second watchdog, does not launch Excel/Explorer, and never approves PDF preflight
review. Invalid passes only for the specific no-statements error, not any arbitrary
worker failure. A timeout is failure and can leave partial output; it is not clean
engine cancellation. Optional `--source` accepts an existing local filing; output
still goes into a new review folder. `--pages` initializes a bounded PDF page draft
without bypassing normal preflight rules. Large filings should be reviewed interactively.

## Automated acceptance evidence

- Fresh-process corporate/fund/invalid flows at 640×700 and 200% text through the
  actual UI/controller/pipeline, without mocked extraction engines.
- Generated workbook reopening verifies source titles, representative values,
  equity missing-value tokens, the last long investment label, percentage format,
  and no formula cells in these fixtures.
- Real output failure using a file where a folder is required; correction and
  retry retain the client/page draft. A repeat extraction creates another workbook
  without modifying the first workbook's bytes.
- The existing one-page real-PDF test now also exercises the live GUI worker in a
  separate process. Its API output-equivalence checks remain intact.
- Unique review directories, no-statements/no-workbook behavior, unrelated-error
  rejection, light imports, callback-error detection, and interactive harness close.
- All earlier UI lifecycle, progress, keyboard, text-scale, and file-action tests
  remain in the suite.

Quick acceptance command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ui_review.py tests/test_page_selection.py
```

## Visual/accessibility findings

The computer-use skill located the actual Phase 8 Python window. Its screenshot
capture returned desktop wallpaper rather than the application. Activating that
window failed with **“failed to activate captured window”**, including one retry
with a fresh window handle. That attempt did not establish pixel-based approval.

On 2026-09-21, a fresh session captured the actual BDC workspace successfully.
The 640x700 / 150% check verified busy/completed states, persistent warning and
actions, F6 scrolling to checks, row selection, and scrollable warning details.
This is partial visual evidence, not the full size/scale acceptance matrix.
See [the BDC review](UI_BDC_REVIEW.md) for source-reconciliation failures and pickup order.

The native accessibility snapshot exposed File/View/Help/Review cases menus and
window chrome, but most workspace content appeared as **unnamed panes** rather
than labeled controls. This is an observed accessibility concern, not merely a
missing screenshot. Keyboard tests and the F8 summary do not prove Narrator/NVDA
support. A manual screen-reader run must establish the impact; if core tasks are
inaccessible, UI Automation integration or a separate UI-platform decision is
required before rollout. This phase does not silently replace the UI framework.

No Windows settings were changed, no assistive software was installed, and no
unrelated open files or applications were operated on.

## Remaining review gates

| Gate | Status | Required evidence |
| --- | --- | --- |
| Automated regression and bounded real-engine flows | Passed | Test output and workbook assertions |
| Installed-wheel GUI/CLI startup | Passed, 2026-09-21 | Isolated install, startup, entry points, shutdown |
| Visual hierarchy and clipping | Partial: live BDC at 640x700 / 150% checked | Complete wide/narrow, 100/150/200%, expanded setup, long checks, errors |
| Screen-reader task completion | Open; unnamed-pane concern | Narrator/NVDA field names, menus, tables/details, status, retry, and focus review |
| Actual Windows contrast scheme | Open | Normal/disabled/selected/focus/warning/error inspection using system colors |
| Representative large filings | Failed bounded BDC fidelity check | Fix column/identity defects, profile scan memory, then rerun and expand the corpus |

Record each manual review's date, reviewer, Windows/Tk/assistive-tool versions,
window size, text scale, case, screenshots/findings, and pass/fail. A lack of evidence
is not approval. Keep client evidence outside the repository and do not upload it
without explicit permission.

## Package validation

Completed on **2026-09-21**, Windows / Python 3.12.14:

- Full project suite: **253 passed** (32.83 seconds).
- Repository Ruff, project-environment `pip check`, and `git diff --check`: passed.
- Wheel and source archive built successfully into `tmp/phase8-dist`, version
  `0.1.0` unchanged.
- Fresh `tmp/phase8-release-smoke` venv has `include-system-site-packages = false`.
  Installed the built wheel with `--no-deps` and TkDND **0.6.2**, matching the project.
- From that environment's directory, the installed `financial-extract.exe --help`
  launcher passed. The GUI startup script ran with `-I`, checked that UI modules
  came from the installed environment, loaded the registered GUI entry point,
  opened the workspace, and closed it without Tk callback errors. The heavy
  extraction stack remained unloaded throughout startup/shutdown.

The resumed pass corrected two import-order lint errors in the package-check
script; no runtime application or extraction behavior changed.

Re-run the installed-package checks from the repository root:

```powershell
.\tmp\phase8-release-smoke\Scripts\python.exe -I "$PWD\scripts\check_ui_package.py"
.\tmp\phase8-release-smoke\Scripts\python.exe -I -m financial_statement_extract --help
```

This deliberately minimal **startup-only** environment omits the document-engine
dependencies. It is not a complete extraction installation or a clean-environment
dependency-validation result. Real extraction acceptance and the passing dependency
check use the existing project `.venv`. All artifacts remain local and ignored;
nothing was published, pushed, or installed system-wide.

Validated artifact SHA-256 fingerprints:

```text
financial_statement_extract-0.1.0-py3-none-any.whl
DDD671960B186BF587E67383A8F151AE9C933001A324CF7DEF369C05756AFAA1

financial_statement_extract-0.1.0.tar.gz
20FDC5D57910632DE968444CC76E6A2B7ED61BF6B05427CF7C1E6C5F2AD6DB98
```

The release checklist links these gates. Do not publish this candidate on the basis
of automated tests alone.
