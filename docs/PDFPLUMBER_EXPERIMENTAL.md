# PDFPlumber experimental workflow

PDF runs now produce an `Experiential` worksheet next to `PDFPlumber`.
The experiment runs automatically on the same resolved page selection, including
when adaptive extraction skips Camelot. HTML and pasted-text runs are unchanged.

The starting algorithm is a copy of the baseline PDFPlumber extractor. Within
each extracted row, whitespace between `$` and a following digit is
removed first (for example, `$   7234` becomes `$7234`). This also joins a trailing
`$` to a number in the next nonempty cell, consuming any empty cells between them.
It never joins across rows or skips intervening text. Dollar amounts within a cell then
split into adjacent columns: `Assets $50 $60` becomes `Assets`, `$50`, `$60`.
Runs of numbers separated by horizontal whitespace also split into adjacent
columns: `Assets 123,456 123,456` becomes `Assets`, `123,456`, `123,456`.
An em dash also counts as an amount placeholder for splitting: `123 — 123`
becomes `123`, `—`, `123`. The dash is preserved, not converted to zero.
Single numbers within labels are left in place unless they have a dollar sign.
Days from 1 through 31 immediately after a month name remain with the month and
preceding label. Month matching ignores case and supports full names, abbreviated
names (with optional periods), and `Feburary`. For example, `January 31 123 456`
becomes `January 31`, `123`, `456`.
A four-digit year following the day stays with the date as well, with an optional
comma and required whitespace before the year. For example,
`Balance at June 30, 2025 123 (456)` becomes `Balance at June 30, 2025`, `123`, `(456)`.
This does not treat `30,2025`, dollar amounts, or decimal values as a date year.
Existing cells to the right shift to make room; other empty cells are retained.
Commas and decimal places stay with their amounts. This cleanup applies
only to the experimental workflow.

Make
experimental extraction changes in
`financial_statement_extract/pdfplumber_experimental.py`. It calls PDFPlumber
independently; it does not copy the baseline output. Normalization, page-number
parsing, and equity geometry helpers remain shared. Change or copy helpers inside
the experimental module if an experiment needs different behavior.

Experimental raw cells, normalized cells, and audit rows have separate fields on
`ExtractionResult`. They never enter baseline coverage, fallback selection,
statement organization, or financial audits. Page extraction errors appear in
the workbook Review sheet with the experimental label. File-open errors propagate.
The second pass adds PDF processing time.

This is an isolated code path within the working tree, not a separate Git branch,
so both tabs can be compared in the same workbook.

## Removal

Remove the experimental module, its import and call in `pipeline.py`, the three
experimental result fields and constructor arguments, and the experimental sheet
and review-audit wiring in `excel_writer.py`. Remove the corresponding test
expectations. The original extractor does not depend on the experiment.
