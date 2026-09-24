import pytest

from financial_statement_extract.pdfplumber_experimental import _expand_amounts


@pytest.mark.parametrize("source,expected", [
    ("Balance at June 30, 2025 123 (456)", ["Balance at June 30, 2025", "123", "(456)"]),
    ("June 30 2025 123", ["June 30 2025", "123"]),
    ("June 30, 2025", ["June 30, 2025"]),
    ("JUN. 30, 2025 $123 \u2014 (234)", ["JUN. 30, 2025", "$123", "\u2014", "(234)"]),
    ("Feburary 28, 2025 50 60", ["Feburary 28, 2025", "50", "60"]),
    ("June 30,2025 123", ["June", "30,2025", "123"]),
    ("June 30 2025.50 123", ["June 30", "2025.50", "123"]),
    ("June 30 20250 123", ["June 30", "20250", "123"]),
    ("June 30 $2025 123", ["June 30", "$2025", "123"]),
    ("June 32 2025 123", ["June", "32", "2025", "123"]),
    ("January 31 123 456", ["January 31", "123", "456"]),
    ("Assets $   7234 $60", ["Assets", "$7234", "$60"]),
    ("123 \u2014 123", ["123", "\u2014", "123"]),
    ("(234) (123)", ["(234)", "(123)"]),
    ("123 (234)", ["123", "(234)"]),
    ("$123 (234)", ["$123", "(234)"]),
    ("$123,456 $124,56", ["$123,456", "$124,56"]),
])
def test_date_protection_and_amount_splitting(source, expected):
    assert _expand_amounts([source]) == expected
