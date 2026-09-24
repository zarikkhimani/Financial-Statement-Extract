"""Single text scan reused for page planning and downstream parsing."""
from pathlib import Path

import pdfplumber

from financial_statement_extract.detection import detect_statement_plan, is_section_boundary, source_headings
from financial_statement_extract.html_guidance import matching_html_guidance
from normalization import normalize_financial_text


def scan_pdf_statements(path: Path):
    texts = []
    unreadable = set()
    raw_rows = []
    audit = []
    with pdfplumber.open(path) as document:
        for number, page in enumerate(document.pages, 1):
            text = page.extract_text() or ""
            texts.append(text)
            # Empty text with graphics is not proof of a blank conversion page.
            if not text.strip() and (page.images or len(page.curves) > 10):
                unreadable.add(number)
            status = "OCR_REQUIRED" if number in unreadable else "TEXT_EXTRACTED" if text.strip() else "BLANK"
            for index, line in enumerate(text.splitlines() or [""], 1):
                raw_rows.append({"source_page": number, "line_no": index, "raw_text": line,
                                 "normalized_text": normalize_financial_text(line), "machine_readable": bool(text.strip()),
                                 "page_status": status})
            audit.append({"Check": "Page machine readability", "Scope": f"Page {number}",
                          "Status": "OCR_REQUIRED" if number in unreadable else "PASS",
                          "Detail": f"Text scan: {status}."})
    guidance, companion, warnings = matching_html_guidance(path, texts)
    plan = detect_statement_plan(texts, str(path), unreadable_pages=unreadable,
                                 guidance=guidance, guidance_source=companion, guidance_warnings=warnings)
    return plan, raw_rows, audit


def statement_rows_from_plan(rows, plan):
    """Attach internal boundaries without inserting HTML names into PDF text."""
    by_page = {}
    for row in rows:
        if row["source_page"] in plan.selected_pages:
            by_page.setdefault(row["source_page"], []).append(row)
    records = {item.page: item for item in plan.pages}
    result = []
    for page, page_rows in by_page.items():
        record = records[page]
        kind, title = record.statement_type, record.source_title
        headings = {index: (t, name) for index, t, name in source_headings([row["raw_text"] for row in page_rows])}
        for index, row in enumerate(page_rows):
            if is_section_boundary(row["raw_text"]):
                break
            if index in headings:
                kind, title = headings[index]
            result.append(dict(row, statement_type_hint=kind, source_title=title))
    return result
