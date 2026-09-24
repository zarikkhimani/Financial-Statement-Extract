# UI Phase 5: real extraction-stage progress

Run `run.bat`. Progress now comes from the pipeline's actual work boundaries,
through the worker queue, into the existing status area. No percentage or ETA is
invented, and the indeterminate indicator remains active during work.

## Stages and scope

PDF: validation → page detection/preflight → table extraction (PDFPlumber, then
Camelot if needed) → statement parsing/source layout → checks → workbook writing.

HTML: validation → HTML reading/table detection → parsing/source layout → checks
→ workbook writing. Reading and detection occur in one existing HTML routine;
the UI does not pretend those are separately observable stages.

Events indicate entry into a stage, not its success. Only a returned workbook
produces the completion event. A stage can remain visible for a long time on a
complex filing. Repeated table-stage events identify the optional fallback method.
PDF review pauses before table extraction; explicit approval starts the pipeline
again with the chosen policy, so validation/detection can legitimately repeat.

The visual approach stays native and restrained: existing status text for the
current stage, a short stage trail in the existing console, and no extra panels.
The only progress motion is the indeterminate indicator. Drafts remain editable
for the next run, and the submitted request stays fixed.

## Reporter contract

`financial_statement_extract/progress.py` defines immutable `ProgressEvent`
objects and `ExtractionStage`. The API and PDF/HTML pipeline functions accept an
optional keyword-only `progress` callback. Without one, reporting is a no-op.

```python
from financial_statement_extract import extract_filing

result, workbook = extract_filing(
    "sample.pdf",
    progress=lambda event: print(event.stage.value, event.detail),
)
```

Callbacks execute synchronously on the extraction caller's thread, must return
promptly, and must not update Tk widgets. Callback exceptions propagate rather
than being silently suppressed. The callback should be a lightweight observer,
not a cancellation mechanism. Unsupported file types and rejected routing paths
can fail before any stage is emitted. No completion event is emitted by the
reporter itself; the function return or exception is authoritative.

The built-in UI runner enables reporting. Existing injected four-argument runners
remain compatible; a custom runner that accepts `progress=` explicitly opts in
with `reports_progress=True` on the controller or workspace. Queue messages carry
the submitted request identity. The UI ignores reports for other requests, during
review, after completion, or after shutdown. Only the Tk thread renders reports.

## Close safety

Closing while a job is active, awaiting review, or awaiting queued completion now
asks whether to close anyway. The default is **No**, keeping the app open. The
warning explains that closing may interrupt extraction and leave an incomplete
workbook. This is not cooperative cancellation or a guarantee of clean rollback.
Completed/idle workspaces still close directly. Queued events are not rendered
after shutdown begins.

## Validation and review gate

Completed validation: 200 tests passed; full-repository Ruff, dependency checks,
and diff whitespace checks passed. Wheel/sdist build, CLI help, and built-wheel
progress/UI imports passed; importing the UI still does not load the pipeline or
heavy extraction libraries.

Validation is deliberately bounded to small synthetic files:

- One-page real PDF engine smoke with reporting enabled and disabled. Compare
  selected pages, statements, source grids, audits, and workbook cell values/types/
  number formats. Native PDF execution is isolated in a subprocess, following the
  project's existing Windows test convention.
- Synthetic HTML through the real public API, comparing statements, extraction
  records, metadata (excluding generation time), and workbook cells/merged ranges.
- Stage-entry assertions at HTML extraction, parsing, audit, and writing calls.
- Review-required PDF preflight cannot reach table work before approval.
- Missing files, reporter exceptions, and parse/audit/write failures stop reporting
  at the relevant boundary. No false completion is reported.
- Fake-runner UI checks exercise responsive Tk callbacks, editable drafts, duplicate
  prevention, UI-thread-only rendering, stale reports, and success/error handling.
- Close confirmation checks cover stay-open, explicit close, reentrant prompts,
  queued completion, and late worker messages.

Quick checks:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline_progress.py tests/test_ui_controller.py tests/test_ui_workspace.py tests/test_app_exit.py
.\.venv\Scripts\python.exe -m pytest tests/test_page_selection.py -k real_pdf
```

Large realistic filing benchmarks and screenshot/accessibility review remain for
final QA. These tests do not establish large-document performance or engine
cancellation safety. Structured results, Open workbook actions, and expanded error
recovery remain Phase 6; cross-session persistence is not added here.
