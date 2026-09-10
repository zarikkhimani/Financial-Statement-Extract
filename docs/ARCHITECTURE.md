# Architecture

Financial Statement Extract is a local Python library with a thin Windows desktop interface. Its core data flow is:

```text
PDF / HTML filing
  -> source extraction
  -> normalization and structural detection
  -> statement parsing and concept mapping
  -> financial and extraction checks
  -> Excel workbook
```

## Boundaries

- `financial_statement_extract/` is the supported package API and command-line surface.
- `app.py` owns the Tkinter desktop interface and delegates extraction to the pipeline.
- `pipeline.py` orchestrates parsing, metadata, audit checks, and workbook creation.
- `extractors.py` and `html_extractor.py` adapt third-party PDF and HTML parsers.
- `normalization.py`, `structure.py`, `statements.py`, and `mapper.py` preserve source semantics while producing structured statement rows.
- `audit.py` produces consistency checks; it does not silently repair source data.
- `excel_writer.py` writes presentation worksheets and literal raw extraction grids.
- `path_policy.py` rejects implicit network and Windows device paths before filesystem access.

The current flat implementation modules remain importable for compatibility. New consumers should import only from `financial_statement_extract`; internal modules may change between releases.

## Security-relevant invariants

1. Document-derived strings are data, never formulas or automatic hyperlinks.
2. Network, UNC, and Windows device paths are denied unless a library or CLI caller explicitly opts in.
3. Source values and raw extraction records are retained; missing data is not replaced with zero.
4. Existing output files are not silently overwritten.
5. The application has no upload or telemetry path and processes selected files locally.

## Current limitations

- Image-only PDFs require a separate OCR workflow.
- Extraction results require reconciliation to the source filing before use.
- Parser resource limits and process isolation are not yet implemented; exceptionally large or adversarial documents can consume substantial CPU or memory.
- The project is not a regulatory certification, model validation, or bank production approval.
