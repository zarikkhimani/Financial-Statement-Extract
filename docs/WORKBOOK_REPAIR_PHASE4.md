# Workbook repair, phase 4: equity components

GBDC's page 5 was classified as changes in net assets (`PartnersCapital`). Its
selected PDFPlumber body grid contained all amounts, but omitted the headers
above the ruled data box. Currency/spacer cells also changed the physical amount
columns between balance rows and movement rows. The earlier equity recovery
targeted a different statement classification and assumed the first detected box
was the body, whereas this PDF has a small Common Stock header box first.

## Repair

The PDF display recovery now uses the wide body table to establish component
boundaries. It reads source words by PDF coordinates, reconstructs parent/leaf
headers, and assigns each amount to a stable component. This applies to both
equity and changes-in-net-assets classifications on unambiguous PDF pages.

The `Changes in Net Assets` sheet has these source columns:

| Excel column | Source component |
|---|---|
| B | Shares |
| C | Par Amount |
| D | Paid in Capital in Excess of Par |
| E | Distributable Earnings (Losses) |
| F | Total Net Assets |

The Common Stock parent header spans Shares and Par Amount. The unit note remains
`In thousands, except share data`. Balances and total-change rows receive emphasis.
Four source-defined reporting periods have repeated component headers and clear
spacing. Period captions come from each source total-change row, not inferred
dates. Identical closing balances in separate rollforwards remain separate rows.

Raw method tabs and extraction candidates are preserved. Recovery changes only
the organized equity display grid and its writer; analytical mappings and engine
selection remain as before. Each recovered grid records original candidate IDs,
word coordinates, component boundaries, header words and period-caption sources.

## Verification and bounds

Geometry must agree across body boxes. Every component must have a distinct
source leaf header, and data cells must contain a single valid value or explicit
missing token. The ordered labels and complete value vectors must agree with
the page text. Each original candidate's amount vectors must also be preserved,
including genuine repeated rows within a candidate.

Conflicting values, missing headers, ambiguous component boundaries, unsupported
wrapped data, or ambiguous page ownership retain the original grids for that
statement and produce an explicit `Equity component layout` Review warning.
This bounded recovery does not claim support for every equity PDF layout.

## GBDC acceptance

Reran physical PDF pages 3-9 using the frozen phase-1 input.

- All **39 financial rows and 126 numeric amounts** match the PDF.
- All five components occupy columns B-F on every financial row.
- All four total-change rows and all eight opening/closing balances remain.
- No missing, changed, excess duplicate or unstructured equity rows were found.
- The nine- and three-month periods ended June 30, 2025 and June 30, 2026 are
  separately labeled, preserving source order.
- All five component movement sums and beginning-plus-change checks pass in
  each of the four periods (20 component rollforwards).
- Income, cash-flow, investment-schedule and all raw/experimental worksheet
  contents and cell formatting are unchanged from the phase-3 workbook.
- **Every worksheet has no freeze panes.** The previously generated phase-3
  cash sheet's freeze setting is absent in this new output, as requested.

The workbook's top, middle and bottom sections were rendered and visually
reviewed for headings, wrapping, alignment and period separation.

## Local evidence

Accepted workbook:
`outputs/GBDC-phase4-verified-pages-3-9/FY26_10Q_Golub_Capital_BDC_Inc_and_Subsidiaries.xlsx`

Evidence: `outputs/GBDC-phase4-verified-comparison/`:

- `comparison.md` / `comparison.json`: frozen-baseline comparison.
- `acceptance.json`: component assignments, period reconciliations, preservation
  checks, no-freeze checks and workbook hash.
- `equity-provenance.json`: source geometry and organized display grid.
- `equity-top.png`, `equity-middle.png`, `equity-bottom.png`: reviewed renders.

Local acceptance script: `tmp/repair-phase4/verify_acceptance.py`.
Other phase-4 outputs are development runs.

All **330 tests** passed, including ten new equity recovery/export cases. Ruff,
dependency checks and source/wheel builds passed. Baseline hashes were verified.
Final scope review compared the writer and pipeline with copies taken at the
start of this phase, preserving pre-existing uncommitted work.

The overall comparison still exits 1: the balance sheet remains absent, and the
previously documented income-label and cash-footnote diagnostics remain. Phase 5
recovers the balance sheet; phases 6-7 cover broader review and final acceptance.
