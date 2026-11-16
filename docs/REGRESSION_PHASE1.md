# Collection regression: phase 1

Completed November 15, 2026. The current program, inputs, environment and prior
outputs are preserved in a local snapshot. Application code was not changed.
The existing uncommitted work is included in the saved source.

- [Snapshot and restore instructions](../outputs/regression-baselines/phase1-20261116T025555Z/README.md)
- [Filing index, CSV](../outputs/regression-baselines/phase1-20261116T025555Z/filings.csv)
- [Detailed filing manifest](../outputs/regression-baselines/phase1-20261116T025555Z/filings.json)
- [Known issues and evidence limits](../outputs/regression-baselines/phase1-20261116T025555Z/known-issues.json)
- [Validation results](../outputs/regression-baselines/phase1-20261116T025555Z/validation/RESULTS.md)

The inventory covers all 116 unique PDFs in `C:\Users\zarik\Desktop\Loan Files`:
98 annual/quarterly filings for 49 BDC issuers and 18 additional annual reports.
It preserves 98 companion HTML files, 98 historical page selections, 105 library
workbooks and 92 project output workbooks. Workbooks are preserved comparison
candidates, not automatically accepted correct results.

SHA-256 verification matched all 9,569 archived files to their originals.
An isolated offline restore matched all 40 installed package versions and passed
456 tests, Ruff, pip check, CLI startup and source/wheel builds.

The catalog leaves seven reporting dates for review. PyMuPDF reported a page-tree
error in the supplementary Travelers 2023 PDF; the file and error are preserved.
This was a cover-date lookup, not a complete readability or extraction test.

Phase 2 will confirm financial-statement and continuation-page coverage for all
116 PDFs, including reporting periods and units. It will measure automatic page
detection separately from extraction on confirmed pages. Numeric comparisons
come after that. Cosmetic heading defects may remain warnings; amounts, signs,
periods, units and row associations remain essential.

The snapshot is ignored by Git and remains local. Nothing was committed or
pushed. Keep it unchanged and use a new directory for later runs.
