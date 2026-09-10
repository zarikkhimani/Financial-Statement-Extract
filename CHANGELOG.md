# Changelog

## Unreleased

## 0.1.0 - 2026-09-10

- Prepared the repository for its first public release with an MIT license, a streamlined quick start, release guidance, and GitHub contribution templates.
- Added built-wheel installation smoke testing to CI and completed the package's public metadata links.
- Added an installable package, public Python API, command-line entry point, package metadata, and automated CI checks.
- Kept document-derived Excel text literal and disabled automatic formula and URL conversion.
- Rejected file URL authorities, UNC paths, and Windows device paths by default before filesystem access.
- Added contributor and architecture documentation plus security regression tests.
- Replaced the original monolithic script with focused extraction, normalization, mapping, audit, Excel, pipeline, and UI modules.
- Removed the embedded Base64 image, hardcoded desktop path, bundled Tabula JAR, and Java dependency.
- Added local PDF and HTML/iXBRL extraction, automatic statement-page detection, presentation-ready Excel output, explicit OCR-required reporting, and automated tests.
- Preserved source values and provenance; missing values are not converted to zero and reporting periods are not invented.
