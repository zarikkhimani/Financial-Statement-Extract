# Collection regression gate

The [Phase 7 acceptance command](REGRESSION_RELEASE.md) uses the current approved
baseline and adds mandatory full coverage, current-code checks and build/test
validation. The standalone commands below retain the original Phase 3 default.

Use `scripts/regression_gate.py` after changing the extractor. The gate compares
each filing and each extraction scope with the sealed Phase 3 baseline. One
filing's improvement cannot compensate for another filing's regression.

The default comparison expects all 217 runs: 114 core statement jobs and 103
expanded jobs with schedules. The inventory also retains the three input
exceptions. An explicit `--run` selects a partial check and the report states
how many runs were not checked.

## What blocks a change

- Changed numbers, signs, decimal scale, numeric cell types or number formats.
- Missing, duplicated or reordered financial rows, changed data labels, changed
  statement sets, or values moving to different columns.
- Changed period headings, currency, unit captions, scaling, unit exceptions,
  source page associations or selected pages.
- New or changed extraction failures. A recovered failure requires source review
  before its new output is accepted.
- Missing results, mismatched source hashes, stale workbook hashes or invalid
  artifacts. These are evidence errors and cannot receive a review waiver.
- Workbook rule violations on any worksheet, including diagnostic worksheets:
  merges, hidden rows or columns, freeze/split panes, occupied margins, incorrect
  left margin widths, and Excel error cells.

Values are compared exactly as saved in Excel, without a numerical tolerance.
Blank, zero, dash and numeric text remain distinct. The comparator reads the
workbook, not a cached cell export. Duplicate rows retain their multiplicity.
Rows match by label and field position, never by choosing the closest amounts.

Cosmetic titles, sheet names, font styling, and blank spacing do not fail the
numerical gate. Normalized case, whitespace and punctuation in ordinary labels
are tolerated. Period/unit headings and cash-flow section labels remain
protected because they affect the meaning of the numbers. Row alignment is
deliberately conservative; ambiguous changes require review.

## Capture a candidate

Install the existing development dependencies and use the project environment.
Read [AGENT_USAGE.md](AGENT_USAGE.md) before extraction. The helper uses the
public Python API and the exact source pages prepared in Phase 2.

```powershell
.venv\Scripts\python.exe scripts/regression_gate.py capture `
  --candidate outputs/regression-candidate-my-change `
  --run core/b4aa15c3e475a116-1
```

Each `capture` handles one prepared run. Repeat with the required `core/JOB_ID`
and `full/JOB_ID` values from the baseline index. It writes a new workbook,
request, result record and serialized extraction metadata in that run's folder.
It refuses to overwrite an existing run or write inside the sealed baseline.
Failed extractions retain an explicit failed result and return exit code 1.
An interrupted capture without a completed result is invalid evidence.

This is the Phase 4 single-run interface. For collection extraction, progress,
timeouts and resume, use the [Phase 5 collection runner](REGRESSION_RUNNER.md).

## Compare

Full collection gate:

```powershell
.venv\Scripts\python.exe scripts/regression_gate.py compare `
  --candidate outputs/regression-candidate-my-change `
  --report-dir outputs/regression-comparison-my-change
```

Partial development check, explicitly labelled as a subset:

```powershell
.venv\Scripts\python.exe scripts/regression_gate.py compare `
  --candidate outputs/regression-candidate-my-change `
  --run core/b4aa15c3e475a116-1 `
  --report-dir outputs/regression-comparison-my-change-ads
```

The report directory must be new and separate from both input directories.
`comparison.md` summarizes each run. `comparison.json` contains exact before
and after values, issue IDs, source identity, known cases and review decisions.

| Exit | Meaning |
| --- | --- |
| 0 | No unreviewed regression within the stated scope. |
| 1 | Changes require source review, including possible improvements. |
| 2 | Evidence is invalid/incomplete or workbook rules are violated. |

The Phase 3 manifest SHA-256 is pinned in the tool. All 2,296 sealed artifacts
are verified before comparison. `--baseline` supports a relocated copy.
`--baseline-sha256` permits an explicitly selected, separately reviewed future
baseline; it must never be changed merely to bypass a failed comparison.
Source PDFs must remain readable and match their recorded hashes. A relocated
candidate may update its `source_path` to the identical input file, and its
`workbook` path must point inside its own run directory.

## Review a deliberate correction

Review the actual source PDF and saved candidate workbook. Record only the exact
issues that represent source-supported corrections. Never approve a whole BDC,
sheet, numeric range, or all differences just to obtain a passing report.

```json
{
  "baseline_manifest_sha256": "064bca779faac8f3ee88585baed69dbf526e9346626afabe692bf68c0d54219c",
  "accepted_changes": [
    {
      "issue_id": "COPY_THE_EXACT_ISSUE_ID_FROM_COMPARISON_JSON",
      "reason": "Explain the corrected extraction behavior.",
      "source_evidence": "Identify the PDF, PDF page, row label, period and printed amount."
    }
  ]
}
```

Run the comparison again with `--decisions path/to/review.json` and a new
`--report-dir`. Decisions bind to the baseline, run, location and exact before
and after content. Unknown, stale, duplicate or non-waivable issue IDs fail.
The baseline is never updated automatically. Source evidence is a recorded
review assertion, not an automated certification of the PDF.

## Existing defects and limits

An unchanged known defect is not a new regression and is not an accuracy pass.
The four existing extraction failures and the reviewed Phase 3 cases remain
visible. Fixes to known defects still produce explicit differences requiring
source review, so those defects cannot conceal a new change nearby.

The gate protects finished financial statement and schedule sheets. Diagnostic
raw-method cell values are not numerically compared, although workbook rules
apply to all worksheets. The gate does not establish completeness against every
source page, validate every financial identity, or certify absolute accuracy.
The source-matched anchors and limitations from Phase 3 remain relevant.

The private PDF library and baseline are local, not shipped to GitHub. The
synthetic adversarial tests run through the existing pytest/CI test collection:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_regression_gate.py
```

Collection release checks require the local baseline and source library.
Comparing the baseline with itself is an identity control, clearly labelled in
the report. It does not substitute for fresh candidate extraction.
