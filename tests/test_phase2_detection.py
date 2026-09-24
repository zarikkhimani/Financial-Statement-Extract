from dataclasses import replace

import pytest

from financial_statement_extract.detection import detect_statement_plan, fingerprint
from financial_statement_extract.page_selection import resolve_page_plan
from models import PageSelectionReviewRequired


BALANCE = "Balance Sheets\n2026 2025\nCash 100 90\nTotal assets 500 450\nTotal liabilities and equity 500 450"
INCOME = "Statements of Operations\n2026 2025\nRevenue 100 90\nNet income 10 9"
CASH = "Statements of Cash Flows\n2026 2025\nDepreciation 10 9\nNet cash from operating activities 20 18"
SCHEDULE = "Consolidated Schedule of Investments\nCost Fair Value\nCompany A 100 90\nCompany B 50 40"
EQUITY = "Statements of Stockholders' Equity\n2026 2025\nOpening balance 100 90\nEnding balance 110 99"


def selected(texts, **kwargs):
    return list(detect_statement_plan(texts, **kwargs).selected_pages)


def test_schedule_has_no_arbitrary_page_limit_or_proximity_limit():
    pages = [BALANCE, INCOME] + [SCHEDULE] * 220 + [EQUITY, CASH, "Notes to Financial Statements\nTax 3 2"]
    plan = detect_statement_plan(pages)
    assert plan.selected_pages == tuple(range(1, 225))
    assert not any("worksheet output remains" in warning for warning in plan.warnings)
    assert not plan.review_required


def test_distant_numeric_sections_are_not_filled_in_between_statements():
    pages = [BALANCE, INCOME, CASH] + ["Management's Discussion\nRevenue 500 600"] * 50 + [SCHEDULE]
    assert selected(pages) == [1, 2, 3]


def test_title_page_and_conversion_blanks_do_not_end_cash_flow_continuation():
    pages = ["Statements of Cash Flows", "", CASH.replace("Statements of Cash Flows\n", ""), "4",
             "Net cash from financing activities 10 9\nCash at end of period 40 35"]
    assert selected(pages) == [1, 3, 5]


def test_split_and_repeated_navigation_headings_are_preserved():
    heading = "CONDENSED CONSOLIDATED\nSTATEMENTS OF CASH FLOWS (Unaudited)"
    plan = detect_statement_plan(["Table of Contents\nExample Company\n" + heading + "\nNet cash 10 9\nCash at end 100 90"])
    assert plan.selected_pages == (1,)
    assert plan.pages[0].source_title == heading


def test_toc_numbers_and_narrative_references_are_not_statements():
    pages = ["Table of Contents\nStatements of Operations 55\nBalance Sheets 56",
             "We refer readers to the Statements of Cash Flows.\nRevenue 300 250\nExpenses 200 150", BALANCE, INCOME, CASH]
    assert selected(pages) == [3, 4, 5]


def test_notes_tables_never_become_continuations():
    pages = [BALANCE, INCOME, CASH, "Notes to Consolidated Financial Statements\nCash 100 90\nInterest paid 10 9",
             "Cash deposits 100 90\nCash collateral 40 30"]
    assert selected(pages) == [1, 2, 3]


def test_notes_starting_mid_page_end_following_continuations():
    pages = [CASH + "\nNotes to Financial Statements\nCash disclosures 100 90", "Cash deposits 100 90\nInterest 10 9"]
    assert selected(pages) == [1]


def test_unrelated_numeric_table_cannot_extend_core_statement():
    assert selected([CASH, "Effective tax rate 3 2\nTax charge 1 2"]) == [1]


def test_schedule_derivatives_and_single_percentage_columns():
    derivative = "Schedule of Investments\nDerivative Instrument Maturity Amount Footnote\nInterest rate swap 3.5% 6/30/2028 300 Note 5\nCurrency swap 2.5% 9/30/2028 200 Note 5"
    percentages = "Schedule of Investments\nIndustry Percentage of Total Investments\nSoftware 20.5%\nHealthcare 79.5%"
    assert selected([SCHEDULE, derivative, percentages]) == [1, 2, 3]


def test_schedule_prose_footnotes_are_not_data_or_title_pages():
    footnote = "Schedule of Investments\n(1) The investments have been valued by the adviser under a methodology described in the accounting policies and supporting notes.\n(2) These securities are restricted and cannot be transferred without the approval of the issuer and applicable agreements."
    pages = [SCHEDULE] + [footnote] * 8 + [SCHEDULE, CASH]
    assert selected(pages) == [1, 10, 11]


def test_scan_gap_requires_review_and_is_never_silently_dropped():
    plan = detect_statement_plan([CASH, "", "Net cash 20 15\nCash at end 100 95"], unreadable_pages={2})
    assert plan.selected_pages == (1, 2, 3)
    with pytest.raises(PageSelectionReviewRequired):
        resolve_page_plan(plan, "review")
    assert resolve_page_plan(plan, "exact").selected_pages == (1, 2, 3)


def test_numeric_only_continuation_is_not_mistaken_for_blank_page():
    plan = detect_statement_plan([CASH, "100 90\n50 40"])
    assert plan.selected_pages == (1, 2)
    assert plan.review_required


def test_equal_competing_statement_sets_require_review():
    plan = detect_statement_plan([BALANCE, INCOME, CASH] + ["Unrelated prose"] * 5 + [BALANCE, INCOME, CASH])
    assert plan.review_required
    assert any("Equally supported" in warning for warning in plan.warnings)


def test_html_can_corroborate_a_page_without_a_recognized_title():
    page = "The fund's original heading\nRevenue 100 90\nNet income 10 9"
    guidance = {"IncomeStatement": {fingerprint("Revenue 100 90"), fingerprint("Net income 10 9")}}
    plan = detect_statement_plan([BALANCE, page, CASH], guidance=guidance, guidance_source="matching.html")
    assert plan.selected_pages == (1, 2, 3)
    assert plan.pages[1].statement_type == "IncomeStatement"
    assert plan.pages[1].source_title == ""  # Never substitute the HTML's title.
    assert plan.guidance_source == "matching.html"


def test_multiple_statements_on_one_page_keep_all_type_evidence():
    plan = detect_statement_plan([BALANCE + "\n" + INCOME + "\n" + CASH])
    assert set(plan.pages[0].statement_types) == {"BalanceSheet", "IncomeStatement", "CashFlowStatement"}
    assert not any("Not all core" in warning for warning in plan.warnings)


def test_parser_hints_preserve_pdf_titles_and_mid_page_boundaries():
    from financial_statement_extract.pdf_detection import statement_rows_from_plan
    text = BALANCE + "\n" + INCOME + "\nNotes to Financial Statements\nRevenue 999 888"
    plan = detect_statement_plan([text])
    rows = [{"source_page": 1, "raw_text": line} for line in text.splitlines()]
    hinted = statement_rows_from_plan(rows, plan)
    assert hinted[-1]["raw_text"] == "Net income 10 9"
    assert hinted[-1]["statement_type_hint"] == "IncomeStatement"
    assert hinted[-1]["source_title"] == "Statements of Operations"


def test_pipeline_reuses_auto_scan_and_forwards_only_selected_pages(tmp_path, monkeypatch):
    import pipeline
    import financial_statement_extract.pdf_detection as scanner
    source = tmp_path / "filing.pdf"
    source.touch()
    plan = detect_statement_plan([INCOME, "", CASH])
    rows = [{"source_page": p, "raw_text": line, "line_no": n} for p, text in [(1, INCOME), (3, CASH)]
            for n, line in enumerate(text.splitlines(), 1)]
    monkeypatch.setattr(pipeline, "get_page_count", lambda path: 3)
    monkeypatch.setattr(scanner, "scan_pdf_statements", lambda path: (plan, rows, []))
    monkeypatch.setattr(pipeline, "extract_page_text_pdfplumber", lambda *a: pytest.fail("Auto text was scanned twice"))
    calls = []
    def tables(path, pages):
        calls.append(pages)
        return [], [], []
    monkeypatch.setattr(pipeline, "extract_tables_camelot", tables)
    monkeypatch.setattr(pipeline, "extract_tables_pdfplumber", tables)
    monkeypatch.setattr(pipeline, "extract_tables_pdfplumber_experimental", lambda *args: ([], [], []))
    monkeypatch.setattr(pipeline, "get_pdf_document_type", lambda path: "")
    result, output = pipeline.extract_pdf_to_workbook(str(source))
    assert calls == ["1,3", "1,3"]
    assert output.exists()
    assert result.page_plan.selected_pages == (1, 3)
    monkeypatch.setattr(scanner, "scan_pdf_statements", lambda path: (replace(plan, review_required=True), rows, []))
    with pytest.raises(PageSelectionReviewRequired):
        pipeline.extract_pdf_to_workbook(str(source))
    assert calls == ["1,3", "1,3"]


def test_schedule_context_survives_untitled_footnotes_and_related_tables():
    footnote = "(1) These investments are valued by the adviser in accordance with the policies described in the accompanying financial statements."
    table = "Portfolio Company Unfunded commitments Fair Value\nCompany One 5 4\nCompany Two 7 6"
    assert selected([SCHEDULE, footnote, table, EQUITY, CASH]) == [1, 3, 4, 5]


def test_guidance_never_uses_filename_alone_and_ignores_ambiguous_siblings(tmp_path, monkeypatch):
    import financial_statement_extract.html_guidance as companion
    path = tmp_path / "fund.pdf"
    html = tmp_path / "fund.html"
    html.touch()
    source_rows = ["Revenue 100 90", "Net income 10 9", "Gross profit 50 40", "Expenses 90 81"]
    def extracted(file):
        return ([{"raw_text": line, "statement_type_hint": "IncomeStatement"} for line in source_rows], [], [], [], {})
    monkeypatch.setattr(companion, "extract_html_filing", extracted)
    guidance, matched, warnings = companion.matching_html_guidance(path, ["\n".join(source_rows)])
    assert guidance and matched == str(html) and not warnings
    assert not companion.matching_html_guidance(path, ["Revenue 999 888\nNet income 66 55"])[0]
    (tmp_path / "fund.htm").touch()
    guidance, matched, warnings = companion.matching_html_guidance(path, ["\n".join(source_rows)])
    assert not guidance and not matched
    assert any("Multiple HTML" in warning for warning in warnings)


def test_guide_identity_is_not_dominated_by_wrapped_schedule_rows(tmp_path, monkeypatch):
    import financial_statement_extract.html_guidance as companion
    html = tmp_path / "fund.html"
    html.touch()
    source_rows = ["Revenue 100 90", "Net income 10 9", "Gross profit 50 40"]
    rows = [{"raw_text": line, "statement_type_hint": "IncomeStatement"} for line in source_rows]
    rows += [{"raw_text": f"Company {i} 100 90", "statement_type_hint": "ScheduleOfInvestments"} for i in range(200)]
    monkeypatch.setattr(companion, "extract_html_filing", lambda path: (rows, [], [], [], {}))
    assert companion.matching_html_guidance(tmp_path / "fund.pdf", ["\n".join(source_rows)])[1] == str(html)
