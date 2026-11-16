# Income period regression tests

Phase 4 repairs PDF income reporting columns using source header evidence.
Fresh core exports recover 1,172 previously trapped amounts in 604 traced rows
across 26 of the 27 affected filings. Phase 5 accepted all 217 prepared runs:
52 source-reviewed improved exports, 161 unchanged exports and four unchanged
known failures. All 674 tests passed. Three input exceptions remain documented.

The active reference is selected by `regression-reference.json`. Phase 6 uses
the supported acceptance command to promote the reviewed outputs into a new
sealed baseline, preserves the old baseline, and checks that prior outputs
which lose the repaired numbers are rejected. Neither source accuracy nor
completion of the known failed extractions is implied by reference acceptance.

The PSEC quarterly filing remains deferred. Its income section also contains
unclassified equity pages. Reinterpreting the entire section with four income
periods would damage existing equity numbers. The generic mixed-statement guard
retains the original output and adds a review warning. Its 20 traced rows and
40 trapped amounts are still unresolved. Separate page ownership and equity
component verification are required before applying the repair to that filing.

Phase 5's first full collection run also exposed unclassified schedule pages in
TSLX's expanded income section. The mixed-statement guard now recognizes
schedule-of-investments headings and preserves that section with a warning.
The isolated core income statement retains the repair. The second fresh full
collection run verified the safeguard: all 570 rows in the expanded section,
their fields and metadata remain unchanged. Expanded page ownership still
needs separate repair.

## Implementation boundaries

`financial_statement_extract/income_periods.py` finds a bounded source header,
keeps repeated years associated with their reporting durations, and accepts
only a unique date/duration/year grouping. It handles three-, four- and
five-column layouts without an issuer-specific branch. Adjacent full dates
are separated for header analysis only; original raw text remains intact.

Ambiguous transition headers use PDF word positions, including ICMB's distinct
twelve-month and six-month reporting columns. If source evidence cannot resolve
the grouping, the existing result remains visible with an explicit warning.
Body amounts never establish the number of reporting periods.

Bounded PDF geometry also keeps KBDC's vertically offset dashes in their actual
columns and preserves PFX's blank source cell. A missing value stays missing;
the repair does not invent zero. Recovered rows retain source line and word
evidence. Adjacent currency prefixes are separated in parser copies when that
produces a complete source-sized row, keeping SCM's two loss rows distinct.
Ordinary complete income headers keep their existing labels.

The PDF pipeline prepares parser copies only. Raw extraction, HTML income
parsing, other statement parsers and workbook writers keep their existing
behavior. Mixed unclassified statement sections
are explicitly deferred rather than reinterpreted with new column counts.

## Portable tests

`tests/test_income_period_regression.py` checks reporting-period identity,
numeric rows and saved Excel cells separately. Nine real excerpts cover BBDC,
Blue Owl Capital Corporation II, CION, ICMB, SCM annual, OFS, PSEC, Trinity and
MSDL. All nine header pages and 27 selected rows (108 amounts) were visually
reviewed in Phase 3. PSEC's isolated income excerpt passes; this does not imply
that its mixed full-filing section is repaired.

`tests/income_period_cases.py` retains the source text, filename/hash/page and
independent expectations. Only verified header word positions were added to
the ICMB input. None of the expected amounts or reporting periods changed.
The 29 resolved expected-failure markers were removed. No PDFs, archived output,
absolute machine paths or network access are needed to run these tests.

`tests/test_income_period_geometry.py` adds source-backed KBDC/PFX row tests,
adversarial geometry/header checks and the mixed-statement preservation guard.
The saved geometry is in `tests/income_geometry_case.py`.

`tests/income_period_controls.py` retains six previously source-reviewed
controls (18 numeric cells), including accounting negatives, share counts and
SLR's four valid source-grid columns. Five deliberate workbook corruptions
test duration swaps, amount swaps, sign flips, numeric text and missing zero.

```powershell
.venv/Scripts/python.exe -m pytest tests/test_income_period_regression.py tests/test_income_period_geometry.py --runxfail
.venv/Scripts/python.exe -m pytest --runxfail
```

Phase 4's final full suite passes 673 tests, with no skips or expected failures.
All workbook margin, visibility, merge and freeze-pane rules remain enforced.

## Collection verification

Phase 4 reruns 36 jobs from a fixed code snapshot: all 27 affected core filings,
six additional control filings and three expanded jobs. Review reads saved
Excel cells, checks the 604 repaired source-traced rows, and protects the 18
specific historical control cells. Other statement frames and finished sheets
are compared unchanged against the approved baseline.

An earlier 213-run saved-input replay was diagnostic. It exposed PFX and PSEC
boundary problems and is not verification of the final guarded implementation.
Likewise, the initial fresh subset contains a rejected PSEC boundary change.
Phase 4's source proofs are in `outputs/regression-column-loss-phase4/candidate`
and its final review. Its intermediate `fresh-final` round predates the SCM
row-boundary repair. The accepted Phase 5 implementation is in
`outputs/regression-column-loss-phase5/recheck`, including the schedule guard.
All diagnostic rounds remain available as evidence of changes caught before
acceptance.

The full collection preserves the 604 traced rows, 1,172 recovered amounts and
18 historical protected cells. It also verifies two additional CCAP PIK amounts
in their proper reporting columns, preserving a blank and a dash as missing
values and keeping the following dividend row separate. Other statement
outputs and raw source text/tables remain unchanged.

Follow `REGRESSION_RELEASE.md` for future changes: all 217 prepared runs, source
review, the known failure inventory and regression comparisons remain required.
Use the active reference without old review decisions for an unchanged program.
Any new correction needs its own exact source-supported decision. A passing
subset does not certify full-collection accuracy. Keep the PSEC and expanded
TSLX deferrals, four known failures, three input exceptions, and existing
balance/equity defects visible.

Sealed Phase 5 evidence is in `outputs/regression-column-loss-phase5`.
Promotion, preservation and rollback-check evidence is recorded in
`outputs/regression-column-loss-phase6`. Earlier phase evidence is preserved.
