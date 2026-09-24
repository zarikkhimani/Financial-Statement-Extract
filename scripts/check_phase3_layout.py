"""Bounded local smoke/benchmark. Writes only under the explicit output directory."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import extract_filing_to_workbook  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("output_dir")
    parser.add_argument("--pages", default="auto")
    parser.add_argument("--strategy", choices=("adaptive", "all"), default="adaptive")
    args = parser.parse_args()
    start = perf_counter()
    result, path = extract_filing_to_workbook(args.source, args.pages, output_dir=args.output_dir,
                                             table_strategy=args.strategy)
    print(json.dumps({"seconds": round(perf_counter() - start, 2), "output": str(path),
                      "statements": list(result.statements), "tables": len(result.statement_tables),
                      "fallback_pages": result.metadata.get("table_fallback_pages"),
                      "layout_audit": [row for row in result.extraction_audit_rows
                                       if row["Check"] in {"Source table coverage", "Source character decoding"}],
                      "equity_preview": [t["rows"][:8] for t in result.statement_tables
                                         if t["statement_type"] == "StockholdersEquityStatement"]}, ensure_ascii=True))


if __name__ == "__main__":
    main()
