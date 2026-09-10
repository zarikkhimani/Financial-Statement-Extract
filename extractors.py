from __future__ import annotations

import logging
import re
from pathlib import Path

import camelot
import pdfplumber

from normalization import normalize_financial_text, parse_numeric_token
from structure import detect_statement_heading_type

logger = logging.getLogger(__name__)

AUTO_STATEMENT_TYPES = ("IncomeStatement", "CashFlowStatement", "BalanceSheet")
_FINANCIAL_NUMBER_RE = re.compile(
    r"\(?\s*\$?\s*-?\d[\d,]*(?:\.\d+)?%?\s*\)?|(?<!\w)[\u2013\u2014\u2212-](?!\w)"
)

def parse_page_numbers(pages_str: str, max_pages: int) -> list[int]:
    text = (pages_str or "").strip().lower()
    if text == "all":
        return list(range(max_pages))
    result: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if "-" in part:
                start_s, end_s = part.split("-", 1)
                start, end = int(start_s), int(end_s)
                if start <= 0 or end <= 0 or start > end:
                    continue
                for page in range(start, end + 1):
                    idx = page - 1
                    if 0 <= idx < max_pages:
                        result.add(idx)
            else:
                page = int(part)
                idx = page - 1
                if page > 0 and 0 <= idx < max_pages:
                    result.add(idx)
        except ValueError:
            continue
    return sorted(result)


def get_page_count(pdf_path: str | Path) -> int:
    with pdfplumber.open(str(pdf_path)) as pdf:
        return len(pdf.pages)

def _page_statement_types(text: str) -> set[str]:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return {
        statement_type
        for line in lines[:30]
        # A statement name ending a prose sentence is a note reference, not a
        # standalone page heading. SEC statement headings conventionally omit
        # terminal periods, including when followed by "(unaudited)".
        if not line.endswith(".")
        if (statement_type := detect_statement_heading_type(line))
    }


def get_pdf_document_type(pdf_path: str | Path) -> str:
    """Infer a filing form from embedded PDF metadata or the cover page."""
    with pdfplumber.open(str(pdf_path)) as pdf:
        metadata = pdf.metadata or {}
        metadata_text = " ".join(str(value) for value in metadata.values() if value)
        cover_text = pdf.pages[0].extract_text() if pdf.pages else ""
    text = f"{metadata_text}\n{cover_text or ''}"
    patterns = (
        (r"\bFORM\s+10-K/A\b|\b10-K/A\b", "10K-A"),
        (r"\bFORM\s+10-Q/A\b|\b10-Q/A\b", "10Q-A"),
        (r"\bFORM\s+10-K\b", "10K"),
        (r"\bFORM\s+10-Q\b", "10Q"),
    )
    for pattern, document_type in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return document_type
    return ""


def _financial_data_line_count(text: str) -> int:
    count = 0
    for line in (text or "").splitlines():
        if not re.search(r"[A-Za-z]", line):
            continue
        if len(_FINANCIAL_NUMBER_RE.findall(line)) >= 2:
            count += 1
    return count


def _statement_page_is_complete(statement_type: str, text: str) -> bool:
    low = normalize_financial_text(text).lower()
    if statement_type == "CashFlowStatement":
        return any(marker in low for marker in (
            "cash and cash equivalents, end of",
            "cash and cash equivalents at end of",
            "cash, cash equivalents and restricted cash, end of",
        ))
    if statement_type == "BalanceSheet":
        return (
            "total liabilities and equity" in low
            or "total liabilities and stockholders" in low
            or "total liabilities and shareholders" in low
            or "net assets consist of" in low
        )
    if statement_type == "IncomeStatement":
        return (
            "total comprehensive income" in low
            or "net increase in net assets resulting from operations" in low
            or (("net income" in low or "net earnings" in low) and "diluted" in low)
        )
    return True


def select_auto_statement_pages(page_texts: list[str]) -> list[int]:
    """Return one-based core financial-statement pages, including continuations."""
    candidates: list[dict] = []
    for page_number, text in enumerate(page_texts, start=1):
        data_lines = _financial_data_line_count(text)
        if data_lines < 4:
            continue
        for statement_type in _page_statement_types(text):
            if statement_type not in AUTO_STATEMENT_TYPES:
                continue
            candidates.append({
                "page": page_number,
                "type": statement_type,
                "data_lines": data_lines,
            })

    selected: dict[str, dict] = {}
    for statement_type in AUTO_STATEMENT_TYPES:
        type_candidates = [item for item in candidates if item["type"] == statement_type]
        if not type_candidates:
            continue

        def rank(item: dict) -> tuple[int, int, int]:
            nearby_types = {
                other["type"]
                for other in candidates
                if other["type"] != statement_type and abs(other["page"] - item["page"]) <= 15
            }
            return len(nearby_types), item["data_lines"], -item["page"]

        selected[statement_type] = max(type_candidates, key=rank)

    pages = {item["page"] for item in selected.values()}
    for statement_type, item in selected.items():
        page_number = item["page"]
        if _statement_page_is_complete(statement_type, page_texts[page_number - 1]):
            continue
        for continuation_page in range(page_number + 1, min(len(page_texts), page_number + 2) + 1):
            continuation_text = page_texts[continuation_page - 1]
            next_types = _page_statement_types(continuation_text)
            if next_types and statement_type not in next_types:
                break
            if _financial_data_line_count(continuation_text) < 2:
                break
            pages.add(continuation_page)
            if _statement_page_is_complete(statement_type, continuation_text):
                break

    return sorted(pages)


def auto_detect_statement_pages(pdf_path: str | Path) -> list[int]:
    with pdfplumber.open(str(pdf_path)) as pdf:
        page_texts = [page.extract_text() or "" for page in pdf.pages]
    return select_auto_statement_pages(page_texts)


def format_page_numbers(page_numbers: list[int]) -> str:
    pages = sorted(set(page for page in page_numbers if page > 0))
    if not pages:
        return ""
    parts: list[str] = []
    start = previous = pages[0]
    for page in pages[1:]:
        if page == previous + 1:
            previous = page
            continue
        parts.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = page
    parts.append(str(start) if start == previous else f"{start}-{previous}")
    return ",".join(parts)


def extract_page_text_pdfplumber(pdf_path: str | Path, pages_str: str) -> tuple[list[dict], list[dict]]:
    raw_rows: list[dict] = []
    audit: list[dict] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        page_indices = parse_page_numbers(pages_str, len(pdf.pages))
        for idx in page_indices:
            page = pdf.pages[idx]
            page_no = idx + 1
            text = page.extract_text() or ""
            normalized = normalize_financial_text(text)
            if not normalized:
                audit.append({
                    "Check": "Page machine readability",
                    "Scope": f"Page {page_no}",
                    "Status": "OCR_REQUIRED",
                    "Detail": "No machine-readable text returned by pdfplumber.",
                })
                raw_rows.append({
                    "source_page": page_no,
                    "line_no": None,
                    "raw_text": "",
                    "normalized_text": "",
                    "machine_readable": False,
                    "page_status": "OCR_REQUIRED",
                })
                continue

            page_lines = text.splitlines()
            for line_no, line in enumerate(page_lines, start=1):
                raw_rows.append({
                    "source_page": page_no,
                    "line_no": line_no,
                    "raw_text": line,
                    "normalized_text": normalize_financial_text(line),
                    "machine_readable": True,
                    "page_status": "TEXT_EXTRACTED",
                })
            audit.append({
                "Check": "Page machine readability",
                "Scope": f"Page {page_no}",
                "Status": "PASS",
                "Detail": f"Extracted {len(page_lines)} text lines.",
            })
    return raw_rows, audit


def _table_score(table) -> float:
    report = getattr(table, "parsing_report", {}) or {}
    accuracy = float(report.get("accuracy", 0) or 0)
    whitespace = float(report.get("whitespace", 100) or 100)
    rows, cols = table.df.shape if hasattr(table, "df") else (0, 0)
    size_bonus = min(8.0, (rows * cols) ** 0.5 / 2 if rows and cols else 0)
    return accuracy - 0.45 * whitespace + size_bonus


def extract_tables_camelot(pdf_path: str | Path, pages_str: str) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Run Camelot page by page with both lattice and stream. Preserve every candidate,
    mark the better flavor per page, and keep table boundaries intact.
    """
    page_count = get_page_count(pdf_path)
    page_indices = parse_page_numbers(pages_str, page_count)
    all_candidates: list[dict] = []
    normalized_cells: list[dict] = []
    audit: list[dict] = []

    for idx in page_indices:
        page_no = idx + 1
        candidates_by_flavor: dict[str, list] = {"lattice": [], "stream": []}
        flavor_errors: dict[str, str] = {}

        for flavor in ("lattice", "stream"):
            try:
                tables = camelot.read_pdf(str(pdf_path), pages=str(page_no), flavor=flavor, suppress_stdout=True)
                candidates_by_flavor[flavor] = list(tables)
            except Exception as exc:
                flavor_errors[flavor] = str(exc)
                logger.warning("Camelot %s failed on page %s: %s", flavor, page_no, exc)

        flavor_scores: dict[str, float] = {}
        for flavor, tables in candidates_by_flavor.items():
            scores = [_table_score(t) for t in tables if hasattr(t, "df") and not t.df.empty]
            flavor_scores[flavor] = sum(scores) / len(scores) if scores else float("-inf")

        best_flavor = max(flavor_scores, key=flavor_scores.get) if any(v != float("-inf") for v in flavor_scores.values()) else ""

        found_any = False
        for flavor, tables in candidates_by_flavor.items():
            for table_idx, table in enumerate(tables, start=1):
                if not hasattr(table, "df") or table.df.empty:
                    continue
                found_any = True
                report = getattr(table, "parsing_report", {}) or {}
                selected = flavor == best_flavor
                table_id = f"P{page_no:04d}_{flavor.upper()}_{table_idx:02d}"
                score = round(_table_score(table), 3)
                for r_idx, row in table.df.iterrows():
                    for c_idx, value in row.items():
                        raw = "" if value is None else str(value)
                        all_candidates.append({
                            "source_page": page_no,
                            "table_id": table_id,
                            "flavor": flavor,
                            "selected": selected,
                            "table_score": score,
                            "accuracy": report.get("accuracy"),
                            "whitespace": report.get("whitespace"),
                            "order": report.get("order"),
                            "row_index": int(r_idx),
                            "column_index": int(c_idx),
                            "raw_text": raw,
                        })
                        if selected:
                            token = parse_numeric_token(raw)
                            normalized_cells.append({
                                "source_page": page_no,
                                "table_id": table_id,
                                "flavor": flavor,
                                "row_index": int(r_idx),
                                "column_index": int(c_idx),
                                "raw_text": raw,
                                "normalized_text": normalize_financial_text(raw),
                                "parsed_value": token.value,
                                "parse_status": token.status,
                                "currency": token.currency,
                                "is_percent": token.is_percent,
                                "is_ratio": token.is_ratio,
                                "precision": token.precision,
                            })

        if found_any:
            detail = f"Selected {best_flavor or 'none'}; lattice={len(candidates_by_flavor['lattice'])}, stream={len(candidates_by_flavor['stream'])}."
            audit.append({"Check": "Camelot table extraction", "Scope": f"Page {page_no}", "Status": "PASS", "Detail": detail})
        else:
            errors = "; ".join(f"{k}: {v}" for k, v in flavor_errors.items())
            audit.append({
                "Check": "Camelot table extraction",
                "Scope": f"Page {page_no}",
                "Status": "NO_TABLE_FOUND",
                "Detail": errors or "No tables detected by lattice or stream.",
            })

    return all_candidates, normalized_cells, audit


def extract_tables_pdfplumber(pdf_path: str | Path, pages_str: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Extract actual table structures with pdfplumber, separate from page-text extraction."""
    raw_cells: list[dict] = []
    normalized_cells: list[dict] = []
    audit: list[dict] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        page_indices = parse_page_numbers(pages_str, len(pdf.pages))
        for idx in page_indices:
            page_no = idx + 1
            try:
                tables = pdf.pages[idx].extract_tables() or []
            except Exception as exc:
                audit.append({
                    "Check": "PDFPlumber table extraction",
                    "Scope": f"Page {page_no}",
                    "Status": "ERROR",
                    "Detail": str(exc),
                })
                continue

            if not tables:
                audit.append({
                    "Check": "PDFPlumber table extraction",
                    "Scope": f"Page {page_no}",
                    "Status": "NO_TABLE_FOUND",
                    "Detail": "No table structure detected by pdfplumber.",
                })
                continue

            audit.append({
                "Check": "PDFPlumber table extraction",
                "Scope": f"Page {page_no}",
                "Status": "PASS",
                "Detail": f"Detected {len(tables)} table(s).",
            })
            for table_idx, table in enumerate(tables, start=1):
                table_id = f"P{page_no:04d}_PDFPLUMBER_{table_idx:02d}"
                for r_idx, row in enumerate(table):
                    for c_idx, value in enumerate(row):
                        raw = "" if value is None else str(value)
                        raw_cells.append({
                            "source_page": page_no,
                            "table_id": table_id,
                            "flavor": "pdfplumber",
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
                            "flavor": "pdfplumber",
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
