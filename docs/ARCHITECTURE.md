# Architecture

Financial Statement Extract is a local Python library with a thin Windows desktop interface. Its core data flow is:

```text
PDF / HTML filing
  -> source extraction
  -> normalization and structural detection
  -> statement parsing and concept mapping
  -> financial and extraction checks
  -> Excel workbook
```

## Boundaries

- `financial_statement_extract/` is the supported package API and command-line surface.
- `financial_statement_extract/ui/` owns the desktop interface; `app.py` retains compatibility imports and a launcher.
- `pipeline.py` orchestrates parsing, metadata, audit checks, and workbook creation.
- `extractors.py` and `html_extractor.py` adapt third-party PDF and HTML parsers.
- `normalization.py`, `structure.py`, `statements.py`, and `mapper.py` preserve source semantics while producing structured statement rows.
- `audit.py` produces consistency checks; it does not silently repair source data.
- `excel_writer.py` writes presentation worksheets and literal raw extraction grids.
- `financial_statement_extract/table_layout.py` associates source grids with statements while keeping presentation independent of analytical concept labels. `pdf_layout.py` recovers ruled equity grids using page geometry. The writer preserves table blocks and uses source leaf headers to collapse only equity HTML layout subdivisions.
- `path_policy.py` rejects implicit network and Windows device paths before filesystem access.

The current flat implementation modules remain importable for compatibility. New consumers should import only from `financial_statement_extract`; internal modules may change between releases.

## Desktop implementation history

The phase sections below describe the implementation as it evolved. Later
phases supersede earlier behavior: the current workspace includes stage
progress, structured results, recovery guidance, and a warning before closing
a pending extraction. Settings remain session-only; cooperative cancellation
and persistence across restarts are not implemented.

## Desktop UI boundaries (Phase 1)

- `ui/state.py` defines the editable, widget-independent `WorkspaceState` and frozen `JobRequest`. Creating a request normalizes local paths, copies draft values, and returns a fresh metadata dictionary to each runner.
- `ui/controller.py` owns the single daemon worker and completion queue. Its injectable runner uses the existing pipeline by default, importing it only when extraction starts. Workers receive a request snapshot and never touch Tk widgets or variables.
- `ui/components.py` binds Tk variables to draft state and renders the source-faithful summary. UI edits (including dialogs and drops) synchronously update state before notifying view subscribers; programmatic changes to a displayed draft should go through these variables too.
- `ui/workspace.py` composes the view and controller, handles dialogs, validates submission, and consumes completion events on the Tk thread.
- `ui/inputs.py` contains shared page-selection and drop helpers and guidance text.
- `ui/theme.py` isolates the existing window defaults, placeholder colors, and `clam` theme selection for the subsequent design-system phase.

Both `python app.py` and `python -m financial_statement_extract.gui` use the same packaged workspace. Existing `app` helper imports remain available; tests and callers can inject a runner with `FinancialExtractorApp(root, runner=...)` or use `ExtractionController(runner=...)` without Tk.

Phase 1 retains the current layout, controls, dialogs, summary text, page warning, and close behavior. Closing during extraction still closes immediately and does not provide cancellation. The new state is in memory only; progressive disclosure, stage progress, history, and cross-session persistence are not implemented in this phase.

The UI regression suite includes plain-state and controller tests plus native Tk construction, input binding, drag/drop, success/error, and retry checks with fake runners. Heavy extraction regression coverage remains in the existing parser, audit, and workbook tests.

## Workspace preview (Phase 2)

`ui/shell.py` provides persistent filing context, a collapsible setup panel, a main
content slot, contextual action slots, and a status region. `ui/theme.py` now also
provides semantic tokens and native-control styles through `apply_workspace_theme`.
The existing `apply_theme` remains available for compatibility.

`ui/preview.py` composes the new shell with synthetic data and simulated UI states.
It does not import the worker controller or pipeline. The preview has a separate
launcher, `run_ui_preview.bat`, so visual review can happen before live integration.
See [Phase 2 design and review notes](UI_PHASE2.md) for layout behavior and scope.

## Live contextual setup (UI Phase 3)

The live `ui/workspace.py` now uses `WorkspaceShell` and the semantic theme.
`ui/setup.py` supplies a `FilingSetupPanel` through the shell's setup factory:
PDF-only page settings and a separate metadata disclosure. The shell displays
persistent source/output controls but delegates file dialogs and validation to
the workspace. The synthetic preview remains independently usable.

`WorkspaceState.draft_key()` compares entered settings without file I/O. The view
captures that key with each submitted request and advances its baseline only on
success, so edits during a run remain visibly unextracted. Disclosures reposition
or hide existing widgets without recreating them. Collapsing a focused section
transfers focus to its restore control. Results retain their source attribution
when the user selects a different filing, until another extraction begins.

The existing controller, source-title summary, PDF preflight review, and pipeline
behavior remain in place. Job cancellation, stage-level progress, structured
result navigation, and persistence across restarts are outside this phase.
See [UI Phase 3 review notes](UI_PHASE3.md).

## Explicit job lifecycle (UI Phase 4)

`ui/lifecycle.py` models `EMPTY`, `READY`, `RUNNING`, `SUCCEEDED`, and `ERROR`
independently of widgets. The workspace owns this model on the Tk thread; the
controller only transports work and outcomes. Running includes pending queue
consumption and PDF preflight review, closing the duplicate-start gap between
worker exit and UI completion. The model retains the submitted request separately
from draft edits and centralizes disabled-action reasons without filesystem I/O.

Fake-runner tests exercise transitions, retries, and worker-start/resume failures
without loading the extraction stack. See [UI Phase 4](UI_PHASE4.md) for the state
contract and fast review command. This does not add pipeline stage reporting,
cooperative cancellation, or persistent sessions.

## Pipeline progress and close safety (UI Phase 5)

UI Phase 5 adds a lightweight `progress.py` event contract shared by the public
API and pipeline. Optional callbacks run on the caller's thread; the desktop
controller supplies a queue-only callback. The workspace displays current stage
text on the Tk thread, filtering reports by submitted-request identity and active
lifecycle. Stage events announce work, not completion. The workbook return remains
the success boundary. See [UI Phase 5](UI_PHASE5.md) for the API contract, close
warning, and bounded PDF/HTML equivalence tests.

## Structured results and recovery (UI Phase 6)

`ui/results.py` projects the existing ExtractionResult into source-titled statement
summaries and financial/extraction check rows, then displays them with native tabs,
scrollable tables, and read-only diagnostics. It does not modify dataframes, infer
missing periods, or certify a saved workbook. The controller now includes the error
class name alongside the original error message so recovery guidance can be specific
without guessing from arbitrary text. Workspace lifecycle owns retry/run decisions.

`ui/file_actions.py` validates explicit local workbook/folder targets and delegates
to Windows' native open operation without a shell. Targets come from the saved
result, not editable setup. Open errors preserve the result. See [UI Phase 6](UI_PHASE6.md)
for outcome semantics, launch boundaries, and review checks.

## Keyboard access and display preferences (UI Phase 7)

`ui/accessibility.py` owns native menus, scoped keyboard bindings, and session-only
text-size/system-color preferences. Theme updates mutate existing font objects;
they do not rebuild fields, replace results, or enter the extraction controller.
`ui/viewport.py` supplies overflow around filing context and the work area, retaining
fixed setup/primary/status controls. Focus reveals offscreen controls without changing
inner table or text scroll. Geometry work is coalesced through top-level-owned idle
callbacks. Result disclosures retain their selection and scroll context.

See [UI Phase 7](UI_PHASE7.md) for shortcuts, the automated text-size matrix, and the
still-open manual visual, high-contrast, and screen-reader review gate.

## Acceptance review (UI Phase 8)

UI Phase 8 adds `ui/review.py` and pure synthetic data in `ui/review_samples.py`.
The harness composes the production workspace without replacing its extraction
runner. It creates unique local review folders, supports bounded one-shot smoke
runs, and never auto-approves PDF page review. `scripts/check_ui_package.py` checks
an isolated installed-wheel startup. See [UI Phase 8](UI_PHASE8.md) for evidence and
the visual/accessibility gates that still prevent rollout.

## Security-relevant invariants

1. Document-derived strings are data, never formulas or automatic hyperlinks.
2. Network, UNC, and Windows device paths are denied unless a library or CLI caller explicitly opts in.
3. Source values and raw extraction records are retained; missing data is not replaced with zero.
4. Existing output files are not silently overwritten.
5. The application has no upload or telemetry path and processes selected files locally.

## Current limitations

Extraction Phase 3 uses adaptive PDF table fallback and source-grid presentation. See [Phase 3](PHASE_3.md) for the coverage screen, structured-output API, validation, and the distinction between source grids and text-derived analytical frames.

- Image-only PDFs require a separate OCR workflow.
- Extraction results require reconciliation to the source filing before use.
- Parser resource limits and process isolation are not yet implemented; exceptionally large or adversarial documents can consume substantial CPU or memory.
- The project is not a regulatory certification, model validation, or bank production approval.
