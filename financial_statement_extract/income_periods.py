"""Recover income reporting columns from header evidence, never body amounts.

Repeated years may belong to different durations. Enumerate source-consistent
groupings and accept exactly one; ambiguous text needs PDF header geometry.
Other statement types continue to use their existing period detection.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
import re

from normalization import normalize_financial_text, parse_numeric_token
from structure import DATE_RE, MONTH_RE, YEAR_RE, detect_period_labels, split_statement_sections


DURATION = re.compile(r"\b(?:(three|six|nine|twelve|\d{1,2})\s+months?|((?:one\s+)?year))\b", re.I)
MONTH = re.compile(rf"\b{MONTH_RE}(?![a-z])", re.I)
COUNTS = {"three": 3, "six": 6, "nine": 9, "twelve": 12}
NAMES = {3: "Three", 6: "Six", 9: "Nine", 12: "Twelve"}


@dataclass
class IncomePeriods:
    labels: list[str]
    header_indices: set[int] = field(default_factory=set)
    warning: str = ""
    evidence: dict = field(default_factory=dict)


def _text(value):
    # A PDF can join a year's final glyph directly to the next month name.
    text = normalize_financial_text(value)
    return re.sub(rf"((?:19|20)\d{{2}})(?={MONTH_RE}\b)", r"\1 ", text, flags=re.I)


def _header_fragment(text):
    remainder = MONTH.sub("", text)
    remainder = re.sub(r"\b(?:for|the|as|of|three|six|nine|twelve|one|months?|years?|ended|end|unaudited|audited)\b",
                       "", remainder, flags=re.I)
    remainder = re.sub(r"\b(?:(?:19|20)\d{2}|[0-3]?\d)\b", "", remainder)
    return not re.sub(r"[\s,().:/-]", "", remainder)


def _header_block(rows):
    block, indices = [], set()
    for index, row in enumerate(rows[:20]):
        text = _text(row.get("raw_text", ""))
        if _header_fragment(text) and (block or DURATION.search(text) or YEAR_RE.search(text)
                                       or re.search(r"\byears? ended\b", text, re.I)):
            block.append(text)
            indices.add(index)
        elif block:
            break
    return block, indices


def _duration_count(match):
    value = match.group(1)
    return 12 if value is None else COUNTS[value.lower()] if value.lower() in COUNTS else int(value)


def _same_label(left, right):
    def key(value):
        return re.sub(r"^for (?:the )?", "", value.lower()).replace(",", "")
    return key(left) == key(right)


def _geometry_allows(words, durations, years, widths):
    """Require each duration anchor inside its assigned source year-column span."""
    year_words = sorted((w for w in words if YEAR_RE.fullmatch(w["text"])), key=lambda w: w["x0"])
    if len(year_words) < 2 or [w["text"] for w in year_words] != years:
        return False
    centers = [(w["x0"] + w["x1"]) / 2 for w in year_words]
    if any(b <= a for a, b in zip(centers, centers[1:])):
        return False
    anchors = []
    for word in words:
        count = COUNTS.get(word["text"].lower())
        if count is None and re.fullmatch(r"\d{1,2}", word["text"]):
            count = int(word["text"])
        if count is None:
            if word["text"].lower() == "year":
                anchors.append((12, (word["x0"] + word["x1"]) / 2))
            continue
        neighbors = [w for w in words if re.fullmatch(r"months?", w["text"], re.I)
                     and abs(w["top"] - word["top"]) < 3 and 0 <= w["x0"] - word["x1"] < 15]
        if len(neighbors) == 1:
            anchors.append((count, (word["x0"] + neighbors[0]["x1"]) / 2))
    anchors.sort(key=lambda item: item[1])
    if [count for count, _ in anchors] != durations:
        return False
    boundaries = [centers[0] - (centers[1] - centers[0])] + [
        (a + b) / 2 for a, b in zip(centers, centers[1:])
    ] + [centers[-1] + (centers[-1] - centers[-2])]
    start = 0
    for (_, center), width in zip(anchors, widths):
        if not boundaries[start] < center < boundaries[start + width]:
            return False
        start += width
    return True


def resolve_income_periods(rows):
    legacy = detect_period_labels(rows)
    # A new period count must not reinterpret another statement's component
    # values. Unrecognized foreign headings need a separate page-boundary repair.
    if any(re.match(r"^(?:(?:consolidated|combined|condensed|unaudited)\s+)*"
                    r"(?:statements? of (?:changes in|cash flows)\b|balance sheets?\b|schedules? of investments\b)",
                     _text(row.get("raw_text", "")), re.I) for row in rows):
        return IncomePeriods(legacy, warning=(
            "Income section contains another financial statement title; original reporting columns retained. "
            "Separate the statement pages before repairing income periods."))
    block, indices = _header_block(rows)
    result = IncomePeriods(legacy)
    if not block:
        return result
    text = " ".join(block)
    years = YEAR_RE.findall(text)
    duration_matches = list(DURATION.finditer(text))
    durations = [_duration_count(m) for m in duration_matches]
    if len(durations) == 1 and len(legacy) == len(years) and len(set(years)) == len(years):
        return result  # One already complete duration group needs no new labels.
    # Ordinary annual headers retain existing labels. Only repair a proved
    # missing full date caused by adjacent PDF text, without changing raw text.
    if not durations or all(d == 12 for d in durations):
        dates = DATE_RE.findall(text)
        if len(dates) >= 2 and len(set(dates)) == len(dates) and len(dates) > len(legacy):
            return IncomePeriods(dates, indices, evidence={"method": "explicit_header_dates", "header_lines": block})
        return result
    if not 1 <= len(durations) <= len(years) <= 12:
        result.warning = "Income header durations and source years could not be aligned; review reporting columns."
        return result
    months = MONTH.findall(text)
    without_years = YEAR_RE.sub("", text)
    without_durations = DURATION.sub("", without_years)
    days = re.findall(r"\b(?:[12]?\d|3[01])\b", without_durations)
    if len(months) != len(days) or len(months) not in {len(durations), len(years)}:
        result.warning = "Income header month/day columns are ambiguous; review reporting columns."
        return result
    complete_dates = re.findall(rf"\b({MONTH_RE})\s+([0-3]?\d)\b", text, flags=re.I)
    if len(complete_dates) != len(months) and (len(set(m.lower() for m in months)) != 1 or len(set(days)) != 1):
        result.warning = "Wrapped income month/day associations are ambiguous; review source column positions."
        return result
    dates = list(zip(months, days))
    words = next((r["income_header_words"] for r in rows if r.get("income_header_words")), [])
    solutions = []
    for cuts in combinations(range(1, len(years)), len(durations) - 1):
        bounds = (0, *cuts, len(years))
        groups = [years[a:b] for a, b in zip(bounds, bounds[1:])]
        if any(len(set(group)) != len(group) for group in groups):
            continue
        widths = [len(group) for group in groups]
        if words and not _geometry_allows(words, durations, years, widths):
            continue
        labels = []
        for group_index, (duration, group) in enumerate(zip(durations, groups)):
            for offset, year in enumerate(group):
                month, day = dates[group_index if len(dates) == len(groups) else bounds[group_index] + offset]
                prefix = "Year Ended" if duration_matches[group_index].group(2) else (
                    f"{NAMES.get(duration, str(duration))} Months Ended")
                labels.append(f"{prefix} {month} {day}, {year}")
        if len(set(labels)) == len(labels):
            solutions.append(labels)
    if len(solutions) != 1:
        result.warning = "Income header permits no unique duration/date/year grouping; source column positions require review."
        return result
    labels = solutions[0]
    if len(legacy) == len(labels) and all(_same_label(a, b) for a, b in zip(legacy, labels)):
        labels = legacy
    evidence = {"method": "header_geometry" if words else "unique_header_grouping", "header_lines": block}
    if words:
        evidence["words"] = words
    return IncomePeriods(labels, indices, evidence=evidence)


def attach_income_header_geometry(pdf_path, rows):
    """Add verified header word positions to parser copies only when text is ambiguous."""
    section = split_statement_sections(rows).get("IncomeStatement", [])
    if not section or not resolve_income_periods(section).warning:
        return rows
    block, indices = _header_block(section)
    pages = {section[i].get("source_page") for i in indices}
    if len(pages) != 1 or None in pages:
        return rows
    import pdfplumber
    page_no = next(iter(pages))
    with pdfplumber.open(str(pdf_path)) as pdf:
        page = pdf.pages[page_no - 1]
        lines = page.extract_text_lines()
        matches = [[line for line in lines if _text(line["text"]) == text] for text in block]
        if not all(len(group) == 1 for group in matches):
            return rows  # The parser retains an explicit ambiguity warning.
        top = min(group[0]["top"] for group in matches)
        bottom = max(group[0]["bottom"] for group in matches)
        words = [{k: w[k] for k in ("text", "x0", "x1", "top", "bottom")}
                 for w in page.crop((0, top, page.width, bottom)).extract_words()]
    target = section[min(indices)]
    return [{**row, "income_header_words": words} if row is target else row for row in rows]


def prepare_income_parser_rows(pdf_path, rows):
    """Keep vertically offset dash cells in their source columns, not text order."""
    prepared = attach_income_header_geometry(pdf_path, rows)
    section = split_statement_sections(prepared).get("IncomeStatement", [])
    if not section:
        return prepared
    layout = resolve_income_periods(section)
    if "another financial statement title" in layout.warning:
        return prepared
    count = len(layout.labels)
    # A currency sign attached to the previous value is a new value's prefix,
    # not part of the row label. Only accept a complete header-sized row.
    from statements import VALUE_TOKEN, _match_desc_first
    currency_rows = {}
    for row in section:
        text = normalize_financial_text(row.get("raw_text", ""))
        spaced = re.sub(r"(?<=[\d)])(?=[$€£¥])", " ", text)
        if spaced == text or _match_desc_first(text, count):
            continue
        match = _match_desc_first(spaced, count)
        if match:
            label, tokens = match
            currency_rows[id(row)] = {**row, "income_label": label, "income_value_tokens": tokens,
                                      "income_row_evidence": {
                                          "method": "adjacent_currency_separator", "source_page": row.get("source_page"),
                                          "source_lines": [row.get("line_no")], "original_text": [row["raw_text"]],
                                          "parser_text": spaced}}
    if currency_rows:
        prepared = [currency_rows.get(id(row), row) for row in prepared]
        section = split_statement_sections(prepared).get("IncomeStatement", [])
    header_rows = {id(section[i]) for i in _header_block(section)[1]}
    candidates = []
    for previous, row in zip(section, section[1:]):
        if id(row) in header_rows or id(previous) in header_rows:
            continue
        text = normalize_financial_text(row.get("raw_text", ""))
        tokens = text.split()
        if (tokens and len(tokens) < count and all(parse_numeric_token(t).status == "DASH" for t in tokens)
                and previous.get("source_page") == row.get("source_page")
                and re.search(r"\d\s*$", previous.get("raw_text", ""))
                and re.search(r"[a-z]", previous.get("raw_text", ""), re.I)):
            candidates.append((previous, row))
    paired = {id(r) for pair in candidates for r in pair}
    for row in section:
        if id(row) in paired or id(row) in header_rows or "income_value_tokens" in row:
            continue
        remaining, tokens = normalize_financial_text(row.get("raw_text", "")), []
        while len(tokens) <= count:
            match = re.search(rf"(?:^|\s)({VALUE_TOKEN})\s*$", remaining, re.I)
            if not match:
                break
            tokens.append(match.group(1))
            remaining = remaining[:match.start()].rstrip()
        if (1 < len(tokens) < count and re.search(r"[a-z]", remaining, re.I)
                and sum(parse_numeric_token(t).status == "NUMERIC" for t in tokens) >= 2):
            candidates.append((row, None))
    if not candidates:
        return prepared
    import pdfplumber
    replacements = {id(previous): {**previous, "income_row_warning":
                    "Incomplete source row could not be assigned to period columns; review the original row."}
                    for previous, _ in candidates}
    removed = set()
    block, _ = _header_block(section)
    with pdfplumber.open(str(pdf_path)) as pdf:
        for previous, row in candidates:
            page_no = previous.get("source_page")
            if page_no is None:
                continue
            page = pdf.pages[page_no - 1]
            lines = page.extract_text_lines()
            sources = [previous, row] if row else [previous]
            matches = [[line for line in lines if _text(line["text"]) == _text(source["raw_text"])]
                       for source in sources]
            header = [line for line in lines if _text(line["text"]) in block
                      and len(YEAR_RE.findall(line["text"])) == count]
            if not all(len(m) == 1 for m in matches) or len(header) != 1:
                continue
            first, second = matches[0][0], matches[-1][0]
            if abs(first["top"] - second["top"]) > max(first["bottom"] - first["top"], second["bottom"] - second["top"]):
                continue
            year_words = [w for w in page.crop((0, header[0]["top"], page.width, header[0]["bottom"])).extract_words()
                          if YEAR_RE.fullmatch(w["text"])]
            if len(year_words) != count or count < 2:
                continue
            year_words.sort(key=lambda w: w["x0"])
            centers = [(w["x0"] + w["x1"]) / 2 for w in year_words]
            if any(b <= a for a, b in zip(centers, centers[1:])):
                continue
            bounds = [centers[0] - (centers[1] - centers[0]) / 2] + [
                (a + b) / 2 for a, b in zip(centers, centers[1:])
            ] + [page.width]
            words = page.crop((0, min(first["top"], second["top"]), page.width,
                              max(first["bottom"], second["bottom"]))).extract_words()
            values = [[] for _ in centers]
            label_words = []
            valid = True
            for word in words:
                center = (word["x0"] + word["x1"]) / 2
                if center < bounds[0]:
                    label_words.append(word)
                    continue
                if word["text"] in {"$", "€", "£", "¥"}:
                    continue
                if parse_numeric_token(word["text"]).status not in {"NUMERIC", "DASH"}:
                    valid = False
                    break
                owners = [i for i in range(count) if bounds[i] <= center < bounds[i + 1]]
                if len(owners) != 1:
                    valid = False
                    break
                values[owners[0]].append(word["text"])
            if (not valid or not label_words or any(len(v) > 1 for v in values)
                    or (row is not None and any(len(v) != 1 for v in values))):
                continue
            label = " ".join(w["text"] for w in sorted(label_words, key=lambda w: w["x0"]))
            evidence = {"method": "offset_dash_row_geometry" if row else "incomplete_row_geometry", "source_page": page_no,
                        "source_lines": [source["line_no"] for source in sources],
                        "original_text": [source["raw_text"] for source in sources],
                        "column_boundaries": bounds,
                        "words": [{k: w[k] for k in ("text", "x0", "x1", "top", "bottom")} for w in words]}
            replacements[id(previous)] = {**previous, "income_label": label,
                                          "income_value_tokens": [v[0] if v else "" for v in values],
                                          "income_row_evidence": evidence}
            if row:
                removed.add(id(row))
    return [replacements.get(id(row), row) for row in prepared if id(row) not in removed]
