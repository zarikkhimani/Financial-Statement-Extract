"""Cash-flow display blocks with local period headings and source-line provenance.

PDF table boxes can omit supplemental rows above a reconciliation. Read complete
text rows on unambiguous cash-flow pages, while checking retained table amounts.
This does not change the analytical concept mapping or any raw extraction grid.
"""
from __future__ import annotations

from collections import Counter
import re

from normalization import parse_numeric_token
from financial_statement_extract.detection import is_section_boundary
from statements import VALUE_TOKEN, _is_structural_header, _match_desc_first
from structure import DATE_RE, detect_period_labels, detect_statement_unit_note


class CashFlowLayoutError(ValueError):
    pass


def _headers(rows):
    """Only standalone source year/date lines establish a value-column count."""
    headers = []
    for i, row in enumerate(rows):
        text = row.get("raw_text", "").strip()
        dates = DATE_RE.findall(text)
        if dates and not DATE_RE.sub("", text).strip(" ,"):
            start = i - 1 if i and rows[i-1]["raw_text"].strip().lower() == "as of" else i
            headers.append((start, i, dates, "As of"))
        elif re.fullmatch(r"(?:19|20)\d{2}(?:\s+(?:19|20)\d{2}){1,5}", text):
            start = i
            if i and re.search(r"\b(?:months?|years?|quarters?|periods?) ended\b", rows[i-1]["raw_text"], re.I):
                start = i - 1
            elif headers or i > 12:
                # A values-only row can happen to contain year-sized amounts.
                # Inside a table, require a fresh period cue before treating it
                # as another header rather than part of a wrapped data row.
                continue
            labels = detect_period_labels(rows[start:i+1])
            headers.append((start, i, labels, ""))
    return headers


def _page_blocks(source, page, title):
    stop = next((i for i, row in enumerate(source) if is_section_boundary(row.get("raw_text", ""))
                 or re.match(r"^see (?:accompanying )?notes", row.get("raw_text", ""), re.I)), len(source))
    source = source[:stop]
    headers = _headers(source)
    if not headers:
        raise CashFlowLayoutError("No standalone cash-flow period headings were found.")
    if any(_match_desc_first(row.get("raw_text", ""), len(headers[0][2])) for row in source[:headers[0][0]]):
        raise CashFlowLayoutError("Cash-flow amounts precede the first usable period heading.")
    blocks = []
    for block_index, (start, end, periods, context) in enumerate(headers):
        if not periods or len(periods) != len(set(periods)):
            raise CashFlowLayoutError("Cash-flow period headings are ambiguous.")
        n = len(periods)
        rows, kinds, provenance = [], [], []
        pending, pending_sources = [], []

        def append(label, values, kind, sources):
            rows.append([label, *values])
            kinds.append(kind)
            provenance.append([{"source_page": page, "line_no": row.get("line_no")} for row in sources])

        def flush():
            if pending:
                # An unparsed numeric line must not quietly become a prose note.
                if any(re.search(rf"\s{VALUE_TOKEN}\s*$", text, re.I) for text in pending):
                    raise CashFlowLayoutError("A cash-flow line has unresolved trailing values.")
                append(" ".join(pending), [""] * n, "note", pending_sources[:])
                pending.clear()
                pending_sources.clear()

        stop = headers[block_index+1][0] if block_index+1 < len(headers) else len(source)
        for record in source[end+1:stop]:
            text = record.get("raw_text", "").strip()
            if not text or re.fullmatch(r"\d{1,4}", text):
                continue
            if re.match(r"^(?:see (?:accompanying )?notes|notes to (?:the )?(?:consolidated )?financial statements)", text, re.I):
                break
            if re.match(r"^\(\d+\)\s+[A-Za-z]", text):
                flush()
                append(text, [""] * n, "note", [record])
                continue
            combined = " ".join([*pending, text])
            if _is_structural_header(combined):
                append(combined, [""] * n, "section", [*pending_sources, record])
                pending.clear()
                pending_sources.clear()
                continue
            if _is_structural_header(text):
                flush()
                append(text, [""] * n, "section", [record])
                continue
            match = _match_desc_first(text, n)
            if match is None and pending:
                match = _match_desc_first(combined, n)
                already_joined = True
            else:
                already_joined = False
            if match is not None:
                label, values = match
                if not already_joined:
                    label = " ".join([*pending, label])
                if re.search(r"\s[+-]?\d[\d,]*(?:\.\d+)?$", label):
                    raise CashFlowLayoutError("More cash-flow values than period headings were found.")
                append(label, values, "data", [*pending_sources, record])
                pending.clear()
                pending_sources.clear()
            else:
                pending.append(text)
                pending_sources.append(record)
        flush()
        if "data" not in kinds:
            continue
        blocks.append(dict(table_id=f"P{page:04d}_CASH_FLOW_TEXT_{block_index+1:02d}",
                           source_page=page, source_order=start, statement_type="CashFlowStatement",
                           source_title=title, flavor="cash_flow_text", rows=rows, spans=[],
                           period_labels=periods, source_context=[context] if context else [],
                           row_kinds=kinds, row_sources=provenance,
                           header_sources=[{"source_page": page, "line_no": r.get("line_no")}
                                           for r in source[start:end+1]]))
    if not blocks:
        raise CashFlowLayoutError("No cash-flow data rows were recovered under source headings.")
    return blocks


def _amounts(values):
    parsed = [parse_numeric_token(value) for value in values]
    return tuple(token.value if token.status == "NUMERIC" else None for token in parsed)


def recover_cash_flow_tables(tables, text_rows, page_plan):
    """Return reviewed display grids, retaining original grids when recovery is uncertain."""
    if page_plan is None:
        return tables, []
    result, issues = list(tables), []
    for page in page_plan.pages:
        if page.page not in page_plan.selected_pages or page.statement_type != "CashFlowStatement":
            continue
        if set(page.statement_types or (page.statement_type,)) != {"CashFlowStatement"}:
            continue
        source = [row for row in text_rows if row.get("source_page") == page.page]
        originals = [table for table in result if table.get("source_page") == page.page
                     and table.get("statement_type") == "CashFlowStatement"]
        try:
            recovered = _page_blocks(source, page.page, page.source_title)
            available = Counter(_amounts(row[1:]) for table in recovered
                                for row, kind in zip(table["rows"], table["row_kinds"]) if kind == "data")
            # Overlapping candidates are alternative observations, not extra source
            # occurrences. Verify each candidate independently, retaining duplicates
            # within a candidate and within the complete source transcription.
            for table in originals:
                required = Counter()
                for row in table["rows"]:
                    if not row[0]:
                        continue
                    values = [v for v in row[1:] if v.strip() and v.strip() not in {"$", "€", "£", "¥"}]
                    if values and all(parse_numeric_token(v).status in {"NUMERIC", "DASH", "NA", "NM"} for v in values):
                        required[_amounts(values)] += 1
                if required - available:
                    raise CashFlowLayoutError("Recovered cash-flow rows do not preserve every selected table amount.")
        except CashFlowLayoutError as exc:
            issues.append({"Check": "Cash flow layout", "Scope": f"Page {page.page}", "Status": "WARN",
                           "Detail": f"{exc} Original source grids retained; cash-flow completeness requires review."})
            continue
        unit = detect_statement_unit_note(source).get("raw_unit_note")
        for table in recovered:
            table["source_context"] = ([unit] if unit else []) + table["source_context"]
            table["source_table_ids"] = [t["table_id"] for t in originals]
        result = [table for table in result if table not in originals] + recovered
        issues.append({"Check": "Cash flow layout", "Scope": f"Page {page.page}", "Status": "INFO",
                       "Detail": f"Recovered {sum(k == 'data' for t in recovered for k in t['row_kinds'])} "
                       "cash-flow rows with section-specific source periods. Raw table candidates remain unchanged."})
    if any(issue["Status"] == "WARN" for issue in issues):
        return tables, [issue for issue in issues if issue["Status"] == "WARN"]
    cash = [table for table in result if table.get("statement_type") == "CashFlowStatement"]
    if any(table.get("flavor") != "cash_flow_text" for table in cash):
        if any(table.get("flavor") == "cash_flow_text" for table in cash):
            return tables, [{"Check": "Cash flow layout", "Scope": "CashFlowStatement", "Status": "WARN",
                             "Detail": "Some cash-flow pages have ambiguous statement ownership. "
                             "Original grids retained for the entire statement; review is required."}]
    return sorted(result, key=lambda t: (t.get("source_page") or 0, t.get("source_order") or 0)), issues
