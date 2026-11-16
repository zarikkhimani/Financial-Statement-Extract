"""Recover PDF equity components from body-column geometry and source headers."""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter
import re

import pdfplumber
import pandas as pd

from normalization import parse_numeric_token
from statements import VALUE_TOKEN, _match_desc_first
from financial_statement_extract.detection import is_section_boundary
from structure import detect_statement_unit_note, infer_company_name
from financial_statement_extract.table_layout import SINGLE_NUMBER


class EquityLayoutError(ValueError):
    pass


def _key(values):
    return tuple((t.status, t.value) for t in map(parse_numeric_token, values))


def _label(text):
    # Superscript footnotes can occupy a separate word line. They do not change
    # row identity; dates, ordinary digits and all amount tokens remain intact.
    return re.sub(r"\s+", " ", re.sub(r"\(\d+\)", "", text)).strip().casefold()


def _end_of_statement(text):
    return (is_section_boundary(text)
            or re.match(r"^(?:see (?:accompanying )?notes|the accompanying notes)", text, re.I)
            or (re.match(r"^\(\d+\)\s+[A-Za-z]", text)
                and not re.search(rf"\s{VALUE_TOKEN}\s*$", text, re.I)))


PERIOD_CAPTION = re.compile(r"^(?:\d+|three|six|nine|twelve)\s+(?:months?|years?)\s+ended\s+.+\b(?:19|20)\d{2}:?$", re.I)


def _lines(words):
    lines = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        # Bold balance labels and regular amounts can differ slightly in font
        # ascent on the same baseline. Full text-vector validation follows.
        if not lines or abs(lines[-1][0]["top"] - word["top"]) > 3:
            lines.append([])
        lines[-1].append(word)
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def _component_headers(header_lines, major):
    boundaries = [c[2] for c in major[:-1]]
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
            # Centered statement captions can span component columns without
            # being parent headings. Keep them in source context, not the schema.
            if (re.fullmatch(r"\(?unaudited\)?", group["text"], re.I)
                    or detect_statement_unit_note([{"raw_text": group["text"]}])["raw_unit_note"]):
                continue
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
    paths = [" ".join(text for left, right, text in parents if left <= c <= right) + " " + v
             for c, v in enumerate(leaf) if c]
    if len({v.casefold() for v in paths}) != len(leaf)-1:
        raise EquityLayoutError("Equity component headers are not unique.")
    parent_row = [""] * len(major)
    occupied = set()
    for left, right, text in parents:
        if occupied & set(range(left, right+1)):
            raise EquityLayoutError("Equity parent headers overlap ambiguously.")
        occupied.update(range(left, right+1))
        parent_row[left] = text
    return leaf, parents, parent_row


def equity_component_grid(page, found):
    """Use a wide data table, never a small parent-header box, to anchor columns."""
    candidates = []
    for table in found:
        for row in table.rows:
            major = [c for c in row.cells if c and c[2] - c[0] >= 15]
            if len(major) >= 3 and major[0][2] - major[0][0] >= page.width * .25:
                candidates.append((table, major))
    if not candidates:
        raise EquityLayoutError("No reliable equity component column boundaries were found.")
    # Parent headers span several body columns. The leaf schema comes from
    # the most detailed rows, including rows below the first table header.
    width = max(len(major) for _, major in candidates)
    candidates = [(table, major) for table, major in candidates if len(major) == width]
    _, major = min(candidates, key=lambda pair: pair[0].bbox[1])
    boundaries = [c[2] for c in major[:-1]]
    for _, other in candidates:
        if len(other) != len(major) or any(abs(a[2]-b[2]) > 2 for a, b in zip(major, other)):
            raise EquityLayoutError("Equity table boxes disagree on component column boundaries.")
    lines = _lines(page.extract_words(x_tolerance=1, y_tolerance=2))
    stop = next((i for i, line in enumerate(lines) if _end_of_statement(" ".join(w["text"] for w in line))), len(lines))
    lines = lines[:stop]

    def cells(line):
        row = [""] * len(major)
        for word in line:
            col = bisect_right(boundaries, (word["x0"] + word["x1"]) / 2)
            row[col] = (row[col] + " " + word["text"]).strip()
        return row

    def is_data(row):
        return bool(row[0] and any(row[1:]) and all(
            parse_numeric_token(v).status in {"NUMERIC", "DASH", "NA", "NM", "BLANK"} for v in row[1:]))

    first_data = next((i for i, line in enumerate(lines) if is_data(cells(line))), None)
    if first_data is None:
        raise EquityLayoutError("No equity data rows were found under the source headers.")
    top = lines[first_data][0]["top"]
    header_lines = [line for line in lines[:first_data] if top - 60 <= line[0]["top"]]
    if not header_lines:
        raise EquityLayoutError("Equity component headers are missing above the data columns.")

    leaf, parents, parent_row = _component_headers(header_lines, major)
    rows = ([parent_row] if parents else []) + [leaf]
    kinds = (["parent_header"] if parents else []) + ["header"]
    sources = [[] for _ in rows]
    spans = [(0, left, 1, right-left+1) for left, right, _ in parents]
    captions = [(i, " ".join(w["text"] for w in line).rstrip(":")) for i, line in enumerate(lines)
                if PERIOD_CAPTION.fullmatch(" ".join(w["text"] for w in line))]
    sections = []
    current_caption = next((caption for i, caption in reversed(captions) if i < first_data), "")
    section_start = len(rows)
    in_header = False
    repeated_header = []
    for i, line in enumerate(lines[first_data:], first_data):
        caption = next((caption for index, caption in captions if index == i), None)
        if caption is not None:
            sections.append(dict(start=section_start, end=len(rows), caption=current_caption))
            if in_header:
                raise EquityLayoutError("An equity period caption has no data block.")
            current_caption, section_start, in_header = caption, len(rows), True
            repeated_header = []
            continue
        row = cells(line)
        if in_header:
            if not is_data(row):
                repeated_header.append(line)
                continue
            repeated = _component_headers(repeated_header, major)
            if repeated != (leaf, parents, parent_row):
                raise EquityLayoutError("Equity period blocks disagree on source component headings.")
            in_header = False
        if not row[0] and not is_data(row):
            if any(parse_numeric_token(v).status == "NUMERIC" for v in row[1:]) and i < len(lines)-1:
                raise EquityLayoutError("An equity row has an unresolved wrapped label.")
            continue
        if re.fullmatch(r"\(\d+\)", row[0]) and not any(row[1:]):
            continue
        if any(row[1:]):
            if not row[0]:
                raise EquityLayoutError("An equity row has missing component text or an unresolved wrapped label.")
            for value in row[1:]:
                token = parse_numeric_token(value)
                if token.status not in {"NUMERIC", "DASH", "NA", "NM", "BLANK"} or (token.status == "NUMERIC" and not SINGLE_NUMBER.fullmatch(value)):
                    raise EquityLayoutError("An equity component contains ambiguous numeric text.")
            kind = "data"
        else:
            kind = "section"
        rows.append(row)
        kinds.append(kind)
        sources.append([dict(text=w["text"], x0=w["x0"], x1=w["x1"], top=w["top"]) for w in line])
    if in_header:
        raise EquityLayoutError("An equity period caption has no data block.")
    if kinds.count("data") < 2:
        raise EquityLayoutError("Too few equity data rows to verify the component layout.")

    # Independently check row order and complete vectors against page text. This
    # catches dropped rows in gaps, combined numbers, and wrong geometric assignments.
    text_rows = []
    for text in (page.extract_text() or "").splitlines():
        if _end_of_statement(text):
            break
        matched = next((m for n in range(len(major)-1, 1, -1) if (m := _match_desc_first(text, n))), None)
        if matched:
            label, values = matched
            if re.search(r"[A-Za-z]", label):
                text_rows.append((_label(label), _key(values)))
    geometry_rows = [(_label(row[0]), _key(v for v in row[1:] if v))
                     for row, kind in zip(rows, kinds) if kind == "data"]
    if text_rows != geometry_rows:
        raise EquityLayoutError("Equity geometry has a missing component or does not match the complete source text rows in order.")
    if captions:
        sections.append(dict(start=section_start, end=len(rows), caption=current_caption))
    balances = [i for i, (row, kind) in enumerate(zip(rows, kinds))
                if kind == "data" and re.match(r"^Balance (?:at|as of)\b", row[0], re.I)]
    if not captions and len(balances) % 2 == 0:
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
                # Raw engine spacer cells do not identify logical blanks. Source
                # geometry above fixes each blank's column and validates every
                # nonblank value against independent text in row order.
                actual = Counter(_key(v for v in row[1:] if v) for row, kind in zip(grid["rows"], grid["row_kinds"]) if kind == "data")
                for table in originals:
                    required = Counter()
                    for row in table["rows"]:
                        if not row[0].strip():
                            continue  # Unlabelled year/header rows are not amounts.
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
