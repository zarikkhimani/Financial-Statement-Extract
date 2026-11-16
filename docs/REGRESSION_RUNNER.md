# Run the collection regression suite

For accepting changes, use [collection acceptance](REGRESSION_RELEASE.md), which
selects the approved reference and enforces full coverage and code checks.
This lower-level runner retains its original Phase 3 default for reproducibility.

From the FinExtract project folder, start a new session:

```powershell
.venv\Scripts\python.exe scripts/regression_runner.py `
  --session outputs/regression-my-change `
  --workers 4
```

This extracts all 217 prepared runs and compares each against the sealed
Phase 3 baseline. It covers the 114 core entity jobs and 103 additional schedule
jobs. The three documented input exceptions remain visible. When a filing's
core and full page selections are identical, the one prepared core job covers
both; the runner does not invent additional full jobs.

The runner captures the current program, including uncommitted application
changes, into the session's `source` folder. Every worker uses that same
snapshot through the supported public API and the exact prepared PDF pages.
No application code or source PDF is edited.

Start a new session for each program change you want to evaluate. Resuming an
old session continues its saved program, even if you have since edited the
application. Changes to the runner, comparator, snapshot, Python environment
or input PDFs prevent reuse with an explicit error.

## Resume

```powershell
.venv\Scripts\python.exe scripts/regression_runner.py `
  --session outputs/regression-my-change `
  --resume --workers 4
```

Completed attempts are rehashed before reuse. Ordinary extraction failures
also remain saved, so the four known failures do not repeatedly consume time.
Interrupted attempts and infrastructure failures are retried in new folders.
The earlier output and log remain available. A newer interrupted attempt never
silently falls back to an older successful attempt.

Use `--retry-failed` with `--resume` to deliberately retry recorded extraction
failures. A success is never skipped merely because its workbook filename
exists; its result, metadata and recorded artifacts must verify.

An existing session requires `--resume`. Resuming fixes its original run
selection and baseline, so omit `--scope`, `--run` and baseline options.
Workers and timeout may change between invocations. The tool refuses to run two
coordinators against the same session.

## Smaller checks

Core statements across the collection:

```powershell
.venv\Scripts\python.exe scripts/regression_runner.py `
  --session outputs/regression-my-change-core --scope core --workers 4
```

One specific filing, or several repeated `--run` arguments:

```powershell
.venv\Scripts\python.exe scripts/regression_runner.py `
  --session outputs/regression-my-change-ads `
  --run core/b4aa15c3e475a116-1
```

Core-only, full-only and individual-run reports are explicitly labelled as
subsets. Their passing result cannot certify the unselected runs.

To split a full session into manageable batches, use `--max-new-runs 8` on the
first invocation or a resume. The selection remains the entire suite, but only
that many additional attempts run. An incomplete batch returns exit code 3
and never produces a passing collection report. Resume without the limit to
finish the remaining jobs.

## Results

The console prints progress and the final report path. During execution,
`progress.json` records completed and active runs. After comparison,
`latest-report.json` points to the latest immutable report directory.

Each report includes:

- `SUMMARY.md`: coverage, execution counts and outcome.
- `comparison.md` and `comparison.json`: per-run regression results and exact
  before/after differences from the Phase 4 gate.
- `collection.csv`: an index of entities, PDF pages, output workbooks and attempts.
- `collection.json`: audit status counts, provenance and infrastructure errors.

Each attempt has `start.json`, `run.log`, its capture artifacts and a receipt
with hashes. Attempts live under `attempts/SCOPE/JOB/NNNN`. Comparison workbooks
are separate copies under `comparisons/REPORT_ID/candidate`. Editing a comparison
copy does not alter its original attempt. Each subsequent comparison gets a
new directory; earlier reports and attempts are retained.

The original source paths must remain accessible. Do not move or edit an active
session. `temp` contains worker scratch files. Keep all these local results
outside version control.

| Exit code | Meaning |
| --- | --- |
| 0 | No unreviewed regression within the stated scope. Known defects may remain. |
| 1 | Numerical or coverage changes require source review. |
| 2 | Invalid evidence, infrastructure failure or workbook-rule violation. |
| 3 | Intentional batch limit reached before the selected suite completed. |
| 130 | Interrupted; worker processes stopped and attempts preserved. |

If invoking through a PowerShell wrapper, use `exit $LASTEXITCODE` to preserve
the Python exit code. A wrapper that converts every nonzero native result to 1
can otherwise obscure the distinction between these outcomes.

## Runtime controls and review

The default is two workers and 900 seconds per worker. `--workers` accepts 1-16;
four is a useful local starting point. Increase concurrency only when memory
and CPU capacity allow it. `--timeout-seconds` changes the limit. A timed-out
worker is stopped, reported as an infrastructure error and preserved for review.
On Windows, kernel job objects own worker process trees, so they are also
terminated if the coordinator crashes. No administrator rights are needed.

Source inputs, the saved program and the Python package versions are checked
before and after execution. The environment is recorded and checked, not copied
into a new virtual environment. Do not update it during a run. Saved artifacts
are hash-checked to detect changes; session files are not a signed security
boundary against deliberate tampering.

The [regression gate policy](REGRESSION_TESTING.md) governs exact values, signs,
periods, units, missing rows and cosmetic differences. Pass `--decisions` with
a source-reviewed decision file to the runner when appropriate. It applies
only to the final comparison and never changes the baseline. Unknown or stale
decisions fail clearly.

A matching output is not an accuracy certification. Known source defects and
`FAIL`, `WARN` and `NOT_TESTED` audit findings remain visible. Diagnostic raw
method amounts remain outside the numerical gate, as documented in Phase 4.

Synthetic orchestration tests are part of the existing pytest suite and CI.
The full PDF suite requires the private local source library and baseline.
