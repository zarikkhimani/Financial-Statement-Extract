# Collection regression: phase 4

Implemented the numerical regression gate without changing extraction logic.

- All 217 baseline runs pass the identity control. The four known extraction
  failures and three input exceptions remain visible.
- Eight fresh representative runs show no new regression: six completed
  workbooks match, and two known failures reproduce unchanged.
- All 11 deliberate real-workbook controls behave as expected, including
  changed amounts, signs, scales, numeric text, missing values/rows, duplicate
  rows, periods, units, a cosmetic title and a forbidden freeze pane.
- All 519 project tests pass, including 63 gate tests. Ruff, dependency checks,
  CLI checks and package builds pass.

The gate checks each filing separately, reads actual saved Excel values, and
blocks unexplained numerical or coverage changes. Cosmetic heading defects do
not fail it. Source-supported improvements require specific review decisions
bound to the exact change. Existing defects are not certified as correct.

[Usage and acceptance policy](REGRESSION_TESTING.md)

[Detailed validation and limits](../outputs/regression-phase4/REPORT.md)

All 48 Phase 1 artifacts, 520 Phase 2 artifacts and 2,296 Phase 3 artifacts remain
sealed and unchanged. The 153 original/restored program files and 693 existing
library/output files also match their saved hashes.

Phase 5 can build the resumable collection runner around this gate. Phase 4
does not claim that all 217 jobs were freshly rerun; that count is the baseline
identity control, with fresh execution verified on the eight-run sample.
