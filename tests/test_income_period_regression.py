"""Source-backed contracts for income reporting columns and saved numeric values."""
from copy import deepcopy
from pathlib import Path
import re

from openpyxl import load_workbook
import pandas as pd
import pytest

from excel_writer import write_extraction_workbook
from models import ExtractionResult
from statements import parse_financial_statements
from income_period_cases import CASES
from income_period_controls import PARSER_CONTROLS, WRITER_CONTROLS


class IncomeContractError(AssertionError):
    """A specific numeric/period contract failed, not test setup or export execution."""


def require(condition, message):
    if not condition:
        raise IncomeContractError(message)


def normalized(value):
    return " ".join(str(value).lower().split()).replace(",", "")


def assert_periods(actual, expected):
    """Check reporting identity, permitting case, commas and 'For the' differences."""
    require(len(actual) == len(expected), f"period count: {actual!r}; expected {expected!r}")
    require(len(set(actual)) == len(actual), "different reporting periods need distinct labels")
    words = {3: "three", 6: "six", 9: "nine", 12: "twelve"}
    for label, (months, month, day, year) in zip(actual, expected):
        value = re.sub(r"^for (?:the )?", "", normalized(label))
        date = f"{month.lower()} {day} {year}"
        if months is None:
            pattern = rf"(?:(?:(?:twelve|12) months? ended |(?:the )?years? ended )?{date}|{year})"
        else:
            duration = rf"(?:{words[months]}|{months}) months? ended"
            if months == 12:
                duration = rf"(?:{duration}|year ended)"
            pattern = rf"{duration} {date}"
        require(re.fullmatch(pattern, value), f"wrong period identity: {label!r}; expected {(months, month, day, year)!r}")


def result_from_rows(rows):
    statements, cells, issues, unmapped = parse_financial_statements(deepcopy(rows))
    return ExtractionResult({"source_file": "fixture.pdf", "rescaled_values": False},
                            deepcopy(rows), [], [], issues, statements, cells, [], unmapped)


def assert_frame_rows(frame, expected_rows):
    periods = frame.attrs["period_labels"]
    for expected in expected_rows:
        matches = frame[frame["RawItem"].map(normalized) == normalized(expected["label"])]
        require(len(matches) == 1, f"missing or contaminated label: {expected['label']!r}")
        actual = [None if pd.isna(matches.iloc[0][p]) else matches.iloc[0][p] for p in periods]
        require(actual == expected["values"], f"wrong amounts for {expected['label']!r}: {actual!r}")


def assert_saved_rows(sheet, expected_rows):
    for expected in expected_rows:
        rows = [r for r in sheet.iter_rows(min_row=9, min_col=3)
                if normalized(r[0].value) == normalized(expected["label"])]
        require(len(rows) == 1, f"saved label missing or contains amounts: {expected['label']!r}")
        cells = rows[0][1:]
        require([c.value for c in cells] == expected["values"], f"saved amount sequence: {expected['label']!r}")
        for cell, value in zip(cells, expected["values"]):
            require(cell.data_type == "n", f"non-numeric storage at {cell.coordinate}")
            if value is not None and value != int(value):
                require(".00" in cell.number_format, f"lost decimal display precision at {cell.coordinate}")


def assert_workbook_rules(book):
    for sheet in book:
        assert not sheet.merged_cells.ranges
        assert sheet.freeze_panes is None
        assert not any(d.hidden or d.height == 0 for d in sheet.row_dimensions.values())
        assert not any(d.hidden or d.width == 0 for d in sheet.column_dimensions.values())
        assert all(c.value is None for row in sheet.iter_rows(max_row=3) for c in row)
        assert all(c.value is None for row in sheet.iter_rows(max_col=2) for c in row)
        for col in ("A", "B"):
            dimensions = [d for d in sheet.column_dimensions.values() if d.min <= (1 if col == "A" else 2) <= d.max]
            assert dimensions and all(1 <= d.width < 2 for d in dimensions)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_source_fixture_is_portable_and_internally_consistent(case):
    assert re.fullmatch(r"[0-9a-f]{64}", case["source"]["pdf_sha256"])
    assert Path(case["source"]["pdf_file"]).name == case["source"]["pdf_file"]
    assert len(case["periods"]) in (3, 4, 5)
    assert len(case["expected_rows"]) == 3
    assert all(len(r["values"]) == len(case["periods"]) for r in case["expected_rows"])
    assert all(r["source_page"] == case["source"]["page"] for r in case["input_rows"])
    assert len({r["line_no"] for r in case["input_rows"]}) == len(case["input_rows"])


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_source_header_preserves_reporting_periods(case):
    result = result_from_rows(case["input_rows"])
    require("IncomeStatement" in result.statements, "income statement was dropped")
    assert_periods(result.statements["IncomeStatement"].attrs["period_labels"], case["periods"])


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_source_amounts_are_numeric_and_outside_labels(case):
    result = result_from_rows(case["input_rows"])
    require("IncomeStatement" in result.statements, "income statement was dropped")
    assert_frame_rows(result.statements["IncomeStatement"], case["expected_rows"])


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_source_periods_and_amounts_survive_excel_export(case, tmp_path):
    result = result_from_rows(case["input_rows"])
    # Execution/setup errors are not expected failures. The assertion checks saved cells.
    path = write_extraction_workbook(result, tmp_path / f"{case['id']}.xlsx")
    book = load_workbook(path)
    try:
        assert_workbook_rules(book)
        sheet = book.worksheets[0]
        assert_periods([sheet.cell(8, c).value for c in range(4, sheet.max_column + 1)], case["periods"])
        assert_saved_rows(sheet, case["expected_rows"])
    finally:
        book.close()


@pytest.mark.parametrize("control", PARSER_CONTROLS, ids=lambda c: c["id"])
def test_working_source_parser_controls(control, tmp_path):
    result = result_from_rows(control["input_rows"])
    frame = result.statements["IncomeStatement"]
    assert frame.attrs["period_labels"] == control["period_labels"]
    expected = [{"label": control["label"], "values": control["values"]}]
    assert_frame_rows(frame, expected)
    path = write_extraction_workbook(result, tmp_path / "control.xlsx")
    book = load_workbook(path)
    try:
        assert_saved_rows(book.worksheets[0], expected)
        assert_workbook_rules(book)
    finally:
        book.close()


@pytest.mark.parametrize("control", WRITER_CONTROLS, ids=lambda c: c["id"])
def test_protected_source_cells_survive_current_writer(control, tmp_path):
    saved = control["frame"]
    frame = pd.DataFrame(deepcopy(saved["rows"]), columns=saved["columns"])
    frame.attrs = deepcopy(saved["attrs"])
    original_attrs = deepcopy(frame.attrs)
    result = ExtractionResult({"source_file": "control.pdf"}, [], [], [], [],
                              {control["statement_type"]: frame}, [], [], [])
    path = write_extraction_workbook(result, tmp_path / "protected.xlsx")
    book = load_workbook(path)
    try:
        # Tab numbering changes when a single statement is exported in isolation.
        sheet = book.worksheets[0]
        assert [sheet[c].value for c in control["cells"]] == control["values"]
        assert all(sheet[c].data_type == "n" for c in control["cells"])
        assert_workbook_rules(book)
        assert frame.attrs == original_attrs
    finally:
        book.close()


def test_working_inline_periods_keep_zero_missing_signs_notes_and_wrapped_labels(tmp_path):
    text = '''Example Fund
Consolidated Statements of Operations
(in thousands, except per share amounts)
Three Months Ended June 30, Six Months Ended June 30,
2026 2025 2026 2025
Interest on 2025 Notes (1) 0 - (12.50) 20.25
Earnings per share 0.00 0.15 (0.25) 1.20
Net realized gain (loss) on
investments 1 2 3 4
'''
    rows = [{"source_page": 1, "line_no": n, "raw_text": line} for n, line in enumerate(text.splitlines(), 1)]
    result = result_from_rows(rows)
    frame = result.statements["IncomeStatement"]
    expected = [{"label": "Interest on 2025 Notes (1)", "values": [0, None, -12.5, 20.25]},
                {"label": "Earnings per share", "values": [0, 0.15, -0.25, 1.2]},
                {"label": "Net realized gain (loss) on investments", "values": [1, 2, 3, 4]}]
    assert_frame_rows(frame, expected)
    assert frame.iloc[0]["Note"] == "1"
    assert frame.attrs["scale_factor"] == 1000
    path = write_extraction_workbook(result, tmp_path / "inline.xlsx")
    book = load_workbook(path)
    try:
        assert_saved_rows(book.worksheets[0], expected)
        assert_workbook_rules(book)
    finally:
        book.close()


@pytest.mark.parametrize("header", ["Years ended December 31, 2026 2025", "2026 2025 2026 2025"],
                         ids=["extra_values", "repeated_years_without_durations"])
def test_unresolved_amount_alignment_is_explicitly_reported(header):
    text = f"Example Fund\nConsolidated Statements of Operations\n{header}\nNet income 10 20 30 40"
    statements, _, issues, _ = parse_financial_statements(text)
    relevant = [i for i in issues if i.get("Status") in {"WARN", "FAIL"}
                and ("Net income" in i.get("Detail", "") or i.get("Check") == "Statement period detection")]
    require(relevant, "ambiguous amount/period alignment was silently accepted")
    if "IncomeStatement" in statements:
        require(len(statements["IncomeStatement"].attrs["period_labels"]) <= 2,
                "unsupported durations or periods were invented")


@pytest.mark.parametrize("fault", ["duration_swap", "amount_swap", "sign_flip", "numeric_text", "missing_zero"])
def test_saved_cell_contract_rejects_deliberate_numeric_faults(fault, tmp_path):
    text = '''Example Fund
Consolidated Statements of Operations
Three Months Ended June 30, Six Months Ended June 30,
2026 2025 2026 2025
Net income (10) 0 30 40
'''
    rows = [{"source_page": 1, "line_no": n, "raw_text": line} for n, line in enumerate(text.splitlines(), 1)]
    path = write_extraction_workbook(result_from_rows(rows), tmp_path / "fault.xlsx")
    book = load_workbook(path)
    sheet = book.worksheets[0]
    if fault == "duration_swap":
        sheet["D8"].value, sheet["F8"].value = sheet["F8"].value, sheet["D8"].value
    elif fault == "amount_swap":
        sheet["D9"].value, sheet["F9"].value = sheet["F9"].value, sheet["D9"].value
    elif fault == "sign_flip":
        sheet["D9"] = 10
    elif fault == "numeric_text":
        sheet["D9"] = "-10"
    else:
        sheet["E9"] = None
    book.save(path)
    book.close()
    book = load_workbook(path)
    try:
        with pytest.raises(IncomeContractError):
            if fault == "duration_swap":
                assert_periods([book.worksheets[0].cell(8, c).value for c in range(4, 8)],
                               [[d, "June", 30, y] for d in (3, 6) for y in (2026, 2025)])
            else:
                assert_saved_rows(book.worksheets[0], [{"label": "Net income", "values": [-10, 0, 30, 40]}])
    finally:
        book.close()
