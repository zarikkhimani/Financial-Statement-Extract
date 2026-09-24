# Releasing

Use [release readiness](RELEASE_READINESS.md) to track the candidate's open items
and evidence. Complete those reviews before publishing. Version changes, pushes,
tags, and publication require an explicit request.

## Prepare the candidate

1. Confirm release scope and resolve open release issues. Record remaining
   limitations without describing incomplete reviews as passed.
2. Review changes to the public Python API, CLI options, dependencies, and workbook
   structure. Explain any required migration in the README and changelog.
3. Choose the version using semantic versioning. Update `pyproject.toml` and
   `financial_statement_extract/__init__.py` together; update README version text.
4. Move relevant changelog entries from `Unreleased` into a dated version section.
   Use that section for the eventual GitHub release notes.
5. Confirm installation and upgrade instructions. Capture reviewed screenshots
   with public or synthetic data and no personal paths.

## Validate

Run the project checks from the repository environment:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m build
git diff --check
```

Review the final diff and built wheel/source archive. Confirm required UI assets
are included and confidential filings, generated workbooks, credentials, logs,
temporary evidence, and local environments are absent. Review dependency status
and security-sensitive changes against [SECURITY.md](../SECURITY.md). Record the
scope and results; passing functional tests alone is not a security audit.

### Clean installation

Use a new environment for each candidate, on each supported Python version.
Replace `<version>` and the environment suffix below with the chosen version.
Install the exact built wheel **with dependencies**:

```powershell
py -3.12 -m venv tmp\release-smoke-<version>-py312
.\tmp\release-smoke-<version>-py312\Scripts\python.exe -m pip install .\dist\financial_statement_extract-<version>-py3-none-any.whl
.\tmp\release-smoke-<version>-py312\Scripts\python.exe -m pip check
```

From a directory outside the source checkout, use the clean environment's
absolute executable paths to:

- Import the package and confirm its version and installed location.
- Run `financial-extract.exe --help` and launch `financial-extract-gui.exe`.
- Extract representative local PDF and HTML fixtures through the CLI and GUI.
- Open the resulting workbooks and compare source rows, periods, and amounts.
- Check failure/retry behavior, non-overwrite behavior, and clean shutdown.

A startup-only installation with `--no-deps` does not satisfy this check.

### Manual acceptance

Complete the visual, screen-reader, and contrast-theme checks listed in
[release readiness](RELEASE_READINESS.md). Use the
[live review harness](UI_PHASE8.md) for repeatable synthetic cases, and representative
filings for source reconciliation. Record exact pages and outstanding warnings.

Confirm every worksheet has three blank top rows, two width-1 left columns,
no merged cells, no hidden rows or columns, and no freeze panes.

Record the final commit, environment, reviewer, date, results, and artifact hashes
in the readiness record. If code or dependencies change afterward, repeat the
affected checks and validate the final build before publication.

## Publish on GitHub

After explicit authorization:

1. Commit the reviewed release state and push it through the repository's normal
   review process. Confirm CI passes on every supported Python version.
2. Create and push an annotated `v<version>` tag for that exact commit.
3. Create a GitHub release from the tag, using the dated changelog section.
4. Attach the validated wheel and source archive, with SHA-256 hashes. Identify
   early evaluation releases as prereleases where appropriate.
5. Check the published installation instructions and download links. Retain the
   previous release so users can return to it if needed.

Package-index publication is a separate decision. Record post-release defects in
the issue tracker, using private reporting for security vulnerabilities.
