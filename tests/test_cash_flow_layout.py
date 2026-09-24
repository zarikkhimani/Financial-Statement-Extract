from copy import deepcopy

from openpyxl import load_workbook
import pandas as pd
import pytest

from excel_writer import _write_statement_sheet
from financial_statement_extract.cash_flow_layout import recover_cash_flow_tables
from models import StatementPage, StatementPagePlan


PAGE_1 = """Example Fund
Consolidated Statements of Cash Flows
(In thousands)
Nine months ended June 30,
2026 2025
Cash flows from operating activities
Net income $ 80 $ 70
Changes in operating assets and liabilities:
Interest payable 10 0
Interest payable 10 0
Net cash provided by operating activities 100 70
Cash flows from financing activities
Distributions paid (20) (30)
Cash, end of period $ 80 $ 40
Supplemental disclosure of cash flow information:
"""
PAGE_2 = """Example Fund
Consolidated Statements of Cash Flows (continued)
(In thousands)
Nine months ended June 30,
2026 2025
Cash paid for interest(1) $ 12 $ 14
Distributions declared 20 35
Supplemental disclosure of non-cash financing activities:
Stock issued through dividend reinvestment $ — $ 5
(1) Cash interest includes contractual swaps.
The following table reconciles cash balances:
As of
June 30, 2026 September 30, 2025
Cash $ 70 $ 25
Restricted cash 10 15
Total cash shown in the
Consolidated Statements of Cash Flows(1) $ 80 $ 40
(1) See Note 2 for cash policies.
See Notes to Consolidated Financial Statements.
Notes to Financial Statements
As of
June 30, 2026 September 30, 2025
Unrelated note table 999 888
"""


def source_and_plan(texts=(PAGE_1, PAGE_2)):
    rows = [dict(source_page=p, line_no=i, raw_text=text) for p, page in enumerate(texts, 1)
            for i, text in enumerate(page.splitlines(), 1)]
    numbers = tuple(range(1, len(texts)+1))
    pages = tuple(StatementPage(p, "data", "CashFlowStatement", "Consolidated Statements of Cash Flows")
                  for p in numbers)
    return rows, StatementPagePlan("source.pdf", "manual", numbers, numbers, numbers, pages)


def candidate(rows, page=2):
    return dict(table_id=f"raw-{page}", source_page=page, source_order=1, flavor="stream",
                statement_type="CashFlowStatement", rows=rows, spans=[], source_context=[])


def test_recovery_includes_supplemental_rows_and_separate_reconciliation_periods():
    source, plan = source_and_plan()
    original = [candidate([["Cash", "$", "70", "$", "25"], ["Restricted cash", "", "10", "", "15"],
                           ["(1)", "$", "80", "$", "40"]])]
    before = deepcopy(original)
    source_before = deepcopy(source)
    tables, issues = recover_cash_flow_tables(original, source, plan)
    assert len(tables) == 3
    assert [t['period_labels'] for t in tables] == [
        ['Nine months ended June 30, 2026', 'Nine months ended June 30, 2025'],
        ['Nine months ended June 30, 2026', 'Nine months ended June 30, 2025'],
        ['June 30, 2026', 'September 30, 2025']]
    assert ["Stock issued through dividend reinvestment", "$ —", "$ 5"] in tables[1]["rows"]
    assert ["Total cash shown in the Consolidated Statements of Cash Flows(1)", "$ 80", "$ 40"] in tables[2]["rows"]
    assert all("Unrelated note" not in row[0] for table in tables for row in table['rows'])
    assert tables[0]['rows'].count(['Interest payable', '10', '0']) == 2
    total_index = next(i for i, row in enumerate(tables[2]['rows']) if row[0].startswith('Total cash'))
    assert tables[2]['row_sources'][total_index] == [{'source_page': 2, 'line_no': 16}, {'source_page': 2, 'line_no': 17}]
    assert all(issue['Status'] == 'INFO' for issue in issues)
    assert original == before and source == source_before


@pytest.mark.parametrize('bad_row', [['Cash', '71', '25'], ['Cash', '70', '0']])
def test_conflicting_selected_table_amounts_retain_originals_with_explicit_warning(bad_row):
    source, plan = source_and_plan()
    tables = [candidate([bad_row])]
    actual, issues = recover_cash_flow_tables(tables, source, plan)
    assert actual == tables
    assert len(issues) == 1 and issues[0]['Status'] == 'WARN'
    assert 'preserve every selected table amount' in issues[0]['Detail']


def test_missing_periods_do_not_attach_supplemental_rows_to_reconciliation_dates():
    source, plan = source_and_plan((PAGE_2.replace('Nine months ended June 30,\n2026 2025\n', ''),))
    original = [candidate([['Cash', '70', '25']], page=1)]
    tables, issues = recover_cash_flow_tables(original, source, plan)
    assert tables == original
    assert 'precede the first usable period heading' in issues[0]['Detail']


def test_no_usable_headers_warns_and_does_not_partially_replace_the_statement():
    source, plan = source_and_plan((PAGE_1, 'Cash paid 12 14'))
    original = [candidate([['Cash', '70', '25']])]
    tables, issues = recover_cash_flow_tables(original, source, plan)
    assert tables == original
    assert len(issues) == 1 and issues[0]['Status'] == 'WARN'


def test_extra_values_cannot_be_silently_folded_into_the_label():
    source, plan = source_and_plan((PAGE_1.replace('Net income $ 80 $ 70', 'Net income 90 80 70'),))
    tables, issues = recover_cash_flow_tables([], source, plan)
    assert tables == []
    assert 'More cash-flow values' in issues[0]['Detail']


def test_wrapped_values_that_look_like_years_are_not_new_period_headers():
    source, plan = source_and_plan((PAGE_1.replace('Net income $ 80 $ 70', 'Net income\n2026 2025'),))
    tables, issues = recover_cash_flow_tables([], source, plan)
    assert len(tables) == 1
    assert ['Net income', '2026', '2025'] in tables[0]['rows']
    assert all(issue['Status'] == 'INFO' for issue in issues)


def test_incomplete_numeric_row_is_not_silently_rendered_as_a_note():
    source, plan = source_and_plan((PAGE_1 + 'Unresolved payment 19\n',))
    tables, issues = recover_cash_flow_tables([], source, plan)
    assert tables == []
    assert issues[0]['Status'] == 'WARN'
    assert 'unresolved trailing values' in issues[0]['Detail']


def test_missing_values_remain_missing_and_overlap_candidates_do_not_multiply_rows():
    source, plan = source_and_plan()
    table = candidate([['Stock issued through dividend reinvestment', '—', '5']])
    tables, issues = recover_cash_flow_tables([table, {**table, 'table_id': 'duplicate'}], source, plan)
    assert sum(row[0].startswith('Stock issued') for t in tables for row in t['rows']) == 1
    assert all(issue['Status'] == 'INFO' for issue in issues)


def test_genuine_duplicate_rows_in_candidate_require_equal_source_multiplicity():
    source, plan = source_and_plan()
    original = [candidate([['Cash', '70', '25'], ['Cash', '70', '25']])]
    tables, issues = recover_cash_flow_tables(original, source, plan)
    assert tables == original and issues[0]['Status'] == 'WARN'


def test_html_without_pdf_page_plan_is_unchanged():
    original = [candidate([['Cash', '70', '25']])]
    actual, issues = recover_cash_flow_tables(original, [], None)
    assert actual is original and not issues


def test_saved_workbook_has_local_dates_missing_amounts_and_emphasized_totals(tmp_path):
    source, plan = source_and_plan((PAGE_1, PAGE_2.replace('Cash paid for interest(1)',
                                  'Supplemental interest rates 1.5% 2.0%\nCash paid for interest(1)')))
    tables, _ = recover_cash_flow_tables([], source, plan)
    frame = pd.DataFrame()
    frame.attrs.update(source_tables=tables, company_name='Example Fund',
                       statement_title='Consolidated Statements of Cash Flows')
    path = tmp_path / 'cash.xlsx'
    with pd.ExcelWriter(path, engine='xlsxwriter') as writer:
        _write_statement_sheet(writer, 'CashFlowStatement', frame)
    book = load_workbook(path)
    sheet = book['Cash Flow']
    assert sheet.freeze_panes is None
    rows = {row[0].value: row for row in sheet.iter_rows(min_col=3) if row[0].value}
    stock = rows['Stock issued through dividend reinvestment']
    assert stock[1].value == '—' and stock[2].value == 5
    assert stock[2].data_type == 'n'
    total = rows['Total cash shown in the Consolidated Statements of Cash Flows(1)']
    assert [c.value for c in total[1:]] == [80, 40]
    assert all(c.font.bold and c.border.top.style for c in total)
    assert rows['Interest payable'][2].value == 0
    rates = rows['Supplemental interest rates']
    assert rates[1].value == 0.015 and '%' in rates[1].number_format
    heads = [(row[0].row, row[1].value, row[2].value) for row in sheet.iter_rows(min_col=3)
             if row[1].value in ('Nine months ended June 30, 2026', 'June 30, 2026')]
    assert len(heads) == 3
    assert heads[1][0] < stock[0].row < heads[2][0] < total[0].row
    assert heads[2][1:] == ('June 30, 2026', 'September 30, 2025')
    assert sheet.max_column == 5
    book.close()
