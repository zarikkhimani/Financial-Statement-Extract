"""Adverse cases for source-bounded continuation and fallback selection."""
from copy import deepcopy

import pytest

from financial_statement_extract.candidate_selection import normalize_selected_cells, preserve_complete_candidates
from financial_statement_extract.cash_flow_layout import _headers, recover_cash_flow_tables
from financial_statement_extract.equity_layout import EquityLayoutError, _component_headers, equity_component_grid
from structure import detect_statement_unit_note
from table_completeness_cases import CASES, SnapshotPage, replay
from test_cash_flow_layout import candidate, source_and_plan


def raw(flavor, rows, selected=False, page=1):
    return [dict(table_id=f"{page}-{flavor}", source_page=page, flavor=flavor, selected=selected,
                 row_index=r, column_index=c, raw_text=value)
            for r, row in enumerate(rows) for c, value in enumerate(row)]


def test_more_complete_candidate_and_its_normalized_cells_replace_truncated_flavor():
    cells = raw("stream", [["Opening", "100", "90"]], True)
    cells += raw("pdfplumber", [["Opening", "100", "90"], ["Ending", "120", "110"]])
    before = deepcopy(cells)
    source = [dict(source_page=1, raw_text="Opening 100 90\nEnding 120 110")]
    issues = preserve_complete_candidates(cells, source, {1})
    assert len(issues) == 1 and issues[0]["Status"] == "INFO"
    assert all(r["selected"] == (r["flavor"] == "pdfplumber") for r in cells)
    assert [{**r, "selected": b["selected"]} for r, b in zip(cells, before)] == before
    normalized = normalize_selected_cells(cells)
    assert len(normalized) == 6 and {r["flavor"] for r in normalized} == {"pdfplumber"}
    assert [r["parsed_value"] for r in normalized if r["parse_status"] == "NUMERIC"] == [100, 90, 120, 110]


@pytest.mark.parametrize("alternative,pages", [
    ([["Opening", "100", "91"], ["Ending", "120", "110"]], {1}),
    ([["Opening", "100", "90"], ["Opening", "100", "90"]], {1}),
    ([["Opening", "100", "90"], ["Ending", "120", "110"]], set()),
])
def test_extra_tokens_duplicates_or_ineligible_pages_do_not_displace_existing_coverage(alternative, pages):
    cells = raw("stream", [["Opening", "100", "90"]], True) + raw("lattice", alternative)
    before = deepcopy(cells)
    assert preserve_complete_candidates(cells, [dict(source_page=1, raw_text="Opening 100 90\nEnding 120 110")], pages) == []
    assert cells == before


def test_repeated_period_block_cannot_silently_reuse_different_component_headings():
    page = SnapshotPage(CASES[3]["pages"][0])
    for word in page.data["words"]:
        if word["top"] > 400 and word["text"] == "Shares":
            word["text"] = "Units"
    with pytest.raises(EquityLayoutError, match="disagree on source component headings"):
        equity_component_grid(page, page.find_tables())


@pytest.mark.parametrize("caption", ["(unaudited)", "(in thousands)", "(in thousands, except shares)"])
def test_centered_statement_caption_is_not_an_overlapping_equity_parent(caption):
    major = [(0, 0, 100, 10), (100, 0, 150, 10), (150, 0, 200, 10)]
    def word(text, x0, x1):
        return dict(text=text, x0=x0, x1=x1)
    headers = [[word("Common Stock", 125, 175)],
               [word("Shares", 110, 140), word("Par Value", 160, 190)]]
    expected = _component_headers(headers, major)
    assert _component_headers([[word(caption, 115, 185)], *headers], major) == expected


def test_genuinely_overlapping_equity_parent_headers_still_fail():
    major = [(0, 0, 100, 10), (100, 0, 150, 10), (150, 0, 200, 10)]
    headers = [[dict(text=text, x0=125, x1=175)] for text in ("Class A", "Class B")]
    headers.append([dict(text="Shares", x0=110, x1=140), dict(text="Value", x0=160, x1=190)])
    with pytest.raises(EquityLayoutError, match="overlap ambiguously"):
        _component_headers(headers, major)


def test_failed_source_recovery_keeps_existing_display_and_selected_candidates(monkeypatch, tmp_path):
    case = deepcopy(CASES[0])
    case["pages"][0]["words"] = [w for w in case["pages"][0]["words"] if w["text"] != "Shares"]
    result, _ = replay(case, monkeypatch, tmp_path)
    assert {r["flavor"] for r in result.raw_table_cells if r["selected"]} == {"stream"}
    assert {t["flavor"] for t in result.statements[case["statement_type"]].attrs["source_tables"]} == {"stream"}
    assert any(r["Status"] == "WARN" and r["Check"] == "Equity component layout" for r in result.extraction_audit_rows)


def test_source_closing_amount_missing_from_geometry_blocks_recovery():
    page = SnapshotPage(CASES[2]["pages"][0])
    page.data["words"] = [w for w in page.data["words"] if w["text"] != "$160,774,300"]
    with pytest.raises(EquityLayoutError, match="complete source text"):
        equity_component_grid(page, page.find_tables())


def test_equity_notes_are_not_appended_as_continuation_amounts():
    page = SnapshotPage(CASES[2]["pages"][0])
    original = equity_component_grid(page, page.find_tables())
    page.data["text"] += "\nUnrelated note 999 888 777 666 555"
    page.data["words"].extend(dict(text=text, x0=x, x1=x+20, top=780)
                              for x, text in [(34, "Unrelated note"), (270, "999"), (340, "888"),
                                              (400, "777"), (480, "666"), (550, "555")])
    assert equity_component_grid(page, page.find_tables())["rows"] == original["rows"]


def test_numbered_equity_amount_row_is_not_mistaken_for_the_start_of_notes():
    page = SnapshotPage(CASES[2]["pages"][0])
    page.data["text"] = page.data["text"].replace("Balance at September 30, 2022", "(1) Balance at September 30, 2022")
    first_balance = next(w for w in page.data["words"] if w["text"] == "Balance")
    first_balance["text"] = "(1) Balance"
    grid = equity_component_grid(page, page.find_tables())
    assert grid["row_kinds"].count("data") == 26
    assert any(row[0].startswith("(1) Balance") for row in grid["rows"])


def test_inline_year_header_requires_an_explicit_source_period_cue():
    assert _headers([dict(raw_text="For the years ended December 31, 2025 2024 2023")])[0][2] == ["2025", "2024", "2023"]
    assert _headers([dict(raw_text="Investment proceeds 2025 2024 2023")]) == []


@pytest.mark.parametrize("first_amount,expected", [("100", "INFO"), ("101", "WARN")])
def test_packed_label_amount_is_preserved_or_warned_without_dropping_a_period(first_amount, expected):
    source, plan = source_and_plan(("Consolidated Statements of Cash Flows\n"
                                   "For the years ended December 31, 2025 2024 2023\n"
                                   "Ending cash 100 90 80",))
    tables = [candidate([["Ending cash " + first_amount, "90", "80"]], page=1)]
    actual, issues = recover_cash_flow_tables(tables, source, plan)
    assert issues[0]["Status"] == expected
    assert (actual == tables) == (expected == "WARN")


@pytest.mark.parametrize("text,scale", [("(amounts in 000's)", 1000), ("(amounts in 000\u2019s)", 1000),
                                       ("(amounts in 000\ufffds)", 1000), ("(millions)", 1000000)])
def test_source_unit_notation_is_retained_and_classified_without_rescaling(text, scale):
    note = detect_statement_unit_note([dict(raw_text=text)])
    assert note["raw_unit_note"] == text and note["scale_factor"] == scale
