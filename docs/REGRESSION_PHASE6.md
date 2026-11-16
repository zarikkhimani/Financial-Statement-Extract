# Collection regression: phase 6

For subsequent changes, use the approved reference and acceptance procedure
from [Phase 7](REGRESSION_RELEASE.md). The commands below preserve the original
Phase 6 review procedure against the older Phase 3 baseline.

This repair addresses split negative accounting amounts across issuers. A
source grid containing `(67,502` followed by `)` now exports a numeric `-67502`
in the original amount column. Only the adjacent closing-parenthesis cell is
cleared in the presentation sheet. Original extraction grids remain unchanged.

The rule applies to PDF balance sheets, cash flows and equity/net-asset
statements. It requires an adjacent closing parenthesis, a labelled row, and
at least two positive amounts of 100 or more in that same column on other rows.
Year-only tokens do not establish a numeric column. Spans, percentages, ratios,
malformed numbers, multiple digit fragments, more than 15 digits, unsupported
layouts and schedules remain outside this repair. This is a conservative
eligibility rule, not a numerical comparison tolerance.

The new module is `financial_statement_extract/numeric_layout.py`; the existing
workbook writer calls it at presentation time. No issuer names or filing IDs
are used in production. The regression gate and runner are unchanged.

## Evidence and ongoing workflow

The [Phase 6 report](../outputs/regression-phase6/REPORT.md) records the complete
collection result, exact source-reviewed corrections, validation and remaining
limitations. Its source review uses independent PDF text/coordinates, with
visual review of exceptions, followed by exact saved-workbook comparisons.

For the next extractor change, use a new session and retain the accepted Phase 6
decisions when those exact corrections recur:

```powershell
.venv\Scripts\python.exe scripts/regression_runner.py `
  --session outputs/regression-next-change --workers 8 `
  --decisions outputs/regression-phase6/review/review-decisions.json
```

The decisions bind to exact before/after values and locations. New changes
need new source review; stale decisions fail. Never replace the baseline merely
to clear a regression. Resume an interrupted session with the same session path
and `--resume`; use a new session for a new program version.

This phase does not fix every known defect. Missing prior-period values, mixed
period associations, truncated statements, unresolved digit fragments, and
existing failed or unusable inputs remain separate work. Subsequent repairs
should target one shared defect pattern, prove it against source PDFs, and
repeat the complete collection comparison. One filing's gain cannot offset
another filing's numerical regression.
