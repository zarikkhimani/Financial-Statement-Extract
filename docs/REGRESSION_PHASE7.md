# Collection regression: phase 7

Phase 7 makes broad validation a requirement for local extractor acceptance.
The [acceptance command](REGRESSION_RELEASE.md) ties full collection evidence to
the current program and environment, runs repository checks, and records the
release decision and remaining limitations.

The [phase report](../outputs/regression-phase7/REPORT.md) records the executed
checks, per-filing outcomes, baseline promotion and rollback control. The new
approved baseline retains the source-reviewed Phase 6 corrections; all earlier
baselines remain unchanged. Production extraction logic is unchanged in Phase 7.

The current numeric reference is pinned by `regression-reference.json`.
Its artifacts and the private source library remain local. Known failures and
input exceptions remain visible. This phase accepts the extractor for the
collection workflow; it does not publish a release or certify universal accuracy.
