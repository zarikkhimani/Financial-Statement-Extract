# Local collection acceptance

Run from the project root with the existing development environment. The
private PDF library and sealed reference must be available locally. Missing
evidence fails explicitly; hosted CI runs synthetic tests and does not certify
the private collection.

## New extractor change

```powershell
.venv\Scripts\python.exe scripts/regression_release.py run `
  --session outputs/regression-my-change `
  --output outputs/acceptance-my-change --workers 8
```

The command reads `regression-reference.json`, runs the full prepared collection,
and checks the actual saved workbooks. It then runs dependency checks, Ruff,
pytest, CLI startup, source/wheel builds, a built-wheel smoke check, and
`git diff --check`. Source code, tests and documentation must remain unchanged
during these checks. Neither Git commits nor remote publication are performed.

The acceptance reference includes the Phase 6 corrections. Returning a corrected
negative number to the old split text is a regression without needing to carry
the earlier review decisions into every run.

The table-completeness reference also protects recovered later rows and ending
balances. Its promotion and rollback evidence are in
`outputs/regression-table-completeness-phase6/`. Keep using the active reference
file; prior correction decisions are already incorporated into that baseline.

## Resume or reuse matching evidence

An interrupted collection can resume with the original paths and `--resume`:

```powershell
.venv\Scripts\python.exe scripts/regression_release.py run `
  --session outputs/regression-my-change `
  --output outputs/acceptance-my-change --resume --workers 8
```

If extraction completed but the acceptance output directory already exists,
use a new acceptance directory. Finished extraction can be checked separately:

```powershell
.venv\Scripts\python.exe scripts/regression_release.py check `
  --session outputs/regression-my-change `
  --output outputs/acceptance-my-change-reviewed
```

Reuse requires the exact current program, dependencies, full selection, source
PDF hashes and completed attempt hashes. An interrupted newer attempt cannot
fall back to an older success. The checker ignores cached success claims and
recomputes the comparison. Changed code or dependencies require a new extraction
session. Changed tests or documentation require new acceptance checks.

The checker also verifies excluded PDFs against the input inventory. Every PDF
must have prepared jobs or a recorded input exception. Known extraction failures
remain unverified outcomes, even when unchanged.

## Intentional correction and reference update

First inspect the reported differences against the source PDFs. Record exact
issue IDs and source evidence using the [gate decision format](REGRESSION_TESTING.md).
Use the active reference's manifest hash, not the historical Phase 3 hash.

```powershell
.venv\Scripts\python.exe scripts/regression_release.py check `
  --session outputs/regression-my-change `
  --output outputs/acceptance-my-change-reviewed `
  --decisions outputs/my-source-review.json `
  --promote-to outputs/regression-approved-next `
  --reason "Describe the source-supported corrections" `
  --activate-reference regression-reference.json
```

Promotion happens only after all acceptance checks pass. It copies the approved
workbooks and extraction records into a new sealed baseline, preserves historical
cases and the exact correction evidence, and records its parent reference.
The old baseline remains intact. A new reference pointer is written only after
the new baseline verifies. Without the promotion arguments, acceptance never
changes the reference. Never select an older reference to hide a regression.

## Decision and limits

Exit 0 means local collection acceptance. Exit 1 means unreviewed numerical or
coverage changes. Exit 2 means invalid evidence or failed code checks. An
interruption returns 130. `ACCEPTANCE.md`, `acceptance.json`, `comparison.json`,
the check logs and built distributions are saved in the new output directory.

Results separate unchanged runs, reviewed changes, worse/unreviewed changes,
and unverified outcomes. Numeric storage counts include numeric headings and
are not source-accuracy percentages. Core and expanded scopes overlap. Worker
seconds are summed across concurrent jobs. Manual cleanup time is reported as
unmeasured, not zero.

Acceptance protects the observed numbers, labels, periods, units, field
positions, coverage and workbook rules. It does not certify every source amount
or fix existing omissions. Cosmetic headings can remain warnings. Improvements
in one filing cannot offset an unexplained regression in another.

This is local extractor acceptance. Public release, clean installation across
supported Python versions, security review, UI/accessibility acceptance, remote
Git changes and publication remain separate under [RELEASING.md](RELEASING.md).
