# UI Phase 4: explicit single-job lifecycle

The live workspace now uses a widget-independent lifecycle model. The existing
dependency-injected thread/queue controller still runs both fake and real runners.
This phase changes lifecycle coordination, not extraction or workbook semantics.

## Design and transition contract

Visual thesis: retain the calm native workspace and use its existing status area
to explain state, rather than adding another panel. Content plan: source and draft
stay visible; running/review state explains unavailable actions; results and errors
identify the submitted filing. Interaction thesis: immediate action feedback,
state-preserving disclosures, and indeterminate progress only while work is active.

| State | Meaning | Primary action |
| --- | --- | --- |
| `EMPTY` | No source selected | Choose filing |
| `READY` | A source is selected or a draft was edited | Extract to Excel, or a visible validation reason |
| `RUNNING` | A submitted job is pending, including queued completion or PDF review | Disabled, with a running/review explanation |
| `SUCCEEDED` | The UI consumed a successful completion | Extract to Excel remains available |
| `ERROR` | A worker failed to start, resume, or finish | Extract again with retained/current settings |

Ready means setup is available, not that the document has been read or validated.
Path-policy and suffix checks are cheap and do not probe the filesystem while
typing. The existing submission check verifies that the source file exists.

- `ui/lifecycle.py` owns transitions, the frozen submitted request, submitted
  draft key, original error message, and the pending-review flag. It does not
  import Tk, parse documents, or inspect files.
- Only the UI thread changes lifecycle state. Worker messages still travel through
  the controller queue. Finishing a worker alone does not release the UI job lock.
- Draft edits during a job cannot replace its request. On failure, extraction can
  be attempted again using the current draft, including any corrections.
- Success/error survives a redraw. Editing the draft moves to Ready (or Empty),
  without erasing the prior result/diagnostic or its submitted request.
- PDF review is a substate of Running, not a second job. Suggested/exact choices
  retain the submitted settings and change only page policy. Declining review
  returns to setup without clearing the modified marker.
- Synchronous worker-start and review-resume failures use the same Error path as
  background failures, restoring controls and keeping the original diagnostic.
- Invalid transitions fail explicitly. There is no fake Cancel control: declining
  preflight review does not imply cooperative cancellation of an active extractor.

## Fast review gate

Run the simulated lifecycle and native UI checks:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ui_lifecycle.py tests/test_ui_controller.py tests/test_ui_workspace.py -k "not live_html"
```

These checks use fake runners and tiny test-owned source placeholders, not document
processing. A fresh-process check alternates 20 failures and successes and confirms
that the pipeline, pandas, PDFPlumber, and Camelot never load. Coverage includes
all five states, redraws, draft edits during a run, duplicate starts before queue
consumption, startup failure/retry, review cancellation, and review-resume failure.

The separate real-HTML smoke test from Phase 3 remains a regression check. Native
widget-bound tests still exercise the minimum window. Screenshot, screen-reader,
and high-contrast review remain unverified; no new visual approval is claimed.

Validation completed: 187 tests passed; full-repository Ruff, dependency checks,
and diff whitespace checks passed; wheel/sdist build succeeded. The built wheel's
lifecycle and live UI imports also passed without loading extraction libraries.

## Next review boundary

Phase 5 adds optional pipeline stage events and validates them with small synthetic
PDF/HTML extractions. Stage reporting, structured result/recovery surfaces, Open
workbook actions, cooperative cancellation, close warnings, and cross-session
persistence have not been added here. The existing immediate-close behavior is
unchanged; keep the app open until extraction finishes.
