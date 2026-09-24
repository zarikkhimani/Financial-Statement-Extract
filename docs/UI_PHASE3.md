# UI Phase 3: live contextual filing setup

Run `run.bat` to review the integrated workspace. This phase connects the Phase 2
shell to real extraction; it does not change parsing, accounting rules, or workbook
generation. The separate `run_ui_preview.bat` remains a synthetic design preview.

## Delivered behavior

- The empty workspace offers **Choose filing**; a selected filing offers
  **Extract to Excel**. Browse, output selection, and Exit are quieter actions.
- Source and output remain above the main work area when setup is hidden.
- PDF page selection appears only for PDFs. HTML retains the PDF draft without
  applying it. Existing large/ambiguous PDF selection review remains intact.
- **Show details** reveals client name, optional year, period, and audit status.
  Collapsing Details or Setup retains values and shows a modified marker when
  appropriate. Focus returns to a visible restore control.
- **Changes not yet extracted** compares settings with the last successful run
  (or the initial defaults before the first success). Failures and page-review
  cancellation do not clear it. Returning to the baseline clears the marker.
- Setup remains editable during extraction. The worker receives a fixed snapshot;
  edits made afterwards remain marked for the next run. The disabled primary
  action explains this behavior.
- Successful summaries remain visible and attributed to their source when a new
  filing is selected. Starting another extraction replaces that summary.
- Narrow windows start with setup collapsed. Expanding it uses a compact page
  control/help row and four metadata columns; wide windows use the side panel.
- Unsupported path policies remain enforced before filesystem access. Missing
  source files are checked again when extraction starts. Failed runs retain the
  draft and restore the extraction action for retry.

These are in-memory drafts, not saved sessions. The marker is about extraction,
not a promise that drafts will survive closing the application.

## Review checkpoints

1. Select a local PDF, enter manual pages and metadata, hide both disclosures,
   then reopen them. Confirm values and modified markers persist.
2. Switch to HTML and back to PDF. Page controls should hide and return with the
   same values; source/output controls should remain available throughout.
3. Run an extraction and edit the client name while it is running. Results should
   identify the submitted filing; the newer draft should remain marked.
4. Cancel a PDF page review or provoke an invalid output-path error. Confirm the
   settings remain available, with an explanation and a way to retry.
5. Resize to 640 × 700 and use a long filename. Expand setup/details and check
   native keyboard focus, horizontal path scrolling, and visible primary action.

## Validation and boundaries

The validation run completed with 162 tests passing, a successful wheel/sdist
build, clean dependency checks, and clean lint for the UI and its regression
tests. Full-repository lint reported an unrelated unused import in
`financial_statement_extract/table_layout.py`; that file was not changed by this
UI phase. The built wheel's UI modules also import without loading the pipeline.

Automated native Tk tests cover the above interactions, chooser cancellation,
invalid/missing source paths, retained result context, success/error/retry, and
minimum-window widget bounds. A synthetic HTML filing also runs through the real
background controller and pipeline; the generated workbook is reopened to verify
its source title, Revenue label, and numeric data. PDF preflight choices are tested
with injected runners; parser behavior remains covered by the extraction suite.

Desktop screenshot review is still unverified: the prior capture attempt did not
show the application. Native geometry checks are not a substitute for visual
approval. Screen-reader and high-contrast checks remain later-phase work.

This phase keeps the existing text result summary and indeterminate progress.
Structured result views, detailed job progress/recovery, cancellation, close-time
warnings, history, and session persistence are not implemented here. Closing
during extraction retains the existing immediate-close behavior.
