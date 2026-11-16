"""Optional, independent PDF comparison. Never supplies baseline statement data."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from time import perf_counter

from financial_statement_extract.page_selection import strict_page_numbers
from normalization import normalize_financial_text, parse_numeric_token


NUMBER = re.compile(r"(?<!\w)\d[\d,]*(?:\.\d+)?")


def require_pymupdf():
    try:
        import pymupdf
    except ModuleNotFoundError as exc:
        if exc.name != "pymupdf":
            raise
        raise ValueError(
            'PyMuPDF comparison is not installed. Run: python -m pip install --editable ".[pymupdf]"'
        ) from exc
    return pymupdf


def token_metrics(reference: list[dict], cells: list[dict], page: int, method: str) -> dict:
    """Count repeated numeric tokens; this does not verify signs, labels or periods."""
    source = Counter(token for row in reference if row.get("source_page") == page
                     for token in NUMBER.findall(str(row.get("raw_text") or "")))
    records = [cell for cell in cells if cell.get("source_page") == page]
    found = Counter(token for cell in records for token in NUMBER.findall(str(cell.get("raw_text") or "")))
    matched = sum((source & found).values())
    total = sum(source.values())
    return dict(method=method, page=page,
                tables=len({cell["table_id"] for cell in records}),
                rows=len({(cell["table_id"], cell["row_index"]) for cell in records}),
                reference_numeric_tokens=total, matched_numeric_tokens=matched,
                numeric_token_recall=matched / total if total else None,
                missing_numeric_tokens=dict(source - found), extra_numeric_tokens=dict(found - source))


def extract_comparison(path: Path, pages: str, reference_text: list[dict], baseline_cells: list[dict]) -> dict:
    pymupdf = require_pymupdf()
    result = dict(version=pymupdf.__version__, raw_text_rows=[], raw_table_cells=[],
                  normalized_table_cells=[], audit_rows=[], metrics=[], timings={})
    audit = result["audit_rows"]
    with pymupdf.open(str(path)) as document:
        selected = strict_page_numbers(pages, len(document))
        # Time text separately from table detection, on the identical resolved pages.
        start = perf_counter()
        for page_no in selected:
            try:
                text = document[page_no - 1].get_text("text", sort=True)
                for line_no, line in enumerate(text.splitlines(), 1):
                    result["raw_text_rows"].append(dict(source_page=page_no, line_no=line_no,
                                                       raw_text=line, normalized_text=normalize_financial_text(line)))
                if not text.strip():
                    audit.append(dict(Check="PyMuPDF text extraction", Scope=f"Page {page_no}",
                                      Status="OCR_REQUIRED", Detail="No readable text; this comparison does not run OCR."))
            except Exception as exc:
                audit.append(dict(Check="PyMuPDF text extraction", Scope=f"Page {page_no}",
                                  Status="ERROR", Detail=str(exc)))
        result["timings"]["pymupdf_text_seconds"] = perf_counter() - start

        for strategy in ("lines", "text"):
            start = perf_counter()
            flavor = f"pymupdf_{strategy}"
            for page_no in selected:
                page_cells = []
                page_normalized = []
                try:
                    page = document[page_no - 1]
                    finder = page.find_tables(strategy=strategy)
                    for table_no, table in enumerate(finder.tables, 1):
                        table_id = f"P{page_no:04d}_PYMUPDF_{strategy.upper()}_{table_no:02d}"
                        # Copy cells while their page and TableFinder are alive.
                        for row_index, row in enumerate(table.extract()):
                            for column_index, value in enumerate(row):
                                raw = "" if value is None else str(value)
                                cell = dict(source_page=page_no, table_id=table_id, flavor=flavor,
                                            selected=False, order=table_no, row_index=row_index,
                                            column_index=column_index, raw_text=raw,
                                            bbox=list(table.bbox),
                                            cell_bbox=list(table.rows[row_index].cells[column_index])
                                            if table.rows[row_index].cells[column_index] is not None else None)
                                page_cells.append(cell)
                                token = parse_numeric_token(raw)
                                page_normalized.append(dict(cell, normalized_text=normalize_financial_text(raw),
                                                            parsed_value=token.value, parse_status=token.status,
                                                            currency=token.currency, is_percent=token.is_percent,
                                                            is_ratio=token.is_ratio, precision=token.precision))
                    result["raw_table_cells"].extend(page_cells)
                    result["normalized_table_cells"].extend(page_normalized)
                    audit.append(dict(Check=f"PyMuPDF {strategy} table extraction", Scope=f"Page {page_no}",
                                      Status="INFO" if finder.tables else "NO_TABLE_FOUND",
                                      Detail=f"Detected {len(finder.tables)} table(s); comparison only."))
                except Exception as exc:
                    # Discard this page's incomplete records, retain an explicit finding.
                    audit.append(dict(Check=f"PyMuPDF {strategy} table extraction", Scope=f"Page {page_no}",
                                      Status="ERROR", Detail=str(exc)))
            result["timings"][f"pymupdf_{strategy}_tables_seconds"] = perf_counter() - start

    methods = {
        "baseline_selected": [cell for cell in baseline_cells if cell.get("selected")],
        "pdfplumber": [cell for cell in baseline_cells if cell.get("flavor") == "pdfplumber"],
        **{f"pymupdf_{strategy}": [cell for cell in result["raw_table_cells"]
                                  if cell["flavor"] == f"pymupdf_{strategy}"] for strategy in ("lines", "text")},
    }
    for method, cells in methods.items():
        for page_no in selected:
            metric = token_metrics(reference_text, cells, page_no, method)
            result["metrics"].append(metric)
            recall = metric["numeric_token_recall"]
            audit.append(dict(Check=f"Comparison numeric tokens: {method}", Scope=f"Page {page_no}",
                              Status="INFO" if recall is not None else "NOT_TESTED",
                              Detail=f"{metric['tables']} tables; {metric['rows']} grid rows; "
                                     f"{metric['matched_numeric_tokens']}/{metric['reference_numeric_tokens']} "
                                     "reference numeric tokens matched. Signs, labels and column alignment unverified."))
    audit.append(dict(Check="PyMuPDF comparison limitations", Scope="Selected PDF pages", Status="NOT_TESTED",
                      Detail="Raw table candidates only; baseline layout repairs are excluded. "
                             "PDFPlumber page text is the reference, not independent ground truth. Token counts include "
                             "dates and footnotes; matching counts do not verify signs, labels, periods, duplicate rows "
                             "or financial accuracy. Both PyMuPDF strategies are retained separately; no OCR is run."))
    audit.append(dict(Check="PyMuPDF comparison timing", Scope="Selected PDF pages", Status="INFO",
                      Detail=f"PyMuPDF {result['version']}; " + "; ".join(
                          f"{name}={seconds:.4f}s" for name, seconds in result["timings"].items())
                      + ". PyMuPDF timings share one open document and exclude file opening."))
    return result
