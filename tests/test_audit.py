import pandas as pd

from audit import run_financial_audits


def _df(rows):
    return pd.DataFrame(rows)


def test_balance_sheet_reconciles():
    bs = _df([
        {"StandardItem": "Total Assets", "MappingRule": "exact_alias", "Context": "ASSET", "2026": 100.0},
        {"StandardItem": "Total Liabilities", "MappingRule": "exact_alias", "Context": "LIABILITY", "2026": 60.0},
        {"StandardItem": "Total Equity", "MappingRule": "exact_alias", "Context": "EQUITY", "2026": 40.0},
    ])
    bs.attrs["unit_label"] = "millions"
    audits = run_financial_audits({"BalanceSheet": bs}, [])
    matches = [x for x in audits if x["Check"] == "Assets = liabilities + equity"]
    assert matches and matches[0]["Status"] == "PASS"


def test_missing_total_is_not_treated_as_zero():
    bs = _df([
        {"StandardItem": "Accounts Receivable, Net", "MappingRule": "exact_alias", "Context": "CURRENT_ASSET", "2026": 100.0},
    ])
    audits = run_financial_audits({"BalanceSheet": bs}, [])
    eq = [x for x in audits if x["Check"] == "Balance sheet equation"]
    assert eq and eq[0]["Status"] == "NOT_TESTED"
