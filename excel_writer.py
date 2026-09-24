from __future__ import annotations

import re
import math
from decimal import Decimal
from pathlib import Path

import pandas as pd

from models import ExtractionResult
from path_policy import normalize_path
from normalization import parse_numeric_token
from financial_statement_extract.table_layout import SINGLE_NUMBER, equity_display_grid
from financial_statement_extract.schedule_layout import schedule_display_grid
from financial_statement_extract.workbook_validation import BALANCE_COMPLETENESS, balance_completeness_status


# Reserve three empty rows and two empty columns on every exported tab.
# Apply offsets to cells, dimensions and filters so their layout stays intact.
TOP_BLANK_ROWS = 3
LEFT_BLANK_COLUMNS = 2


STATEMENT_SHEET_NAMES = {
    "BalanceSheet": "Balance Sheet",
    "IncomeStatement": "Income Statement",
    "CashFlowStatement": "Cash Flow",
    "PartnersCapital": "Partners Capital",
    "ScheduleOfInvestments": "Schedule of Investments",
}

STATEMENT_TITLES = {
    "BalanceSheet": "Consolidated Balance Sheets",
    "IncomeStatement": "Consolidated Statements of Operations",
    "CashFlowStatement": "Consolidated Statements of Cash Flows",
    "PartnersCapital": "Statement of Changes in Partners Capital",
    "ScheduleOfInvestments": "Schedule of Investments",
}

RAW_METHOD_SHEETS = (
    ("lattice", "Lattice", "Lattice"),
    ("stream", "Stream", "Stream"),
    ("pdfplumber", "PDFPlumber", "PDFPlumber tables"),
)


def ensure_unique_filename(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def safe_filename_component(text: str) -> str:
    text = re.sub(r"[<>:\"/\\|?*]+", "_", str(text or "").strip())
    return re.sub(r"\s+", "_", text).strip("_ .")


def _is_total_row(label: str) -> tuple[bool, bool]:
    low = label.lower().strip()
    total = (
        low.startswith("total ")
        or low.startswith("net cash ")
        or low.startswith("net income")
        or low.startswith("operating income")
        or low.startswith("income before ")
        or low.startswith("net increase ")
        or low.startswith("net decrease ")
    )
    grand = (
        low == "net income"
        or low == "total assets"
        or low.startswith("total liabilities and ")
        or low.endswith("cash, cash equivalents and restricted cash, end of year")
    )
    return total, grand


def _numeric_precision(value: object) -> int:
    numeric = float(value)
    if numeric.is_integer():
        return 0
    exponent = Decimal(str(numeric)).normalize().as_tuple().exponent
    return min(6, max(0, -exponent))


def _write_literal(worksheet, row: int, column: int, value: object, cell_format=None):
    text = "" if value is None else str(value)
    if not text:
        return worksheet.write_blank(row, LEFT_BLANK_COLUMNS + column, None, cell_format)
    return worksheet.write_string(row, LEFT_BLANK_COLUMNS + column, text, cell_format)


def _write_spanned_literal(
    worksheet,
    first_row: int,
    first_column: int,
    last_row: int,
    last_column: int,
    value: object,
    cell_format=None,
):
    """Write independent cells only; horizontal headings may center across them.

    Vertical source spans keep their value in the top-left cell. Never translate
    a source span into an Excel merge: every output cell must remain editable.
    """
    for row in range(first_row, last_row + 1):
        for column in range(first_column, last_column + 1):
            worksheet.write_blank(row, LEFT_BLANK_COLUMNS + column, None, cell_format)
    return _write_literal(worksheet, first_row, first_column, value, cell_format)



def _write_statement_sheet(writer, statement_type: str, df: pd.DataFrame, *, use_source_grids: bool = True):
    workbook = writer.book
    source_title = str(df.attrs.get("statement_title") or "")
    existing = {name.casefold() for name in writer.sheets}
    valid_title = (
        bool(source_title) and len(source_title) <= 31
        and not any(char in source_title for char in "[]:*?/\\")
        and not source_title.startswith("'") and not source_title.endswith("'")
        and source_title.casefold() not in existing | {"history", "review"}
    )
    cash_blocks = df.attrs.get("source_tables", [])
    formatted_cash = (statement_type == "CashFlowStatement" and cash_blocks
                      and all(t.get("flavor") == "cash_flow_text" for t in cash_blocks))
    formatted_balance = (statement_type == "BalanceSheet" and cash_blocks
                         and all(t.get("flavor") == "balance_geometry" for t in cash_blocks))
    formatted_equity = (statement_type in {"PartnersCapital", "StockholdersEquityStatement"} and cash_blocks
                        and all(t.get("flavor") == "equity_geometry" for t in cash_blocks))
    fallback_name = STATEMENT_SHEET_NAMES.get(statement_type) if not use_source_grids or formatted_cash or formatted_balance else None
    if formatted_equity:
        fallback_name = "Changes in Net Assets" if "net assets" in source_title.lower() else "Changes in Equity"
    sheet_name = source_title if valid_title else fallback_name or f"Statement {len(writer.sheets) + 1}"
    while sheet_name.casefold() in existing:
        sheet_name += "_"
    worksheet = workbook.add_worksheet(sheet_name)
    writer.sheets[sheet_name] = worksheet
    if (formatted_cash or formatted_balance) and use_source_grids:
        return _write_period_grids(workbook, worksheet, df)
    if formatted_equity and use_source_grids:
        return _write_equity_grids(workbook, worksheet, df)
    if use_source_grids and df.attrs.get("source_tables"):
        return _write_source_grids(workbook, worksheet, df)

    periods = list(df.attrs.get("period_labels", []))
    last_col = max(1, len(periods))
    company_name = str(df.attrs.get("company_name") or "").strip()
    statement_title = source_title
    unit_note = str(df.attrs.get("raw_unit_note") or "").strip()

    company_format = workbook.add_format({"bold": True, "font_size": 12, "font_color": "#000000", "align": "center_across", "valign": "vcenter"})
    title_format = workbook.add_format({"bold": True, "font_size": 14, "font_color": "#000000", "align": "center_across", "valign": "vcenter"})
    unit_format = workbook.add_format({"italic": True, "font_color": "#000000", "align": "center_across"})
    label_header_format = workbook.add_format({"bold": True, "font_color": "#000000", "align": "left", "bottom": 1, "bottom_color": "#000000"})
    period_header_format = workbook.add_format({"bold": True, "font_color": "#000000", "align": "right", "valign": "bottom", "text_wrap": True, "bottom": 1, "bottom_color": "#000000"})
    section_format = workbook.add_format({"bold": True, "font_color": "#000000", "align": "left", "valign": "vcenter", "text_wrap": True, "top": 1, "bottom": 1, "top_color": "#000000", "bottom_color": "#000000"})
    label_format = workbook.add_format({"align": "left", "valign": "vcenter", "text_wrap": True, "indent": 1})
    total_label_format = workbook.add_format({"bold": True, "align": "left", "valign": "vcenter", "text_wrap": True, "top": 1})
    grand_label_format = workbook.add_format({"bold": True, "align": "left", "valign": "vcenter", "text_wrap": True, "top": 1, "bottom": 6})
    number_formats: dict[tuple[int, bool, bool, bool], object] = {}

    def number_cell_format(precision: int, is_total: bool, is_grand: bool, is_percent: bool = False):
        key = (precision, is_total, is_grand, is_percent)
        if key not in number_formats:
            positive = ("0" + ("." + "0" * precision if precision else "") + "%") if is_percent else "#,##0" + ("." + "0" * precision if precision else "")
            properties = {"align": "right", "num_format": f"{positive};({positive});-"}
            if is_total or is_grand:
                properties.update({"bold": True, "top": 1})
            if is_grand:
                properties["bottom"] = 6
            number_formats[key] = workbook.add_format(properties)
        return number_formats[key]

    _write_spanned_literal(worksheet, TOP_BLANK_ROWS, 0, TOP_BLANK_ROWS, last_col, company_name, company_format)
    _write_spanned_literal(worksheet, TOP_BLANK_ROWS + 1, 0, TOP_BLANK_ROWS + 1, last_col, statement_title, title_format)
    _write_spanned_literal(worksheet, TOP_BLANK_ROWS + 2, 0, TOP_BLANK_ROWS + 2, last_col, unit_note, unit_format)
    worksheet.write_blank(TOP_BLANK_ROWS + 4, LEFT_BLANK_COLUMNS, None, label_header_format)
    for column_index, period in enumerate(periods, start=1):
        _write_literal(worksheet, TOP_BLANK_ROWS + 4, column_index, period, period_header_format)

    current_section = ""
    output_row = TOP_BLANK_ROWS + 5
    for _, item in df.iterrows():
        row_type = str(item.get("RowType", "Data"))
        label = str(item.get("RawItem") or "").strip()
        if not label and row_type == "Section":
            continue

        if row_type == "Section":
            current_section = label
            _write_spanned_literal(worksheet, output_row, 0, output_row, last_col, label, section_format)
            worksheet.set_row(output_row, 34 if len(label) > 80 else 20)
            output_row += 1
            continue

        is_total, is_grand = _is_total_row(label)
        label_cell_format = grand_label_format if is_grand else total_label_format if is_total else label_format
        numeric_values = [pd.to_numeric(item.get(period), errors="coerce") for period in periods]
        non_percent_values = [
            value
            for period, value in zip(periods, numeric_values)
            if "%" not in str(period) and "percent" not in str(period).lower() and not pd.isna(value)
        ]
        precision = max((_numeric_precision(value) for value in non_percent_values), default=0)
        if "earnings per share" in current_section.lower():
            precision = max(2, precision)

        _write_literal(worksheet, output_row, 0, label, label_cell_format)
        for column_index, (period, value) in enumerate(zip(periods, numeric_values), start=1):
            is_percent = "%" in str(period) or "percent" in str(period).lower()
            row_number_format = number_cell_format(1 if is_percent else precision, is_total, is_grand, is_percent)
            if pd.isna(value):
                worksheet.write_blank(output_row, LEFT_BLANK_COLUMNS + column_index, None, row_number_format)
            else:
                worksheet.write_number(output_row, LEFT_BLANK_COLUMNS + column_index, float(value), row_number_format)
        worksheet.set_row(output_row, 54 if len(label) > 130 else 38 if len(label) > 80 else 30 if len(label) > 55 else 18)
        output_row += 1

    worksheet.set_column(LEFT_BLANK_COLUMNS, LEFT_BLANK_COLUMNS, 62)
    if periods:
        period_width = max(15, min(22, max(len(str(period)) for period in periods) + 2))
        worksheet.set_column(LEFT_BLANK_COLUMNS + 1, LEFT_BLANK_COLUMNS + last_col, period_width)
    worksheet.set_row(TOP_BLANK_ROWS, 22)
    worksheet.set_row(TOP_BLANK_ROWS + 1, 26)
    worksheet.set_row(TOP_BLANK_ROWS + 2, 18)
    worksheet.set_row(TOP_BLANK_ROWS + 3, 8)
    worksheet.set_row(TOP_BLANK_ROWS + 4, 36 if any(len(str(period)) > 24 for period in periods) else 21)
    worksheet.hide_gridlines(2)
    worksheet.set_landscape()
    worksheet.fit_to_pages(1, 0)
    worksheet.set_margins(left=0.35, right=0.35, top=0.5, bottom=0.5)
    return worksheet


def _write_period_grids(workbook, worksheet, df):
    """Readable balance/cash-flow sections with their own source date headers."""
    tables = df.attrs["source_tables"]
    last_col = max(len(table["period_labels"]) for table in tables)
    base = {"font_size": 11, "valign": "top", "text_wrap": True}
    title = workbook.add_format({**base, "bold": True, "font_size": 14, "align": "center_across", "text_wrap": False})
    company = workbook.add_format({**base, "bold": True, "font_size": 12, "align": "center_across", "text_wrap": False})
    unit = workbook.add_format({**base, "italic": True, "align": "center_across", "text_wrap": False})
    header = workbook.add_format({**base, "bold": True, "align": "right", "bottom": 1})
    section = workbook.add_format({**base, "bold": True, "top": 1, "bottom": 1})
    note = workbook.add_format({**base, "font_size": 9, "italic": True})
    label_format = workbook.add_format(base)
    total_label = workbook.add_format({**base, "bold": True, "top": 1})
    formats = {}
    _write_spanned_literal(worksheet, TOP_BLANK_ROWS, 0, TOP_BLANK_ROWS, last_col, df.attrs.get("company_name", ""), company)
    _write_spanned_literal(worksheet, TOP_BLANK_ROWS + 1, 0, TOP_BLANK_ROWS + 1, last_col, df.attrs.get("statement_title", ""), title)
    worksheet.set_row(TOP_BLANK_ROWS, 22)
    worksheet.set_row(TOP_BLANK_ROWS + 1, 28)
    worksheet.set_column(LEFT_BLANK_COLUMNS, LEFT_BLANK_COLUMNS, 88)
    worksheet.set_column(LEFT_BLANK_COLUMNS + 1, LEFT_BLANK_COLUMNS + last_col, 23)
    out = TOP_BLANK_ROWS + 3
    for table in tables:
        for caption in table.get("source_context", []):
            _write_spanned_literal(worksheet, out, 0, out, last_col, caption, unit)
            worksheet.set_row(out, 19)
            out += 1
        for c, period in enumerate(table["period_labels"], 1):
            _write_literal(worksheet, out, c, period, header)
        worksheet.set_row(out, 34)
        out += 1
        if any(table.get("period_notes", [])):
            for c, text in enumerate(table["period_notes"], 1):
                _write_literal(worksheet, out, c, text, header)
            worksheet.set_row(out, 19)
            out += 1
        for row, kind in zip(table["rows"], table["row_kinds"]):
            label = row[0]
            if kind != "data":
                _write_spanned_literal(worksheet, out, 0, out, last_col, label, section if kind == "section" else note)
                worksheet.set_row(out, max(22, 15 * math.ceil(len(label) / 80)))
            else:
                total = (_is_total_row(label)[0] or label.lower().startswith("net change in cash")
                         or bool(re.search(r"\bcash\b.*\bend of (?:period|year)$", label, re.I)))
                _write_literal(worksheet, out, 0, label, total_label if total else label_format)
                for c, raw in enumerate(row[1:], 1):
                    token = parse_numeric_token(raw)
                    key = (token.precision or 0, token.currency, total, token.is_percent, token.is_ratio)
                    if key not in formats:
                        positive = '#,##0' + ('.' + '0' * key[0] if key[0] else '')
                        if token.currency:
                            positive = '"' + token.currency + '"' + positive
                        if token.is_percent:
                            positive += '%'
                        if token.is_ratio:
                            positive += '"x"'
                        formats[key] = workbook.add_format({**base, "align": "right", "bold": total,
                                                           "top": 1 if total else 0,
                                                           "num_format": f"{positive};({positive});{positive}"})
                    if token.status == "NUMERIC":
                        worksheet.write_number(out, LEFT_BLANK_COLUMNS + c, token.value, formats[key])
                    else:
                        # Keep source missing amounts distinct from an explicit zero.
                        _write_literal(worksheet, out, c, re.sub(r"^[$€£¥]\s*", "", raw), formats[key])
                worksheet.set_row(out, max(19, 15 * math.ceil(len(label) / 80)))
            out += 1
        if table.get("source_note"):
            _write_spanned_literal(worksheet, out, 0, out, last_col, table["source_note"], note)
            worksheet.set_row(out, max(22, 15 * math.ceil(len(table["source_note"]) / 80)))
            out += 1
        out += 2
    worksheet.hide_gridlines(2)
    worksheet.set_landscape()
    worksheet.fit_to_pages(1, 0)
    worksheet.set_margins(left=0.35, right=0.35, top=0.5, bottom=0.5)
    return worksheet


def _write_equity_grids(workbook, worksheet, df):
    """Write stable source components and separate source-defined rollforwards."""
    tables = df.attrs["source_tables"]
    last_col = max(len(t["component_labels"]) for t in tables)
    base = {"font_size": 11, "valign": "top", "text_wrap": True}
    normal = workbook.add_format(base)
    bold = workbook.add_format({**base, "bold": True, "align": "center_across", "text_wrap": False})
    total_label = workbook.add_format({**base, "bold": True, "top": 1})
    title = workbook.add_format({**base, "bold": True, "font_size": 14, "align": "center_across", "text_wrap": False})
    header = workbook.add_format({**base, "bold": True, "align": "center", "bottom": 1})
    parent_header = workbook.add_format({**base, "bold": True, "align": "center_across", "text_wrap": False, "bottom": 1})
    caption_format = workbook.add_format({**base, "bold": True, "top": 1, "bottom": 1})
    formats = {}
    _write_spanned_literal(worksheet, TOP_BLANK_ROWS, 0, TOP_BLANK_ROWS, last_col, df.attrs.get("company_name", ""), bold)
    _write_spanned_literal(worksheet, TOP_BLANK_ROWS + 1, 0, TOP_BLANK_ROWS + 1, last_col, df.attrs.get("statement_title", ""), title)
    worksheet.set_row(TOP_BLANK_ROWS, 22)
    worksheet.set_row(TOP_BLANK_ROWS + 1, 28)
    worksheet.set_column(LEFT_BLANK_COLUMNS, LEFT_BLANK_COLUMNS, 68)
    worksheet.set_column(LEFT_BLANK_COLUMNS + 1, LEFT_BLANK_COLUMNS + last_col, 21)
    out = TOP_BLANK_ROWS + 3
    for table in tables:
        for caption in table.get("source_context", []):
            _write_spanned_literal(worksheet, out, 0, out, last_col, caption, normal)
            worksheet.set_row(out, max(20, 15 * math.ceil(len(caption) / 65)))
            out += 1
        data_start = table["row_kinds"].index("data")
        sections = table.get("period_sections") or [dict(start=data_start, end=len(table["rows"]), caption="")]
        for section in sections:
            if section["caption"]:
                _write_spanned_literal(worksheet, out, 0, out, last_col, section["caption"], caption_format)
                worksheet.set_row(out, max(24, 15 * math.ceil(len(section["caption"]) / 65)))
                out += 1
            for r, (row, kind) in enumerate(zip(table["rows"][:data_start], table["row_kinds"][:data_start])):
                if kind not in {"header", "parent_header"}:
                    continue
                covered = set()
                for sr, c, rs, cs in table["spans"]:
                    if sr == r:
                        _write_spanned_literal(worksheet, out, c, out+rs-1, c+cs-1, row[c], parent_header if rs == 1 else header)
                        covered.update(range(c, c+cs))
                for c, value in enumerate(row):
                    if c not in covered:
                        _write_literal(worksheet, out, c, value, header)
                worksheet.set_row(out, 46 if kind == "header" else 20)
                out += 1
            for r in range(section["start"], section["end"]):
                row, kind = table["rows"][r], table["row_kinds"][r]
                if kind == "section":
                    _write_spanned_literal(worksheet, out, 0, out, last_col, row[0], bold)
                    worksheet.set_row(out, max(23, 15 * math.ceil(len(row[0]) / (65+20*last_col))))
                else:
                    emphasized = row[0].lower().startswith(("total ", "balance at", "balance as of"))
                    _write_literal(worksheet, out, 0, row[0], total_label if emphasized else normal)
                    for c, raw in enumerate(row[1:], 1):
                        token = parse_numeric_token(raw)
                        key = (token.precision or 0, token.currency, emphasized, token.is_percent)
                        if key not in formats:
                            positive = '#,##0' + ('.' + '0'*key[0] if key[0] else '')
                            if token.currency:
                                positive = '"' + token.currency + '"' + positive
                            if token.is_percent:
                                positive += '%'
                            formats[key] = workbook.add_format({**base, "align": "right", "bold": emphasized,
                                                               "top": 1 if emphasized else 0,
                                                               "num_format": f"{positive};({positive});{positive}"})
                        if token.status == "NUMERIC":
                            worksheet.write_number(out, LEFT_BLANK_COLUMNS + c, token.value, formats[key])
                        else:
                            _write_literal(worksheet, out, c, re.sub(r"^[$€£¥]\s*", "", raw), formats[key])
                    worksheet.set_row(out, max(21, 15 * math.ceil(len(row[0]) / 60)))
                out += 1
            out += 2
    worksheet.hide_gridlines(2)
    worksheet.set_landscape()
    worksheet.fit_to_pages(1, 0)
    worksheet.set_margins(left=0.35, right=0.35, top=0.5, bottom=0.5)
    return worksheet


def _write_source_grids(workbook, worksheet, df):
    """Render each source schema separately, with literal source headings/cells.

    The analytical DataFrame is deliberately not the display-label authority.
    Typed numbers retain their source precision, currency, percent and sign style.
    """
    normal = workbook.add_format({"font_size": 11, "text_wrap": True, "valign": "top"})
    heading = workbook.add_format({"font_size": 11, "bold": True, "align": "center_across", "valign": "top"})
    span_text = workbook.add_format({"font_size": 11, "align": "center_across", "valign": "top"})
    formats = {}
    _write_literal(worksheet, TOP_BLANK_ROWS, 0, df.attrs.get("company_name", ""), heading)
    title = str(df.attrs.get("statement_title", ""))
    _write_literal(worksheet, TOP_BLANK_ROWS + 1, 0, title, heading)
    tables = [schedule_display_grid(equity_display_grid(table)) for table in df.attrs["source_tables"]]
    width_count = max(len(row) for table in tables for row in table["rows"])
    widths = [2] * width_count
    for table in tables:
        for row in table["rows"]:
            for c, raw in enumerate(row):
                if not raw:
                    continue
                token = parse_numeric_token(raw)
                width = 16 if token.status == "NUMERIC" else min(50 if c == 0 else 28, max(5, len(raw) + 2))
                widths[c] = max(widths[c], width)
    widths[0] = max(widths[0], 50)
    missing_format = workbook.add_format({"font_size": 11, "align": "right", "valign": "top"})
    for c, width in enumerate(widths):
        worksheet.set_column(LEFT_BLANK_COLUMNS + c, LEFT_BLANK_COLUMNS + c, width)
    # Source titles are not shortened to satisfy Excel tab/column limits.
    last_col = max(1, width_count - 1)
    if title:
        _write_spanned_literal(worksheet, TOP_BLANK_ROWS + 1, 0, TOP_BLANK_ROWS + 1, last_col, title, heading)
    worksheet.set_row(TOP_BLANK_ROWS + 1, 30)
    output_row = TOP_BLANK_ROWS + 4
    for table in tables:
        block_title = table.get("source_title", "")
        source_rows = table["rows"]
        kept = {r for r, row in enumerate(source_rows) if any(row)}
        for r, c, rs, cs in table.get("spans", []):
            if source_rows[r][c]:
                kept.update(range(r, min(r + rs, len(source_rows))))
        row_map = {r: i for i, r in enumerate(sorted(kept))}
        rows = [source_rows[r] for r in sorted(kept)]
        if block_title and block_title != title and not any(block_title in row for row in rows[:10]):
            _write_spanned_literal(worksheet, output_row, 0, output_row, last_col, block_title, heading)
            worksheet.set_row(output_row, 30)
            output_row += 1
        for caption in table.get("source_context", []):
            if caption and not any(caption in row for row in rows):
                _write_spanned_literal(worksheet, output_row, 0, output_row, last_col, caption, normal)
                worksheet.set_row(output_row, 20)
                output_row += 1
        spans = {(row_map[r], c): (sum(rr in row_map for rr in range(r, r + rs)), cs)
                 for r, c, rs, cs in table.get("spans", [])
                 if r in row_map and r + rs <= len(source_rows) and c + cs <= len(source_rows[r])}
        spans = {key: span for key, span in spans.items() if span != (1, 1)}
        covered = {(rr, cc) for (r, c), (rs, cs) in spans.items()
                   for rr in range(r, r + rs) for cc in range(c, c + cs) if (rr, cc) != (r, c)}
        for r, row in enumerate(rows):
            height = 15
            for c, raw in enumerate(row):
                if (r, c) in covered:
                    continue
                if raw.strip() == "%" and c and parse_numeric_token(row[c - 1]).status == "NUMERIC":
                    continue
                if c + 1 < len(row) and row[c + 1].strip() == "%" and parse_numeric_token(raw).status == "NUMERIC":
                    raw += "%"
                if (r, c) in spans:
                    rs, cs = spans[r, c]
                    _write_spanned_literal(worksheet, output_row + r, c, output_row + r + rs - 1,
                                   c + cs - 1, "", span_text if rs == 1 else normal)
                    available = sum(widths[c:c + cs]) if rs == 1 else widths[c]
                else:
                    available = widths[c]
                token = parse_numeric_token(raw)
                # Source identifiers, replacement glyphs and unsupported currencies
                # remain literal. Do not apply the OCR S -> dollar heuristic here.
                numeric = c > 0 and token.status == "NUMERIC" and math.isfinite(token.value) and SINGLE_NUMBER.fullmatch(raw)
                if numeric:
                    precision = token.precision or 0
                    code = "#,##0" + ("." + "0" * precision if precision else "")
                    if token.currency:
                        code = '"' + token.currency + '"' + code
                    if token.is_percent:
                        code += "%"
                    if token.is_ratio:
                        code += '"x"'
                    negative = f"({code})" if "(" in raw else f"-{code}"
                    code = f"{code};{negative};{code}"
                    if code not in formats:
                            formats[code] = workbook.add_format({"font_size": 11, "num_format": code, "align": "right", "valign": "top"})
                    worksheet.write_number(output_row + r, LEFT_BLANK_COLUMNS + c, token.value, formats[code])
                else:
                    _write_literal(worksheet, output_row + r, c, raw,
                                   span_text if (r, c) in spans and spans[r, c][0] == 1 else
                                   missing_format if c and token.status in {"DASH", "NA", "NM"} else normal)
                height = max(height, 15 * sum(max(1, math.ceil(len(line) / max(1, available - 2)))
                                            for line in str(raw).split("\n")))
            worksheet.set_row(output_row + r, min(409, height))
        output_row += len(rows) + 2
    worksheet.hide_gridlines(2)
    worksheet.set_landscape()
    worksheet.fit_to_pages(1, 0)
    return worksheet


def _is_pdf_result(result: ExtractionResult) -> bool:
    source = str(result.metadata.get("source_path") or result.metadata.get("source_file") or "").strip()
    return Path(source).suffix.lower() == ".pdf"


def _write_raw_method_sheet(
    writer,
    flavor: str,
    sheet_name: str,
    display_name: str,
    raw_cells: list[dict],
):
    workbook = writer.book
    worksheet = workbook.add_worksheet(sheet_name)
    writer.sheets[sheet_name] = worksheet

    title_format = workbook.add_format({
        "bold": True,
        "font_size": 14,
        "font_color": "#000000",
        "align": "left",
        "valign": "vcenter",
    })
    note_format = workbook.add_format({
        "italic": True,
        "font_color": "#000000",
        "align": "left",
        "valign": "vcenter",
    })
    table_format = workbook.add_format({
        "bold": True,
        "font_color": "#000000",
        "align": "left",
        "valign": "vcenter",
    })
    raw_format = workbook.add_format({
        "font_color": "#000000",
        "align": "left",
        "valign": "top",
        "text_wrap": True,
    })

    worksheet.write_string(TOP_BLANK_ROWS, LEFT_BLANK_COLUMNS, f"{display_name} output", title_format)
    worksheet.write_string(
        TOP_BLANK_ROWS + 1,
        LEFT_BLANK_COLUMNS,
        ("Experimental extracted cells; dollar amounts and space-separated numbers use separate columns."
         if flavor == "pdfplumber_experimental"
         else "Unmodified extracted cells. Edit or clean this sheet as needed."),
        note_format,
    )
    worksheet.set_row(TOP_BLANK_ROWS, 22)

    method_cells = [row for row in raw_cells if str(row.get("flavor") or "").lower() == flavor]
    tables: dict[tuple[int, str], list[dict]] = {}
    for cell in method_cells:
        page = int(cell.get("source_page") or 0)
        table_id = str(cell.get("table_id") or f"Page_{page}")
        tables.setdefault((page, table_id), []).append(cell)

    if not tables:
        worksheet.write_string(TOP_BLANK_ROWS + 3, LEFT_BLANK_COLUMNS, "No tables were extracted with this method.", raw_format)
        worksheet.set_column(LEFT_BLANK_COLUMNS, LEFT_BLANK_COLUMNS, 62)
        return worksheet

    column_widths: dict[int, int] = {0: 24, 1: 12, 2: 16, 3: 16, 4: 16, 5: 16}
    output_row = TOP_BLANK_ROWS + 3
    for (page, table_id), cells in sorted(tables.items()):
        sample = cells[0]
        metadata = [
            f"Table: {table_id}",
            f"Page: {page}",
            f"Selected: {'Yes' if sample.get('selected') else 'No'}",
        ]
        for key, label in (
            ("table_score", "Score"),
            ("accuracy", "Accuracy"),
            ("whitespace", "Whitespace"),
        ):
            value = sample.get(key)
            if value is not None:
                metadata.append(f"{label}: {value}")
        for column_index, value in enumerate(metadata):
            worksheet.write_string(output_row, LEFT_BLANK_COLUMNS + column_index, value, table_format)
            column_widths[column_index] = max(column_widths.get(column_index, 10), len(value) + 2)

        grid_start = output_row + 1
        max_row_index = max(int(cell.get("row_index") or 0) for cell in cells)
        row_heights: dict[int, int] = {}
        for cell in cells:
            row_index = int(cell.get("row_index") or 0)
            column_index = int(cell.get("column_index") or 0)
            raw = "" if cell.get("raw_text") is None else str(cell.get("raw_text"))
            if raw:
                worksheet.write_string(grid_start + row_index, LEFT_BLANK_COLUMNS + column_index, raw, raw_format)
                longest_line = max((len(line) for line in raw.splitlines()), default=0)
                column_widths[column_index] = max(column_widths.get(column_index, 10), longest_line + 2)
                if "\n" in raw or len(raw) > 80:
                    visible_lines = min(4, max(2, raw.count("\n") + 1))
                    row_heights[row_index] = max(row_heights.get(row_index, 15), visible_lines * 15)
        for row_index, height in row_heights.items():
            worksheet.set_row(grid_start + row_index, height)
        output_row = grid_start + max_row_index + 3

    for column_index, width in column_widths.items():
        worksheet.set_column(LEFT_BLANK_COLUMNS + column_index, LEFT_BLANK_COLUMNS + column_index, min(62, max(10, width)))
    return worksheet


def write_extraction_workbook(
    result: ExtractionResult,
    output_path: str | Path,
    *,
    allow_nonlocal_paths: bool = False,
) -> Path:
    output = ensure_unique_filename(
        normalize_path(output_path, allow_nonlocal_paths=allow_nonlocal_paths)
    )
    if not result.statements:
        raise ValueError("No financial statements were extracted; no workbook was created.")
    pdf_result = _is_pdf_result(result)
    income = result.statements.get("IncomeStatement")
    if pdf_result and income is not None:
        periods = income.attrs.get("period_labels", [])
        if not periods or any(period not in income.columns for period in periods):
            raise ValueError("PDF income statement periods could not be parsed; no workbook was created. "
                             "Review the source period headings before exporting.")
    output.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(
        output,
        engine="xlsxwriter",
        engine_kwargs={
            "options": {
                "strings_to_formulas": False,
                "strings_to_urls": False,
            }
        },
    ) as writer:
        first_worksheet = None
        statement_order = ["IncomeStatement", "CashFlowStatement", "BalanceSheet", "PartnersCapital", "ScheduleOfInvestments"]
        ordered_types = [statement_type for statement_type in statement_order if statement_type in result.statements]
        ordered_types.extend(statement_type for statement_type in result.statements if statement_type not in ordered_types)
        for statement_type in ordered_types:
            dataframe = result.statements[statement_type]
            # PDF table grids can omit duration/date headings and split currency
            # symbols into columns. Use the parsed income statement presentation;
            # retain source tables and raw method sheets for inspection.
            worksheet = _write_statement_sheet(
                writer, statement_type, dataframe,
                use_source_grids=not (pdf_result and statement_type == "IncomeStatement"),
            )
            if statement_type == "BalanceSheet":
                completeness = balance_completeness_status(result.financial_audit_rows + result.extraction_audit_rows)
                if completeness in {"FAIL", "NOT_TESTED"}:
                    message = ("INCOMPLETE BALANCE SHEET" if completeness == "FAIL"
                               else "BALANCE SHEET COMPLETENESS UNVERIFIED")
                    alert = writer.book.add_format({"bold": True, "text_wrap": True, "valign": "vcenter",
                                                    "font_color": "#9C0006", "bg_color": "#F8DFDF"})
                    # The title location is shared by every writer path. Retain
                    # the source title and all existing unit/context/data rows.
                    title = str(dataframe.attrs.get("statement_title") or "Balance sheet")
                    _write_literal(worksheet, TOP_BLANK_ROWS + 1, 0, title + "\n" + message + " — see Review", alert)
                    worksheet.set_row(TOP_BLANK_ROWS + 1, 66)
                    worksheet.set_tab_color("#C00000")
            if first_worksheet is None:
                first_worksheet = worksheet

        if _is_pdf_result(result):
            for flavor, sheet_name, display_name in RAW_METHOD_SHEETS:
                _write_raw_method_sheet(
                    writer,
                    flavor,
                    sheet_name,
                    display_name,
                    result.raw_table_cells,
                )

            _write_raw_method_sheet(
                writer,
                "pdfplumber_experimental",
                "Experiential",
                "PDFPlumber Experimental tables",
                result.experimental_raw_table_cells,
            )

        review_rows = list(result.financial_audit_rows)
        review_rows.extend(row for row in result.extraction_audit_rows + result.experimental_audit_rows
                           if row.get("Status") not in {"PASS", "INFO"}
                           or row.get("Check") in {"Selected statement page coverage", "Source text amount-row coverage", BALANCE_COMPLETENESS})
        if not review_rows:
            review_rows = [dict(Status="NOT_TESTED", Check="Workbook validation", Scope="Document",
                                Detail="No validation results are available. Workbook creation is not proof of accuracy or completeness.")]
        if review_rows:
            review_name = "Review"
            review = writer.book.add_worksheet(review_name)
            writer.sheets[review_name] = review
            _write_review_checks(writer.book, review, review_rows)

        if first_worksheet is None:
            raise ValueError("No financial statements were extracted; no workbook was created.")
        for worksheet in writer.book.worksheets():
            worksheet.set_column(0, LEFT_BLANK_COLUMNS - 1, 1)
        first_worksheet.activate()

    return output


def _write_review_checks(workbook, sheet, rows):
    """Expose failed, untested and successful checks without touching statements."""
    from collections import Counter
    rows = list({tuple(str(row.get(k, "")) for k in ("Status", "Check", "Scope", "Detail")): row for row in rows}.values())
    severity = {"ERROR": 0, "FAIL": 1, "WARN": 2, "NOT_TESTED": 3, "PASS": 4, "INFO": 5}
    rows.sort(key=lambda row: severity.get(row.get("Status"), 3))
    counts = Counter(row.get("Status", "UNKNOWN") for row in rows)
    base = {"text_wrap": True, "valign": "top", "font_size": 11}
    normal = workbook.add_format(base)
    heading = workbook.add_format({**base, "bold": True, "font_size": 16, "align": "center_across", "text_wrap": False})
    summary = workbook.add_format({**base, "align": "center_across", "text_wrap": False})
    header = workbook.add_format({**base, "bold": True, "bg_color": "#E9EEF2", "bottom": 1})
    formats = {status: workbook.add_format({**base, "bold": True, "bg_color": color})
               for status, color in {"PASS": "#E4EFE7", "FAIL": "#F8DFDF", "ERROR": "#F8DFDF",
                                     "WARN": "#FFF0CC", "NOT_TESTED": "#ECEFF2"}.items()}
    sheet.set_column(LEFT_BLANK_COLUMNS, LEFT_BLANK_COLUMNS, 15)
    sheet.set_column(LEFT_BLANK_COLUMNS + 1, LEFT_BLANK_COLUMNS + 1, 43)
    sheet.set_column(LEFT_BLANK_COLUMNS + 2, LEFT_BLANK_COLUMNS + 2, 52)
    sheet.set_column(LEFT_BLANK_COLUMNS + 3, LEFT_BLANK_COLUMNS + 3, 94)
    completeness = balance_completeness_status(rows)
    title = {"FAIL": "Workbook checks — INCOMPLETE BALANCE SHEET",
             "NOT_TESTED": "Workbook checks — balance-sheet completeness unverified"}.get(completeness, "Workbook checks")
    _write_spanned_literal(sheet, TOP_BLANK_ROWS, 0, TOP_BLANK_ROWS, 3, title, heading)
    _write_spanned_literal(sheet, TOP_BLANK_ROWS + 1, 0, TOP_BLANK_ROWS + 1, 3,
                   f"{counts['FAIL'] + counts['ERROR']} failed  |  {counts['WARN']} warnings  |  "
                   f"{sum(v for k, v in counts.items() if k not in {'PASS', 'INFO', 'WARN', 'FAIL', 'ERROR'})} not tested/unknown  |  {counts['PASS']} passed", summary)
    _write_spanned_literal(sheet, TOP_BLANK_ROWS + 2, 0, TOP_BLANK_ROWS + 2, 3, "Pass applies only to the named check. Matching totals do not prove that every source row was extracted. Not tested means no conclusion was reached.", summary)
    sheet.set_row(TOP_BLANK_ROWS, 27)
    sheet.set_row(TOP_BLANK_ROWS + 1, 23)
    sheet.set_row(TOP_BLANK_ROWS + 2, 30)
    sheet.write_row(TOP_BLANK_ROWS + 4, LEFT_BLANK_COLUMNS, ["Status", "Check", "Scope", "Evidence / review needed"], header)
    for r, row in enumerate(rows, TOP_BLANK_ROWS + 5):
        for c, key in enumerate(("Status", "Check", "Scope", "Detail")):
            _write_literal(sheet, r, c, str(row.get(key, "")), formats.get(row.get("Status"), normal) if c == 0 else normal)
        sheet.set_row(r, max(34, 15 * max(math.ceil(len(str(row.get('Scope', ''))) / 48), math.ceil(len(str(row.get('Detail', ''))) / 90))))
    sheet.autofilter(TOP_BLANK_ROWS + 4, LEFT_BLANK_COLUMNS, TOP_BLANK_ROWS + 4 + len(rows), LEFT_BLANK_COLUMNS + 3)
    sheet.hide_gridlines(2)
