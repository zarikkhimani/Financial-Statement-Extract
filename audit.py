from __future__ import annotations

import re
from typing import Optional

import pandas as pd


def _period_columns(df: pd.DataFrame) -> list[str]:
    fixed = {"RowType", "Category", "SubCategory", "RawItem", "StandardItem", "MappingConfidence", "MappingRule", "Context", "Note", "SourcePage", "SourceLine"}
    return [c for c in df.columns if c not in fixed]


def _series_value(df: pd.DataFrame, item: str, period: str) -> Optional[float]:
    if df.empty or "StandardItem" not in df.columns or period not in df.columns:
        return None
    rows = df[df["StandardItem"].astype(str).str.strip().str.lower() == item.lower()]
    if rows.empty:
        return None
    value = pd.to_numeric(rows.iloc[0][period], errors="coerce")
    return None if pd.isna(value) else float(value)


def _tolerance(*values: Optional[float]) -> float:
    finite = [abs(v) for v in values if v is not None]
    base = max(finite) if finite else 0.0
    return max(1.0, base * 1e-6)


def _year(label: str) -> str:
    match = re.search(r"\b(?:19|20)\d{2}\b", str(label))
    return match.group(0) if match else str(label)


def _status_from_diff(diff: float, tol: float) -> str:
    return "PASS" if abs(diff) <= tol else "FAIL"


def audit_balance_sheet(df: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for period in _period_columns(df):
        assets = _series_value(df, "Total Assets", period)
        reported_le = _series_value(df, "Total Liabilities and Equity", period)
        liabilities = _series_value(df, "Total Liabilities", period)
        equity = _series_value(df, "Total Equity", period)

        if assets is None:
            rows.append({"Check": "Balance sheet equation", "Scope": period, "Status": "NOT_TESTED", "Detail": "Total Assets not extracted."})
            continue

        if reported_le is not None:
            diff = assets - reported_le
            tol = _tolerance(assets, reported_le)
            rows.append({"Check": "Assets = reported liabilities + equity", "Scope": period, "Status": _status_from_diff(diff, tol), "Detail": f"Difference={diff:.6g}; tolerance={tol:.6g}."})
        elif liabilities is not None and equity is not None:
            calc = liabilities + equity
            diff = assets - calc
            tol = _tolerance(assets, calc)
            rows.append({"Check": "Assets = liabilities + equity", "Scope": period, "Status": _status_from_diff(diff, tol), "Detail": f"Difference={diff:.6g}; tolerance={tol:.6g}."})
        else:
            rows.append({"Check": "Balance sheet equation", "Scope": period, "Status": "NOT_TESTED", "Detail": "Need Total Liabilities and Equity, or both Total Liabilities and Total Equity."})

        for context, total_item, check_name in (
            ("CURRENT_ASSET", "Total Current Assets", "Current asset subtotal"),
            ("CURRENT_LIABILITY", "Total Current Liabilities", "Current liability subtotal"),
        ):
            total = _series_value(df, total_item, period)
            if total is None:
                rows.append({"Check": check_name, "Scope": period, "Status": "NOT_TESTED", "Detail": f"{total_item} not extracted."})
                continue
            components = df[(df["Context"] == context) & (df["StandardItem"] != total_item)]
            values = pd.to_numeric(components[period], errors="coerce").dropna()
            if len(values) < 2:
                rows.append({"Check": check_name, "Scope": period, "Status": "NOT_TESTED", "Detail": "Fewer than two component rows available."})
                continue
            calc = float(values.sum())
            diff = total - calc
            tol = _tolerance(total, calc)
            rows.append({"Check": check_name, "Scope": period, "Status": _status_from_diff(diff, tol), "Detail": f"Reported={total:.6g}; extracted components={calc:.6g}; difference={diff:.6g}."})
    return rows


def audit_cash_flow(df: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for period in _period_columns(df):
        begin = _series_value(df, "Cash and Cash Equivalents at Beginning of Period", period)
        change = _series_value(df, "Net Increase (Decrease) in Cash and Cash Equivalents", period)
        end = _series_value(df, "Cash and Cash Equivalents at End of Period", period)
        if begin is None or change is None or end is None:
            rows.append({"Check": "Cash rollforward", "Scope": period, "Status": "NOT_TESTED", "Detail": "Beginning cash, net change, and ending cash are all required."})
            continue
        diff = begin + change - end
        tol = _tolerance(begin, change, end)
        rows.append({"Check": "Beginning cash + change = ending cash", "Scope": period, "Status": _status_from_diff(diff, tol), "Detail": f"Difference={diff:.6g}; tolerance={tol:.6g}."})
    return rows


def audit_duplicates(statements: dict[str, pd.DataFrame]) -> list[dict]:
    rows: list[dict] = []
    for statement_type, df in statements.items():
        if df.empty or "StandardItem" not in df.columns:
            continue
        mapped = df[(df["MappingRule"] != "unmapped") & (df["MappingRule"] != "section") & df["StandardItem"].astype(str).str.strip().ne("")]
        counts = mapped["StandardItem"].value_counts()
        for item, count in counts[counts > 1].items():
            rows.append({"Check": "Duplicate mapped concept", "Scope": statement_type, "Status": "WARN", "Detail": f"'{item}' appears {int(count)} times."})
    return rows


def audit_cross_statement(statements: dict[str, pd.DataFrame]) -> list[dict]:
    rows: list[dict] = []
    bs = statements.get("BalanceSheet")
    cf = statements.get("CashFlowStatement")
    is_df = statements.get("IncomeStatement")

    if bs is not None and cf is not None and not bs.empty and not cf.empty:
        bs_map = {_year(p): p for p in _period_columns(bs)}
        cf_map = {_year(p): p for p in _period_columns(cf)}
        for yr in sorted(set(bs_map) & set(cf_map), reverse=True):
            bs_cash = _series_value(bs, "Cash and Cash Equivalents", bs_map[yr])
            if bs_cash is None:
                bs_cash = _series_value(bs, "Cash", bs_map[yr])
            cf_cash = _series_value(cf, "Cash and Cash Equivalents at End of Period", cf_map[yr])
            if bs_cash is None or cf_cash is None:
                rows.append({"Check": "CF ending cash = BS cash", "Scope": yr, "Status": "NOT_TESTED", "Detail": "Required cash line missing in one statement."})
                continue
            diff = bs_cash - cf_cash
            tol = _tolerance(bs_cash, cf_cash)
            rows.append({"Check": "CF ending cash = BS cash", "Scope": yr, "Status": _status_from_diff(diff, tol), "Detail": f"Difference={diff:.6g}; tolerance={tol:.6g}."})

    if is_df is not None and cf is not None and not is_df.empty and not cf.empty:
        is_map = {_year(p): p for p in _period_columns(is_df)}
        cf_map = {_year(p): p for p in _period_columns(cf)}
        for yr in sorted(set(is_map) & set(cf_map), reverse=True):
            is_ni = _series_value(is_df, "Net Income (Loss)", is_map[yr])
            cf_ni = _series_value(cf, "Net Income (Loss)", cf_map[yr])
            if is_ni is None or cf_ni is None:
                rows.append({"Check": "IS net income = CF net income", "Scope": yr, "Status": "NOT_TESTED", "Detail": "Net income line missing in one statement."})
                continue
            diff = is_ni - cf_ni
            tol = _tolerance(is_ni, cf_ni)
            rows.append({"Check": "IS net income = CF net income", "Scope": yr, "Status": _status_from_diff(diff, tol), "Detail": f"Difference={diff:.6g}; tolerance={tol:.6g}."})
    return rows


def audit_units(statements: dict[str, pd.DataFrame]) -> list[dict]:
    units = {}
    for name, df in statements.items():
        if not df.empty:
            units[name] = (df.attrs.get("unit_label", "reported units"), df.attrs.get("currency", ""))
    known = {v for v in units.values() if v[0] != "reported units" or v[1]}
    detail = "; ".join(f"{k}={v[0]} {v[1]}".strip() for k, v in units.items()) or "No parsed statements."
    if len(known) <= 1:
        return [{"Check": "Statement unit consistency", "Scope": "All statements", "Status": "PASS" if units else "NOT_TESTED", "Detail": detail}]
    return [{"Check": "Statement unit consistency", "Scope": "All statements", "Status": "WARN", "Detail": detail}]


def run_financial_audits(statements: dict[str, pd.DataFrame], parser_issues: list[dict]) -> list[dict]:
    rows = list(parser_issues)
    bs = statements.get("BalanceSheet")
    cf = statements.get("CashFlowStatement")
    if bs is not None and not bs.empty:
        rows.extend(audit_balance_sheet(bs))
    if cf is not None and not cf.empty:
        rows.extend(audit_cash_flow(cf))
    rows.extend(audit_cross_statement(statements))
    rows.extend(audit_duplicates(statements))
    rows.extend(audit_units(statements))
    return rows
