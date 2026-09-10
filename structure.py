from __future__ import annotations

import re
from collections import defaultdict

from config import SECTION_HINTS, STATEMENT_TITLES
from normalization import classify_unit_note, normalize_financial_text


YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
MONTH_RE = r"(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|Aug\.?|Sep\.?|Sept\.?|Oct\.?|Nov\.?|Dec\.?)"
DATE_RE = re.compile(rf"\b{MONTH_RE}\s+\d{{1,2}},?\s+(?:19|20)\d{{2}}\b", re.IGNORECASE)
INTERIM_PERIOD_RE = re.compile(
    rf"\b(?:three|six|nine|twelve|\d+)\s+months?\s+ended\s+{MONTH_RE}\s+\d{{1,2}}\b",
    re.IGNORECASE,
)


def normalize_title(text: str) -> str:
    t = normalize_financial_text(text).lower().replace("’", "'")
    t = re.sub(r"\b(?:condensed\s+)?consolidated\s+", "", t)
    t = re.sub(r"[^a-z0-9' ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def detect_statement_heading_type(line: str) -> str | None:
    """Match only a standalone statement heading, not a narrative reference."""
    heading = normalize_financial_text(line)
    heading = re.sub(r"\s*\((?:unaudited|audited|continued)\)\s*\.?\s*$", "", heading, flags=re.IGNORECASE)
    norm = normalize_title(heading)
    if not norm:
        return None
    for statement_type, titles in STATEMENT_TITLES.items():
        if any(norm == normalize_title(title) for title in titles):
            return statement_type
    return None


def detect_statement_type(line: str) -> str | None:
    norm = normalize_title(line)
    if not norm:
        return None
    exact_heading = detect_statement_heading_type(line)
    if exact_heading:
        return exact_heading
    for statement_type, titles in STATEMENT_TITLES.items():
        for title in titles:
            title_norm = normalize_title(title)
            if norm == title_norm or norm.startswith(title_norm + " ") or title_norm in norm:
                return statement_type
    return None


def is_period_header_line(line: str) -> bool:
    low = normalize_financial_text(line).lower()
    if not low:
        return False
    if any(x in low for x in ("years ended", "year ended", "as of", "months ended", "quarters ended", "quarter ended", "period ended")):
        return True
    years = YEAR_RE.findall(line)
    return len(years) >= 2


def detect_period_labels(lines: list[dict]) -> list[str]:
    """Detect labels from only the statement's own header block. Never extrapolates periods."""
    header_lines = [normalize_financial_text(x.get("raw_text", "")) for x in lines[:20]]

    # Interim statements commonly repeat the same years for multiple duration
    # groups, such as "Three Months Ended" and "Six Months Ended". Preserve
    # all source columns and make their labels unique instead of deduplicating
    # the years and silently dropping the leading values.
    for index, line in enumerate(header_lines):
        groups = [normalize_financial_text(match.group(0)).strip(" ,") for match in INTERIM_PERIOD_RE.finditer(line)]
        if not groups:
            continue
        for candidate in header_lines[index:index + 4]:
            years = YEAR_RE.findall(candidate)
            if not years or len(years) % len(groups):
                continue
            years_per_group = len(years) // len(groups)
            if years_per_group == 0:
                continue
            labels = [
                f"{group}, {year}"
                for group_index, group in enumerate(groups)
                for year in years[group_index * years_per_group:(group_index + 1) * years_per_group]
            ]
            if len(labels) == len(years) and len(set(labels)) == len(labels):
                return labels

    # Prefer multiple full dates from the same source line. This avoids treating
    # a fund's formation date as an extra reporting period when the actual
    # column headings appear together on the next line.
    for line in header_lines:
        line_dates: list[str] = []
        for match in DATE_RE.findall(line):
            cleaned = normalize_financial_text(match)
            if cleaned not in line_dates:
                line_dates.append(cleaned)
        if len(line_dates) >= 2:
            return line_dates

    # Otherwise collect explicit full dates because balance sheets are point-in-time.
    full_dates: list[str] = []
    for line in header_lines:
        for match in DATE_RE.findall(line):
            cleaned = normalize_financial_text(match)
            if cleaned not in full_dates:
                full_dates.append(cleaned)
    if len(full_dates) >= 2:
        return full_dates

    # Then collect years in the order presented. Require at least one likely header cue.
    years: list[str] = []
    saw_header_cue = False
    for line in header_lines:
        if is_period_header_line(line):
            saw_header_cue = True
        found = YEAR_RE.findall(line)
        if found and (saw_header_cue or len(found) >= 2):
            for year in found:
                if year not in years:
                    years.append(year)
        if years and len(years) >= 5:
            break
    if years:
        return years

    # Last-resort scan of first 12 lines for adjacent years, still source-derived only.
    for line in header_lines[:12]:
        found = YEAR_RE.findall(line)
        if len(found) >= 1:
            for year in found:
                if year not in years:
                    years.append(year)
    return years



def detect_schedule_value_headers(lines: list[dict]) -> list[str]:
    """Detect common Schedule of Investments value columns when no period row exists."""
    header = " ".join(normalize_financial_text(x.get("raw_text", "")) for x in lines[:25]).lower()
    labels: list[str] = []
    candidates = [
        ("principal amount", "Principal Amount"),
        ("par amount", "Par Amount"),
        ("cost", "Cost"),
        ("fair value", "Fair Value"),
    ]
    for token, label in candidates:
        if token in header and label not in labels:
            labels.append(label)
    if any(token in header for token in ("percentage of net assets", "% of net assets", "percent of net assets")):
        labels.append("% of Net Assets")
    # Most schedules present cost and fair value as the trailing numeric columns.
    if "Cost" in labels and "Fair Value" in labels:
        ordered = ["Cost", "Fair Value"]
        if "% of Net Assets" in labels:
            ordered.append("% of Net Assets")
        return ordered
    return labels


def detect_partners_capital_value_headers(lines: list[dict]) -> list[str]:
    """Detect class columns used by fund statements of changes in net assets."""
    header = " ".join(normalize_financial_text(row.get("raw_text", "")) for row in lines[:8])
    labels: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"\bClass\s+[A-Z0-9]+(?:-[A-Z0-9]+)*\b", header, re.IGNORECASE):
        label = normalize_financial_text(match.group(0))
        if label.casefold() not in seen:
            labels.append(label)
            seen.add(label.casefold())
    if len(labels) < 2:
        return []
    if re.search(r"\bTotal\b", header, re.IGNORECASE):
        labels.append("Total")
    return labels

def detect_statement_unit_note(lines: list[dict]) -> dict:
    for row in lines[:20]:
        text = normalize_financial_text(row.get("raw_text", ""))
        low = text.lower()
        if any(token in low for token in ("in thousands", "in millions", "in billions", "$000", "$mm", "$bn", "000s")):
            match = re.search(r"\([^)]*(?:in thousands|in millions|in billions|\$000|\$mm|\$bn|000s)[^)]*\)", text, re.IGNORECASE)
            unit_text = match.group(0) if match else text
            result = classify_unit_note(unit_text)
            result["raw_unit_note"] = unit_text
            return result
    return {"unit_label": "reported units", "scale_factor": 1, "currency": "", "raw_unit_note": ""}


def infer_company_name(lines: list[dict]) -> str:
    for row in lines[:12]:
        text = normalize_financial_text(row.get("raw_text", ""))
        if not text:
            continue
        if detect_statement_type(text):
            continue
        if is_period_header_line(text):
            continue
        low = text.lower()
        if low == "table of contents":
            continue
        if re.fullmatch(r"part\s+[ivx]+\.?\s+financial information", low):
            continue
        if re.fullmatch(r"item\s+\d+[a-z]?\.?\s+financial statements", low):
            continue
        if "sec.gov/" in low or low.startswith(("http://", "https://")):
            continue
        if re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}(?:,?\s+\d{1,2}:\d{2}\s+[ap]m)?\s+form\s+10-[kq]$", low):
            continue
        if "in millions" in low or "in thousands" in low or "in billions" in low:
            continue
        if text.upper() in SECTION_HINTS:
            continue
        return text
    return "Unknown Company"


def split_statement_sections(lines: list[dict]) -> dict[str, list[dict]]:
    sections: dict[str, list[dict]] = defaultdict(list)
    current: str | None = None

    for row in lines:
        text = normalize_financial_text(row.get("raw_text", ""))
        if not text:
            continue
        detected = detect_statement_type(text)
        if detected:
            current = detected
            sections[current].append(row)
            continue

        if current is None:
            upper = text.upper().rstrip(":")
            if upper in {"ASSETS", "CURRENT ASSETS"}:
                current = "BalanceSheet"
            elif upper in {"OPERATING ACTIVITIES", "CASH FLOWS FROM OPERATING ACTIVITIES"}:
                current = "CashFlowStatement"
            elif upper in {"REVENUES", "REVENUE"}:
                current = "IncomeStatement"
            elif upper in {"PARTNERS' CAPITAL", "PARTNERS’ CAPITAL"}:
                current = "PartnersCapital"

        if current:
            sections[current].append(row)

    return dict(sections)


def section_hint_for_line(text: str, current_hint: str) -> str:
    cleaned = normalize_financial_text(text).upper().rstrip(":")
    if cleaned in SECTION_HINTS:
        return SECTION_HINTS[cleaned]
    if cleaned.startswith("CASH FLOWS FROM OPERATING ACTIVITIES"):
        return "OPERATING_ACTIVITY"
    if cleaned.startswith("CASH FLOWS FROM INVESTING ACTIVITIES"):
        return "INVESTING_ACTIVITY"
    if cleaned.startswith("CASH FLOWS FROM FINANCING ACTIVITIES"):
        return "FINANCING_ACTIVITY"
    if "LIABILITIES AND" in cleaned and ("EQUITY" in cleaned or "CAPITAL" in cleaned):
        return "LIABILITY_EQUITY"
    return current_hint
