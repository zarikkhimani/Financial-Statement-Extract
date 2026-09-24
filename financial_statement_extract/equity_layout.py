"""Recover PDF equity components from body-column geometry and source headers."""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter
import re

import pdfplumber
import pandas as pd

from normalization import parse_numeric_token
from statements import _match_desc_first
from structure import detect_statement_unit_note, infer_company_name
from financial_statement_extract.table_layout import SINGLE_NUMBER


class EquityLayoutError(ValueError):
    pass


def _key(values):
    return tuple(parse_numeric_token(v).value if parse_numeric_token(v).status == "NUMERIC" else None for v in values)


def _lines(words):
    lines = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if not lines or abs(lines[-1][0]["top"] - word["top"]) > 2:
            lines.append([])
        lines[-1].append(word)
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def equity_component_grid(page, found):
    """Use a wide data table, never a small parent-header box, to anchor columns."""
    candidates = []
    for table in found:
        major = [c for c in table.rows[0].cells if c and c[2] - c[0] >= 15]
        if len(major) >= 3 and major[0][2] - major[0][0] >= page.width * .25:
            candidates.append((table, major))
    if not candidates:
        raise EquityLayoutError("No reliable equity component column boundaries were found.")
    first, major = min(candidates, key=lambda pair: pair[0].bbox[1])
    boundaries = [c[2] for c in major[:-1]]
    for _, other in candidates:
        if len(other) != len(major) or any(abs(a[2]-b[2]) > 2 for a, b in zip(major, other)):
            raise EquityLayoutError("Equity table boxes disagree on component column boundaries.")
    lines = _lines(page.extract_words(x_tolerance=1, y_tolerance=2))
    top, bottom = first.bbox[1], max(t.bbox[3] for t, _ in candidates)
    header_lines = [line for line in lines if top - 45 <= line[0]["top"] < top]
    if not header_lines:
        raise EquityLayoutError("Equity component headers are missing above the data columns.")

    # The lowest header line supplies each leaf column. Upper text either belongs
    # to one leaf or spans leaves (for example Common Stock over Shares/Par Amount).
    leaf = [""] * len(major)
    parents = []
    for line_index, line in enumerate(header_lines):
        groups = []
        for word in line:
            if groups and word["x0"] - groups[-1]["x1"] <= 4:
                groups[-1]["text"] += " " + word["text"]
                groups[-1]["x1"] = word["x1"]
            else:
                groups.append(dict(word))
        for group in groups:
            if group["x0"] < major[0][2] - 2:
                continue
            left = bisect_right(boundaries, group["x0"] + 1)
            right = bisect_right(boundaries, group["x1"] - 1)
            if right >= len(major):
                raise EquityLayoutError("An equity header extends beyond the detected component columns.")
            if right > left and line_index < len(header_lines)-1:
                parents.append((left, right, group["text"]))
            elif right == left:
                leaf[left] = (leaf[left] + " " + group["text"]).strip()
            else:
                raise EquityLayoutError("A leaf equity header crosses component boundaries.")
    if not all(leaf[1:]):
        raise EquityLayoutError("Not every equity component has a source header.")
    if len({v.casefold() for v in leaf[1:]}) != len(leaf)-1:
        raise EquityLayoutError("Equity component headers are not unique.")
    parent_row = [""] * len(major)
    occupied = set()
    for left, right, text in parents:
        if occupied & set(range(left, right+1)):
            raise EquityLayoutError("Equity parent headers overlap ambiguously.")
        occupied.update(range(left, right+1))
        parent_row[left] = text
    rows = ([parent_row] if parents else []) + [leaf]
    kinds = (["parent_header"] if parents else []) + ["header"]
    sources = [[] for _ in rows]
    spans = [(0, left, 1, right-left+1) for left, right, _ in parents]
    for line in lines:
        if not top <= line[0]["top"] <= bottom:
            continue
        row = [""] * len(major)
        for word in line:
            col = bisect_right(boundaries, (word["x0"] + word["x1"]) / 2)
            row[col] = (row[col] + " " + word["text"]).strip()
        if any(row[1:]):
            if not row[0] or any(not v for v in row[1:]):
                raise EquityLayoutError("An equity row has missing component text or an unresolved wrapped label.")
            for value in row[1:]:
                token = parse_numeric_token(value)
                if token.status not in {"NUMERIC", "DASH", "NA", "NM"} or (token.status == "NUMERIC" and not SINGLE_NUMBER.fullmatch(value)):
                    raise EquityLayoutError("An equity component contains ambiguous numeric text.")
            kind = "data"
        else:
            kind = "section"
        rows.append(row)
        kinds.append(kind)
        sources.append([dict(text=w["text"], x0=w["x0"], x1=w["x1"], top=w["top"]) for w in line])
    if kinds.count("data") < 2:
        raise EquityLayoutError("Too few equity data rows to verify the component layout.")

    # Independently check row order and complete vectors against page text. This
    # catches dropped rows in gaps, combined numbers, and wrong geometric assignments.
    text_rows = []
    for text in (page.extract_text() or "").splitlines():
        matched = _match_desc_first(text, len(major)-1)
        if matched:
            label, values = matched
            text_rows.append((re.sub(r"\s+", " ", label).strip(), _key(values)))
    geometry_rows = [(re.sub(r"\s+", " ", row[0]).strip(), _key(row[1:]))
                     for row, kind in zip(rows, kinds) if kind == "data"]
    if text_rows != geometry_rows:
        raise EquityLayoutError("Equity geometry does not match the complete source text rows in order.")
    balances = [i for i, (row, kind) in enumerate(zip(rows, kinds))
                if kind == "data" and re.match(r"^Balance (?:at|as of)\b", row[0], re.I)]
    sections = []
    if len(balances) % 2 == 0:
        for start, end in zip(balances[::2], balances[1::2]):
            period = re.search(r"^Total .*? for the (.+)$", rows[end-1][0], re.I)
            if period:
                sections.append(dict(start=start, end=end+1, caption=period[1], caption_source_row=end-1))
    # Split only when the source establishes every block, including all data.
    if {i for section in sections for i in range(section["start"], section["end"])} != set(range(kinds.index("data"), len(rows))):
        sections = []
    return dict(rows=rows, row_kinds=kinds, row_sources=sources, spans=spans,
                period_sections=sections,
                component_labels=leaf[1:], column_bounds=[list(c[::2]) for c in major],
                header_words=[[dict(text=w["text"], x0=w["x0"], x1=w["x1"], top=w["top"])
                               for w in line] for line in header_lines])


def recover_pdf_equity_tables(pdf_path, tables, statements, page_plan):
    kinds = {"PartnersCapital", "StockholdersEquityStatement"}
    eligible = [p for p in page_plan.pages if p.page in page_plan.selected_pages and p.statement_type in kinds]
    ambiguous = [p for p in eligible if set(p.statement_types or (p.statement_type,)) != {p.statement_type}]
    failed = {p.statement_type for p in ambiguous}
    issues = [{"Check": "Equity component layout", "Scope": f"Page {p.page}", "Status": "WARN",
               "Detail": "Equity page ownership is ambiguous. Original grids retained; source review is required."}
              for p in ambiguous]
    pages = [p for p in eligible if p.statement_type not in failed]
    if not pages:
        return tables, issues
    replacements = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pages:
            originals = [t for t in tables if t["source_page"] == page.page and t["statement_type"] == page.statement_type]
            try:
                source = pdf.pages[page.page-1]
                grid = equity_component_grid(source, source.find_tables())
                actual = Counter(_key(row[1:]) for row, kind in zip(grid["rows"], grid["row_kinds"]) if kind == "data")
                for table in originals:
                    required = Counter()
                    for row in table["rows"]:
                        values = [v for v in row[1:] if v.strip() and v.strip() not in {"$", "€", "£", "¥"}]
                        if values and all(parse_numeric_token(v).status in {"NUMERIC", "DASH", "NA", "NM"} for v in values):
                            required[_key(values)] += 1
                    if required - actual:
                        raise EquityLayoutError("Recovered equity does not preserve all selected table amount vectors.")
                unit = detect_statement_unit_note([{"raw_text": line} for line in source.extract_text().splitlines()])
                grid.update(table_id=f"P{page.page:04d}_EQUITY_GEOMETRY", source_page=page.page, source_order=0,
                            statement_type=page.statement_type, source_title=page.source_title, flavor="equity_geometry",
                            source_context=[unit["raw_unit_note"]] if unit.get("raw_unit_note") else [],
                            source_table_ids=[t["table_id"] for t in originals])
                grid["company_name"] = infer_company_name([{"raw_text": line} for line in source.extract_text().splitlines()])
                replacements[page.page] = grid
            except EquityLayoutError as exc:
                failed.add(page.statement_type)
                issues.append({"Check": "Equity component layout", "Scope": f"Page {page.page}", "Status": "WARN",
                               "Detail": f"{exc} Original equity grids retained; source review is required."})
    replacements = {p: t for p, t in replacements.items() if t["statement_type"] not in failed}
    result = [t for t in tables if not (t["source_page"] in replacements and t["statement_type"] in kinds)]
    result.extend(replacements.values())
    result.sort(key=lambda t: (t.get("source_page") or 0, t.get("source_order") or 0))
    for kind in {t["statement_type"] for t in replacements.values()}:
        if kind not in statements:
            source = next(t for t in replacements.values() if t["statement_type"] == kind)
            statements[kind] = pd.DataFrame()
            statements[kind].attrs.update(company_name=source["company_name"], statement_title=source["source_title"],
                                          statement_type=kind, period_labels=[])
        statements[kind].attrs["source_tables"] = [t for t in result if t["statement_type"] == kind]
    for page, table in replacements.items():
        issues.append({"Check": "Equity component layout", "Scope": f"Page {page}", "Status": "INFO",
                       "Detail": f"Recovered {len(table['component_labels'])} source component headings and "
                       f"{table['row_kinds'].count('data')} rows with stable PDF column assignments. Raw tables retained."})
    return result, issues
