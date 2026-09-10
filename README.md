# Financial Statement Extract

[![CI](https://github.com/zarikkhimani/Financial-Statement-Extract/actions/workflows/ci.yml/badge.svg)](https://github.com/zarikkhimani/Financial-Statement-Extract/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-2ea44f.svg)](LICENSE)

Local, auditable extraction of financial statements from PDF and HTML filings into reviewable Excel workbooks.

```text
PDF / HTML -> extraction -> normalization -> statement detection
           -> concept mapping -> validation -> Excel
```

> [!IMPORTANT]
> This is an early-stage reference implementation. Always reconcile generated workbooks to the source filing before relying on them. The project is not bank-approved, regulatory-certified, or a substitute for institutional model validation.

## Why this project

Financial Statement Extract is designed for workflows where traceability matters. It keeps raw source values separate from normalized values, records extraction provenance, surfaces uncertainty, and avoids silently inventing periods or converting missing values to zero.

The application runs locally and includes:

- A Windows desktop interface with file browsing and drag-and-drop.
- A command-line interface for repeatable workflows.
- A small Python API for integration into other local tools.
- PDF extraction using PDFPlumber and Camelot (`lattice` and `stream`).
- Local HTML and inline-XBRL statement-table extraction.
- Presentation-ready Excel statements plus editable raw extraction grids.
- Financial consistency checks and explicit `OCR_REQUIRED` reporting.

## Supported inputs and outputs

| Input | Support | Notes |
| --- | --- | --- |
| Machine-readable PDF | Yes | Automatic or explicit page selection; both Camelot modes are retained for comparison. |
| Local HTML / HTM / XHTML | Yes | Detects visible statement tables and inline-XBRL filing metadata. |
| Image-only PDF | Reported, not OCR'd | Pages are marked `OCR_REQUIRED`; no result is fabricated. |

The generated `.xlsx` file can contain:

- `Income Statement`
- `Cash Flow`
- `Balance Sheet`
- `Partners Capital`, when present
- `Schedule of Investments`, when present
- Raw Camelot and PDFPlumber grids for PDF sources

## Quick start on Windows

Requirements:

- Python 3.11 or newer
- A local PDF or HTML filing

Clone the repository, then run:

```bat
install_dependencies.bat
run.bat
```

The installer creates a repository-local `.venv` and installs the application and development tools. The launcher always uses that environment.

To install only the application manually:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install --editable .
.\.venv\Scripts\financial-extract-gui.exe
```

## Command-line use

```powershell
.\.venv\Scripts\financial-extract.exe "C:\Filings\example-10k.pdf" `
  --output-dir "C:\ExtractedStatements"
```

Select PDF pages explicitly when automatic detection is not appropriate:

```powershell
.\.venv\Scripts\financial-extract.exe "C:\Filings\example-10k.pdf" --pages "12,14-16"
```

Run `.\.venv\Scripts\financial-extract.exe --help` for metadata and path-policy options. Page selection is ignored for HTML input.

## Python API

```python
from financial_statement_extract import extract_filing

result, workbook_path = extract_filing(
    r"C:\Filings\example-10k.pdf",
    output_dir=r"C:\ExtractedStatements",
)

print(workbook_path)
print(result.statements.keys())
```

New integrations should import from `financial_statement_extract`. The repository's flat modules remain available for compatibility but are considered internal and may change between releases.

## Auditability and safe defaults

- Raw and normalized data are stored separately; source text is not overwritten.
- Numeric parsing distinguishes dashes, blanks, `N/A`, `NM`, parse errors, currencies, percentages, ratios, and reported precision.
- Values are not automatically rescaled from thousands, millions, or billions.
- Periods are detected per statement and are never extrapolated when missing.
- Mapping records the raw item, standardized item, confidence, rule, and section context.
- Document-derived spreadsheet content is written as literal text; formula and automatic URL conversion are disabled.
- UNC shares, file URL authorities, Windows device namespaces, and reserved DOS device names are rejected by default.
- The application has no upload or telemetry integration.
- Existing output files are not silently overwritten.

Financial checks include balance-sheet balancing, current subtotals, cash roll-forward, cross-statement cash and net-income agreement, duplicate concepts, unit consistency, parse errors, and period alignment.

## Known limitations

- Extraction quality depends on the source document's structure and text layer.
- Image-only PDFs require a separate OCR workflow.
- Parser resource limits and process isolation are not yet implemented; unusually large or adversarial files may consume substantial resources.
- The current desktop experience and automated CI are Windows-focused.
- Results require human review and source reconciliation.

See [Architecture](docs/ARCHITECTURE.md) for component boundaries and design invariants.

## Development

Install the development environment with `install_dependencies.bat`, then run:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m build
```

The same checks run in GitHub Actions on Python 3.11 and 3.12. See [Contributing](CONTRIBUTING.md) before opening a pull request and [Releasing](docs/RELEASING.md) for the maintainer checklist.

## Privacy

Source filings and generated workbooks may contain confidential information. Keep real client files outside the repository even though common financial-document and output formats are excluded by `.gitignore`. Use only synthetic, public, or irreversibly anonymized data in issues and tests.

## Security

Please report suspected vulnerabilities privately. See the [Security Policy](SECURITY.md) for supported versions, reporting guidance, and current security boundaries.

## License

Financial Statement Extract is available under the [MIT License](LICENSE).
