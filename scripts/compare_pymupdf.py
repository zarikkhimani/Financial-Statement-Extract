"""Run the supported API and save a bounded, local PyMuPDF comparison report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from financial_statement_extract import extract_filing  # noqa: E402
from financial_statement_extract.page_selection import strict_page_numbers  # noqa: E402
from financial_statement_extract.pymupdf_comparison import require_pymupdf  # noqa: E402
from extractors import extract_page_text_pdfplumber  # noqa: E402
from normalization import normalize_financial_text  # noqa: E402


def benchmark_text(source: Path, pages: str) -> dict:
    """Alternate three runs per engine, including open/close for both."""
    pymupdf = require_pymupdf()
    durations = {"pdfplumber": [], "pymupdf": []}
    for repetition in range(3):
        engines = ("pdfplumber", "pymupdf") if repetition % 2 == 0 else ("pymupdf", "pdfplumber")
        for engine in engines:
            start = perf_counter()
            if engine == "pdfplumber":
                extract_page_text_pdfplumber(source, pages)
            else:
                with pymupdf.open(str(source)) as document:
                    for page in strict_page_numbers(pages, len(document)):
                        text = document[page - 1].get_text("text", sort=True)
                        normalize_financial_text(text)
                        for line in text.splitlines():
                            normalize_financial_text(line)
            durations[engine].append(perf_counter() - start)
    return {"runs_seconds": durations,
            "median_seconds": {engine: median(runs) for engine, runs in durations.items()},
            "scope": "Selected pages only; three alternating runs, with open/close and text normalization. "
                     "Same process with warm OS caches; not a full-filing or end-to-end speedup."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pages", default="auto")
    parser.add_argument("--page-policy", choices=("review", "exact", "suggested"), default="review")
    args = parser.parse_args()
    start = perf_counter()
    result, workbook = extract_filing(args.source, pages=args.pages, output_dir=args.output_dir,
                                      page_policy=args.page_policy, compare_pymupdf=True)
    comparison = result.pymupdf_comparison
    report = dict(source=str(args.source.resolve()), workbook=str(workbook),
                  selected_pages=list(result.page_plan.selected_pages),
                  extraction_with_comparison_seconds=perf_counter() - start,
                  pymupdf_version=comparison["version"], statements={
                      name: dict(rows=len(frame), periods=frame.attrs.get("period_labels", []))
                      for name, frame in result.statements.items()},
                  metrics=comparison["metrics"], table_timings=comparison["timings"],
                  text_benchmark=benchmark_text(args.source, result.metadata["pages_selected"]),
                  comparison_audit=comparison["audit_rows"],
                  baseline_findings=[row for row in result.financial_audit_rows + result.extraction_audit_rows
                                     + result.experimental_audit_rows if row.get("Status") not in {"PASS", "INFO"}])
    output = workbook.with_suffix(".comparison.json")
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(dict(workbook=str(workbook), report=str(output),
                         selected_pages=report["selected_pages"],
                         text_medians=report["text_benchmark"]["median_seconds"],
                         table_timings=report["table_timings"], metrics=report["metrics"]), indent=2))


if __name__ == "__main__":
    main()
