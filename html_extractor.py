from __future__ import annotations

import re
import warnings
from pathlib import Path

from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning

from config import STATEMENT_TITLES
from normalization import normalize_financial_text, parse_numeric_token
from structure import detect_statement_heading_type, detect_statement_type


HTML_SUFFIXES = {".html", ".htm", ".xhtml"}
_FINANCIAL_NUMBER_RE = re.compile(
    r"\(?\s*\$?\s*-?\d[\d,]*(?:\.\d+)?%?\s*\)?|(?<!\w)[\u2013\u2014\u2212-](?!\w)"
)


def _is_hidden(tag: Tag) -> bool:
    for current in (tag, *tag.parents):
        if not isinstance(current, Tag):
            continue
        name = str(current.name or "").lower()
        attrs = current.attrs or {}
        style = re.sub(r"\s+", "", str(attrs.get("style") or "").lower())
        classes = {str(item).lower() for item in attrs.get("class", [])}
        if (
            name in {"ix:hidden", "xbrli:context", "xbrli:unit"}
            or "hidden" in attrs
            or str(attrs.get("aria-hidden") or "").lower() == "true"
            or "display:none" in style
            or "visibility:hidden" in style
            or classes.intersection({"hidden", "hide", "d-none"})
        ):
            return True
    return False


def _find_ix_fact(soup: BeautifulSoup, suffix: str) -> str:
    matches: list[Tag] = []
    suffix_lower = suffix.lower()
    for tag in soup.find_all(True):
        fact_name = str(tag.attrs.get("name") or "").lower()
        if fact_name.endswith(suffix_lower):
            matches.append(tag)
    for tag in sorted(matches, key=_is_hidden):
        text = normalize_financial_text(tag.get_text(" ", strip=True) or tag.attrs.get("content"))
        if text:
            return text
    return ""


def _document_metadata(soup: BeautifulSoup) -> dict:
    client_name = _find_ix_fact(soup, "entityregistrantname")
    document_type = _find_ix_fact(soup, "documenttype")
    year = _find_ix_fact(soup, "documentfiscalyearfocus")
    period_focus = _find_ix_fact(soup, "documentfiscalperiodfocus").upper()
    if not year:
        period_end = _find_ix_fact(soup, "documentperiodenddate")
        match = re.search(r"(?<!\d)((?:19|20|21)\d{2})(?!\d)", period_end)
        year = match.group(1) if match else ""
    period = {"FY": "Annual", "Q1": "Q1", "Q2": "Q2", "Q3": "Q3", "Q4": "Q4"}.get(period_focus, "")
    return {
        key: value
        for key, value in {
            "client_name": client_name,
            "document_type": document_type,
            "year": year,
            "period": period,
        }.items()
        if value
    }


def _clean_dom(soup: BeautifulSoup) -> None:
    for tag in list(soup.find_all(["script", "style", "noscript", "template", "svg", "sup"])):
        tag.decompose()
    for tag in list(soup.find_all(True)):
        if tag.parent is not None and _is_hidden(tag):
            tag.decompose()


def _table_rows(table: Tag) -> tuple[list[str], list[list[str]]]:
    lines: list[str] = []
    cell_rows: list[list[str]] = []
    for row in table.find_all("tr"):
        if row.find_parent("table") is not table:
            continue
        cells = row.find_all(["th", "td"], recursive=False)
        values = [normalize_financial_text(cell.get_text(" ", strip=True)) for cell in cells]
        if not any(values):
            continue
        cell_rows.append(values)
        line = normalize_financial_text(" ".join(value for value in values if value))
        line = re.sub(r"(?<=\d)\s+%", "%", line)
        line = re.sub(r"(?<=\d)\s+[xX]\b", "x", line)
        if line and (not lines or line != lines[-1]):
            lines.append(line)
    return lines, cell_rows


def _financial_line_count(lines: list[str]) -> int:
    return sum(
        1
        for line in lines
        if re.search(r"[A-Za-z]", line) and len(_FINANCIAL_NUMBER_RE.findall(line)) >= 2
    )


def _is_schedule_statement_grid(lines: list[str]) -> bool:
    header = lines[0].lower() if lines else ""
    if "valuation techniques" in header or "unobservable inputs" in header:
        return False
    has_value_column = "fair value" in header or ("cost" in header and "value" in header)
    has_investment_column = any(
        token in header
        for token in ("investment", "portfolio", "security", "cash equivalents")
    )
    has_schedule_metric = any(
        token in header
        for token in ("percentage of net assets", "% of net assets", "cost")
    )
    return has_value_column and has_investment_column and has_schedule_metric


def _nearby_statement_heading(table: Tag) -> tuple[str, str]:
    for element in table.find_all_previous(["h1", "h2", "h3", "h4", "h5", "h6", "p", "div"], limit=30):
        if element.find("table") is not None:
            continue
        text = normalize_financial_text(element.get_text(" ", strip=True))
        if not text or len(text) > 220:
            continue
        statement_type = detect_statement_heading_type(text)
        if statement_type:
            return statement_type, text
    return "", ""


def _detect_statement_table(table: Tag, lines: list[str]) -> tuple[str, str, int]:
    data_lines = _financial_line_count(lines)
    if data_lines < 2:
        return "", "", data_lines
    for line in lines[:25]:
        statement_type = detect_statement_heading_type(line) or detect_statement_type(line)
        if statement_type and len(line) <= 220:
            return statement_type, line, data_lines
    low = " ".join(lines).lower()
    if "total assets" in low and "total liabilities" in low:
        return "BalanceSheet", "Consolidated Statements of Assets and Liabilities", data_lines
    if (
        "operating activities" in low
        and "financing activities" in low
        and ("net cash used" in low or "net cash provided" in low)
    ):
        return "CashFlowStatement", "Consolidated Statements of Cash Flows", data_lines
    if (
        "net assets at" in low
        and "capital unit transactions" in low
        and ("contributions for units issued" in low or "net assets resulting from operations" in low)
    ):
        return "PartnersCapital", "Statements of Changes in Net Assets", data_lines
    if (
        "investment income" in low
        and "expenses" in low
        and ("net investment income" in low or "net investment loss" in low)
    ):
        return "IncomeStatement", "Consolidated Statement of Operations", data_lines
    if ("revenue" in low or "net sales" in low) and ("net income" in low or "net earnings" in low):
        return "IncomeStatement", STATEMENT_TITLES["IncomeStatement"][0], data_lines
    if "partners' capital" in low and ("contributions" in low or "distributions" in low):
        return "PartnersCapital", STATEMENT_TITLES["PartnersCapital"][0], data_lines
    if _is_schedule_statement_grid(lines):
        return "ScheduleOfInvestments", "Schedule of Investments", data_lines
    nearby_type, nearby_heading = _nearby_statement_heading(table)
    if nearby_type and nearby_type != "ScheduleOfInvestments":
        return nearby_type, nearby_heading, data_lines
    return "", "", data_lines


def _select_statement_candidates(candidates: list[dict]) -> list[dict]:
    selected: list[dict] = []
    statement_types = {candidate["statement_type"] for candidate in candidates}
    for statement_type in statement_types:
        matching = sorted(
            (candidate for candidate in candidates if candidate["statement_type"] == statement_type),
            key=lambda item: item["table_index"],
        )
        if statement_type != "ScheduleOfInvestments":
            selected.append(max(matching, key=lambda item: item["data_lines"]))
            continue

        groups: list[list[dict]] = []
        for candidate in matching:
            if not groups or candidate["table_index"] != groups[-1][-1]["table_index"] + 1:
                groups.append([candidate])
            else:
                groups[-1].append(candidate)
        selected.extend(max(groups, key=lambda group: sum(item["data_lines"] for item in group)))
    return sorted(selected, key=lambda item: item["table_index"])


def _cell_records(table_index: int, cell_rows: list[list[str]]) -> tuple[list[dict], list[dict]]:
    raw_cells: list[dict] = []
    normalized_cells: list[dict] = []
    table_id = f"HTML_{table_index:04d}"
    for row_index, row in enumerate(cell_rows):
        for column_index, raw in enumerate(row):
            token = parse_numeric_token(raw)
            raw_cells.append({
                "source_page": None,
                "table_id": table_id,
                "flavor": "html",
                "selected": True,
                "table_score": None,
                "accuracy": None,
                "whitespace": None,
                "order": table_index,
                "row_index": row_index,
                "column_index": column_index,
                "raw_text": raw,
            })
            normalized_cells.append({
                "source_page": None,
                "table_id": table_id,
                "flavor": "html",
                "row_index": row_index,
                "column_index": column_index,
                "raw_text": raw,
                "normalized_text": normalize_financial_text(raw),
                "parsed_value": token.value,
                "parse_status": token.status,
                "currency": token.currency,
                "is_percent": token.is_percent,
                "is_ratio": token.is_ratio,
                "precision": token.precision,
            })
    return raw_cells, normalized_cells


def extract_html_filing(path: str | Path) -> tuple[list[dict], list[dict], list[dict], list[dict], dict]:
    source = Path(path)
    if source.suffix.lower() not in HTML_SUFFIXES:
        raise ValueError(f"Unsupported HTML extension: {source.suffix or '(none)'}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(source.read_bytes(), "lxml")
    detected_metadata = _document_metadata(soup)
    _clean_dom(soup)

    candidates: list[dict] = []
    leaf_tables = [table for table in soup.find_all("table") if table.find("table") is None]
    for table_index, table in enumerate(leaf_tables, start=1):
        lines, cell_rows = _table_rows(table)
        statement_type, heading, data_lines = _detect_statement_table(table, lines)
        if statement_type:
            candidates.append({
                "table_index": table_index,
                "statement_type": statement_type,
                "heading": heading,
                "data_lines": data_lines,
                "lines": lines,
                "cell_rows": cell_rows,
            })

    selected = _select_statement_candidates(candidates)

    raw_text_rows: list[dict] = []
    raw_cells: list[dict] = []
    normalized_cells: list[dict] = []
    line_number = 1

    def append_line(text: str, row_type_hint: str = "") -> None:
        nonlocal line_number
        normalized = normalize_financial_text(text)
        if not normalized:
            return
        record = {
            "source_page": None,
            "line_no": line_number,
            "raw_text": normalized,
            "normalized_text": normalized,
            "machine_readable": True,
            "page_status": "HTML_EXTRACTED",
        }
        if row_type_hint:
            record["row_type_hint"] = row_type_hint
        raw_text_rows.append(record)
        line_number += 1

    if detected_metadata.get("client_name"):
        append_line(detected_metadata["client_name"])
    for candidate in selected:
        if not any(detect_statement_type(line) == candidate["statement_type"] for line in candidate["lines"][:25]):
            append_line(candidate["heading"] or STATEMENT_TITLES[candidate["statement_type"]][0])
        for line, cell_row in zip(candidate["lines"], candidate["cell_rows"]):
            has_values = any(
                parse_numeric_token(value).status in {"NUMERIC", "DASH", "NA", "NM"}
                for value in cell_row[1:]
            )
            append_line(line, "" if has_values else "section")
        table_raw, table_normalized = _cell_records(candidate["table_index"], candidate["cell_rows"])
        raw_cells.extend(table_raw)
        normalized_cells.extend(table_normalized)

    audit = [{
        "Check": "HTML statement table detection",
        "Scope": "Document",
        "Status": "PASS" if selected else "NO_TABLE_FOUND",
        "Detail": (
            f"Selected {len(selected)} table(s) covering "
            f"{len({item['statement_type'] for item in selected})} statement(s) "
            f"from {len(leaf_tables)} HTML table(s): "
            + ", ".join(dict.fromkeys(item["statement_type"] for item in selected))
            if selected
            else f"No financial-statement tables were detected among {len(leaf_tables)} HTML table(s)."
        ),
    }]
    return raw_text_rows, raw_cells, normalized_cells, audit, detected_metadata
