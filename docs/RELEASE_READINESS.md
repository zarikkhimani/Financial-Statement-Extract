# Release readiness

Status: **In preparation.** Version and release date are not yet selected.
This document tracks the next release; [Releasing](RELEASING.md) describes the
procedure. Update this record as evidence changes. Historical test results do not
approve a later candidate.

## Scope

- Updated Windows desktop workflow, progress reporting, results, and recovery.
- Automatic PDF page discovery and review of large manual selections.
- Improved statement layouts, source preservation, and workbook review checks.
- An experimental PDF comparison worksheet, documented separately from the
  baseline extraction output.

OCR and unattended accuracy across arbitrary filings are outside the current
capabilities. See the [README](../README.md) for user-facing limitations.

## Open release checks

| Item | Current evidence | Required before release |
| --- | --- | --- |
| Corporate 10-K balance-sheet completeness | The [Apple balance-sheet acceptance](APPLE_BALANCE_REPAIR_PHASE6.md) records the repaired sheet passing source, amount, arithmetic, and presentation checks. | Preserve this regression coverage and validate other corporate layouts. Acceptance covers the tested Apple balance sheet; unsupported layouts remain unverified. |
| Broader filing coverage | Acceptance is limited to selected pages. Other samples retain layout and coverage warnings. | Reconcile representative PDF and HTML outputs to source, record exact page scopes, and document remaining limitations. |
| Visual review | Partial BDC review at 640 × 700 and 150% text. | Complete wide/narrow windows, 100/150/200% text, long results, setup, and error states. |
| Accessibility | Earlier inspection found unnamed workspace panes. | Verify core tasks with Narrator or NVDA and an actual Windows contrast theme; resolve failures. |
| Final automated checks | Earlier runs are recorded in the phase notes. | Run dependency, lint, test, and build checks against the final candidate on supported Python versions. |
| Clean installation | Earlier isolated checks covered startup without the full extraction dependencies. | Install the built wheel with dependencies in a fresh environment; run GUI, CLI, PDF, and HTML extraction outside the source checkout. |
| Compatibility and experimental output | Workbook layouts and public extraction options have changed; PDF runs include an additional experimental pass. | Review API/CLI and workbook compatibility, processing cost, and whether the experimental worksheet will ship. Document the decision. |
| Release contents and security | Existing policy covers local processing, literal workbook text, path restrictions, and parser resource limits. | Review the final diff and artifacts for confidential data; verify security controls and dependency status. Record security review scope and unresolved findings. |
| Documentation and images | README, changelog, and release procedure consolidated. | Confirm claims against the final build and add reviewed screenshots using public or synthetic data with personal paths removed. |

## Accepted evidence and its limits

The [BDC statement repair acceptance](WORKBOOK_REPAIR_PHASE7.md) records successful
source reconciliation for selected statement pages. This bounded acceptance does
not establish full-filing completeness or resolve findings in other BDC and
corporate 10-K layouts. Accessibility, scan-memory, and broader coverage concerns
remain documented in the [UI acceptance record](UI_PHASE8.md).

The [Apple balance-sheet acceptance](APPLE_BALANCE_REPAIR_PHASE6.md) records
reconciliation of all 27 balance-sheet rows, 54 amounts, and 18 arithmetic
equations in the saved workbook from pages 32–36. It also records successful
packaged CLI extraction and an explicit completeness failure when layout
recovery was deliberately disabled. This resolves the documented Apple
balance-sheet omission; it does not establish completeness for other statements
or corporate layouts.

The reviewed BDC output retains warnings and untested checks, and its selected
investment schedule is partial. Other sample checks establish regression stability
for the documented inputs, not complete source coverage. Both acceptance records
remain bounded historical evidence and must be checked against the final release
candidate.

## Evidence to record for the final candidate

- Version, commit, review date, reviewer, Windows version, and Python version.
- Commands run and results, including clean-install extraction.
- Filing identity, exact pages, source comparison, and remaining warnings.
- Visual and accessibility outcomes, with sanitized evidence where appropriate.
- Security review scope, dependency review, and disposition of findings.
- Built artifact names and SHA-256 hashes.

Keep confidential evidence and generated workbooks outside version control.
Do not describe the release as security-audited or accessibility-approved without
the corresponding review. Publication requires an explicit request.
