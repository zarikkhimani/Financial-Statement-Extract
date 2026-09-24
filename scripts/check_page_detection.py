"""Read-only source check. Writes diagnostics only to the specified local report."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractors import format_page_numbers
from financial_statement_extract.pdf_detection import scan_pdf_statements


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf")
    parser.add_argument("report")
    args = parser.parse_args()
    plan, rows, _ = scan_pdf_statements(Path(args.pdf))
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"plan": plan.to_dict(), "rows": rows}, indent=2), encoding="utf-8")
    print("Selected:", format_page_numbers(list(plan.selected_pages)))
    print("HTML:", plan.guidance_source or "PDF only")
    print("Warnings:", plan.warnings)
    for kind in sorted({p.statement_type for p in plan.pages if p.page in plan.selected_pages}):
        print(kind, format_page_numbers([p.page for p in plan.pages if p.page in plan.selected_pages and p.statement_type == kind]))


if __name__ == "__main__":
    main()
