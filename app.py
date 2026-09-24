"""Compatibility imports and launcher for the packaged desktop UI."""

from tkinter import filedialog, messagebox

from financial_statement_extract.ui.controller import run_extraction
from financial_statement_extract.ui.inputs import (
    HTML_SUFFIXES,
    PAGE_WARNING_LIMIT,
    PAGES_HELP_TEXT,
    PAGES_PLACEHOLDER,
    count_requested_pages,
    effective_pages_value,
    normalize_dropped_path,
    select_dropped_filing,
)
from financial_statement_extract.ui.workspace import FinancialExtractorApp, main

__all__ = [
    "FinancialExtractorApp",
    "HTML_SUFFIXES",
    "PAGE_WARNING_LIMIT",
    "PAGES_HELP_TEXT",
    "PAGES_PLACEHOLDER",
    "count_requested_pages",
    "effective_pages_value",
    "filedialog",
    "main",
    "messagebox",
    "normalize_dropped_path",
    "run_extraction",
    "select_dropped_filing",
]


if __name__ == "__main__":
    main()
