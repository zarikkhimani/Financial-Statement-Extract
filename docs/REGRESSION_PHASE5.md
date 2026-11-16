# Collection regression: phase 5

Completed the resumable collection runner and the full collection comparison.

- All 217 prepared runs were freshly executed: 213 workbooks match the
  baseline and four known failures are unchanged.
- No new regression events or infrastructure errors. Three input exceptions
  remain documented. Existing numerical defects are not certified as correct.
- Actual shutdown recovery verified: 127 completed attempts were reused,
  and the remaining 90 ran without overwriting earlier work.
- All 543 tests passed, including 24 runner tests. Ruff and dependency checks
  passed. Detailed validation records are linked in the results report.

[Results and evidence](../outputs/regression-phase5/REPORT.md)

[Run or resume the collection](REGRESSION_RUNNER.md)

The runner captures one program version, limits concurrent workers, enforces
timeouts, saves logs and hashes, preserves retries and calls the Phase 4 gate.
Numerical changes require source review; cosmetic headings do not fail the
gate. Extraction logic and prior baselines remain unchanged.
