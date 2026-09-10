# Security Policy

## Project scope and maturity

Financial Statement Extract is an early-stage, local financial-document
extraction tool. This policy covers the Python package, desktop application,
command-line interface, document parsers, and generated Excel workbooks.

The project is not a regulatory certification, penetration test, model
validation, or bank production approval.

## Supported versions

Security fixes are applied to the latest code on the `main` branch. Older
snapshots and locally modified copies are not supported.

## Reporting a vulnerability

Do not report security vulnerabilities through a public GitHub issue.

Use GitHub's private vulnerability-reporting or Security Advisory feature when
available. Otherwise, contact the repository owner privately before disclosing
the issue publicly.

Include:

- The affected version, revision, or file.
- A concise description of the security impact.
- Reproduction steps using synthetic or public data.
- Relevant logs or screenshots with confidential information removed.
- Any suggested remediation or regression test.

Never submit client filings, generated client workbooks, credentials, account
details, or other confidential information in a vulnerability report.

The maintainer aims to acknowledge reports within three business days and
provide an initial assessment within ten business days. Complex findings may
require additional investigation.

## Security boundaries

- Filing extraction and workbook generation run locally.
- The application contains no upload or telemetry integration.
- Document-derived spreadsheet text is written literally; automatic formula
  and URL conversion are disabled.
- Network shares, UNC paths, Windows device namespaces, and reserved DOS device
  names are rejected by default before filesystem access.
- Nonlocal paths require an explicit library or command-line opt-in and should
  be enabled only under a separately governed network-share policy.
- Source filings, generated workbooks, credentials, logs, and local
  environments are excluded from version control.

## Known limitations

- PDF and HTML parsers do not yet have enforceable file-size, page-count,
  complexity, time, CPU, or memory limits. Large or adversarial filings can
  consume substantial workstation resources.
- Third-party parser and spreadsheet dependencies remain part of the software
  supply-chain boundary.
- Image-only PDFs require a separate OCR workflow.
- Extracted values must be reconciled to the source filing before use.

For institutional evaluation, process untrusted documents in an isolated,
least-privilege environment and apply organization-approved dependency,
endpoint, retention, access-control, and network policies.

## Coordinated disclosure

Please allow reasonable time to investigate and remediate a validated issue
before public disclosure. Do not test against systems, accounts, networks, or
data that you do not own or have explicit permission to use.
