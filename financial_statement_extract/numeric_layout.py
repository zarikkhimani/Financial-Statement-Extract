"""Conservative display repair for accounting amounts split by PDF table grids.

Keep the original extraction grids as evidence. Join only one amount and its
immediately adjacent closing parenthesis in an established numeric column.
"""
from __future__ import annotations

from collections import Counter
import re


_AMOUNT = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_OPEN_AMOUNT = re.compile(r"\s*\(\s*(?:[$\u20ac\u00a3\u00a5]\s*)?(" + _AMOUNT + r")\s*")
_POSITIVE = re.compile(r"\s*(?:[$\u20ac\u00a3\u00a5]\s*)?(" + _AMOUNT + r")\s*")
_CORE_TYPES = {"BalanceSheet", "CashFlowStatement", "PartnersCapital", "StockholdersEquityStatement"}
_PDF_GRIDS = {"pdfplumber", "stream", "lattice"}


def split_accounting_cells(table: dict) -> list[dict]:
    """Return explicit, local repairs, with zero-based source grid coordinates.

    Positive amounts of at least 100 on two other labelled rows establish the
    amount column. Small integer reference columns do not qualify. Unsupported
    layouts, spans, rates, digit fragments, missing values and unlabelled rows
    remain literal. Schedules are outside this repair's scope.
    """
    if table.get("flavor") not in _PDF_GRIDS or table.get("statement_type") not in _CORE_TYPES:
        return []
    rows = table.get("rows", [])
    spans = {(r, c) for row, col, height, width in table.get("spans", [])
             for r in range(row, row + height) for c in range(col, col + width)}
    positive_rows = Counter()
    for row in rows:
        if not row or not re.search(r"[A-Za-z]", row[0]):
            continue
        for c, text in enumerate(row[1:], 1):
            match = _POSITIVE.fullmatch(text)
            if match and not re.fullmatch(r"(?:19|20)\d{2}", match[1]) and float(match[1].replace(",", "")) >= 100:
                positive_rows[c] += 1
    repairs = []
    for r, row in enumerate(rows):
        if not row or not re.search(r"[A-Za-z]", row[0]):
            continue
        for c in range(1, len(row) - 1):
            match = _OPEN_AMOUNT.fullmatch(row[c])
            if not match or row[c + 1].strip() != ")" or positive_rows[c] < 2:
                continue
            if (r, c) in spans or (r, c + 1) in spans:
                continue
            next_text = next((text.strip().lower() for text in row[c + 2:] if text.strip()), "")
            if next_text in {"%", "x"}:
                continue
            # Excel cannot faithfully store more than 15 significant digits.
            if len(re.sub(r"\D", "", match[1])) > 15:
                continue
            repairs.append({"row": r, "column": c, "closing_column": c + 1,
                            "original": [row[c], row[c + 1]], "joined": row[c].rstrip() + ")"})
    return repairs


def accounting_display_grid(table: dict) -> dict:
    repairs = split_accounting_cells(table)
    if not repairs:
        return table
    rows = [list(row) for row in table["rows"]]
    for repair in repairs:
        row = rows[repair["row"]]
        row[repair["column"]] = repair["joined"]
        row[repair["closing_column"]] = ""
    return {**table, "rows": rows}
