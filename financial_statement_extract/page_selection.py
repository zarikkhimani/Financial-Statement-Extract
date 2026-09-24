"""Lightweight page planning shared by the API, CLI and desktop preflight.

Manual preflight retains unknown pages. Automatic plans use detection.py.
"""
from __future__ import annotations

import re
from dataclasses import replace

from models import PageSelectionReviewRequired, StatementPage, StatementPagePlan
from structure import detect_statement_heading_type

MANUAL_REVIEW_LIMIT = 50
PAGE_POLICIES = ("review", "exact", "suggested")


def strict_page_numbers(spec: str, count: int) -> list[int]:
    if spec.strip().lower() == "all":
        return list(range(1, count + 1))
    result = set()
    for part in spec.split(","):
        match = re.fullmatch(r"\s*(\d+)(?:\s*-\s*(\d+))?\s*", part)
        if not match:
            raise ValueError(f"Invalid PDF page selection: {part!r}.")
        start, end = int(match[1]), int(match[2] or match[1])
        if not 1 <= start <= end <= count:
            raise ValueError(f"PDF page range {part!r} is outside pages 1-{count} or reversed.")
        result.update(range(start, end + 1))
    return sorted(result)


def _blank(text: str, page: int) -> bool:
    # Only remove empty pages and standalone page-number/footer rules. Scans,
    # title pages and footnotes must never be discarded for low numeric density.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    content = [line for line in lines if not re.fullmatch(r"[-–—_]+", line)]
    return not content or content == [str(page)]


def build_page_plan(source_path: str, rows: list[dict], requested: list[int], mode: str) -> StatementPagePlan:
    by_page = {page: [] for page in requested}
    for row in rows:
        page = row.get("source_page")
        if page in by_page:
            by_page[page].append(row)
    records = []
    current_type = ""
    current_title = ""
    previous = None
    for page, page_rows in by_page.items():
        if previous is not None and page != previous + 1:
            current_type = current_title = ""
        previous = page
        lines = [str(row.get("raw_text", "")) for row in page_rows]
        text = "\n".join(lines)
        headings = [(line, detect_statement_heading_type(line)) for line in lines[:30]]
        heading = next(((line, kind) for line, kind in headings if kind), None)
        if heading:
            current_title, current_type = heading
        numeric = sum(bool(re.search(r"\d", line) and re.search(r"[A-Za-z]", line)) for line in lines)
        unreadable = any(row.get("page_status") == "OCR_REQUIRED" for row in page_rows)
        if unreadable or not page_rows:
            role, confidence, evidence = "unknown", 0.0, "No readable text; retained for review"
        elif not heading and _blank(text, page):
            role, confidence, evidence = "blank", 1.0, "Only a page number/footer rule or empty text"
        elif heading:
            role = "data" if numeric >= 2 else "title"
            confidence, evidence = 0.9, "Source statement heading"
        elif re.search(r"(?im)^\s*notes to (?:the )?(?:condensed )?(?:consolidated )?financial statements", text):
            current_type = current_title = ""
            role, confidence, evidence = "supporting", 0.9, "Notes heading; retained in manual selection"
        else:
            role, confidence, evidence = "unknown", 0.3, "Continuation not yet confirmed; retained"
        records.append(StatementPage(page, role, current_type, current_title, confidence, (evidence,)))
    suggested = tuple(item.page for item in records if item.role != "blank")
    warnings = []
    if any(item.role == "unknown" for item in records):
        warnings.append("Some pages need classification; the suggestion retains them.")
    return StatementPagePlan(
        source_path, mode, tuple(requested), tuple(requested), suggested, tuple(records),
        mode == "manual" and len(requested) > MANUAL_REVIEW_LIMIT, tuple(warnings),
    )


def resolve_page_plan(plan: StatementPagePlan, policy: str) -> StatementPagePlan:
    if policy not in PAGE_POLICIES:
        raise ValueError(f"Unknown page policy: {policy!r}.")
    if plan.review_required and policy == "review":
        raise PageSelectionReviewRequired(plan)
    selected = plan.suggested_pages if policy == "suggested" else plan.requested_pages
    if not selected:
        raise ValueError("No pages remain in the suggested selection.")
    return replace(plan, selected_pages=selected, review_required=False)
