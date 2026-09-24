# Workbook repair, phase 2: investment schedule overlap

The PDF schedule writer previously promoted every selected Camelot candidate.
On GBDC physical pages 8-9, three candidates covered the same page area, causing
each investment and subtotal to appear three times. Phase 2 consolidates these
overlapping grids before exporting the investment schedule.

## Behavior and safeguards

- Camelot raw cells now retain PDF row and column bounds. Original candidates,
  their selected flags, and raw worksheet values remain available.
- Consolidation applies only to PDF investment schedules from the same page and
  extraction flavor. Column boundaries must agree within one PDF point, except
  the outer left edge of the label column, which can vary with indentation.
- Rows must occupy the same vertical location (centers within two PDF points,
  with at least 60% overlap of the shorter row) and have identical cell text
  after whitespace normalization. Equal investments at different positions or
  on different pages remain separate.
- Partial overlaps preserve unique rows and source order. Every retained row has
  source table IDs and row indices in `row_sources` on the organized grid.
- Conflicting values or ambiguous row matches fail clearly. Missing geometry or
  incompatible overlapping columns retain both candidates with a review warning.
  There is no content-only deduplication.
- A single standalone date in the first 12 source text lines is attached as the
  schedule context. Multiple possible dates produce a review warning.
- The display repair moves a trailing `PIK` from a maturity cell only when the
  source headers identify adjacent Interest/Maturity columns, the preceding cell
  contains a mixed cash/PIK percentage rate, and the remaining maturity is an
  exact month/year. Raw source text stays unchanged.

This does not change engine selection or numeric-coverage routing. Consolidation
is not proof that a selected page or the full portfolio is complete.

## GBDC acceptance result

Input: frozen `outputs/repair-baseline-20260921/source.pdf`, physical pages 3-9.
The selected schedule covers pages 8-9 only, not the complete portfolio.

| Check | Before phase 2 | After phase 2 |
|---|---:|---:|
| Investment rows | 279 | 93 |
| Subtotal rows | 9 | 3 |
| Excess financial rows | 192 | 0 |
| Source financial rows matched | 96 | 96 |
| Selected numeric values matched | 290 | 290 |
| Missing or changed schedule amounts | 0 | 0 |
| Selected investment fair value, thousands | 1,055,022 | 351,674 |
| Mixed cash/PIK suffixes in the maturity column | 72 | 0 |

All 93 investment types, interest rates and maturities were independently checked
against the frozen source transcription. The output has 25 PIK rates, including
24 repaired mixed cash/PIK rates and one already-correct fixed PIK rate. The June
30, 2026 date is present above both page blocks. Genuine repeated API Holdings
and Denali rows remain with their source multiplicity. All six raw Camelot
schedule candidates remain available; they produce two organized source grids.

The income, cash, equity, Lattice, Stream and PDFPlumber sheets retain their
corrected-baseline cell contents and formats. The separately existing experimental
sheet name `Experiential` is preserved.

## Local evidence and validation

- Workbook: `outputs/GBDC-phase2-final-pages-3-9/FY26_10Q_Golub_Capital_BDC_Inc_and_Subsidiaries.xlsx`
- Comparison: `outputs/GBDC-phase2-final-comparison/comparison.md` and `comparison.json`
- Acceptance checks and per-row rate/maturity results: `acceptance.json` in that folder.
- Organized grids and original row references: `schedule-provenance.json` in that folder.
- Visually reviewed previews: `schedule-top.png`, `schedule-pik.png`, and `schedule-boundary.png`.
- Local acceptance script: `tmp/repair-phase2/verify_acceptance.py`.

Validation passed: 308 project tests, Ruff, dependency checks, and wheel/source
package build. Sixteen new synthetic tests cover overlap, partial-table merging,
genuine repeated rows, conflicting amounts, missing geometry, incompatible
columns, raw extraction preservation, rate guards, and saved-workbook output.
The frozen phase-1 artifacts passed their hash checks.

The overall comparison still exits 1 because the balance sheet is absent,
three cash-flow supplemental rows are missing, and equity headings/alignment
remain defective. These are later repair phases. Other presentation issues
recorded in phase 1 also remain; phase 2 does not certify the entire workbook.
