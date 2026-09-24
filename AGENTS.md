# Workbook rules

- NEVER create or use merged cells on any worksheet. Use Center Across
  Selection for horizontal headings where suitable; otherwise put the content
  in an ordinary cell. Source document spans must not become Excel merges.
- NEVER hide rows or columns on any worksheet. Keep all rows and columns
  visible, including blank spacing and raw data. Do not use zero heights,
  zero widths, or collapsed groups to hide them.
- Leave three blank rows at the top of every exported worksheet.
- Leave two blank columns on the left of every exported worksheet, each with
  Excel column width 1.
- NEVER create or use freeze panes when creating a workbook. This applies to
  every worksheet, including financial statements, raw data, review sheets,
  and experimental output. Do not freeze rows, columns, or both.
- Preserve this rule when adding or changing workbook writers, templates,
  scripts, and export paths.

## Agent usage

Before extracting a filing, read [the agent usage guide](docs/AGENT_USAGE.md).
Use the supported CLI or Python API and follow its procedures for page
selection, output review, and reporting. Preserve the workbook rules above
when creating or modifying exports.
