# Collection regression: phase 3

Completed baseline execution across all usable reviewed inputs, with known
defects and accuracy limits retained. Application code was not changed.

- Core: 113/114 workbooks produced.
- Core plus schedules: 100/103 workbooks produced.
- 22,035 core numeric values matched across 8,740 unambiguous source rows.
- All 116 PDFs remain accounted for, including three input exceptions.

[Full results and limitations](../outputs/regression-phase3/REPORT.md)

[Run and workbook index](../outputs/regression-phase3/baseline.csv)

[Reviewed source cases](../outputs/regression-phase3/reviewed-cases.json)

An exported workbook is not a numerical accuracy pass. Confirmed defects include
missing values, split numeric text, mixed-period column loss and truncated
statements. Unresolved source-reader and row-association cases remain separate.

Phase 1 and Phase 2 snapshots, the original/restored source, prior outputs and
the frozen environment remain unchanged. Phase 4 can now build the comparison
gate without treating every current output as correct ground truth.
