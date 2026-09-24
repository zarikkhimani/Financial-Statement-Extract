from __future__ import annotations

import argparse
from collections.abc import Sequence

from financial_statement_extract.api import extract_filing
from models import PageSelectionReviewRequired


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="financial-extract",
        description="Extract a local PDF or HTML financial filing into Excel.",
    )
    parser.add_argument("input_path", help="Path to a PDF, HTML, HTM, or XHTML filing.")
    parser.add_argument("--output-dir", help="Directory for the generated workbook.")
    parser.add_argument("--pages", default="auto", help="PDF pages such as 12,14-16; default: auto.")
    parser.add_argument(
        "--page-policy", choices=("review", "exact", "suggested"), default="review",
        help="Large manual selections require review; exact preserves every requested page; "
        "suggested removes only clearly blank/footer-only pages and retains schedules.",
    )
    parser.add_argument("--client-name")
    parser.add_argument("--table-strategy", choices=("adaptive", "all"), default="adaptive",
                        help="Adaptive uses PDFPlumber first and runs Camelot for incomplete pages; all runs every method.")
    parser.add_argument("--fiscal-year")
    parser.add_argument("--period")
    parser.add_argument("--audit-status")
    parser.add_argument(
        "--allow-nonlocal-paths",
        action="store_true",
        help="Explicitly allow network/device paths; disabled by default.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    metadata = {
        key: value
        for key, value in {
            "client_name": args.client_name,
            "year": args.fiscal_year,
            "period": args.period,
            "audit_status": args.audit_status,
        }.items()
        if value
    }
    try:
        _, output = extract_filing(
            args.input_path,
            pages=args.pages,
            metadata=metadata,
            output_dir=args.output_dir,
            allow_nonlocal_paths=args.allow_nonlocal_paths,
            page_policy=args.page_policy,
            table_strategy=args.table_strategy,
        )
    except PageSelectionReviewRequired as exc:
        from extractors import format_page_numbers
        suggestion = format_page_numbers(list(exc.plan.suggested_pages))
        parser.exit(2, f"{exc}\nSuggested pages: {suggestion or '(none)'}\n"
                    "Choose --page-policy suggested or --page-policy exact to continue.\n")
    except (OSError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(output)
    return 0
