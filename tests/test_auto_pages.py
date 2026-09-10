from extractors import format_page_numbers, select_auto_statement_pages


def test_auto_pages_find_core_statements_and_cash_flow_continuation():
    page_texts = [
        """Table of Contents
Consolidated Statements of Earnings 56
Consolidated Balance Sheets 58
Consolidated Statements of Cash Flows 59
""",
        """Example Company
Consolidated Statements of Earnings
Years Ended December 31, 2026 2025
Revenue 300 —
Operating income 80 —
Net earnings 60 —
Basic earnings per share 1.00 —
Diluted earnings per share 0.98 —
""",
        """Example Company
Consolidated Balance Sheets
December 31, 2026 2025
Cash and cash equivalents 100 90
Total assets 500 450
Total liabilities 300 280
Total equity 200 170
Total liabilities and equity 500 450
""",
        """Example Company
Consolidated Statements of Cash Flows
Years Ended December 31, 2026 2025
Net income 60 50
Depreciation 20 18
Net cash from operating activities 80 68
Capital expenditures (30) (25)
Net cash used in investing activities (30) (25)
""",
        """Net cash from financing activities 10 7
Effect of exchange rates on cash 1 0
Cash and cash equivalents, beginning of year 39 40
Cash and cash equivalents, end of year 100 90
""",
        "Management discussion without a statement table.",
    ]

    assert select_auto_statement_pages(page_texts) == [2, 3, 4, 5]


def test_page_numbers_are_compacted_for_the_extraction_pipeline():
    assert format_page_numbers([2, 3, 4, 5, 7, 9, 10]) == "2-5,7,9-10"


def test_auto_pages_handle_combined_income_title_and_skip_equity_rollforward():
    page_texts = [
        """Example Company
Consolidated Balance Sheets
December 31, 2026 2025
Cash and cash equivalents 100 90
Accounts receivable 50 40
Accounts payable 30 20
Retained earnings 120 110
$ 150 $ 130
""",
        """Example Company
Consolidated Statements of Operations and Comprehensive Income
Years Ended December 31, 2026 2025
Revenue 300 250
Gross profit 120 100
Net income 30 20
Basic earnings per share 1.50 1.10
Diluted earnings per share 1.49 1.09
""",
        """Example Company
Consolidated Statements of Stockholders' Equity
Years Ended December 31, 2026 2025
Opening balance 100 90
Net income 30 20
Share repurchases (10) (5)
Ending balance 120 105
""",
        """Example Company
Consolidated Statements of Cash Flows
Years Ended December 31, 2026 2025
Net income 30 20
Depreciation 10 8
Net cash provided by operating activities 40 28
Cash and cash equivalents, beginning of year 60 42
Cash and cash equivalents, end of year 100 70
""",
    ]

    assert select_auto_statement_pages(page_texts) == [1, 2, 4]


def test_auto_pages_accept_unaudited_headings_and_ignore_note_sentence_references():
    page_texts = [
        """Example Bank
Consolidated Balance Sheets
June 30, 2025 December 31, 2024
Cash 100 90
Loans 400 380
Total assets 500 470
Total liabilities 300 290
Total liabilities and shareholders' equity 500 470
""",
        """Example Bank
Consolidated Statements of Comprehensive Income (unaudited)
Three Months Ended June 30, Six Months Ended June 30,
2025 2024 2025 2024
Interest income 30 28 60 55
Interest expense 10 9 20 18
Net income 15 14 30 27
Basic earnings per share 1.00 .90 2.00 1.80
Diluted earnings per share .99 .89 1.98 1.78
""",
        """Example Bank
Consolidated Statements of Cash Flows (unaudited)
Six Months Ended June 30,
2025 2024
Net income 30 27
Depreciation 4 3
Net cash from operating activities 34 30
Cash and cash equivalents at beginning of period 50 40
Cash and cash equivalents at end of period 84 70
""",
        """Notes to Consolidated Financial Statements
The following table summarizes amounts reported in the company's
Consolidated Statements of Comprehensive Income.
Three Months Ended June 30, Six Months Ended June 30,
2025 2024 2025 2024
Tax expense 3 2 6 4
Tax credits 1 1 2 2
Other benefit 1 1 2 2
Total tax 1 0 2 0
""",
    ]

    assert select_auto_statement_pages(page_texts) == [1, 2, 3]
