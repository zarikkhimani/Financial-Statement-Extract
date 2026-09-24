# Financial Statement Extract

Financial Statement Extract helps analysts convert PDF and HTML financial filings into structured, reviewable Excel workbooks.

The project is designed for controlled financial workflows. It runs locally, preserves source detail, records extraction provenance, and highlights uncertainty for review. It does not silently create missing periods, convert blanks to zero, or rescale reported values.

The extractor can handle financial statements from most public companies,
business development companies (BDCs), private investment companies, '40 Act
funds, insurance companies, and specialized businesses such as data centers.

> **Project status:** Early-stage software for reviewed extraction. The package
> version remains 0.1.0; current development changes are unreleased. Reconcile
> every workbook to its source filing before use.

See the [changelog](CHANGELOG.md) for changes and [release readiness](docs/RELEASE_READINESS.md)
for outstanding validation.

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

Launch `run.bat` from your unlocked Windows desktop. Keep the application open
until extraction finishes. Closing a pending job requires confirmation and may
leave an incomplete workbook. Minimizing the window keeps the app running.

### Updating an existing installation

Close the application, preserve any local code changes, and obtain the intended
release. Run `install_dependencies.bat` from that release folder, then `run.bat`.
The installer reuses or creates the folder's `.venv` and installs the project and
its dependencies. Keep filings and generated workbooks outside the source folder.

### Extract a filing

1. Drag a supported filing into the application, or select it with **Choose filing**, **Filing…**, or **File → Browse filing**.
2. Choose the output folder.
3. For PDFs, leave **PDF pages** on Auto, or enter specific pages such as `12,14-16`. Use **Show setup** if collapsed and **Show details** for optional client, year, period, and audit settings.
4. Select **Extract to Excel**.
5. Review the workbook and reconcile the results to the source filing.

After extraction, use **Open workbook** or **Open output folder**. The Statements
and Checks tabs summarize the result; **Show diagnostics** exposes technical detail.
Warnings and unperformed checks remain marked for review. If extraction fails,
follow the recovery guidance, adjust setup, and select **Retry**.

Settings and accessibility preferences last for the session. Changes made during
extraction apply to the next run. Use **View -> Text size** for 100-200% text,
**View -> Use Windows system colors** for the Windows palette, **F1** for
shortcuts, and **F8** for the current status summary.

Manual PDF selections over 50 pages pause for review before table extraction.
Choose the entered pages, a conservative suggestion, or cancel. Auto mode searches
for statement sections, including equity and investment schedules; ambiguous or
unreadable sections remain subject to review. HTML filings do not use PDF page
selection.

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
- Stockholders' Equity
- Schedule of Investments
- Editable raw extraction grids for PDF sources

Worksheets retain source titles and item labels. Supported PDF layouts organize
amounts under their reporting periods and preserve statement-specific details,
such as equity components and investment terms. Unsupported layouts may retain
original extraction grids with warnings; review them against the filing.

Every exported worksheet has three blank rows at the top and two blank columns
on the left, each with Excel width 1. Worksheets contain no merged cells, hidden
rows or columns, or freeze panes.

PDF output includes editable raw extraction sheets and an experimental comparison
sheet currently named `Experiential`. That experiment performs a separate PDF pass,
adds processing time, and does not feed the baseline financial checks. See the
[experimental workflow](docs/PDFPLUMBER_EXPERIMENTAL.md) for details.

The `Review` sheet records financial and extraction checks. Depending on the
available source data, checks include balance-sheet equations, cash and equity
roll-forwards, cross-statement agreement, and source coverage. Warnings, failures,
and checks that could not be performed remain visible. Passing checks do not
prove that every source row was captured.

## AI agent use

AI agents with access to local files and a terminal can run Financial Statement
Extract through its command-line interface or Python API. Provide the agent
with the project folder, source filing, and output folder. The
[agent usage guide](docs/AGENT_USAGE.md) covers installation, extraction,
result inspection, and recovery; [`AGENTS.md`](AGENTS.md) directs repository
agents to those instructions.

Example request:

> Read `docs/AGENT_USAGE.md` and extract `C:\Filings\example-10k.pdf` into
> `C:\ExtractedStatements`. Report the workbook path, selected pages,
> statements found, and outstanding review findings. State which results
> you checked against the source filing.

Agent workflows use the same extraction pipeline as the desktop application.
Generated workbooks remain subject to source reconciliation before use.

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

- Extraction quality depends on document structure and its text layer. Some
  layouts still omit or misalign content; reconcile rows, periods, and amounts.
- Image-only PDFs require a separate OCR process.
- Large or adversarial files may consume substantial workstation resources.
- The desktop app and tests are Windows-focused. Screen-reader and Windows
  contrast-theme acceptance are still open.
- Output supports review; it does not replace professional judgment or constitute
  regulatory certification or institutional model validation.

## Privacy and security

Financial documents and generated workbooks may contain confidential information. Keep client files outside the repository and use only synthetic, public, or irreversibly anonymized data in issues and tests.

Network shares, file URL authorities, Windows device namespaces, and reserved DOS device names are rejected by default. See the [Security Policy](SECURITY.md) for reporting guidance and current security boundaries.

## Development

The installation script includes development tools. Before submitting a change,
run:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m build
```

GitHub Actions runs these checks on Python 3.11 and 3.12.

Run `run_ui_review.bat` to exercise the live app with synthetic corporate, fund,
and failure cases. Generated workbooks go to a new `tmp/ui-review/session-*`
folder. See the [UI review guide](docs/UI_PHASE8.md) for procedures and historical
results, and [release readiness](docs/RELEASE_READINESS.md) for current open items.
The separate `run_ui_preview.bat` is a sample-data design preview and does not
extract documents.

## Project documentation

- [AI agent usage guide](docs/AGENT_USAGE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Contributing](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)
- [Release readiness](docs/RELEASE_READINESS.md)
- [Release procedure](docs/RELEASING.md)
- [Changelog](CHANGELOG.md)

## License

Financial Statement Extract is available under the [MIT License](LICENSE).
