"""Source-reviewed completeness contracts and safeguards for the Phase 4 repair."""
from copy import deepcopy
import json
from pathlib import Path
import re
from types import SimpleNamespace

from openpyxl import Workbook, load_workbook
import pandas as pd
import pytest

from excel_writer import write_extraction_workbook
from models import ExtractionResult, StatementPage, StatementPagePlan
from table_completeness_cases import CASES, CONTROLS, replay
from table_completeness_contract import (CompletenessContractError, assert_context, assert_page_endings,
                                         assert_rows, assert_selected_endings)
from test_income_period_regression import assert_workbook_rules

@pytest.fixture(params=CASES, ids=lambda c: c["id"] + "-" + c["name"])
def exported(request, monkeypatch, tmp_path):
    case = deepcopy(request.param)
    result, path = replay(case, monkeypatch, tmp_path)
    book = load_workbook(path)
    try:
        # Workbook layout and the numeric source contracts are both required.
        assert_workbook_rules(book)
        assert case["statement_type"] in result.statements
        yield case, result, book.worksheets[0]
    finally:
        book.close()


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_cutoff_source_fixtures_are_portable_and_independent(case):
    assert re.fullmatch(r"[a-f0-9]{64}", case["source"]["pdf_sha256"])
    assert Path(case["source"]["pdf_file"]).name == case["source"]["pdf_file"]
    assert case["source"]["independent_reader"].startswith("PyMuPDF")
    assert not re.search(r"[A-Za-z]:\\\\|/Users/|outputs/regression", json.dumps(case))
    assert {p["number"] for p in case["pages"]} == set(case["source"]["pages"])
    assert len({r["source_id"] for r in case["expected_rows"]}) == len(case["expected_rows"])
    assert all(r in case["expected_rows"] for r in case["endings"])
    if case["id"] == "TC02":
        assert sum(v is None for r in case["expected_rows"] for v in r["values"]) == 1
        assert case["blank_annotation"]
    if case["id"] == "TC07":
        assert len(case["excluded_source_headers"]) == 1
        assert len(case["expected_rows"]) == 41


def test_reviewed_endings_reach_their_pages_and_saved_workbook(exported):
    case, result, sheet = exported
    assert_page_endings(result, case)
    assert_rows(sheet, case["endings"])


def test_complete_source_row_sequence_and_period_context_survive_export(exported):
    case, _, sheet = exported
    assert_rows(sheet, case["expected_rows"], reject_extra=True)
    assert_context(sheet, case)


@pytest.mark.parametrize("case", [c for c in CASES if c["id"] in ("TC01", "TC04", "TC06", "TC07")], ids=lambda c: c["id"])
def test_fallback_retains_endings_already_captured_by_another_candidate(case, monkeypatch, tmp_path):
    result, _ = replay(deepcopy(case), monkeypatch, tmp_path)
    assert_selected_endings(result, case)


@pytest.mark.parametrize("control", CONTROLS, ids=lambda c: c["id"] + "-" + c["name"])
def test_working_table_endings_keep_numeric_cells_and_source_metadata(control, tmp_path):
    data = deepcopy(control["frame"])
    frame = pd.DataFrame(data["rows"], columns=data["columns"])
    frame.attrs = data["attrs"]
    before = deepcopy(frame.attrs)
    result = ExtractionResult({"source_file": "control.pdf"}, [], [], [], [], {control["statement_type"]: frame}, [], [], [])
    path = write_extraction_workbook(result, tmp_path / "control.xlsx")
    book = load_workbook(path)
    try:
        assert_workbook_rules(book)
        sheet = book.worksheets[0]
        for coordinate, data_type, value, number_format in control["cells"]:
            cell = sheet[coordinate]
            assert [cell.data_type, cell.value, cell.number_format] == [data_type, value, number_format]
        assert_rows(sheet, control["expected_rows"])
        assert frame.attrs == before
    finally:
        book.close()


GOLD = [
    {"source_id": "opening", "label": "Beginning net assets", "values": ["100", "90"]},
    {"source_id": "distributions", "label": "Distributions", "values": ["-10", "SOURCE_DASH"]},
    {"source_id": "income", "label": "Net income", "values": [None, "20"]},
    {"source_id": "ending", "label": "Ending net assets", "values": ["90", "110"]},
]
GOLD_CONTEXT = {"period_years": ["2026", "2025"], "unit_word": "thousands", "period_sections": []}


def golden_book():
    book = Workbook()
    sheet = book.active
    sheet.column_dimensions["A"].width = sheet.column_dimensions["B"].width = 1
    sheet["C6"] = "Amounts in thousands"
    sheet["D8"], sheet["E8"] = "2026", "2025"
    for number, row in enumerate(GOLD, 9):
        sheet.cell(number, 3, row["label"])
        for col, value in enumerate(row["values"], 4):
            sheet.cell(number, col, "-" if value == "SOURCE_DASH" else None if value is None else float(value))
    return book


def check_gold(sheet):
    assert_rows(sheet, GOLD, reject_extra=True)
    assert_context(sheet, GOLD_CONTEXT)


def test_contract_accepts_verified_numbers_with_minor_heading_and_footnote_variations(tmp_path):
    book = golden_book()
    book.active["C9"] = "Beginning net assets (1)"
    book.active["C5"] = "A slightly imperfect heading"
    path = tmp_path / "gold.xlsx"
    book.save(path)
    book.close()
    saved = load_workbook(path)
    try:
        check_gold(saved.active)
        assert_workbook_rules(saved)
    finally:
        saved.close()


@pytest.mark.parametrize("mutation", ["missing_ending", "wrong_amount", "sign_flip", "period_swap", "numeric_text",
                                     "blank_to_zero", "dash_to_zero", "shifted_column", "duplicate_ending",
                                     "wrong_label", "wrong_units"])
def test_contract_rejects_numeric_period_and_row_corruptions(mutation, tmp_path):
    book = golden_book()
    sheet = book.active
    check_gold(sheet)
    if mutation == "missing_ending":
        sheet.delete_rows(12)
    elif mutation == "wrong_amount":
        sheet["D12"] = 91
    elif mutation == "sign_flip":
        sheet["D10"] = 10
    elif mutation == "period_swap":
        sheet["D8"], sheet["E8"] = "2025", "2026"
    elif mutation == "numeric_text":
        sheet["E12"] = "110"
    elif mutation == "blank_to_zero":
        sheet["D11"] = 0
    elif mutation == "dash_to_zero":
        sheet["E10"] = 0
    elif mutation == "shifted_column":
        sheet["F12"], sheet["E12"] = 110, None
    elif mutation == "duplicate_ending":
        sheet["C13"], sheet["D13"], sheet["E13"] = "Ending net assets", 90, 110
    elif mutation == "wrong_label":
        sheet["C12"] = "Unrelated total"
    elif mutation == "wrong_units":
        sheet["C6"] = "Amounts in millions"
    path = tmp_path / f"{mutation}.xlsx"
    book.save(path)
    book.close()
    saved = load_workbook(path)
    try:
        with pytest.raises(CompletenessContractError):
            check_gold(saved.active)
    finally:
        saved.close()


def test_equal_balance_on_another_page_cannot_cover_a_missing_comparison_block():
    frame = pd.DataFrame()
    frame.attrs["source_tables"] = [{"source_page": 7, "rows": [["Balance as of June 30, 2025", "100", "20"]]}]
    result = SimpleNamespace(statements={"PartnersCapital": frame})
    case = {"statement_type": "PartnersCapital", "source": {"pages": [7, 8]},
            "endings": [{"source_id": f"p{p}:ending", "page": p, "label": "Balance as of June 30, 2025", "values": ["100", "20"]}
                        for p in (7, 8)]}
    with pytest.raises(CompletenessContractError, match="page-specific.*p8"):
        assert_page_endings(result, case)


def test_period_captions_must_govern_their_own_rows_even_when_balances_repeat():
    book = Workbook()
    sheet = book.active
    captions = ["Three Months Ended June 30, 2025", "Six Months Ended June 30, 2025"]
    expected = []
    for section, start in enumerate((8, 12)):
        sheet.cell(start, 3, captions[section])
        for offset, label, values in [(1, "Opening balance", [100 + section, 20]),
                                       (2, "Balance as of June 30, 2025", [120, 30])]:
            sheet.cell(start + offset, 3, label)
            for col, value in enumerate(values, 4):
                sheet.cell(start + offset, col, value)
            expected.append({"source_id": f"section{section}:row{offset}", "label": label,
                             "values": list(map(str, values))})
    case = {"period_years": [], "unit_word": None, "period_sections": captions,
            "expected_rows": expected, "endings": [expected[1], expected[3]]}
    assert_context(sheet, case)
    sheet["C7"], sheet["C8"], sheet["C12"] = captions[0], captions[1], None
    with pytest.raises(CompletenessContractError, match="missing source row"):
        assert_context(sheet, case)
    book.close()


@pytest.mark.parametrize("kind", ["PartnersCapital", "CashFlowStatement"])
def test_mixed_statement_ownership_keeps_original_numbers(kind):
    from financial_statement_extract.equity_layout import recover_pdf_equity_tables
    from financial_statement_extract.cash_flow_layout import recover_cash_flow_tables
    original = [{"table_id": "mixed", "source_page": 1, "statement_type": kind,
                 "rows": [["Protected amount", "100", "20"]]}]
    saved = deepcopy(original)
    frame = pd.DataFrame()
    frame.attrs["source_tables"] = original
    plan = StatementPagePlan("unused.pdf", "manual", (1,), (1,), (1,),
        (StatementPage(1, "data", kind, statement_types=(kind, "ScheduleOfInvestments")),))
    if kind == "PartnersCapital":
        actual, _ = recover_pdf_equity_tables("unused.pdf", original, {kind: frame}, plan)
    else:
        actual, _ = recover_cash_flow_tables(original, [], plan)
    assert actual == saved and frame.attrs["source_tables"] == saved


def test_notes_after_a_cash_flow_statement_are_not_appended_as_continuation():
    from financial_statement_extract.cash_flow_layout import _page_blocks
    text = ["Consolidated Statements of Cash Flows", "For the years ended December 31,", "2026 2025",
            "Net cash provided by operating activities 10 9", "Cash, end of period 100 90",
            "Notes to Consolidated Financial Statements", "Unrelated investment total 999 888"]
    source = [{"source_page": 1, "line_no": i, "raw_text": line} for i, line in enumerate(text, 1)]
    blocks = _page_blocks(source, 1, text[0])
    assert blocks[-1]["rows"][-1] == ["Cash, end of period", "100", "90"]
    assert not any("999" in value for b in blocks for row in b["rows"] for value in row)
