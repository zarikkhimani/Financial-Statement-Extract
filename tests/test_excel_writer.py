from openpyxl import load_workbook
import pandas as pd
import pytest

from excel_writer import write_extraction_workbook
from models import ExtractionResult
from pipeline import parse_text_to_result


@pytest.mark.parametrize("source_type", ["pdf", "html"])
def test_pdf_income_uses_full_parsed_periods_without_changing_html_grids(tmp_path, source_type):
    result = parse_text_to_result(
        """Example Fund
Consolidated Statements of Operations (unaudited)
(In thousands, except share and per share data)
Three months ended June 30, Nine months ended June 30,
2026 2025 2026 2025
Investment income
Interest income 100 90 300 270
Fee income 20 10 60 30
Total investment income 120 100 360 300
Excise tax benefit — — — (5)
Net income 12.50 10.25 37.50 30.75
"""
    )
    result.metadata["source_file"] = f"example.{source_type}"
    frame = result.statements["IncomeStatement"]
    # The table engine captured years and currency columns, but missed the
    # duration/date headings. Its replacement glyph must stay in raw output.
    grid = {
        "rows": [["", "", "2026", "", "2025", "", "2026", "", "2025"],
                 ["Interest income", "$", "100", "$", "90", "$", "300", "$", "270"],
                 ["Excise tax benefit", "", "�", "", "�", "", "�", "", "(5)"]],
        "flavor": source_type, "statement_type": "IncomeStatement", "spans": [],
    }
    frame.attrs["source_tables"] = [grid]
    result.raw_table_cells = [
        dict(source_page=1, table_id="P0001_STREAM_01", flavor="stream", selected=True,
             row_index=r, column_index=c, raw_text=value)
        for r, row in enumerate(grid["rows"]) for c, value in enumerate(row)
    ] if source_type == "pdf" else []
    result.extraction_audit_rows.append(dict(
        Check="Source table coverage", Scope="Page 1", Status="WARN", Detail="Review source coverage."
    ))
    output = write_extraction_workbook(result, tmp_path / f"{source_type}.xlsx")
    book = load_workbook(output)
    try:
        if source_type == "html":
            sheet = book["Statement 1"]
            assert sheet["E8"].value == 2026
            assert sheet["D9"].value == "$"
            assert sheet["E10"].value == "�"
            return
        sheet = book["Income Statement"]
        assert sheet.max_column == 7
        assert sheet["C5"].value == "Consolidated Statements of Operations (unaudited)"
        assert sheet["C6"].value == "(In thousands, except share and per share data)"
        assert [sheet.cell(8, c).value for c in range(4, 8)] == [
            "Three months ended June 30, 2026", "Three months ended June 30, 2025",
            "Nine months ended June 30, 2026", "Nine months ended June 30, 2025",
        ]
        assert sheet["D8"].alignment.wrap_text
        assert sheet.row_dimensions[8].height >= 30
        rows = {row[0].value: row for row in sheet.iter_rows(min_row=9, min_col=3)}
        assert [c.value for c in rows["Total investment income"][1:]] == [120, 100, 360, 300]
        assert rows["Total investment income"][1].font.bold
        assert rows["Total investment income"][1].border.top.style == "thin"
        assert [c.value for c in rows["Excise tax benefit"][1:]] == [None, None, None, -5]
        assert [c.value for c in rows["Net income"][1:]] == [12.5, 10.25, 37.5, 30.75]
        assert rows["Net income"][1].number_format == "#,##0.00;(#,##0.00);-"
        assert not any(c.value == "�" for row in sheet.iter_rows(min_col=3) for c in row)
        assert book["Stream"]["E10"].value == "�"
        assert any(row[3].value == "Review source coverage." and row[0].value == "WARN" for row in book["Review"].iter_rows(min_col=3))
        assert frame.attrs["source_tables"] == [grid]
    finally:
        book.close()


def test_pdf_income_without_parsed_periods_fails_before_creating_workbook(tmp_path):
    result = parse_text_to_result("Income Statements\n2026 2025\nNet income 10 9")
    result.metadata["source_file"] = "example.pdf"
    result.statements["IncomeStatement"].attrs["period_labels"] = []
    output = tmp_path / "missing-periods.xlsx"
    with pytest.raises(ValueError, match="income statement periods could not be parsed"):
        write_extraction_workbook(result, output)
    assert not output.exists()


def test_pasted_text_result_writes_workbook(tmp_path):
    result = parse_text_to_result(
        """Example Company
Income Statements
Years Ended December 31, 2026 2025
Revenue 300 250
Net income 30 20
"""
    )

    output = write_extraction_workbook(result, tmp_path / "result.xlsx")

    workbook = load_workbook(output)
    try:
        assert workbook.sheetnames == ["Income Statements", "Review"]
        sheet = workbook["Income Statements"]
        assert sheet["C4"].value == "Example Company"
        assert sheet["C5"].value == "Income Statements"
        assert sheet["C6"].value is None
        assert sheet["D8"].value == "2026"
        assert sheet["C9"].value == "Revenue"
        assert sheet.freeze_panes is None
        for row in sheet.iter_rows(min_col=3):
            for cell in row:
                assert cell.fill is None or cell.fill.fill_type is None
                if cell.font is not None and cell.font.color is not None and cell.font.color.type == "rgb":
                    assert cell.font.color.rgb in {"00000000", "FF000000"}
    finally:
        workbook.close()

def test_reported_decimal_precision_is_preserved(tmp_path):
    result = parse_text_to_result(
        """Example Company
Income Statements
Years Ended December 31, 2026 2025
Revenue 300.5 250.0
Net income 30.2 20.1
"""
    )

    output = write_extraction_workbook(result, tmp_path / "decimal_result.xlsx")

    workbook = load_workbook(output, read_only=True)
    try:
        sheet = workbook["Income Statements"]
        assert sheet["D9"].value == 300.5
        assert sheet["D9"].number_format == "#,##0.0;(#,##0.0);-"
    finally:
        workbook.close()

def test_period_columns_are_wide_enough_for_full_dates(tmp_path):
    result = parse_text_to_result(
        """Example Fund
Consolidated Statements of Assets and Liabilities
December 31, 2025 December 31, 2024
Assets
Cash and cash equivalents 1234567890 100000
Total Assets 1234567890 100000
"""
    )

    output = write_extraction_workbook(result, tmp_path / "dated_result.xlsx")

    workbook = load_workbook(output)
    try:
        sheet = workbook["Statement 1"]
        assert sheet["C5"].value == "Consolidated Statements of Assets and Liabilities"
        period_columns = next(
            dimension
            for dimension in sheet.column_dimensions.values()
            if dimension.min <= 4 and dimension.max >= 5
        )
        assert period_columns.width >= 19
    finally:
        workbook.close()


def test_long_interim_period_headers_wrap_and_have_sufficient_height(tmp_path):
    result = parse_text_to_result(
        """Example Bank
Consolidated Statements of Comprehensive Income (unaudited)
Three Months Ended June 30, Six Months Ended June 30,
(in millions) 2025 2024 2025 2024
Net income 15 14 30 27
"""
    )

    output = write_extraction_workbook(result, tmp_path / "interim_result.xlsx")
    workbook = load_workbook(output)
    try:
        sheet = workbook["Statement 1"]
        assert sheet["D8"].alignment.wrap_text is True
        assert sheet.row_dimensions[8].height >= 30
    finally:
        workbook.close()


def test_pdf_result_writes_raw_methods_and_experiment_as_editable_grids(tmp_path):
    result = parse_text_to_result(
        """Example Company
Income Statements
Years Ended December 31, 2026 2025
Revenue 300 250
Net income 30 20
"""
    )
    result.metadata["source_file"] = "example.pdf"
    result.raw_table_cells = [
        {
            "source_page": 2,
            "table_id": "P0002_LATTICE_01",
            "flavor": "lattice",
            "selected": True,
            "table_score": 95.0,
            "accuracy": 99.0,
            "whitespace": 1.0,
            "row_index": 0,
            "column_index": 0,
            "raw_text": "Revenue",
        },
        {
            "source_page": 2,
            "table_id": "P0002_LATTICE_01",
            "flavor": "lattice",
            "selected": True,
            "table_score": 95.0,
            "accuracy": 99.0,
            "whitespace": 1.0,
            "row_index": 0,
            "column_index": 1,
            "raw_text": "=1+1",
        },
        {
            "source_page": 2,
            "table_id": "P0002_STREAM_01",
            "flavor": "stream",
            "selected": False,
            "row_index": 0,
            "column_index": 0,
            "raw_text": "Net income",
        },
        {
            "source_page": 2,
            "table_id": "P0002_PDFPLUMBER_01",
            "flavor": "pdfplumber",
            "selected": False,
            "row_index": 0,
            "column_index": 0,
            "raw_text": "Cash",
        },
    ]

    output = write_extraction_workbook(result, tmp_path / "raw_methods.xlsx")
    workbook = load_workbook(output)
    try:
        assert workbook.sheetnames == [
            "Income Statements",
            "Lattice",
            "Stream",
            "PDFPlumber",
            "Experiential",
            "Review",
        ]
        for tab in workbook:
            assert all(cell.value is None for row in tab.iter_rows(min_row=1, max_row=3) for cell in row)
            assert all(cell.value is None and not cell.has_style
                       for row in tab.iter_rows(max_col=2) for cell in row)
            assert tab.freeze_panes is None
            assert not tab.merged_cells.ranges
        assert workbook["Income Statements"]["C4"].alignment.horizontal == "centerContinuous"
        assert workbook["Review"].auto_filter.ref.startswith("C8:")
        lattice = workbook["Lattice"]
        assert lattice["C7"].value == "Table: P0002_LATTICE_01"
        assert lattice["C8"].value == "Revenue"
        assert lattice["D8"].value == "=1+1"
        assert lattice["D8"].data_type == "s"
        assert workbook["Stream"]["C8"].value == "Net income"
        assert workbook["PDFPlumber"]["C8"].value == "Cash"
        for sheet_name in ["Lattice", "Stream", "PDFPlumber", "Experiential"]:
            sheet = workbook[sheet_name]
            assert sheet.freeze_panes is None
            for row in sheet.iter_rows(min_col=3):
                for cell in row:
                    assert cell.fill is None or cell.fill.fill_type is None
                    if cell.font is not None and cell.font.color is not None and cell.font.color.type == "rgb":
                        assert cell.font.color.rgb in {"00000000", "FF000000"}
    finally:
        workbook.close()


def test_document_text_is_always_written_as_literal_strings(tmp_path):
    first_period = "@SOURCE_PERIOD"
    second_period = "https://example.invalid/period"
    statement = pd.DataFrame(
        [
            {
                "RowType": "Section",
                "RawItem": "=SECTION()",
                first_period: None,
                second_period: None,
            },
            {
                "RowType": "Data",
                "RawItem": '=HYPERLINK("https://example.invalid", "open")',
                first_period: 125.5,
                second_period: 100,
            },
            {
                "RowType": "Data",
                "RawItem": "https://example.invalid/line-item",
                first_period: 1,
                second_period: 2,
            },
        ]
    )
    statement.attrs.update(
        {
            "company_name": "=1+1",
            "statement_title": "+SUM(1,1)",
            "raw_unit_note": "-1+1",
            "period_labels": [first_period, second_period],
        }
    )
    result = ExtractionResult(
        metadata={"source_file": "example.html"},
        raw_text_rows=[],
        raw_table_cells=[],
        normalized_table_cells=[],
        extraction_audit_rows=[],
        statements={"IncomeStatement": statement},
        parsed_cells=[],
        financial_audit_rows=[],
        unmapped_rows=[],
    )

    output = write_extraction_workbook(result, tmp_path / "literal_strings.xlsx")
    workbook = load_workbook(output, data_only=False)
    try:
        sheet = workbook["+SUM(1,1)"]
        expected_strings = {
            "C4": "=1+1",
            "C5": "+SUM(1,1)",
            "C6": "-1+1",
            "D8": first_period,
            "E8": second_period,
            "C9": "=SECTION()",
            "C10": '=HYPERLINK("https://example.invalid", "open")',
            "C11": "https://example.invalid/line-item",
        }
        for coordinate, expected in expected_strings.items():
            cell = sheet[coordinate]
            assert cell.value == expected
            assert cell.data_type == "s"
            assert cell.hyperlink is None
        assert sheet["D10"].value == 125.5
        assert sheet["D10"].data_type == "n"
    finally:
        workbook.close()
