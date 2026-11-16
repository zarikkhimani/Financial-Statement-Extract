"""Check source-associated rows and numeric storage without exact heading typography."""
from decimal import Decimal
import re


class CompletenessContractError(AssertionError):
    """A reviewed row/value contract failed; setup errors are never expected failures."""


def require(condition, message):
    if not condition:
        raise CompletenessContractError(message)


def label_key(text):
    text = re.sub(r"\(\d+\)|(?<=[a-zA-Z])\d+$", "", str(text))
    return re.sub(r"[^a-z0-9]", "", text.lower())


def label_matches(expected, actual):
    return label_key(expected) in label_key(actual)


def scalar(cell):
    if cell.value is None or cell.value == "":
        return None
    if cell.data_type == "n":
        return format(Decimal(str(cell.value)).normalize(), "f")
    if str(cell.value).strip() in {"-", "\u2013", "\u2014", "\u2212", "\ufffd"}:
        return "SOURCE_DASH"
    return (cell.data_type, str(cell.value))


def observed_rows(sheet, min_row=8, max_row=None):
    rows = []
    for cells in sheet.iter_rows(min_row=min_row, max_row=max_row, min_col=3):
        if cells[0].value is None:
            continue
        if not any(c.data_type == "n" and c.value is not None or scalar(c) == "SOURCE_DASH" for c in cells[1:]):
            continue
        rows.append({"row": cells[0].row, "label": str(cells[0].value), "cells": cells[1:]})
    return rows


def assert_rows(sheet, expected, *, stable_columns=True, reject_extra=False, min_row=8, max_row=None):
    """Associate by labels and source order first, then compare amounts; never search by amount."""
    actual, cursor, paired = observed_rows(sheet, min_row, max_row), 0, []
    for source in expected:
        match = next((i for i in range(cursor, len(actual)) if label_matches(source["label"], actual[i]["label"])), None)
        require(match is not None, f"missing source row {source['source_id']}: {source['label']}")
        paired.append((source, actual[match]))
        cursor = match + 1
    columns = None
    if stable_columns:
        for source, row in paired:
            if all(v not in (None, "SOURCE_DASH") for v in source["values"]):
                columns = [i for i, c in enumerate(row["cells"]) if c.data_type == "n" and c.value is not None]
                require(len(columns) == len(source["values"]), f"missing numeric columns at {source['source_id']}")
                break
        require(columns is not None, "no complete numeric anchor establishes column positions")
    for source, row in paired:
        if columns is None:
            values = [scalar(c) for c in row["cells"] if scalar(c) is not None and str(c.value).strip() not in {"$", "\u20ac", "\u00a3"}]
        else:
            values = [scalar(row["cells"][i]) if i < len(row["cells"]) else None for i in columns]
            extras = [scalar(c) for i, c in enumerate(row["cells"]) if i not in columns
                      and (c.data_type == "n" and c.value is not None or scalar(c) == "SOURCE_DASH")]
            require(not extras, f"amounts outside established columns at {source['source_id']}")
        require(values == source["values"], f"wrong amount/sign/blank/storage at {source['source_id']}: {values!r}")
    if reject_extra:
        used = {r["row"] for _, r in paired}
        for row in actual:
            require(row["row"] in used or not any(label_matches(e["label"], row["label"]) for e in expected),
                    f"duplicate or misplaced source row at worksheet row {row['row']}")
    return paired


def assert_context(sheet, case):
    lines = [" ".join(str(c.value) for c in row if c.value is not None) for row in sheet.iter_rows(min_row=4, min_col=3)]
    if case["period_years"]:
        require(any(re.findall(r"\b(?:19|20)\d{2}\b", line) == case["period_years"] for line in lines), "source period order missing or changed")
    if case["unit_word"]:
        require(any(case["unit_word"] in line.lower() for line in lines[:10]), "source units missing or changed")
    cursor, section_positions = 0, []
    for section in case["period_sections"]:
        index = next((i for i in range(cursor, len(lines)) if label_matches(section, lines[i])), None)
        require(index is not None, f"source period section missing: {section}")
        section_positions.append(index + 4)
        cursor = index + 1
    if section_positions:
        ending_ids = {r["source_id"] for r in case["endings"]}
        groups, group = [], []
        for row in case["expected_rows"]:
            group.append(row)
            if row["source_id"] in ending_ids:
                groups.append(group)
                group = []
        require(not group and len(groups) == len(section_positions), "source section boundaries do not cover the expected rows")
        for i, (start, group) in enumerate(zip(section_positions, groups)):
            stop = section_positions[i + 1] - 1 if i + 1 < len(section_positions) else sheet.max_row
            assert_rows(sheet, group, reject_extra=True, min_row=start + 1, max_row=stop)


def assert_page_endings(result, case):
    """Do not let a repeated balance on one page cover another page's missing row."""
    from normalization import parse_numeric_token
    from statements import _match_desc_first
    tables = result.statements[case["statement_type"]].attrs.get("source_tables", [])
    for page in case["source"]["pages"]:
        expected = [r for r in case["endings"] if r["page"] == page]
        actual = [row for t in tables if t.get("source_page") == page for row in t["rows"]]
        cursor = 0
        for source in expected:
            index = next((i for i in range(cursor, len(actual)) if label_matches(source["label"], " ".join(actual[i]))), None)
            require(index is not None, f"missing page-specific ending: {source['source_id']}")
            text = re.sub(r"\s+", " ", " ".join(actual[index])).strip()
            matched = _match_desc_first(text, len(source["values"]))
            require(matched is not None, f"incomplete ending vector: {source['source_id']}")
            values = [format(Decimal(str(parse_numeric_token(v).value)).normalize(), "f")
                      if parse_numeric_token(v).status == "NUMERIC" else "SOURCE_DASH" for v in matched[1]]
            require(values == source["values"], f"wrong page-specific ending: {source['source_id']}")
            cursor = index + 1


def assert_selected_endings(result, case):
    from normalization import parse_numeric_token
    from statements import _match_desc_first
    from financial_statement_extract.table_layout import selected_grids
    selected = selected_grids(result.raw_table_cells)
    # This contract concerns source-verified endings that at least one reader captured.
    all_grids = selected_grids([{**c, "selected": True} for c in result.raw_table_cells])
    for source in case["endings"]:
        def matches(tables):
            for table in tables:
                if table["source_page"] != source["page"]:
                    continue
                for row in table["rows"]:
                    text = re.sub(r"\s+", " ", " ".join(row)).strip()
                    if not label_matches(source["label"], text):
                        continue
                    match = _match_desc_first(text, len(source["values"]))
                    if match:
                        values = [format(Decimal(str(parse_numeric_token(v).value)).normalize(), "f")
                                  if parse_numeric_token(v).status == "NUMERIC" else "SOURCE_DASH" for v in match[1]]
                        if values == source["values"]:
                            return True
            return False
        alternatives, actual = matches(all_grids), matches(selected)
        if alternatives:
            require(actual, f"selection discarded a source ending on page {source['page']}: {source['label']}")
