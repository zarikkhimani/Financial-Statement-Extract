# Table completeness regression tests

Phase 4 repairs tables that stop before later rows or ending balances, using
the source tests added in Phase 3. The seven confirmed filings are Sixth
Street, Kayne Anderson BDC, PhenixFIN, Trinity, Saratoga, Morgan Stanley Direct
Lending and Progressive.

## Scope

`tests/test_table_completeness.py` exercises the public API and real candidate
scoring, selection, recovery, auditing and workbook writing. External PDF readers
receive portable source snapshots from `tests/fixtures/table_completeness/`.
No original PDFs, archived outputs, network connection or absolute machine paths
are required at test runtime. Reader snapshots do not replace a fresh collection
run after implementation changes.

The fixtures retain source hashes, page numbers, text, word positions and detected
tables. Expectations come from the independently extracted and reviewed PDF
evidence: eight pages, 172 numeric-row candidates and 498 numeric amounts.
Kayne Anderson's blank 2023 tax-benefit cell is explicitly preserved as blank.
Progressive's inline year heading is excluded from the financial-row inventory.
The fixture manifest detects unreviewed edits to inputs or expectations.

Three working statement endings protect 50 numeric cells, their types and
formats. Existing income-period tests and historical controls remain in place.
Adverse-case checks reject wrong values, signs, periods, units, numeric text,
missing or duplicated rows, shifted columns, and zero substituted for blank or
dash. Repeated balances must belong to their own page and period section.
Mixed statements and notes must not become continuation rows. Minor heading
and footnote differences are permitted.

## Run the tests

```powershell
.venv/Scripts/python.exe -B -m pytest tests/test_table_completeness.py
.venv/Scripts/python.exe -B -m pytest tests/test_table_completeness.py --runxfail
.venv/Scripts/python.exe -B -m pytest
```

All 45 targeted tests now pass. The 18 former expected failures are ordinary
required tests: seven page/ending checks, seven complete-row/context checks and
four candidate-selection checks. The source fixtures and expected amounts are
unchanged. Additional repair guards are in `test_table_completeness_repairs.py`.

The program now uses body columns beneath spanning headers, reads through the
last source row instead of stopping at a detected table border, and keeps each
comparative period with its own rows. It preserves source blanks and verifies
amounts and row order before replacing a table. Cash-flow recovery also accepts
years printed on the same line as the period heading.

For unambiguous equity and cash-flow pages, the program selects a more complete
raw candidate only after source-verified statement recovery succeeds and the
candidate preserves every source-supported numeric token already captured.
If recovery fails, the existing display and raw selection stay in place.
Token coverage is a selection aid, not a correctness check.
Raw alternatives and review warnings remain available.

## Phase 4 acceptance

Repair shared behavior without issuer-specific production branches. Preserve
source values, signs, units, periods, blanks, dashes and earlier working rows.
Do not weaken expectations or remove safeguards merely to pass a test. If a fix
needs additional reader geometry, capture it from the source and document it.

Run the entire suite with `--runxfail`. Fresh extraction and source-reviewed comparison of all 217 prepared
runs remain required before accepting a new baseline. Keep previous baselines,
the unconfirmed review queue and known input/ownership exceptions visible.

Phase 3 evidence and the implementation handoff are in
`outputs/regression-table-completeness-phase3/`. Test work directories are retained
for inspection but excluded from the sealed manifest; logs, reports, inputs and
copies of the added test/documentation files are sealed.

Phase 4 implementation and fresh affected-filing checks are recorded in
`outputs/regression-table-completeness-phase4/`. Its subset results do not approve
the remaining collection. Phase 5 runs the complete comparison; the approved
baseline is unchanged until that review and the promotion phase are complete.

The Phase 5 collection review caught a regression in four previously working
equity layouts. Centered unit captions and "unaudited" text were being treated
as overlapping column headings. Header parsing now excludes those captions;
four additional tests protect that distinction and still reject genuinely
overlapping component headings. The original source expectations are unchanged.

Phase 5 evidence is in `outputs/regression-table-completeness-phase5/`.
It retains the rejected run, a fresh full run, source-row and column comparisons,
earlier numerical controls, and a separate decision for each accepted difference.
Baseline promotion remains a separate step.

## Approved reference

Phase 6 uses the reviewed Phase 5 outputs as the next local baseline. Future
changes must preserve the recovered rows and ending balances, as well as the
earlier number and period-column fixes. The previous baseline is retained.

Use `scripts/regression_release.py` with `regression-reference.json` for future
changes. The completed promotion and rollback checks are recorded in
`outputs/regression-table-completeness-phase6/`. The 133 unconfirmed review
scopes, four known extraction failures and three input exceptions remain open.
