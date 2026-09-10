# Release checklist

This project uses semantic versioning and keeps the package version in both `pyproject.toml` and `financial_statement_extract/__init__.py`.

## Prepare

1. Choose the next version and update both version declarations.
2. Move relevant entries from `Unreleased` in `CHANGELOG.md` into a dated version section.
3. Confirm that user-facing setup, limitations, and security guidance are current.
4. Confirm that no source filings, generated workbooks, credentials, logs, or local environments are staged.

## Validate

From the repository environment, run:

```powershell
python -m pip check
python -m ruff check .
python -m pytest
python -m build
```

Install the generated wheel into a clean environment and confirm the package and command-line entry point load:

```powershell
py -3.12 -m venv tmp\release-smoke
.\tmp\release-smoke\Scripts\python.exe -m pip install --no-deps .\dist\financial_statement_extract-<version>-py3-none-any.whl
.\tmp\release-smoke\Scripts\python.exe -c "import financial_statement_extract; print(financial_statement_extract.__version__)"
.\tmp\release-smoke\Scripts\python.exe -m financial_statement_extract --help
```

## Publish on GitHub

1. Commit the release changes on `main` and push them to GitHub.
2. Confirm that the CI workflow passes on every supported Python version.
3. Create an annotated tag such as `v0.1.0` and push it.
4. Create a GitHub release from the tag using the matching changelog section as the release notes.
5. Attach the wheel and source archive from `dist/` if you want users to install release artifacts directly.

Publishing to a package index is a separate decision and is not performed by the GitHub release process.
