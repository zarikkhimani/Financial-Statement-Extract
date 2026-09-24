# UI Phase 6: structured results and recovery

Run `run.bat` to review the live workspace. This phase replaces the primary status
console with a native results/recovery surface while keeping original diagnostics
available. Extraction, source-table organization, and workbook writing are unchanged.

## Design and behavior

Visual thesis: a quiet native work surface with one clear outcome and one primary
action. Content plan: submitted filing, saved workbook and selected pages, source-
titled statement summaries, then checks. Interaction thesis: native tab/row selection,
instant state-preserving diagnostic disclosure, and progress motion only during work.

- **Success:** Open workbook is primary; Extract again and Open output folder are
  secondary. Changing the draft makes Extract to Excel primary while the saved
  workbook remains available through its secondary action.
- **Statements:** source titles, parsed row counts, and identified periods appear
  in a read-only table. Source-only grids without analytical frames are explicitly
  labeled Not parsed. Internal standardized accounting names are not substituted
  for source titles, and absent periods are not invented.
- **Checks:** financial audit rows, extraction audit rows, and page-plan warnings
  are all available. Select a row for its full scope and detail; native scrollbars
  handle long content. Warning results initially select the Checks tab.
- **Warnings/partial output:** saving a workbook is distinct from completeness or
  correctness. Warnings, failures, not-tested/unknown checks, absent financial
  checks, or no parsed statements cause a visible review-required outcome. A
  source-only result is not presented as a fully parsed statement set.
- **Diagnostics:** Show diagnostics replaces the central table area, without
  destroying it. Hide diagnostics restores the previous tab, row selection, and
  scroll position. Diagnostic text is selectable/copyable but not user-editable.
- **Failure:** an inline recovery message replaces the completion popup; Retry is
  primary. Original error text and exception type remain in diagnostics, with
  full worker tracebacks still logged as before. Permission/file-creation errors,
  missing paths, validation errors, and no-statements errors have specific guidance.
  Unknown failures retain their diagnostic and conservative retry instructions.
- **Retry:** uses the current draft, including corrections or edits made during the
  failed run. It never silently reverts the form to an older request.

Successful extraction and background failure no longer open blocking message boxes.
Input-validation dialogs, PDF page review, close confirmation, and failed file-open
dialogs remain explicit. Diagnostics and original submitted-source attribution stay
available when setup changes. Starting another extraction replaces the prior result;
this remains a single-job workspace, not history storage.

## File-action boundaries

Workbook/folder actions only occur after a user click and always refer to the saved
result, not the currently edited output folder. Local-path policy is applied before
filesystem checks; workbook actions accept only existing `.xlsx` files. Native
Windows `os.startfile` receives the path directly; no shell command is constructed.

If a file is missing, access is denied, or no default application can open it, the
workspace retains the result and draft and shows an actionable error. No open failure
automatically reruns extraction or overwrites output. The application cannot verify
that Excel subsequently displayed the workbook; a successful launch request is not
proof of that. Opening a folder does not imply its contents were validated.

## Review checklist

1. Extract a synthetic/local filing. Confirm the source title, periods, pages, and
   saved location match the result. Open the workbook and output folder deliberately.
2. Inspect a result with warnings or unperformed checks. Confirm the outcome says
   review required and both financial and extraction checks are accessible.
3. Select a long check, change tabs, and show/hide diagnostics. Confirm selection,
   full diagnostic text, and table scroll are retained.
4. Edit the output folder after success. The folder action must still open the
   saved result's folder; extraction with the new draft is a separate action.
5. Provoke a permission/validation error, inspect its original diagnostic, correct
   setup, and Retry. A missing/moved saved workbook must not clear the result.
6. At 640 × 700, confirm the default collapsed-setup result view keeps its tabs,
   diagnostics toggle, folder action, and primary action visible.

## Validation and remaining scope

Completed validation: 221 tests passed on two full-suite runs after the fixture
repair. Full-repository Ruff, dependency checks, diff whitespace checks, wheel/sdist
build, and built-wheel UI imports passed. UI imports remain independent of the
heavy extraction stack.

Automated coverage includes source-faithful summaries, warning/failure/not-tested
states, source-only results, error guidance, safe launch arguments, rejected nonlocal
paths, missing workbooks, preserved result context, native selection/scroll/focus
retention, and the minimum-window result view. The real HTML smoke test still creates
and reopens a workbook through the live workspace. OS launch calls are mocked: the
tests do not start Excel or File Explorer.

The UI suite now shares one Tk/TkDND interpreter across preview and live-workspace
fixtures, with separate Toplevels per test. This avoids a Windows Tcl reinitialization
failure found during full-suite validation, without suppressing errors or skipping UI
tests. The source-path test setup remains intact.

Screenshot/visual approval, screen-reader/high-contrast behavior, and full 100–200%
text-scaling review remain unverified and belong to Phase 7/final QA. The result
tables summarize extraction; they are not an editable financial grid or embedded
document viewer. Session persistence and multiple-job history are not added.
