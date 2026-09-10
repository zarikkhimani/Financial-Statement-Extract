from statements import parse_financial_statements


def test_two_year_cash_flow_does_not_invent_third_year():
    text = """Example Company
Statements of Cash Flows
Years Ended December 31, 2026 2025
Operating Activities
Net income 100 90
Net increase in cash and cash equivalents 20 10
Cash and cash equivalents at beginning of period 30 20
Cash and cash equivalents at end of period 50 30
"""
    statements, cells, issues, unmapped = parse_financial_statements(text)
    df = statements["CashFlowStatement"]
    assert df.attrs["period_labels"] == ["2026", "2025"]
    assert "2024" not in df.columns


def test_three_year_statement_reads_three_source_years():
    text = """Example Company
Income Statements
Years Ended December 31, 2026 2025 2024
Revenue 300 250 200
Net income 30 20 10
"""
    statements, *_ = parse_financial_statements(text)
    df = statements["IncomeStatement"]
    assert df.attrs["period_labels"] == ["2026", "2025", "2024"]


def test_interim_statement_preserves_repeated_year_columns_and_sec_company_name():
    text = """Table of Contents
Part I. FINANCIAL INFORMATION
Item 1. Financial Statements
CONSOLIDATED STATEMENTS OF COMPREHENSIVE INCOME (unaudited)
Comerica Incorporated and Subsidiaries
Three Months Ended June 30, Six Months Ended June 30,
(in millions) 2025 2024 2025 2024
Interest income 30 28 60 55
Net income 15 14 30 27
"""
    statements, *_ = parse_financial_statements(text)
    df = statements["IncomeStatement"]

    assert df.attrs["company_name"] == "Comerica Incorporated and Subsidiaries"
    assert df.attrs["period_labels"] == [
        "Three Months Ended June 30, 2025",
        "Three Months Ended June 30, 2024",
        "Six Months Ended June 30, 2025",
        "Six Months Ended June 30, 2024",
    ]
    net_income = df[df["RawItem"] == "Net income"].iloc[0]
    assert list(net_income[df.attrs["period_labels"]]) == [15, 14, 30, 27]


def test_missing_period_header_causes_no_invention():
    text = """Example Company
Income Statements
Revenue 300 250
Net income 30 20
"""
    statements, cells, issues, unmapped = parse_financial_statements(text)
    assert "IncomeStatement" not in statements
    assert any(row["Check"] == "Statement period detection" and row["Status"] == "FAIL" for row in issues)


def test_private_equity_partner_capital_statement_supported():
    text = """Example Fund LP
Statement of Changes in Partners' Capital
Years Ended December 31, 2026 2025
Capital contributions 100 80
Distributions (20) (10)
Ending balance 500 420
"""
    statements, *_ = parse_financial_statements(text)
    assert "PartnersCapital" in statements
    assert "Capital Contributions" in set(statements["PartnersCapital"]["StandardItem"])


def test_schedule_of_investments_uses_cost_and_fair_value_columns():
    text = """Example Fund LP
Schedule of Investments
December 31, 2026
Cost Fair Value
Company A 100 120
Company B 50 45
"""
    statements, *_ = parse_financial_statements(text)
    df = statements["ScheduleOfInvestments"]
    assert df.attrs["period_labels"] == ["Cost", "Fair Value"]
    assert list(df["StandardItem"]) == ["Company A", "Company B"]
    assert list(df["Fair Value"]) == [120.0, 45.0]


def test_section_header_is_not_merged_into_line_item():
    text = """Example Company
Income Statements
Years Ended December 31, 2026 2025
Other income (expense):
Interest expense (10) (8)
Net income 90 80
"""
    statements, *_ = parse_financial_statements(text)
    df = statements["IncomeStatement"]

    assert "Other income (expense)" in set(df.loc[df["RowType"] == "Section", "RawItem"])
    interest = df[df["RawItem"] == "Interest expense"].iloc[0]
    assert interest["2026"] == -10
    assert interest["2025"] == -8


def test_equity_row_with_years_in_description_is_not_dropped():
    text = """Example Company
Balance Sheets
As of December 31,
2026 2025
Assets
Cash and cash equivalents 100 90
Total assets 100 90
Liabilities and Stockholders' Equity
Stockholders' equity:
Common stock, shares outstanding at December 31, 2026 and December 31, 2025 60 50
Total stockholders' equity 60 50
Total liabilities and stockholders' equity 100 90
"""
    statements, *_ = parse_financial_statements(text)
    df = statements["BalanceSheet"]

    common_stock = df[df["RawItem"].str.startswith("Common stock", na=False)]
    assert len(common_stock) == 1
    periods = df.attrs["period_labels"]
    assert common_stock.iloc[0][periods[0]] == 60
    assert common_stock.iloc[0][periods[1]] == 50

def test_statement_of_income_loss_title_is_supported():
    text = """Telesat Corporation
Consolidated Statements of Income (Loss)
For the years ended December 31,
(in thousands of Canadian dollars) Notes 2022 2021 2020
(Note 3) (Note 3)
Revenue 759169 758212 820468
Net income (loss) (80117) 155025 244820
(80117) 155025 244820
Net income (loss) per common share
Basic (1.90) 1.89 4.95
"""
    statements, *_ = parse_financial_statements(text)
    df = statements["IncomeStatement"]
    assert df.attrs["period_labels"] == ["2022", "2021", "2020"]
    assert df.attrs["raw_unit_note"] == "(in thousands of Canadian dollars)"
    assert "Revenue" in set(df["StandardItem"])
    assert not any(str(label).startswith("(Note") or str(label).startswith("(80117)") for label in df["RawItem"])


def test_formation_date_is_not_an_extra_reporting_period():
    text = """VistaOne, L.P.
Consolidated Statements of Operations
Period from
September 30, 2024
Year Ended (Date of Formation) to
December 31, 2025 December 31, 2024
Interest income 7546772 -
Net investment loss (41851656) -
"""
    statements, *_ = parse_financial_statements(text)
    df = statements["IncomeStatement"]
    assert df.attrs["period_labels"] == ["December 31, 2025", "December 31, 2024"]
    assert len(df[df["RowType"] == "Data"]) == 2


def test_sec_browser_header_is_not_used_as_company_name():
    text = """8/16/23, 6:38 PM sec.gov/Archives/example.htm
Table of Contents
Telesat Corporation
Consolidated Balance Sheets
December 31, 2022 December 31, 2021
Assets
Cash and cash equivalents 100 90
Total assets 100 90
"""
    statements, *_ = parse_financial_statements(text)
    assert statements["BalanceSheet"].attrs["company_name"] == "Telesat Corporation"

def test_section_label_without_colon_is_not_merged_into_first_line_item():
    text = """Example Fund
Statements of Operations
Years Ended December 31, 2026 2025
Investment Income
Interest income 10 9
Expenses
Professional fees 2 1
"""
    statements, *_ = parse_financial_statements(text)
    df = statements["IncomeStatement"]
    assert {"Investment Income", "Expenses"}.issubset(set(df.loc[df["RowType"] == "Section", "RawItem"]))
    assert {"Interest income", "Professional fees"}.issubset(set(df.loc[df["RowType"] == "Data", "RawItem"]))


def test_wrapped_equity_description_with_dates_remains_one_row():
    text = """Example Fund
Consolidated Statements of Assets and Liabilities
December 31, 2025 December 31, 2024
Assets
Cash and cash equivalents 100 90
Total Assets 100 90
Net Assets Consist of
Limited partnership units - Class A-B, unlimited units authorized (8,305,934 and
0 units issued and outstanding as of December 31, 2025 and December 31, 2024,
respectively) 247849398 -
Net Assets 247849398 100000
"""
    statements, *_ = parse_financial_statements(text)
    df = statements["BalanceSheet"]
    unit_rows = df[df["RawItem"].str.startswith("Limited partnership units", na=False)]
    assert len(unit_rows) == 1
    assert unit_rows.iloc[0]["December 31, 2025"] == 247849398
    assert not any(str(label).strip().lower() == "respectively)" for label in df["RawItem"])

def test_liabilities_and_equity_sections_are_not_merged_into_accounts_payable():
    text = """Example Company
Consolidated Balance Sheets
December 31,
2026 2025
Assets
Cash and cash equivalents 100 90
Total assets 100 90
Liabilities and equity
Current liabilities
Accounts payable 30 20
Total liabilities and equity 100 90
"""
    statements, *_ = parse_financial_statements(text)
    df = statements["BalanceSheet"]

    assert {"Liabilities and equity", "Current liabilities"}.issubset(
        set(df.loc[df["RowType"] == "Section", "RawItem"])
    )
    assert "Accounts payable" in set(df.loc[df["RowType"] == "Data", "RawItem"])


def test_unlabeled_balance_sheet_totals_are_preserved_from_source_values():
    text = """Example Company
Consolidated Balance Sheets
December 31,
2026 2025
ASSETS
Current assets
Cash and cash equivalents 60 50
Accounts receivable 40 30
100 80
Property and equipment, net 400 370
500 450
LIABILITIES AND STOCKHOLDERS' EQUITY
Current liabilities
Accounts payable 100 90
100 90
Long-term debt 200 190
300 280
Stockholders' equity
Retained earnings 200 170
200 170
500 450
"""
    statements, *_ = parse_financial_statements(text)
    df = statements["BalanceSheet"]

    expected = {
        "Total Current Assets": (100, 80),
        "Total Assets": (500, 450),
        "Total Current Liabilities": (100, 90),
        "Total Liabilities": (300, 280),
        "Total Equity": (200, 170),
        "Total Liabilities and Equity": (500, 450),
    }
    for standard_item, values in expected.items():
        row = df[df["StandardItem"] == standard_item].iloc[0]
        assert (row["2026"], row["2025"]) == values


def test_stockholders_equity_heading_ends_income_statement_without_output_tab():
    text = """Example Company
Consolidated Statements of Operations and Comprehensive Income
Years Ended December 31, 2026 2025
Revenue 300 250
Net income 30 20
Consolidated Statements of Stockholders' Equity
Years Ended December 31, 2026 2025
Opening balance 100 90
Net income 30 20
Ending balance 120 110
"""
    statements, *_ = parse_financial_statements(text)

    assert set(statements) == {"IncomeStatement"}
    income = statements["IncomeStatement"]
    assert list(income.loc[income["RowType"] == "Data", "RawItem"]) == ["Revenue", "Net income"]
