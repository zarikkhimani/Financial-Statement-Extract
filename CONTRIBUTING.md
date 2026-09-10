# Contributing

Thank you for helping improve Financial Statement Extract. Changes should preserve source fidelity, reviewability, and safe local defaults.

Report suspected vulnerabilities through the private process in [SECURITY.md](SECURITY.md), not through a public issue.

## Development setup

On Windows, run `install_dependencies.bat`. It creates `.venv` in the repository and installs the project with its development tools.

Manual equivalent:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --editable ".[dev]"
```

## Before submitting a change

Run the same checks used by CI:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m build
```

Add regression tests for bug fixes and document any change to extraction semantics, supported inputs, workbook output, or security boundaries.

## Data-handling rules

- Never commit client filings, generated workbooks, credentials, or identifying test data.
- Use synthetic, public, or irreversibly anonymized fixtures.
- Preserve raw source values and provenance; do not convert missing values to zero or invent reporting periods.
- Keep network and Windows device paths disabled by default.
- Keep document-derived spreadsheet text inert.

## Pull requests

Keep changes focused, explain user-visible behavior, list the checks run, and call out limitations that were not tested. A change is not ready to merge while required CI checks are failing.

By contributing, you agree that your contribution will be licensed under the repository's [MIT License](LICENSE).
