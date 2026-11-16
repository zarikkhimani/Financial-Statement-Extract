import pytest

from financial_statement_extract.detection import detect_statement_plan
from financial_statement_extract.pdf_detection import statement_rows_from_plan
from structure import detect_statement_heading_type, infer_company_name


@pytest.mark.parametrize(("title", "kind"), [
    ("consolidated balance sheets", "BalanceSheet"),
    ("consolidated statements\nof earnings", "IncomeStatement"),
    ("consolidated statements of\ncomprehensive income", "IncomeStatement"),
    ("consolidated statements\nof equity", "StockholdersEquityStatement"),
    ("consolidated statements of\ncash flows", "CashFlowStatement"),
])
def test_issuer_prefixed_heading_keeps_source_title_and_statement_ownership(title, kind):
    heading = "Example & Company and subsidiaries " + title
    text = heading + "\n2024 2023\nNet earnings 100 90\nCash at end of year 200 180"
    assert detect_statement_heading_type(heading) == kind
    plan = detect_statement_plan([text])
    assert plan.selected_pages == (1,)
    assert plan.pages[0].source_title == heading
    assert plan.pages[0].statement_type == kind
    rows = [{"source_page": 1, "raw_text": line} for line in text.splitlines()]
    assert infer_company_name(rows) == "Example & Company"
    hinted = statement_rows_from_plan(rows, plan)
    assert all(row["source_title"] == heading for row in hinted)
    assert all(row["statement_type_hint"] == kind for row in hinted)


@pytest.mark.parametrize("text", [
    "Refer to Example & Company and subsidiaries consolidated balance sheets",
    "The accompanying Example & Company and subsidiaries consolidated balance sheets",
    "Example & Company and subsidiaries consolidated balance sheets 44",
    "Example & Company and subsidiaries consolidated balance sheets show total assets",
])
def test_issuer_prefix_does_not_turn_prose_or_toc_entries_into_headings(text):
    assert detect_statement_heading_type(text) is None
