from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import unicodedata

from audit import run_financial_audits
from excel_writer import write_extraction_workbook
from extractors import extract_page_text_pdfplumber, extract_tables_camelot, extract_tables_pdfplumber, format_page_numbers, get_page_count, get_pdf_document_type
from html_extractor import HTML_SUFFIXES, extract_html_filing
from models import ExtractionResult
from financial_statement_extract.pdfplumber_experimental import extract_tables_pdfplumber_experimental
from path_policy import normalize_path
from statements import parse_financial_statements
from financial_statement_extract.page_selection import build_page_plan, resolve_page_plan, strict_page_numbers
from financial_statement_extract.table_layout import covered_pages, organize_source_tables
from financial_statement_extract.progress import ExtractionStage as Stage, ProgressReporter, report


PUBLIC_DOCUMENT_PATTERNS = (
    (r"(?<!\d)10[\s_.-]*K[\s_.-]*(?:/|_)?A(?![A-Z0-9])", "10K-A"),
    (r"(?<!\d)10[\s_.-]*Q[\s_.-]*(?:/|_)?A(?![A-Z0-9])", "10Q-A"),
    (r"(?<!\d)8[\s_.-]*K[\s_.-]*(?:/|_)?A(?![A-Z0-9])", "8K-A"),
    (r"(?<!\d)20[\s_.-]*F[\s_.-]*(?:/|_)?A(?![A-Z0-9])", "20F-A"),
    (r"(?<!\d)40[\s_.-]*F[\s_.-]*(?:/|_)?A(?![A-Z0-9])", "40F-A"),
    (r"(?<!\d)6[\s_.-]*K[\s_.-]*(?:/|_)?A(?![A-Z0-9])", "6K-A"),
    (r"(?<!\d)10[\s_.-]*K(?![A-Z0-9])", "10K"),
    (r"(?<!\d)10[\s_.-]*Q(?![A-Z0-9])", "10Q"),
    (r"(?<!\d)8[\s_.-]*K(?![A-Z0-9])", "8K"),
    (r"(?<!\d)20[\s_.-]*F(?![A-Z0-9])", "20F"),
    (r"(?<!\d)40[\s_.-]*F(?![A-Z0-9])", "40F"),
    (r"(?<!\d)6[\s_.-]*K(?![A-Z0-9])", "6K"),
    (r"(?<![A-Z0-9])S[\s_.-]*1(?!\d)", "S1"),
    (r"(?<![A-Z0-9])F[\s_.-]*1(?!\d)", "F1"),
    (r"(?<![A-Z0-9])DEF[\s_.-]*14[\s_.-]*A(?![A-Z0-9])", "DEF14A"),
    (r"ANNUAL[\s_.-]+REPORT", "AnnualReport"),
)

PRIVATE_DOCUMENT_PATTERNS = (
    (r"(?<![A-Z0-9])Q[\s_.-]*O[\s_.-]*E(?![A-Z0-9])|QUALITY[\s_.-]+OF[\s_.-]+EARNINGS", "QoE"),
    (r"(?<![A-Z0-9])CIM(?![A-Z0-9])|CONFIDENTIAL[\s_.-]+INFORMATION[\s_.-]+MEMORANDUM", "CIM"),
    (r"MANAGEMENT[\s_.-]+ACCOUNTS", "ManagementAccounts"),
    (r"TRIAL[\s_.-]+BALANCE", "TrialBalance"),
    (r"(?<![A-Z0-9])BUDGET(?![A-Z0-9])", "Budget"),
    (r"(?<![A-Z0-9])FORECAST(?![A-Z0-9])", "Forecast"),
)

AUDIT_STATUS_TOKENS = {
    "audited": "AuditedFinancials",
    "reviewed": "ReviewedFinancials",
    "compiled": "CompiledFinancials",
    "company prepared": "CompanyPreparedFinancials",
    "draft": "DraftFinancials",
}


def _filename_component(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9]+", "_", text)
    return text.strip("_")


def _fiscal_year_token(value: object) -> str:
    text = str(value or "").strip()
    four_digit = re.search(r"(?<!\d)((?:19|20|21)\d{2})(?!\d)", text)
    if four_digit:
        return f"FY{four_digit.group(1)[-2:]}"
    short = re.fullmatch(r"(?i)\s*(?:FY\s*)?'?(\d{2})\s*", text)
    return f"FY{short.group(1)}" if short else ""


def _infer_fiscal_year(statements: dict) -> str:
    years: list[int] = []
    for frame in statements.values():
        for label in frame.attrs.get("period_labels", []):
            years.extend(int(year) for year in re.findall(r"(?<!\d)((?:19|20|21)\d{2})(?!\d)", str(label)))
    return f"FY{max(years) % 100:02d}" if years else ""


def _infer_client_name(statements: dict) -> str:
    priority = ("IncomeStatement", "CashFlowStatement", "BalanceSheet", "PartnersCapital", "ScheduleOfInvestments")
    frames = [statements[name] for name in priority if name in statements]
    frames.extend(frame for name, frame in statements.items() if name not in priority)
    for frame in frames:
        name = str(frame.attrs.get("company_name") or "").strip()
        if name and name.casefold() != "unknown company":
            return _filename_component(name)
    return ""


def _document_type(source_stem: str, metadata: dict) -> tuple[str, bool]:
    explicit = str(metadata.get("document_type") or "").strip()
    text = explicit or source_stem
    upper = text.upper()
    for pattern, token in PUBLIC_DOCUMENT_PATTERNS:
        if re.search(pattern, upper):
            return token, True
    for pattern, token in PRIVATE_DOCUMENT_PATTERNS:
        if re.search(pattern, upper):
            return token, False
    audit_status = re.sub(r"\s+", " ", str(metadata.get("audit_status") or "").strip().lower())
    return AUDIT_STATUS_TOKENS.get(audit_status, ""), False


def _period_token(value: object, source_stem: str, document_type: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "", str(value or "")).upper()
    tokens = {
        "Q1": "Q1",
        "Q2": "Q2",
        "Q3": "Q3",
        "Q4": "Q4",
        "SEMIANNUAL": "SemiAnnual",
        "HALFYEAR": "SemiAnnual",
        "MONTHLY": "Monthly",
    }
    period = tokens.get(text, "")
    if document_type.startswith("10K"):
        return ""
    if not period and document_type.startswith("10Q"):
        match = re.search(r"(?<![A-Z0-9])Q([1-4])(?![A-Z0-9])", source_stem.upper())
        if match:
            period = f"Q{match.group(1)}"
    return period


def build_output_filename(source_path: str | Path, metadata: dict | None, statements: dict) -> str:
    """Build a concise filing-style filename with progressively simpler fallbacks."""
    path = Path(source_path)
    meta = dict(metadata or {})
    fiscal_year = _fiscal_year_token(meta.get("year")) or _infer_fiscal_year(statements) or _fiscal_year_token(path.stem)
    client = _filename_component(meta.get("client_name")) or _infer_client_name(statements)
    document_type, is_public = _document_type(path.stem, meta)
    period = _period_token(meta.get("period"), path.stem, document_type)

    candidates: list[list[str]] = []
    if is_public:
        if document_type.startswith("10Q") and period:
            candidates.append([fiscal_year, period, document_type, client])
        candidates.extend([
            [fiscal_year, document_type, client],
            [document_type, client],
            [fiscal_year, client],
            [client, "Financials"],
            [fiscal_year, document_type],
            [document_type],
            [fiscal_year, "Financials"],
        ])
    else:
        if period:
            candidates.append([fiscal_year, period, document_type, client])
        candidates.extend([
            [fiscal_year, document_type, client],
            [fiscal_year, period, client] if period else [],
            [fiscal_year, client],
            [document_type, client],
            [client, "Financials"],
            [fiscal_year, document_type],
            [document_type],
            [fiscal_year, "Financials"],
        ])

    for parts in candidates:
        if parts and all(parts):
            return "_".join(parts) + ".xlsx"
    return "Extracted_Financials.xlsx"

def _extraction_metrics(raw_text_rows: list[dict], raw_table_cells: list[dict], normalized_table_cells: list[dict], pages_requested: list[int], statements: dict, parsed_cells: list[dict], unmapped: list[dict]) -> list[dict]:
    text_pages = {r.get("source_page") for r in raw_text_rows if r.get("machine_readable")}
    ocr_pages = {r.get("source_page") for r in raw_text_rows if r.get("page_status") == "OCR_REQUIRED"}
    table_ids = {r.get("table_id") for r in raw_table_cells if r.get("selected")}
    low_quality_table_ids = {
        r.get("table_id") for r in raw_table_cells
        if r.get("selected") and (float(r.get("accuracy") or 0) < 80 or float(r.get("whitespace") or 0) > 50)
    }
    parse_errors = sum(1 for r in parsed_cells if r.get("parse_status") == "PARSE_ERROR")
    mapped_rows = sum(len(df) for df in statements.values())

    return [
        {"Check": "Pages requested", "Scope": "Document", "Status": "INFO", "Detail": str(len(pages_requested))},
        {"Check": "Pages with machine-readable text", "Scope": "Document", "Status": "INFO", "Detail": str(len(text_pages))},
        {"Check": "Pages requiring OCR", "Scope": "Document", "Status": "WARN" if ocr_pages else "PASS", "Detail": ", ".join(map(str, sorted(x for x in ocr_pages if x))) if ocr_pages else "0"},
        {"Check": "Selected tables", "Scope": "Document", "Status": "INFO", "Detail": str(len(table_ids))},
        {"Check": "Low-quality selected tables", "Scope": "Document", "Status": "WARN" if low_quality_table_ids else "PASS", "Detail": ", ".join(sorted(x for x in low_quality_table_ids if x)) if low_quality_table_ids else "0"},
        {"Check": "Parsed statement rows", "Scope": "Document", "Status": "INFO", "Detail": str(mapped_rows)},
        {"Check": "Unmapped or low-confidence rows", "Scope": "Document", "Status": "WARN" if unmapped else "PASS", "Detail": str(len(unmapped))},
        {"Check": "Numeric parse errors", "Scope": "Document", "Status": "WARN" if parse_errors else "PASS", "Detail": str(parse_errors)},
        {"Check": "Normalized table cells", "Scope": "Document", "Status": "INFO", "Detail": str(len(normalized_table_cells))},
    ]


def extract_pdf_to_workbook(
    pdf_path: str,
    pages: str = "auto",
    metadata: dict | None = None,
    output_dir: str | None = None,
    *,
    allow_nonlocal_paths: bool = False,
    page_policy: str = "review",
    table_strategy: str = "adaptive",
    progress: ProgressReporter | None = None,
) -> tuple[ExtractionResult, Path]:
    report(progress, Stage.VALIDATING)
    if table_strategy not in {"adaptive", "all"}:
        raise ValueError("table_strategy must be 'adaptive' or 'all'.")
    path = normalize_path(pdf_path, allow_nonlocal_paths=allow_nonlocal_paths)
    if not path.exists():
        raise FileNotFoundError(path)

    report(progress, Stage.DETECTING_PAGES, "Reading PDF text and preparing the page selection")
    page_count = get_page_count(path)
    requested_pages = (pages or "").strip()
    auto_mode = requested_pages.lower() in {"", "auto", "(auto)"}
    if auto_mode:
        from financial_statement_extract.pdf_detection import scan_pdf_statements
        page_plan, raw_text_rows, text_audit = scan_pdf_statements(path)
        effective_pages = format_page_numbers(list(page_plan.selected_pages))
        if not effective_pages:
            raise ValueError("Auto page detection could not find financial statements. Type page numbers in the Pages field and try again.")
    else:
        effective_pages = requested_pages
    requested_numbers = strict_page_numbers(effective_pages, page_count)
    page_indices = [page - 1 for page in requested_numbers]
    if not page_indices:
        raise ValueError("No valid pages were selected.")

    if not auto_mode:
        raw_text_rows, text_audit = extract_page_text_pdfplumber(path, effective_pages)
        page_plan = build_page_plan(str(path), raw_text_rows, requested_numbers, "manual")
    page_plan = resolve_page_plan(page_plan, page_policy)
    effective_pages = format_page_numbers(list(page_plan.selected_pages))
    page_indices = [page - 1 for page in page_plan.selected_pages]
    raw_text_rows = [row for row in raw_text_rows if row.get("source_page") in page_plan.selected_pages]
    report(progress, Stage.EXTRACTING_TABLES, f"PDFPlumber · {len(page_plan.selected_pages)} selected pages")
    plumber_raw, plumber_normalized, plumber_table_audit = extract_tables_pdfplumber(path, effective_pages)
    for row in plumber_raw:
        row["selected"] = True
    covered = covered_pages(plumber_raw, raw_text_rows)
    fallback_pages = list(page_plan.selected_pages) if table_strategy == "all" else [
        page for page in page_plan.selected_pages if page not in covered]
    camelot_raw, camelot_normalized, camelot_audit = ([], [], [])
    if fallback_pages:
        report(progress, Stage.EXTRACTING_TABLES, f"Camelot fallback · {len(fallback_pages)} pages")
        camelot_raw, camelot_normalized, camelot_audit = extract_tables_camelot(
            path, format_page_numbers(fallback_pages))

    # Keep sufficiently covered PDFPlumber grids. For other pages use Camelot's
    # selected flavor if available, preserving every attempted raw candidate.
    for row in camelot_raw:
        if row.get("source_page") in covered:
            row["selected"] = False
    camelot_selected_pages = {r.get("source_page") for r in camelot_raw if r.get("selected")}
    for row in plumber_raw:
        row["selected"] = row.get("source_page") not in camelot_selected_pages
    plumber_selected_pages = {r.get("source_page") for r in plumber_raw if r.get("selected")}
    raw_table_cells = camelot_raw + plumber_raw
    normalized_table_cells = [r for r in camelot_normalized if r.get("source_page") in camelot_selected_pages] + [r for r in plumber_normalized if r.get("source_page") in plumber_selected_pages]
    table_audit = camelot_audit + plumber_table_audit
    table_audit.append({"Check": "Table extraction strategy", "Scope": "Document", "Status": "INFO",
                        "Detail": f"{table_strategy}: PDFPlumber first; Camelot attempted on "
                        f"{len(fallback_pages)} of {len(page_plan.selected_pages)} pages. "
                        "Adaptive skips Camelot only with at least 97% numeric-token coverage."})

    report(progress, Stage.EXTRACTING_TABLES, "PDFPlumber Experimental - independent comparison")
    experimental_raw, experimental_normalized, experimental_audit = extract_tables_pdfplumber_experimental(
        path, effective_pages)

    report(progress, Stage.PARSING, "Preserving statement labels and source-table layouts")
    if auto_mode:
        from financial_statement_extract.pdf_detection import statement_rows_from_plan
        parser_rows = statement_rows_from_plan(raw_text_rows, page_plan)
    else:
        parser_rows = raw_text_rows
    statements, parsed_cells, parser_issues, unmapped = parse_financial_statements(parser_rows)
    statement_tables, layout_issues = organize_source_tables(raw_table_cells, parser_rows, statements, page_plan)
    from financial_statement_extract.balance_layout import recover_pdf_balance_tables
    statement_tables, balance_issues = recover_pdf_balance_tables(path, statement_tables, statements, page_plan)
    layout_issues.extend(balance_issues)
    from financial_statement_extract.equity_layout import recover_pdf_equity_tables
    statement_tables, equity_issues = recover_pdf_equity_tables(path, statement_tables, statements, page_plan)
    layout_issues.extend(equity_issues)
    table_audit.extend(layout_issues)
    incomplete = set(page_plan.selected_pages) - covered_pages(raw_table_cells, raw_text_rows)
    if incomplete:
        table_audit.append({"Check": "Source table coverage", "Scope": "Document", "Status": "WARN",
                            "Detail": "Raw extraction candidates have incomplete numeric-token coverage on pages " + format_page_numbers(list(incomplete))
                            + ". Recovered statement rows are checked separately. Review the source; table discovery alone is not proof of completeness."})
    report(progress, Stage.AUDITING, "Checking extracted statements and preparing output metadata")
    financial_audit = run_financial_audits(statements, parser_issues)

    meta = dict(metadata or {})
    if not str(meta.get("document_type") or "").strip():
        detected_document_type = get_pdf_document_type(path)
        if detected_document_type:
            meta["document_type"] = detected_document_type
    meta.update({
        "source_file": path.name,
        "source_path": str(path),
        "pages_requested": "auto" if auto_mode else requested_pages,
        "pages_selected": effective_pages,
        "statement_page_plan": page_plan.to_dict(),
        "page_count": page_count,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "rescaled_values": False,
        "table_strategy": table_strategy,
        "table_fallback_pages": fallback_pages,
        "value_policy": "Source dashes/NA/NM/blanks remain missing statuses; no missing periods are invented.",
    })

    extraction_audit = text_audit + table_audit
    extraction_audit.extend(_extraction_metrics(raw_text_rows, raw_table_cells, normalized_table_cells, page_indices, statements, parsed_cells, unmapped))

    result = ExtractionResult(
        metadata=meta,
        raw_text_rows=raw_text_rows,
        raw_table_cells=raw_table_cells,
        normalized_table_cells=normalized_table_cells,
        extraction_audit_rows=extraction_audit,
        statements=statements,
        parsed_cells=parsed_cells,
        financial_audit_rows=financial_audit,
        unmapped_rows=unmapped,
        page_plan=page_plan,
        statement_tables=statement_tables,
        experimental_raw_table_cells=experimental_raw,
        experimental_normalized_table_cells=experimental_normalized,
        experimental_audit_rows=experimental_audit,
    )

    from financial_statement_extract.workbook_validation import audit_selected_page_coverage
    result.extraction_audit_rows.extend(audit_selected_page_coverage(result))

    destination = (
        normalize_path(output_dir, allow_nonlocal_paths=allow_nonlocal_paths)
        if output_dir
        else path.parent
    )
    filename = build_output_filename(path, meta, statements)
    report(progress, Stage.WRITING, "Saving the Excel workbook; keep the application open")
    output_path = write_extraction_workbook(
        result,
        destination / filename,
        allow_nonlocal_paths=allow_nonlocal_paths,
    )
    return result, output_path


def extract_html_to_workbook(
    html_path: str,
    metadata: dict | None = None,
    output_dir: str | None = None,
    *,
    allow_nonlocal_paths: bool = False,
    progress: ProgressReporter | None = None,
) -> tuple[ExtractionResult, Path]:
    report(progress, Stage.VALIDATING)
    path = normalize_path(html_path, allow_nonlocal_paths=allow_nonlocal_paths)
    if not path.exists():
        raise FileNotFoundError(path)

    report(progress, Stage.EXTRACTING_TABLES, "Reading HTML and detecting statement tables")
    raw_text_rows, raw_table_cells, normalized_table_cells, extraction_audit, detected_metadata = extract_html_filing(path)
    report(progress, Stage.PARSING, "Preserving statement labels and source-table layouts")
    statements, parsed_cells, parser_issues, unmapped = parse_financial_statements(raw_text_rows)
    statement_tables, layout_issues = organize_source_tables(raw_table_cells, raw_text_rows, statements)
    extraction_audit.extend(layout_issues)
    report(progress, Stage.AUDITING, "Checking extracted statements and preparing output metadata")
    financial_audit = run_financial_audits(statements, parser_issues)

    meta = dict(detected_metadata)
    for key, value in (metadata or {}).items():
        if value is not None and str(value).strip() and str(value).strip().casefold() != "auto":
            meta[key] = value
    meta.update({
        "source_file": path.name,
        "source_path": str(path),
        "input_type": "HTML",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "rescaled_values": False,
        "value_policy": "Source dashes/NA/NM/blanks remain missing statuses; no missing periods are invented.",
    })
    parse_errors = sum(1 for row in parsed_cells if row.get("parse_status") == "PARSE_ERROR")
    extraction_audit.extend([
        {"Check": "Parsed statement rows", "Scope": "Document", "Status": "INFO", "Detail": str(sum(len(frame) for frame in statements.values()))},
        {"Check": "Unmapped or low-confidence rows", "Scope": "Document", "Status": "WARN" if unmapped else "PASS", "Detail": str(len(unmapped))},
        {"Check": "Numeric parse errors", "Scope": "Document", "Status": "WARN" if parse_errors else "PASS", "Detail": str(parse_errors)},
    ])

    result = ExtractionResult(
        metadata=meta,
        raw_text_rows=raw_text_rows,
        raw_table_cells=raw_table_cells,
        normalized_table_cells=normalized_table_cells,
        extraction_audit_rows=extraction_audit,
        statements=statements,
        parsed_cells=parsed_cells,
        financial_audit_rows=financial_audit,
        unmapped_rows=unmapped,
        statement_tables=statement_tables,
    )
    destination = (
        normalize_path(output_dir, allow_nonlocal_paths=allow_nonlocal_paths)
        if output_dir
        else path.parent
    )
    filename = build_output_filename(path, meta, statements)
    report(progress, Stage.WRITING, "Saving the Excel workbook; keep the application open")
    output_path = write_extraction_workbook(
        result,
        destination / filename,
        allow_nonlocal_paths=allow_nonlocal_paths,
    )
    return result, output_path


def extract_filing_to_workbook(
    input_path: str,
    pages: str = "auto",
    metadata: dict | None = None,
    output_dir: str | None = None,
    *,
    allow_nonlocal_paths: bool = False,
    page_policy: str = "review",
    table_strategy: str = "adaptive",
    progress: ProgressReporter | None = None,
) -> tuple[ExtractionResult, Path]:
    path = normalize_path(input_path, allow_nonlocal_paths=allow_nonlocal_paths)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_to_workbook(
            str(path),
            pages,
            metadata,
            output_dir,
            allow_nonlocal_paths=allow_nonlocal_paths,
            page_policy=page_policy,
            table_strategy=table_strategy,
            progress=progress,
        )
    if suffix in HTML_SUFFIXES:
        return extract_html_to_workbook(
            str(path),
            metadata,
            output_dir,
            allow_nonlocal_paths=allow_nonlocal_paths,
            progress=progress,
        )
    raise ValueError("Choose a PDF, HTML, HTM, or XHTML financial filing.")

def parse_text_to_result(text: str, metadata: dict | None = None) -> ExtractionResult:
    statements, parsed_cells, parser_issues, unmapped = parse_financial_statements(text)
    financial_audit = run_financial_audits(statements, parser_issues)
    meta = dict(metadata or {})
    meta.update({
        "source_file": "Clipboard / pasted text",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "rescaled_values": False,
        "value_policy": "Source dashes/NA/NM/blanks remain missing statuses; no missing periods are invented.",
    })
    raw_text_rows = [
        {"source_page": None, "line_no": idx, "raw_text": line, "normalized_text": line.strip(), "machine_readable": True, "page_status": "PASTED_TEXT"}
        for idx, line in enumerate(text.splitlines(), start=1)
    ]
    extraction_audit = [{"Check": "Input type", "Scope": "Text parser", "Status": "INFO", "Detail": f"{len(raw_text_rows)} pasted lines."}]
    return ExtractionResult(meta, raw_text_rows, [], [], extraction_audit, statements, parsed_cells, financial_audit, unmapped)
