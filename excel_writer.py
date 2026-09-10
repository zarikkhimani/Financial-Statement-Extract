from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pandas as pd

from models import ExtractionResult
from path_policy import normalize_path


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
    ("lattice", "Raw Camelot Lattice", "Camelot lattice"),
    ("stream", "Raw Camelot Stream", "Camelot stream"),
    ("pdfplumber", "Raw PDFPlumber", "PDFPlumber tables"),
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
    return worksheet.write_string(row, column, text, cell_format)


def _merge_literal(
    worksheet,
    first_row: int,
    first_column: int,
    last_row: int,
    last_column: int,
    value: object,
    cell_format=None,
):
    text = "" if value is None else str(value)
    result = worksheet.merge_range(
        first_row,
        first_column,
        last_row,
        last_column,
        "",
        cell_format,
    )
    if text:
        return worksheet.write_string(first_row, first_column, text, cell_format)
    return result


def _write_statement_sheet(writer, statement_type: str, df: pd.DataFrame):
    workbook = writer.book
    sheet_name = STATEMENT_SHEET_NAMES.get(statement_type, statement_type[:31])
    worksheet = workbook.add_worksheet(sheet_name)
    writer.sheets[sheet_name] = worksheet

    periods = list(df.attrs.get("period_labels", []))
    last_col = max(1, len(periods))
    company_name = str(df.attrs.get("company_name") or "").strip()
    statement_title = str(df.attrs.get("statement_title") or STATEMENT_TITLES.get(statement_type, statement_type))
    unit_note = str(df.attrs.get("raw_unit_note") or "").strip()

    company_format = workbook.add_format({"bold": True, "font_size": 12, "font_color": "#000000", "align": "left", "valign": "vcenter"})
    title_format = workbook.add_format({"bold": True, "font_size": 14, "font_color": "#000000", "align": "left", "valign": "vcenter"})
    unit_format = workbook.add_format({"italic": True, "font_color": "#000000", "align": "left"})
    label_header_format = workbook.add_format({"bold": True, "font_color": "#000000", "align": "left", "bottom": 1, "bottom_color": "#000000"})
    period_header_format = workbook.add_format({"bold": True, "font_color": "#000000", "align": "right", "bottom": 1, "bottom_color": "#000000"})
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

    _merge_literal(worksheet, 0, 0, 0, last_col, company_name, company_format)
    _merge_literal(worksheet, 1, 0, 1, last_col, statement_title, title_format)
    _merge_literal(worksheet, 2, 0, 2, last_col, unit_note, unit_format)
    worksheet.write_blank(4, 0, None, label_header_format)
    for column_index, period in enumerate(periods, start=1):
        _write_literal(worksheet, 4, column_index, period, period_header_format)

    current_section = ""
    output_row = 5
    for _, item in df.iterrows():
        row_type = str(item.get("RowType", "Data"))
        label = str(item.get("RawItem") or "").strip()
        if not label:
            continue

        if row_type == "Section":
            current_section = label
            _merge_literal(worksheet, output_row, 0, output_row, last_col, label, section_format)
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
                worksheet.write_blank(output_row, column_index, None, row_number_format)
            else:
                worksheet.write_number(output_row, column_index, float(value), row_number_format)
        worksheet.set_row(output_row, 54 if len(label) > 130 else 38 if len(label) > 80 else 30 if len(label) > 55 else 18)
        output_row += 1

    worksheet.set_column(0, 0, 62)
    if periods:
        period_width = max(15, min(22, max(len(str(period)) for period in periods) + 2))
        worksheet.set_column(1, last_col, period_width)
    worksheet.set_row(0, 22)
    worksheet.set_row(1, 26)
    worksheet.set_row(2, 18)
    worksheet.set_row(3, 8)
    worksheet.set_row(4, 21)
    worksheet.hide_gridlines(2)
    worksheet.set_landscape()
    worksheet.fit_to_pages(1, 0)
    worksheet.set_margins(left=0.35, right=0.35, top=0.5, bottom=0.5)
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

    worksheet.write_string(0, 0, f"{display_name} raw output", title_format)
    worksheet.write_string(
        1,
        0,
        "Unmodified extracted cells. Edit or clean this sheet as needed.",
        note_format,
    )
    worksheet.set_row(0, 22)

    method_cells = [row for row in raw_cells if str(row.get("flavor") or "").lower() == flavor]
    tables: dict[tuple[int, str], list[dict]] = {}
    for cell in method_cells:
        page = int(cell.get("source_page") or 0)
        table_id = str(cell.get("table_id") or f"Page_{page}")
        tables.setdefault((page, table_id), []).append(cell)

    if not tables:
        worksheet.write_string(3, 0, "No tables were extracted with this method.", raw_format)
        worksheet.set_column(0, 0, 62)
        return worksheet

    column_widths: dict[int, int] = {0: 24, 1: 12, 2: 16, 3: 16, 4: 16, 5: 16}
    output_row = 3
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
            worksheet.write_string(output_row, column_index, value, table_format)
            column_widths[column_index] = max(column_widths.get(column_index, 10), len(value) + 2)

        grid_start = output_row + 1
        max_row_index = max(int(cell.get("row_index") or 0) for cell in cells)
        row_heights: dict[int, int] = {}
        for cell in cells:
            row_index = int(cell.get("row_index") or 0)
            column_index = int(cell.get("column_index") or 0)
            raw = "" if cell.get("raw_text") is None else str(cell.get("raw_text"))
            if raw:
                worksheet.write_string(grid_start + row_index, column_index, raw, raw_format)
                longest_line = max((len(line) for line in raw.splitlines()), default=0)
                column_widths[column_index] = max(column_widths.get(column_index, 10), longest_line + 2)
                if "\n" in raw or len(raw) > 80:
                    visible_lines = min(4, max(2, raw.count("\n") + 1))
                    row_heights[row_index] = max(row_heights.get(row_index, 15), visible_lines * 15)
        for row_index, height in row_heights.items():
            worksheet.set_row(grid_start + row_index, height)
        output_row = grid_start + max_row_index + 3

    for column_index, width in column_widths.items():
        worksheet.set_column(column_index, column_index, min(62, max(10, width)))
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
            worksheet = _write_statement_sheet(writer, statement_type, dataframe)
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

        if first_worksheet is None:
            raise ValueError("No financial statements were extracted; no workbook was created.")
        first_worksheet.activate()

    return output
