# Phase 2: theme and workspace shell

## Design direction

Visual thesis: a quiet, light workspace with native Windows controls, clear typography, thin dividers, and a single blue primary action surrounding the financial work surface.

Content plan: product title and filing context first; optional extraction setup beside the main work surface; selection information and the primary action below it; session status at the bottom. The result table is the visual anchor. No decorative imagery or dashboard cards are needed.

Interaction thesis: native hover and keyboard-focus feedback identify actionable controls; setup collapses immediately with its restore button always visible; responsive reflow keeps the same widgets, values, and selections. The only ongoing motion is the indeterminate progress indicator in the simulated running state.

## Review preview

Run `run_ui_preview.bat`, or:

```powershell
.\.venv\Scripts\python.exe -m financial_statement_extract.ui.preview
```

This separate preview uses synthetic data only. It does not read filings, run the pipeline, create workbooks, or upload data. The existing `run.bat` remains the live extraction entry point while this layout is reviewed.

Use the preview's scenario selector to inspect empty, ready, running, completed, warning, error, and long-label layouts. Use its window-size selector to compare wide and narrow layouts. Sample actions, setup edits, selection, and collapse/restore are interactive.

## Implementation boundaries

- `theme.py`: purpose-based colors; native-family fonts; spacing, control and row sizing; focus, selection, disabled, and semantic message states. Native corners follow the active platform theme. Windows `vista` controls are preferred; the primary action uses ttk's built-in drawing elements to provide an accent fill.
- `shell.py`: reusable title, source context, setup region, main content slot, action area, and status region. Resizing repositions existing widgets. It has no extraction or filesystem dependencies.
- `preview.py`: synthetic scenario data and preview-only interactions. It composes the shell without importing the extraction controller or pipeline.

Wide windows show a compact setup column and give the main work surface the remaining width. Below the theme's narrow breakpoint, setup starts collapsed to preserve room for results; Show setup opens a three-column strip above the work surface. Visibility choices are remembered separately for wide and narrow layouts. Hiding setup does not destroy widgets. Its restore control remains in the header, and modified settings are identified even when hidden.

The preview is the Phase 2 review deliverable. Live contextual setup rules, the job lifecycle, pipeline progress, and the production results/recovery view remain in their later phases.

## Validation and remaining review

Native Windows tests cover the wide layout, minimum 640 × 700 window, narrow layout,
setup collapse/restore, focus transfer, retained draft values, table selection and
scroll position, visible disabled-action reasons, all seven sample scenarios, and
125% text sizing. The simulated extraction is also checked in a fresh process to
confirm that it does not import the extraction stack.

The full workspace test suite, lint, and dependency checks passed during this phase.
Desktop screenshot review remains pending: the capture tool found the preview window
but could not activate it (`failed to activate captured window`), and its images did
not show the application. Open the preview to review the actual appearance before
live integration. Screen-reader and high-contrast verification belong to the later
accessibility phase and have not been completed here.
