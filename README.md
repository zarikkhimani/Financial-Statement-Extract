# Financial Statement Extract

Financial Statement Extract helps analysts convert PDF and HTML financial filings into structured, reviewable Excel workbooks.

The project is designed for controlled financial workflows. It runs locally, preserves source detail, records extraction provenance, and highlights uncertainty for review. It does not silently create missing periods, convert blanks to zero, or rescale reported values.

> **Project status:** Version 0.1.0 is an early-stage reference implementation. Every generated workbook should be reconciled to the source filing before use. The project is not bank-approved, regulatory-certified, or a substitute for institutional model validation.

## Start here

The desktop application is the simplest way to evaluate the project.

### Requirements

- Windows
- Python 3.11 or newer
- A local PDF or HTML filing

### Install and run

After cloning or downloading the repository, open the project folder and run:

```bat
install_dependencies.bat
run.bat
```

The installer creates an isolated Python environment inside the project folder. The launcher uses that environment automatically.

### Extract a filing

1. Drag a supported filing into the application, or select it with **Browse**.
2. Choose the output folder.
3. Leave **Pages** on Auto, or enter specific PDF pages such as `12,14-16`.
4. Select **Extract to Excel**.
5. Review the workbook and reconcile the results to the source filing.

HTML filings do not use PDF page selection.

## Supported sources

| Source | Support | Notes |
| --- | --- | --- |
| Machine-readable PDF | Supported | Uses automatic or manual page selection and retains PDFPlumber and Camelot extraction data. |
| Local HTML, HTM, or XHTML | Supported | Detects visible statement tables and inline-XBRL filing metadata. |
| Image-only PDF | Identified only | Pages are marked `OCR_REQUIRED`; the application does not perform OCR or fabricate a result. |

## Workbook output

Depending on the filing, the generated workbook may include:

- Income Statement
- Cash Flow
- Balance Sheet
- Partners Capital
- Schedule of Investments
- Editable raw extraction grids for PDF sources

The workbook also includes financial consistency checks where the necessary source data is available. These checks cover balance-sheet balancing, current subtotals, cash roll-forward, cross-statement cash and net-income agreement, duplicate concepts, unit consistency, parse errors, and period alignment.

## Command-line use

The command-line interface is useful for repeatable local workflows:

```powershell
.\.venv\Scripts\financial-extract.exe "C:\Filings\example-10k.pdf" `
  --output-dir "C:\ExtractedStatements"
```

To select PDF pages manually:

```powershell
.\.venv\Scripts\financial-extract.exe "C:\Filings\example-10k.pdf" --pages "12,14-16"
```

Run `.\.venv\Scripts\financial-extract.exe --help` to view all available options.

## Python use

The supported Python API is intentionally small:

```python
from financial_statement_extract import extract_filing

result, workbook_path = extract_filing(
    r"C:\Filings\example-10k.pdf",
    output_dir=r"C:\ExtractedStatements",
)

print(workbook_path)
print(result.statements.keys())
```

New integrations should import from `financial_statement_extract`. The flat modules in the repository remain available for compatibility but are considered internal.

## Review and control features

- Raw and normalized values are stored separately.
- Dashes, blanks, `N/A`, `NM`, parse errors, currencies, percentages, ratios, and reported precision remain distinguishable.
- Values are not automatically rescaled from thousands, millions, or billions.
- Reporting periods are detected by statement and are not extrapolated when missing.
- Concept mapping records the source item, standardized item, confidence, rule, and section context.
- Document-derived spreadsheet content is written as literal text; formula and automatic URL conversion are disabled.
- Existing output files are not silently overwritten.
- The application has no upload or telemetry integration.

## Important limitations

- Extraction quality depends on the source document's structure and text layer.
- Image-only PDFs require a separate OCR process.
- Large or adversarial files may consume substantial workstation resources.
- The desktop application and automated tests are currently Windows-focused.
- Output is intended to support review, not replace professional judgment.

## Privacy and security

Financial documents and generated workbooks may contain confidential information. Keep client files outside the repository and use only synthetic, public, or irreversibly anonymized data in issues and tests.

Network shares, file URL authorities, Windows device namespaces, and reserved DOS device names are rejected by default. See the [Security Policy](SECURITY.md) for reporting guidance and current security boundaries.

## Development

The installation script includes the development tools used by the project. Before submitting a change, run:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m build
```

The same checks run in GitHub Actions on Python 3.11 and 3.12.

## Project documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Contributing](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)
- [Release Checklist](docs/RELEASING.md)
- [Changelog](CHANGELOG.md)

## License

Financial Statement Extract is available under the [MIT License](LICENSE).
