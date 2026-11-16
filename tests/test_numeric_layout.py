from copy import deepcopy

import pandas as pd
import pytest
from openpyxl import load_workbook

from excel_writer import write_extraction_workbook
from financial_statement_extract.numeric_layout import accounting_display_grid
from models import ExtractionResult


def grid(row=None, **overrides):
    return {
        "table_id": "P0001_PDFPLUMBER_01", "source_page": 1,
        "statement_type": "PartnersCapital", "flavor": "pdfplumber", "spans": [],
        "rows": [["Opening net assets", "1,234", "", "2025"],
                 ["Investment income", "567", "", "2024"],
                 row or ["Realized loss", "(67,502", ")", "27,753,373"]],
        **overrides,
    }


@pytest.mark.parametrize("kind", ["BalanceSheet", "CashFlowStatement", "PartnersCapital",
                                 "StockholdersEquityStatement"])
@pytest.mark.parametrize("flavor", ["pdfplumber", "stream", "lattice"])
def test_repair_keeps_columns_and_raw_grid(kind, flavor):
    original = grid(statement_type=kind, flavor=flavor)
    before = deepcopy(original)
    fixed = accounting_display_grid(original)
    assert fixed["rows"][2] == ["Realized loss", "(67,502)", "", "27,753,373"]
    assert fixed["rows"][:2] == before["rows"][:2]
    assert original == before
    assert {k: v for k, v in fixed.items() if k != "rows"} == {
        k: v for k, v in before.items() if k != "rows"}


@pytest.mark.parametrize("row", [
    ["Loss", "(123", "456)"],
    ["Loss", "(12,34", ")"],
    ["Loss", "123", ")"],
    ["Loss", "(123)", ""],
    ["Loss", "(123", "", ")"],
    ["Loss", "(", "123)"],
    ["Loss", "(1,234 567", ")"],
    ["Loss", "(123", ") (1)"],
    ["Loss", "(1.25", ")", "%"],
    ["Loss", "(1.25", ")", "", "%"],
    ["Loss", "(1.25", ")", "x"],
    ["Loss", "(1234567890123456", ")"],
    ["Loss", "(S123", ")"],
    ["Loss", "-", ""],
    ["Loss", "", ""],
    ["", "(123", ")"],
])
def test_ambiguous_or_unsupported_tokens_stay_literal(row):
    original = grid(row)
    assert accounting_display_grid(original) is original


@pytest.mark.parametrize("changes", [
    {"flavor": "html"}, {"flavor": "balance_geometry"},
    {"statement_type": "ScheduleOfInvestments"}, {"statement_type": "IncomeStatement"},
    {"spans": [[2, 1, 1, 2]]}, {"spans": [[1, 2, 2, 1]]},
])
def test_unsupported_grids_and_spans_stay_literal(changes):
    original = grid(**changes)
    assert accounting_display_grid(original) is original


@pytest.mark.parametrize("anchors", [["1", "2"], ["2025", "2024"], ["100", ""], ["0", "0"]])
def test_note_columns_years_and_insufficient_support_do_not_qualify(anchors):
    original = grid(["Notes", "(1", ")"])
    original["rows"][0][1], original["rows"][1][1] = anchors
    assert accounting_display_grid(original) is original


def test_saved_workbook_contains_numeric_losses_and_preserves_raw_evidence(tmp_path):
    table = grid()
    table["rows"].extend([
        ["Loss per share", "(0.50", ")", "0.25"],
        ["Cash distribution", "($1,200.00", ")", "5,678"],
        ["Zero", "0", "", ""],
        ["Missing", "", "", ""],
    ])
    before = deepcopy(table)
    frame = pd.DataFrame({"RawItem": [r[0] for r in table["rows"]]})
    frame.attrs.update(source_tables=[table], statement_title="Changes in Net Assets",
                       raw_unit_note="In thousands, except share and per share data")
    raw = [dict(source_page=1, table_id=table["table_id"], flavor="pdfplumber", selected=True,
                row_index=r, column_index=c, raw_text=value)
           for r, row in enumerate(table["rows"]) for c, value in enumerate(row)]
    result = ExtractionResult(metadata={"source_file": "example.pdf"}, raw_text_rows=[],
                              raw_table_cells=raw, normalized_table_cells=[], extraction_audit_rows=[],
                              statements={"PartnersCapital": frame}, parsed_cells=[],
                              financial_audit_rows=[], unmapped_rows=[])
    output = write_extraction_workbook(result, tmp_path / "amounts.xlsx")
    book = load_workbook(output)
    try:
        sheet = book["Changes in Net Assets"]
        rows = {r[0].value: r for r in sheet.iter_rows(min_col=3)}
        assert [c.value for c in rows["Realized loss"][:4]] == ["Realized loss", -67502, None, 27753373]
        assert rows["Realized loss"][1].data_type == "n"
        assert rows["Loss per share"][1].value == -0.5
        assert rows["Loss per share"][1].number_format == "#,##0.00;(#,##0.00);#,##0.00"
        assert rows["Cash distribution"][1].value == -1200
        assert rows["Cash distribution"][3].value == 5678
        assert rows["Zero"][1].value == 0
        assert rows["Missing"][1].value is None
        raw_rows = {r[0].value: r for r in book["PDFPlumber"].iter_rows(min_col=3)}
        assert [c.value for c in raw_rows["Realized loss"][:4]] == ["Realized loss", "(67,502", ")", "27,753,373"]
        for tab in book:
            assert not tab.merged_cells.ranges
            assert tab.freeze_panes is None
            assert not any(d.hidden for d in tab.row_dimensions.values())
            assert not any(d.hidden for d in tab.column_dimensions.values())
            # XlsxWriter stores width 1 with Excel's character padding.
            for column in (1, 2):
                dimension = next(d for d in tab.column_dimensions.values() if d.min <= column <= d.max)
                assert dimension.width == 1.7109375
            assert all(c.value is None for row in tab.iter_rows(max_row=3) for c in row)
            assert all(c.value is None for row in tab.iter_rows(max_col=2) for c in row)
    finally:
        book.close()
    assert table == before
    assert frame.attrs["source_tables"] == [before]
