from __future__ import annotations

import re
from typing import Iterable

import pandas as pd

from config import SECTION_HINTS
from mapper import map_concept
from normalization import normalize_financial_text, parse_numeric_token
from structure import (
    DATE_RE,
    detect_partners_capital_value_headers,
    detect_period_labels,
    detect_schedule_value_headers,
    detect_statement_type,
    detect_statement_unit_note,
    infer_company_name,
    section_hint_for_line,
    split_statement_sections,
)

# Source tokens only. Dashes remain missing-status tokens rather than zeros.
VALUE_TOKEN = r"(?:[$€£¥]\s*)?(?:\(\s*[-+]?\d[\d,]*(?:\.\d+)?\s*\)|[-+]?\d[\d,]*(?:\.\d+)?%?|[-+]?\d[\d,]*(?:\.\d+)?x|N/?A|N\.A\.?|NM|N\.M\.?|-|\u2013|\u2014|\u2212)"

BOUNDARY_ONLY_STATEMENT_TYPES = frozenset({"StockholdersEquityStatement"})


def _is_structural_header(text: str) -> bool:
    normalized = normalize_financial_text(text)
    cleaned = normalized.upper().rstrip(":")
    if normalized.endswith(":") and not re.search(r"\d", normalized):
        return True
    if cleaned in SECTION_HINTS:
        return True
    if any(cleaned.startswith(prefix) for prefix in (
        "CASH FLOWS FROM OPERATING ACTIVITIES",
        "CASH FLOWS FROM INVESTING ACTIVITIES",
        "CASH FLOWS FROM FINANCING ACTIVITIES",
        "LIABILITIES AND STOCKHOLDERS",
        "LIABILITIES AND SHAREHOLDERS",
        "LIABILITIES AND PARTNERS",
    )):
        return True
    if cleaned.startswith("CASH FLOWS ") and cleaned.endswith("ACTIVITIES"):
        return True
    if cleaned.startswith("ADJUSTMENTS TO RECONCILE") and "OPERATING ACTIVITIES" in cleaned:
        return True
    if cleaned.startswith("CHANGES IN OPERATING ASSETS AND LIABILITIES"):
        return True
    if cleaned.startswith("NET INCOME") and "PER COMMON SHARE" in cleaned and "SHAREHOLDER" in cleaned:
        return True
    if cleaned.startswith("TOTAL WEIGHTED AVERAGE COMMON SHARES") and "OUTSTANDING" in cleaned:
        return True
    if cleaned.startswith("COMMITMENTS AND CONTINGENCIES"):
        return True
    return False


def _is_non_data_header(text: str) -> bool:
    normalized = normalize_financial_text(text)
    low = normalized.lower()
    if not low:
        return True
    if detect_statement_type(text):
        return True
    if any(x in low for x in ("years ended", "year ended", "months ended", "quarters ended", "quarter ended", "period ended")):
        return True
    if low.startswith("as of "):
        return True
    if "sec.gov/" in low or low.startswith(("http://", "https://")):
        return True
    if re.fullmatch(r"(?:19|20)\d{2}(?:\s+(?:19|20)\d{2}){0,4}", normalized):
        return True
    if re.match(r"^(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+(?:19|20)\d{2}$", normalized, re.IGNORECASE):
        return True
    if len(DATE_RE.findall(normalized)) >= 2 and not DATE_RE.sub("", normalized).strip():
        return True
    if re.fullmatch(r"(?:\(\s*Note\s+\d+\s*\)\s*)+", normalized, re.IGNORECASE):
        return True
    if "fair value" in low and "cost" in low and not re.search(r"\d", low):
        return True
    if "fair value" in low and "net assets" in low and not re.search(r"\d", low):
        return True
    if len(re.findall(r"\bclass\s+[a-z0-9]+(?:-[a-z0-9]+)*\b", low)) >= 2:
        return True
    if len(re.findall(r"\bunits\b", low)) >= 2 and low.endswith("total"):
        return True
    if any(x in low for x in ("in thousands", "in millions", "in billions", "except per share", "unaudited")):
        return True
    return False


def _match_desc_first(line: str, n_periods: int):
    if n_periods <= 0:
        return None
    # A wrapped description can contain full dates (for example, an equity
    # authorization sentence ending in "as of December 31, 2025..."). Do not
    # mistake the day/year components for statement values unless a complete
    # set of values actually follows the final date.
    date_matches = list(DATE_RE.finditer(line))
    if date_matches:
        tail = line[date_matches[-1].end():].strip(" ,")
        tail_values = re.findall(VALUE_TOKEN, tail, flags=re.IGNORECASE)
        if len(tail_values) < n_periods:
            return None
    groups = r"\s+".join([f"({VALUE_TOKEN})" for _ in range(n_periods)])
    pattern = re.compile(rf"^(.*?)\s+{groups}\s*$", re.IGNORECASE)
    match = pattern.match(line)
    if not match:
        return None
    groups_out = match.groups()
    raw_values = list(groups_out[1:])
    if raw_values and all(re.fullmatch(r"(?:19|20)\d{2},?", value.strip()) for value in raw_values):
        if len(DATE_RE.findall(line)) >= len(raw_values):
            return None
    return groups_out[0].strip(), raw_values


def _match_value_first(line: str, n_periods: int):
    if n_periods <= 0:
        return None
    groups = r"\s+".join([f"({VALUE_TOKEN})" for _ in range(n_periods)])
    pattern = re.compile(rf"^{groups}\s+(.*?)\s*$", re.IGNORECASE)
    match = pattern.match(line)
    if not match:
        return None
    groups_out = match.groups()
    return groups_out[-1].strip(), list(groups_out[:-1])


def _is_values_only(line: str, n_periods: int) -> bool:
    if n_periods <= 0:
        return False
    groups = r"\s+".join([f"(?:{VALUE_TOKEN})" for _ in range(n_periods)])
    return bool(re.fullmatch(groups, line, re.IGNORECASE))


def _infer_unlabeled_balance_total(
    current_context: str,
    inferred_counts: dict[str, int],
) -> tuple[str, str] | None:
    """Label source total rows whose description cell is visually blank."""
    if current_context == "CURRENT_ASSET":
        inferred_counts["CURRENT_ASSET"] = inferred_counts.get("CURRENT_ASSET", 0) + 1
        return "Total current assets", "ASSET"
    if current_context in {"ASSET", "NONCURRENT_ASSET"} and not inferred_counts.get("ASSET"):
        inferred_counts["ASSET"] = 1
        return "Total assets", "ASSET"
    if current_context == "CURRENT_LIABILITY":
        inferred_counts["CURRENT_LIABILITY"] = inferred_counts.get("CURRENT_LIABILITY", 0) + 1
        return "Total current liabilities", "LIABILITY"
    if current_context in {"LIABILITY", "NONCURRENT_LIABILITY"} and not inferred_counts.get("LIABILITY"):
        inferred_counts["LIABILITY"] = 1
        return "Total liabilities", "LIABILITY"
    if current_context == "EQUITY":
        equity_count = inferred_counts.get("EQUITY", 0)
        inferred_counts["EQUITY"] = equity_count + 1
        if equity_count == 0:
            return "Total stockholders' equity", "EQUITY"
        if equity_count == 1:
            return "Total liabilities and stockholders' equity", "EQUITY"
    return None


def _extract_note_from_description(desc: str) -> tuple[str, str]:
    # Conservative note extraction: a final parenthesized 1-3 digit note only.
    match = re.match(r"^(.*?)(?:\s+\((\d{1,3})\))$", desc.strip())
    if match:
        return match.group(1).strip(), match.group(2)
    return desc.strip(), ""


def _condense_lines(section_rows: list[dict], n_periods: int, statement_type: str) -> list[dict]:
    output: list[dict] = []
    acc_text: list[str] = []
    acc_sources: list[dict] = []
    balance_context = "GENERAL"
    inferred_balance_totals: dict[str, int] = {}

    def flush_acc():
        nonlocal acc_text, acc_sources
        if acc_text:
            output.append({
                "raw_text": " ".join(acc_text),
                "source_page": acc_sources[0].get("source_page") if acc_sources else None,
                "line_no": acc_sources[0].get("line_no") if acc_sources else None,
            })
        acc_text, acc_sources = [], []

    for row in section_rows:
        text = normalize_financial_text(row.get("raw_text", ""))
        if not text:
            continue
        if statement_type == "BalanceSheet":
            balance_context = section_hint_for_line(text, balance_context)
        if _is_non_data_header(text):
            flush_acc()
            header_row = dict(row)
            header_row.pop("row_type_hint", None)
            output.append(header_row)
            continue
        if row.get("row_type_hint") == "section":
            flush_acc()
            output.append(row)
            continue
        if _is_structural_header(text):
            if acc_text and _is_structural_header(" ".join(acc_text)):
                flush_acc()
            acc_text.append(text)
            acc_sources.append(row)
            continue
        if _is_values_only(text, n_periods):
            if acc_text:
                output.append({
                    "raw_text": f"{' '.join(acc_text)} {text}",
                    "source_page": acc_sources[0].get("source_page") if acc_sources else row.get("source_page"),
                    "line_no": acc_sources[0].get("line_no") if acc_sources else row.get("line_no"),
                })
                acc_text, acc_sources = [], []
                continue
            if statement_type == "BalanceSheet":
                inferred = _infer_unlabeled_balance_total(balance_context, inferred_balance_totals)
                if inferred:
                    label, balance_context = inferred
                    output.append({
                        "raw_text": f"{label} {text}",
                        "source_page": row.get("source_page"),
                        "line_no": row.get("line_no"),
                    })
            continue

        has_values = bool(_match_desc_first(text, n_periods) or _match_value_first(text, n_periods)) if n_periods else False
        if has_values:
            prefix = " ".join(acc_text)
            if prefix and _is_structural_header(prefix):
                output.append({
                    "raw_text": prefix,
                    "source_page": acc_sources[0].get("source_page") if acc_sources else row.get("source_page"),
                    "line_no": acc_sources[0].get("line_no") if acc_sources else row.get("line_no"),
                })
                prefix = ""
            output.append({
                "raw_text": f"{prefix} {text}".strip(),
                "source_page": acc_sources[0].get("source_page") if acc_sources else row.get("source_page"),
                "line_no": acc_sources[0].get("line_no") if acc_sources else row.get("line_no"),
            })
            acc_text, acc_sources = [], []
        else:
            if acc_text and _is_structural_header(" ".join(acc_text)):
                flush_acc()
            acc_text.append(text)
            acc_sources.append(row)

    flush_acc()
    return output
def _parse_statement_section(statement_type: str, section_rows: list[dict], company_name: str) -> tuple[pd.DataFrame, list[dict], list[dict]]:
    if statement_type == "ScheduleOfInvestments":
        period_labels = detect_schedule_value_headers(section_rows) or detect_period_labels(section_rows)
    elif statement_type == "PartnersCapital":
        period_labels = detect_partners_capital_value_headers(section_rows) or detect_period_labels(section_rows)
    else:
        period_labels = detect_period_labels(section_rows)
    unit_info = detect_statement_unit_note(section_rows)
    statement_title = next((
        normalize_financial_text(row.get("raw_text", ""))
        for row in section_rows[:20]
        if detect_statement_type(row.get("raw_text", "")) == statement_type
    ), "")
    parsed_rows: list[dict] = []
    parsed_cells: list[dict] = []
    issues: list[dict] = []

    if not period_labels:
        issues.append({
            "Check": "Statement period detection",
            "Scope": statement_type,
            "Status": "FAIL",
            "Detail": "No source-derived period labels detected. No periods were invented.",
        })
        return pd.DataFrame(), parsed_cells, issues

    n_periods = len(period_labels)
    current_context = "GENERAL"
    condensed = _condense_lines(section_rows, n_periods, statement_type)

    for row_idx, row in enumerate(condensed, start=1):
        text = normalize_financial_text(row.get("raw_text", ""))
        if not text:
            continue

        new_context = section_hint_for_line(text, current_context)
        if row.get("row_type_hint") == "section" or _is_structural_header(text):
            current_context = new_context
            parsed_rows.append({
                "RowType": "Section",
                "Category": "",
                "SubCategory": "",
                "RawItem": text.rstrip(":"),
                "StandardItem": text.rstrip(":"),
                "MappingConfidence": 1.0,
                "MappingRule": "section",
                "Context": current_context,
                "Note": "",
                "SourcePage": row.get("source_page"),
                "SourceLine": row.get("line_no"),
            })
            continue
        current_context = new_context

        if _is_non_data_header(text):
            continue

        matched = _match_desc_first(text, n_periods)
        source_order = "description_first"
        if not matched and statement_type == "CashFlowStatement":
            matched = _match_value_first(text, n_periods)
            source_order = "value_first"

        if not matched:
            # If a line ends in numeric-looking tokens but does not match the period count, flag it.
            trailing = re.findall(VALUE_TOKEN, text, flags=re.IGNORECASE)
            if trailing:
                issues.append({
                    "Check": "Period-count alignment",
                    "Scope": f"{statement_type} row {row_idx}",
                    "Status": "WARN",
                    "Detail": f"Detected numeric-looking tokens but could not align exactly to {n_periods} period(s): {text}",
                })
            continue

        raw_desc, raw_values = matched
        raw_desc, note = _extract_note_from_description(raw_desc)
        if not raw_desc:
            continue

        if statement_type == "ScheduleOfInvestments":
            from models import MappingResult
            mapping = MappingResult(raw_desc, raw_desc, "Investment Schedule", "Investment", 1.0, "investment_row")
        else:
            mapping = map_concept(statement_type, raw_desc, current_context)
        out = {
            "RowType": "Data",
            "Category": mapping.category or current_context.replace("_", " ").title(),
            "SubCategory": mapping.subcategory,
            "RawItem": raw_desc,
            "StandardItem": mapping.standard_item,
            "MappingConfidence": mapping.confidence,
            "MappingRule": mapping.rule,
            "Context": current_context,
            "Note": note,
            "SourcePage": row.get("source_page"),
            "SourceLine": row.get("line_no"),
        }

        for period, raw_value in zip(period_labels, raw_values):
            token = parse_numeric_token(raw_value)
            out[period] = token.value if token.status == "NUMERIC" else pd.NA
            parsed_cells.append({
                "statement_type": statement_type,
                "row_index": row_idx,
                "source_page": row.get("source_page"),
                "source_line": row.get("line_no"),
                "source_order": source_order,
                "raw_item": raw_desc,
                "standard_item": mapping.standard_item,
                "mapping_confidence": mapping.confidence,
                "mapping_rule": mapping.rule,
                "context": current_context,
                "period": period,
                "raw_value": raw_value,
                "normalized_value": token.normalized_text,
                "parsed_value": token.value,
                "parse_status": token.status,
                "currency": token.currency,
                "is_percent": token.is_percent,
                "is_ratio": token.is_ratio,
                "precision": token.precision,
                "reported_unit_label": unit_info["unit_label"],
                "reported_scale_factor": unit_info["scale_factor"],
            })
            if token.status == "PARSE_ERROR":
                issues.append({
                    "Check": "Numeric parsing",
                    "Scope": f"{statement_type}: {raw_desc} / {period}",
                    "Status": "WARN",
                    "Detail": f"Could not parse source token '{raw_value}'.",
                })

        parsed_rows.append(out)

        # Totals close the current sub-section so later grand totals are not
        # accidentally treated as current-asset/current-liability components.
        if mapping.standard_item == "Total Current Assets":
            current_context = "ASSET"
        elif mapping.standard_item == "Total Current Liabilities":
            current_context = "LIABILITY"

    df = pd.DataFrame(parsed_rows)
    if not df.empty:
        df.attrs.update({
            "company_name": company_name,
            "statement_title": statement_title,
            "statement_type": statement_type,
            "period_labels": period_labels,
            "unit_label": unit_info["unit_label"],
            "scale_factor": unit_info["scale_factor"],
            "currency": unit_info["currency"],
            "raw_unit_note": unit_info["raw_unit_note"],
        })
    return df, parsed_cells, issues


def parse_financial_statements(text_rows: Iterable[dict] | str) -> tuple[dict[str, pd.DataFrame], list[dict], list[dict], list[dict]]:
    if isinstance(text_rows, str):
        lines = [
            {"source_page": None, "line_no": idx, "raw_text": line, "normalized_text": normalize_financial_text(line)}
            for idx, line in enumerate(text_rows.splitlines(), start=1)
        ]
    else:
        lines = list(text_rows)

    company_name = infer_company_name(lines)
    sections = split_statement_sections(lines)
    statements: dict[str, pd.DataFrame] = {}
    parsed_cells: list[dict] = []
    issues: list[dict] = []
    unmapped: list[dict] = []

    for statement_type, section_rows in sections.items():
        if statement_type in BOUNDARY_ONLY_STATEMENT_TYPES:
            continue
        df, cells, section_issues = _parse_statement_section(statement_type, section_rows, company_name)
        parsed_cells.extend(cells)
        issues.extend(section_issues)
        if df.empty:
            continue
        statements[statement_type] = df
        for _, row in df.iterrows():
            if row.get("RowType", "Data") != "Data":
                continue
            if row.get("MappingRule") == "unmapped" or float(row.get("MappingConfidence", 0) or 0) < 0.75:
                unmapped.append({
                    "statement_type": statement_type,
                    "source_page": row.get("SourcePage"),
                    "source_line": row.get("SourceLine"),
                    "raw_item": row.get("RawItem"),
                    "proposed_item": row.get("StandardItem"),
                    "mapping_confidence": row.get("MappingConfidence"),
                    "mapping_rule": row.get("MappingRule"),
                    "context": row.get("Context"),
                })

    return statements, parsed_cells, issues, unmapped
