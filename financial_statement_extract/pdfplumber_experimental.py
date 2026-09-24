"""Disposable PDFPlumber experiment, initially forked from the baseline extractor.

Keep algorithm changes here; results never participate in statement selection.
Shared normalization and equity geometry helpers retain their baseline behavior.
"""
from __future__ import annotations

from pathlib import Path
import re

import pdfplumber

from extractors import parse_page_numbers
from normalization import normalize_financial_text, parse_numeric_token


MONTH_DATE = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary|urary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\.?[^\S\r\n]+(?P<day>0?[1-9]|[12][0-9]|3[01])(?![\w.]|,[0-9])"
    r"(?:,?[^\S\r\n]+(?P<year>[0-9]{4})(?![\w.%]|,[0-9]))?",
    re.IGNORECASE,
)


def _group_dollars(row: list) -> list[str]:
    """Join a dollar sign to the next number in its extracted row before splitting."""
    cells = ["" if value is None else str(value) for value in row]
    grouped = []
    index = 0
    while index < len(cells):
        text = cells[index]
        while text.rstrip().endswith("$"):
            next_index = index + 1
            while next_index < len(cells) and not cells[next_index].strip():
                next_index += 1
            if next_index == len(cells) or not re.match(r"\s*[0-9]", cells[next_index]):
                break
            text = text.rstrip() + cells[next_index].lstrip()
            index = next_index
        grouped.append(re.sub(r"\$\s+(?=[0-9])", "$", text))
        index += 1
    return grouped


def _expand_amounts(row: list) -> list[str]:
    """Split dollar amounts and space-separated numeric runs into adjacent cells."""
    number = r"(?:\(?\$?[+-]?[0-9][0-9,]*(?:\.[0-9]+)?%?\)?|\u2014)"
    numeric_run = rf"(?<![\w.,]){number}(?:[^\S\r\n]+{number})+(?![\w.,])"
    amounts = rf"({numeric_run}|\$[0-9][0-9,]*(?:\.[0-9]+)?)"
    expanded = []
    for text in _group_dollars(row):
        protected_date_parts = {
            match.start(part)
            for match in MONTH_DATE.finditer(text)
            for part in ("day", "year")
            if match.start(part) >= 0
        }
        cursor = 0
        split = False
        for match in re.finditer(amounts, text):
            for token in re.finditer(r"\S+", match.group()):
                start = match.start() + token.start()
                end = match.start() + token.end()
                if start in protected_date_parts:
                    continue
                if text[cursor:start].strip():
                    expanded.append(text[cursor:start].strip())
                expanded.append(text[start:end])
                cursor = end
                split = True
        if not split:
            expanded.append(text)
        elif text[cursor:].strip():
            expanded.append(text[cursor:].strip())
    return expanded


def extract_tables_pdfplumber_experimental(pdf_path: str | Path, pages_str: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Extract actual table structures with pdfplumber, separate from page-text extraction."""
    raw_cells: list[dict] = []
    normalized_cells: list[dict] = []
    audit: list[dict] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        page_indices = parse_page_numbers(pages_str, len(pdf.pages))
        for idx in page_indices:
            page_no = idx + 1
            try:
                page = pdf.pages[idx]
                found = page.find_tables()
                tables = [table.extract() for table in found]
                from structure import detect_statement_heading_type
                is_equity = any(detect_statement_heading_type(line) == "StockholdersEquityStatement"
                                for line in (page.extract_text() or "").splitlines()[:25])
                if is_equity:
                    from financial_statement_extract.pdf_layout import equity_grid
                    grid = equity_grid(page, found)
                    if grid:
                        tables = [grid]
            except Exception as exc:
                audit.append({
                    "Check": "PDFPlumber Experimental table extraction",
                    "Scope": f"Page {page_no}",
                    "Status": "ERROR",
                    "Detail": str(exc),
                })
                continue

            if not tables:
                audit.append({
                    "Check": "PDFPlumber Experimental table extraction",
                    "Scope": f"Page {page_no}",
                    "Status": "NO_TABLE_FOUND",
                    "Detail": "No table structure detected by pdfplumber.",
                })
                continue

            audit.append({
                "Check": "PDFPlumber Experimental table extraction",
                "Scope": f"Page {page_no}",
                "Status": "PASS",
                "Detail": f"Detected {len(tables)} table(s).",
            })
            for table_idx, table in enumerate(tables, start=1):
                table_id = f"P{page_no:04d}_PDFPLUMBER_EXPERIMENTAL_{table_idx:02d}"
                for r_idx, row in enumerate(table):
                    for c_idx, raw in enumerate(_expand_amounts(row)):
                        raw_cells.append({
                            "source_page": page_no,
                            "table_id": table_id,
                            "flavor": "pdfplumber_experimental",
                            "selected": False,
                            "table_score": None,
                            "accuracy": None,
                            "whitespace": None,
                            "order": table_idx,
                            "row_index": r_idx,
                            "column_index": c_idx,
                            "raw_text": raw,
                        })
                        token = parse_numeric_token(raw)
                        normalized_cells.append({
                            "source_page": page_no,
                            "table_id": table_id,
                            "flavor": "pdfplumber_experimental",
                            "row_index": r_idx,
                            "column_index": c_idx,
                            "raw_text": raw,
                            "normalized_text": normalize_financial_text(raw),
                            "parsed_value": token.value,
                            "parse_status": token.status,
                            "currency": token.currency,
                            "is_percent": token.is_percent,
                            "is_ratio": token.is_ratio,
                            "precision": token.precision,
                        })
    return raw_cells, normalized_cells, audit
