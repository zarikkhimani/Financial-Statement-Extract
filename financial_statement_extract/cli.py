from __future__ import annotations

import argparse
from collections.abc import Sequence

from financial_statement_extract.api import extract_filing


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="financial-extract",
        description="Extract a local PDF or HTML financial filing into Excel.",
    )
    parser.add_argument("input_path", help="Path to a PDF, HTML, HTM, or XHTML filing.")
    parser.add_argument("--output-dir", help="Directory for the generated workbook.")
    parser.add_argument("--pages", default="auto", help="PDF pages such as 12,14-16; default: auto.")
    parser.add_argument("--client-name")
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
        )
    except (OSError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(output)
    return 0
