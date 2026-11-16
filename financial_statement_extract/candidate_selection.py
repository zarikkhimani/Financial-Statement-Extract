"""Keep more complete raw candidates without discarding source-supported tokens.

Token coverage is a selection signal, not proof of amount/column correctness.
Statement recovery separately verifies ordered rows, signs and source columns.
"""
from collections import Counter, defaultdict
import re

from financial_statement_extract.detection import financial_rows
from normalization import normalize_financial_text, parse_numeric_token

NUMBER = re.compile(r"(?<!\w)\d[\d,]*(?:\.\d+)?")


def preserve_complete_candidates(cells, text_rows, pages):
    """Replace a truncated flavor only with a strict coverage superset on a page."""
    source = defaultdict(Counter)
    groups = defaultdict(lambda: defaultdict(list))
    for row in text_rows:
        for line in financial_rows(row.get("raw_text", "")):
            source[row["source_page"]].update(NUMBER.findall(line))
    for cell in cells:
        if cell["source_page"] in pages:
            groups[cell["source_page"]][cell["flavor"]].append(cell)
    issues = []
    for page, flavors in groups.items():
        current = next((flavor for flavor, rows in flavors.items() if any(r.get("selected") for r in rows)), None)
        if current is None or not source[page]:
            continue
        coverage = {flavor: Counter(NUMBER.findall(" ".join(r.get("raw_text", "") for r in rows))) & source[page]
                    for flavor, rows in flavors.items()}
        old = coverage[current]
        better = [flavor for flavor, tokens in coverage.items() if not (old - tokens) and tokens != old]
        if not better:
            continue
        best = max(better, key=lambda f: sum(coverage[f].values()))
        for flavor, rows in flavors.items():
            for row in rows:
                row["selected"] = flavor == best
        issues.append(dict(Check="Candidate completeness", Scope=f"Page {page}", Status="INFO",
                           Detail=f"Selected {best} instead of {current}: retained all "
                           f"{sum(old.values())} source-supported numeric tokens and added "
                           f"{sum(coverage[best].values()) - sum(old.values())}. "
                           "Raw alternatives retained; row and column validation remains separate."))
    return issues


def normalize_selected_cells(cells):
    """Normalize the final selected flavor, including previously unselected cells."""
    result = []
    for cell in cells:
        if not cell.get("selected"):
            continue
        raw = cell.get("raw_text", "")
        token = parse_numeric_token(raw)
        result.append({**{key: cell[key] for key in ("source_page", "table_id", "flavor", "row_index", "column_index")},
                       "raw_text": raw, "normalized_text": normalize_financial_text(raw),
                       "parsed_value": token.value, "parse_status": token.status, "currency": token.currency,
                       "is_percent": token.is_percent, "is_ratio": token.is_ratio, "precision": token.precision})
    return result
