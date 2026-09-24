"""Source grids are an output contract, independent of analytical concept mapping.

Keep each table's schema and order. Positional column IDs are internal, never labels.
No joins by standardized concept and no inferred accounting equivalences occur here.
"""
from __future__ import annotations

from collections import defaultdict
import re

import pandas as pd

from normalization import parse_numeric_token
from structure import DATE_RE, detect_statement_heading_type, detect_statement_unit_note, infer_company_name
from financial_statement_extract.schedule_layout import merge_overlapping_schedule_tables
from financial_statement_extract.cash_flow_layout import recover_cash_flow_tables


SINGLE_NUMBER = re.compile(
    r"\s*(?:[$€£¥]\s*)?(?:\(\s*(?:[$€£¥]\s*)?[+-]?\d[\d,]*(?:\.\d+)?(?:%|[xX])?\s*\)"
    r"|[+-]?\d[\d,]*(?:\.\d+)?(?:%|[xX])?)\s*"
)


def equity_display_grid(table: dict) -> dict:
    """Collapse HTML layout subdivisions using leaf headers, not accounting aliases.

    SEC dollar/spacer cells and colspans are physical HTML columns. Source leaf
    header boundaries define the actual equity components. The original grid
    remains untouched in ExtractionResult.statement_tables.
    """
    if table.get("flavor") != "html" or table.get("statement_type") != "StockholdersEquityStatement":
        return table
    rows = table["rows"]
    data_start = next((r for r, row in enumerate(rows) if row[0] and
                       sum(parse_numeric_token(v).status == "NUMERIC" for v in row[1:]) >= 2), None)
    if data_start is None:
        return table
    spans = {(r, c): (rs, cs) for r, c, rs, cs in table["spans"]}
    headers = [(r, c, spans.get((r, c), (1, 1))[1]) for r, row in enumerate(rows[:data_start])
               for c, text in enumerate(row) if c and text]
    leaves = sorted({c for r, c, cs in headers if not any(
        rr > r and c <= cc < c + cs for rr, cc, _ in headers)})
    if len(leaves) < 2:
        return table
    boundaries = [0] + leaves + [len(rows[0])]
    if len(set(boundaries)) != len(boundaries):
        return table
    # Never concatenate two amounts into one number when header/data geometry
    # disagrees. Preserve the physical source grid for review instead.
    if any(sum(parse_numeric_token(v).status == "NUMERIC" for v in row[left:right]) > 1
           for row in rows[data_start:] for left, right in zip(boundaries[1:], boundaries[2:])):
        return table
    compact = [[" ".join(v for v in row[left:right] if v) for left, right in zip(boundaries, boundaries[1:])]
               for row in rows]
    from bisect import bisect_right
    remapped = []
    for (r, c), (rs, cs) in spans.items():
        start = bisect_right(boundaries, c) - 1
        end = bisect_right(boundaries, c + cs - 1) - 1
        if rs > 1 or end > start:
            remapped.append((r, start, rs, end - start + 1))
    return {**table, "rows": compact, "spans": remapped}


def selected_grids(cells: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for cell in cells:
        if cell.get("selected"):
            groups.setdefault(cell["table_id"], []).append(cell)
    blocks = []
    for table_id, records in groups.items():
        height = max(c["row_index"] for c in records) + 1
        width = max(c["column_index"] for c in records) + 1
        rows = [[""] * width for _ in range(height)]
        spans = []
        row_bounds = [None] * height
        column_bounds = [None] * width
        for cell in records:
            r, c = cell["row_index"], cell["column_index"]
            rows[r][c] = cell.get("raw_text") or ""
            row_bounds[r] = cell.get("row_bounds")
            column_bounds[c] = cell.get("column_bounds")
            if cell.get("rowspan", 1) > 1 or cell.get("colspan", 1) > 1:
                spans.append((r, c, cell.get("rowspan", 1), cell.get("colspan", 1)))
        sample = records[0]
        blocks.append(dict(table_id=table_id, source_page=sample.get("source_page"),
                           statement_type=sample.get("statement_type_hint", ""),
                           source_title=sample.get("source_title", ""), rows=rows, spans=spans,
                           flavor=sample.get("flavor", ""), source_context=sample.get("source_context", []),
                           row_bounds=row_bounds, column_bounds=column_bounds,
                           source_order=sample.get("order") or 0))
    # Engine batches arrive separately; their execution order is not source order.
    return sorted(blocks, key=lambda block: (block["source_page"] or 0, block["source_order"]))


def grid_has_data(block: dict) -> bool:
    return any(
        any(re.search(r"[A-Za-z]", str(v)) for v in row)
        and any(parse_numeric_token(v).status == "NUMERIC" for v in row[1:])
        for row in block["rows"]
    )


def covered_pages(cells: list[dict], text_rows: list[dict]) -> set[int]:
    """Require source numeric-token coverage, not merely a nonempty table.

    A rule-based table engine can omit rows between two boxes. A count/multiset
    check catches those gaps and triggers an explicitly audited fallback.
    """
    from collections import Counter
    pattern = re.compile(r"(?<!\w)\d[\d,]*(?:\.\d+)?")
    source = defaultdict(Counter)
    extracted = defaultdict(Counter)
    for row in text_rows:
        source[row.get("source_page")].update(pattern.findall(str(row.get("raw_text", ""))))
    for block in selected_grids(cells):
        if grid_has_data(block):
            for row in block["rows"]:
                extracted[block["source_page"]].update(pattern.findall(" ".join(row)))
    return {page for page, tokens in source.items() if tokens and
            all(extracted[page][token] >= n for token, n in tokens.items() if re.fullmatch(r"(?:19|20)\d{2}", token)) and
            sum((tokens & extracted[page]).values()) / sum(tokens.values()) >= 0.97}


def organize_source_tables(cells: list[dict], text_rows: list[dict], statements: dict,
                          page_plan=None) -> tuple[list[dict], list[dict]]:
    """Attach source grids to frames without replacing analytical IDs/RawItem."""
    blocks, issues = [], []
    by_page = {p.page: p for p in page_plan.pages} if page_plan else {}
    company = infer_company_name(text_rows)
    grouped = defaultdict(list)
    for block in selected_grids(cells):
        if not grid_has_data(block):
            continue
        kind = block["statement_type"]
        page = by_page.get(block["source_page"])
        headings = [(text, detect_statement_heading_type(text))
                    for row in block["rows"][:25] for text in row if text]
        headings = [(text, kind) for text, kind in headings if kind]
        if not kind and len({kind for _, kind in headings}) == 1:
            block["source_title"], kind = headings[0]
        if not kind and page and len(page.statement_types or (page.statement_type,)) == 1:
            kind = page.statement_type
            block["source_title"] = page.source_title
        if not kind:
            issues.append({"Check": "Table organization", "Scope": block["table_id"], "Status": "WARN",
                           "Detail": "Table statement association is ambiguous; retained in raw output."})
            continue
        block["statement_type"] = kind
        if page:
            source_page_rows = [row for row in text_rows if row.get("source_page") == page.page]
            unit_note = detect_statement_unit_note(source_page_rows).get("raw_unit_note")
            if unit_note:
                block["source_context"] = [unit_note]
            if kind == "ScheduleOfInvestments":
                dates = list(dict.fromkeys(row["raw_text"].strip() for row in source_page_rows[:12]
                                          if DATE_RE.fullmatch(row.get("raw_text", "").strip())))
                if len(dates) == 1:
                    block["source_context"] = dates + block["source_context"]
                elif len(dates) > 1:
                    issues.append({"Check": "Schedule table overlap", "Scope": block["table_id"], "Status": "WARN",
                                   "Detail": "Multiple schedule dates occur above this table. Review the source date association."})
            block["source_context"].extend(row["raw_text"] for row in source_page_rows[:20]
                                           if re.fullmatch(r"\s*\(?unaudited\)?\s*", row.get("raw_text", ""), re.I))
        # Trim an explicit notes boundary; do not append supporting tables to statements.
        from financial_statement_extract.detection import is_section_boundary
        for i, row in enumerate(block["rows"]):
            if is_section_boundary(" ".join(row)):
                block["rows"] = block["rows"][:i]
                block["row_bounds"] = block["row_bounds"][:i]
                block["spans"] = [s for s in block["spans"] if s[0] + s[2] <= i]
                break
        if not grid_has_data(block):
            continue
        blocks.append(block)
    blocks, overlap_issues = merge_overlapping_schedule_tables(blocks)
    issues.extend(overlap_issues)
    blocks, cash_issues = recover_cash_flow_tables(blocks, text_rows, page_plan)
    issues.extend(cash_issues)
    for block in blocks:
        grouped[block["statement_type"]].append(block)
    for kind, tables in grouped.items():
        if kind not in statements:
            # Equity requires the grid: dates embedded in row labels are not periods.
            frame = pd.DataFrame([{"RawItem": row[0], "RowType": "Data"}
                                  for table in tables for row in table["rows"] if any(row)])
            frame.attrs.update(company_name=company, statement_title=tables[0]["source_title"],
                               statement_type=kind, period_labels=[])
            statements[kind] = frame
        statements[kind].attrs["source_tables"] = tables
        issues.append({"Check": "Source table organization", "Scope": kind, "Status": "INFO",
                       "Detail": f"{len(tables)} separate source grid(s); labels, columns and table order preserved. "
                       "Analytical text mappings are separate from displayed source grids."})
    expected = {row.get("statement_type_hint") for row in text_rows}
    if page_plan:
        expected.update(p.statement_type for p in page_plan.pages if p.page in page_plan.selected_pages)
    if "StockholdersEquityStatement" in expected and "StockholdersEquityStatement" not in grouped:
        raise ValueError("Stockholders' equity was detected but its column layout could not be extracted. "
                         "No workbook was written. Try the matching HTML or all table methods.")
    for block in blocks:
        if (block["statement_type"] == "StockholdersEquityStatement" and block["flavor"] == "html"
                and equity_display_grid(block) is block):
            issues.append({"Check": "Table organization", "Scope": block["table_id"], "Status": "WARN",
                           "Detail": "Equity component boundaries are uncertain. The physical source grid is preserved; "
                           "columns were not combined."})
        if any(parse_numeric_token(value).status == "NUMERIC" and not SINGLE_NUMBER.fullmatch(value)
               for row in block["rows"] for value in row[1:] if value):
            issues.append({"Check": "Table organization", "Scope": block["table_id"], "Status": "WARN",
                           "Detail": "Some cells contain ambiguous numeric text. It remains literal in Excel "
                           "rather than combining separate amounts into a number."})
        if any("\ufffd" in value for row in block["rows"] for value in row):
            issues.append({"Check": "Source character decoding", "Scope": block["table_id"], "Status": "WARN",
                           "Detail": "The PDF text contains undecodable characters (replacement glyphs). "
                           "They were retained, not guessed; compare the PDF or matching HTML."})
    return blocks, issues
