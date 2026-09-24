"""Input guidance and pure page/drop helpers shared by the desktop view."""

from pathlib import Path

from financial_statement_extract.page_selection import MANUAL_REVIEW_LIMIT
from path_policy import normalize_path

HTML_SUFFIXES = {".html", ".htm", ".xhtml"}
PAGE_WARNING_LIMIT = MANUAL_REVIEW_LIMIT
PAGES_PLACEHOLDER = "(Auto) Enter PDF page numbers, not printed 10-K page numbers"
PAGES_HELP_TEXT = (
    "For manual page selection, use the PDF viewer's page numbers (for example, page 42 of 180), "
    "not the page numbers printed inside the 10-K."
)



def effective_pages_value(value: str, placeholder_active: bool = False) -> str:
    text = (value or "").strip()
    if placeholder_active or not text or text == PAGES_PLACEHOLDER:
        return "auto"
    return text


def count_requested_pages(value: str) -> int | None:
    """Count distinct pages in a manual selection without expanding large ranges."""
    text = (value or "").strip().lower()
    if text in {"", "auto", "(auto)", "all"}:
        return None

    intervals: list[tuple[int, int]] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if "-" in part:
                start_text, end_text = part.split("-", 1)
                start, end = int(start_text), int(end_text)
                if start <= 0 or end <= 0 or start > end:
                    continue
                intervals.append((start, end))
            else:
                page = int(part)
                if page > 0:
                    intervals.append((page, page))
        except ValueError:
            continue

    if not intervals:
        return 0

    intervals.sort()
    total = 0
    current_start, current_end = intervals[0]
    for start, end in intervals[1:]:
        if start <= current_end + 1:
            current_end = max(current_end, end)
        else:
            total += current_end - current_start + 1
            current_start, current_end = start, end
    return total + current_end - current_start + 1


def normalize_dropped_path(value: str, *, allow_nonlocal_paths: bool = False) -> Path:
    text = (value or "").strip().strip('"').strip("{}")
    return normalize_path(text, allow_nonlocal_paths=allow_nonlocal_paths)


def select_dropped_filing(values: list[str] | tuple[str, ...]) -> Path | None:
    for value in values:
        try:
            path = normalize_dropped_path(value)
        except ValueError:
            continue
        if path.suffix.lower() == ".pdf" or path.suffix.lower() in HTML_SUFFIXES:
            return path
    return None
