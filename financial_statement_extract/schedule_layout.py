"""Geometry-backed consolidation and bounded presentation repairs for PDF schedules."""
from __future__ import annotations

from copy import deepcopy
import math
import re


def _bounds(value):
    return (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(v, (int, float)) and math.isfinite(v) for v in value)
            and value[0] != value[1])


def _has_geometry(table):
    return (bool(table["rows"]) and bool(table["rows"][0])
            and all(len(row) == len(table["rows"][0]) for row in table["rows"])
            and len(table.get("row_bounds", [])) == len(table["rows"])
            and all(_bounds(v) for v in table["row_bounds"])
            and len(table.get("column_bounds", [])) == len(table["rows"][0])
            and all(_bounds(v) for v in table["column_bounds"]))


def _same_columns(a, b):
    ac, bc = a["column_bounds"], b["column_bounds"]
    # The left edge of the label column can vary with indentation/cropping.
    return len(ac) == len(bc) and all(
        abs(x[1] - y[1]) <= 1 and (i == 0 or abs(x[0] - y[0]) <= 1)
        for i, (x, y) in enumerate(zip(ac, bc)))


def _same_position(a, b):
    al, ah = sorted(a)
    bl, bh = sorted(b)
    overlap = min(ah, bh) - max(al, bl)
    return abs((al + ah) / 2 - (bl + bh) / 2) <= 2 and overlap >= .6 * min(ah - al, bh - bl)


def _row_key(row):
    return tuple(re.sub(r"\s+", " ", v).strip() for v in row)


def merge_overlapping_schedule_tables(tables):
    """Combine identical rows only at the same page coordinates and column schema.

    Genuine equal rows at distinct positions/pages survive. Every original table
    remains in raw extraction records; output rows retain all their source IDs.
    Conflicting values at an overlapping position fail rather than silently pick
    a number. Missing geometry is never replaced with content-only deduplication.
    """
    result, issues = [], []
    for original in tables:
        if original.get("statement_type") != "ScheduleOfInvestments" or original.get("flavor") not in {"stream", "lattice"}:
            result.append(original)
            continue
        table = deepcopy(original)
        table["source_table_ids"] = [table["table_id"]]
        table["row_sources"] = [[{"table_id": table["table_id"], "row_index": i}]
                                for i in range(len(table["rows"]))]
        # Candidate may bridge two previously disjoint portions of a page.
        for prior in list(result):
            if (prior.get("statement_type") != "ScheduleOfInvestments"
                    or prior.get("source_page") != table.get("source_page")
                    or prior.get("flavor") != table.get("flavor")):
                continue
            if table.get("source_page") is None or not _has_geometry(prior) or not _has_geometry(table):
                if set(map(_row_key, prior["rows"])) & set(map(_row_key, table["rows"])):
                    issues.append({"Check": "Schedule table overlap", "Scope": table["table_id"], "Status": "WARN",
                                   "Detail": "Similar schedule rows lack usable PDF geometry. Both tables retained; review for overlap."})
                continue
            if not _same_columns(prior, table):
                left = max(prior["column_bounds"][0][0], table["column_bounds"][0][0])
                right = min(prior["column_bounds"][-1][1], table["column_bounds"][-1][1])
                if right > left and any(_same_position(a, b) for a in prior["row_bounds"] for b in table["row_bounds"]):
                    issues.append({"Check": "Schedule table overlap", "Scope": table["table_id"], "Status": "WARN",
                                   "Detail": "Overlapping schedule candidates have different column boundaries. "
                                   "Both tables retained; source review is required."})
                continue
            matches = []
            for i, (row, bounds) in enumerate(zip(table["rows"], table["row_bounds"])):
                if not any(row):
                    continue
                hits = [j for j, pb in enumerate(prior["row_bounds"])
                        if any(prior["rows"][j]) and _same_position(bounds, pb)]
                if len(hits) > 1:
                    raise ValueError(f"Ambiguous overlapping schedule rows on page {table['source_page']}: "
                                     f"{prior['table_id']} and {table['table_id']}. Review source table boundaries.")
                if hits:
                    j = hits[0]
                    if _row_key(row) != _row_key(prior["rows"][j]):
                        raise ValueError(f"Conflicting overlapping schedule tables on page {table['source_page']}: "
                                         f"{prior['table_id']} and {table['table_id']}. No values were chosen.")
                    matches.append((i, j))
            if not matches:
                continue
            if table.get("spans") or prior.get("spans"):
                raise ValueError("Overlapping PDF schedule grids with merged cells require source review.")
            if len({j for _, j in matches}) != len(matches):
                raise ValueError("Ambiguous many-to-one schedule row geometry; no rows were removed.")
            merged = deepcopy(prior)
            merged["source_order"] = min(prior.get("source_order") or 0, table.get("source_order") or 0)
            merged["source_table_ids"] += table["source_table_ids"]
            for i, j in matches:
                merged["row_sources"][j] += table["row_sources"][i]
            duplicate_indices = {i for i, _ in matches}
            for i, row in enumerate(table["rows"]):
                if i not in duplicate_indices and any(row):
                    merged["rows"].append(row)
                    merged["row_bounds"].append(table["row_bounds"][i])
                    merged["row_sources"].append(table["row_sources"][i])
            order = sorted(range(len(merged["rows"])), key=lambda i: -sum(merged["row_bounds"][i]))
            for key in ("rows", "row_bounds", "row_sources"):
                merged[key] = [merged[key][i] for i in order]
            merged["source_context"] = list(dict.fromkeys(prior.get("source_context", []) + table.get("source_context", [])))
            issues.append({"Check": "Schedule table overlap", "Scope": f"Page {table['source_page']}", "Status": "INFO",
                           "Detail": f"Consolidated {len(matches)} repeated rows at the same PDF positions from "
                           f"{table['table_id']} and {prior['table_id']}. All raw candidates and row provenance retained."})
            result.remove(prior)
            table = merged
        result.append(table)
    return sorted(result, key=lambda t: (t.get("source_page") or 0, t.get("source_order") or 0)), issues


def schedule_display_grid(table):
    """Move a narrowly recognized trailing PIK rate suffix out of maturity dates.

    Source headers, adjacent rate syntax and an exact month/year date are required.
    Raw grids remain unchanged; arbitrary words and unsupported layouts stay literal.
    """
    if table.get("statement_type") != "ScheduleOfInvestments" or table.get("flavor") not in {"stream", "lattice"}:
        return table
    rows = table["rows"]
    maturity_columns = {c for row in rows[:12] for c, text in enumerate(row) if text.strip().lower() == "maturity"}
    interest_columns = {c for row in rows[:12] for c, text in enumerate(row) if text.strip().lower() == "interest"}
    output = deepcopy(table)
    for row in output["rows"]:
        for c in maturity_columns:
            if c == 0 or c - 1 not in interest_columns:
                continue
            match = re.fullmatch(r"\s*(PIK)\s+((?:0[1-9]|1[0-2])/\d{4})\s*", row[c])
            if match and re.fullmatch(r"\s*\d+(?:\.\d+)?%\s+cash/\s*\d+(?:\.\d+)?%\s*", row[c-1]):
                row[c-1] = row[c-1].rstrip() + " " + match[1]
                row[c] = match[2]
    return output
