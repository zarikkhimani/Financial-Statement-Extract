"""Geometry recovery for ruled equity rollforwards with open header borders."""
from __future__ import annotations

from bisect import bisect_right

from normalization import parse_numeric_token


def equity_grid(page, tables) -> list[list[str]] | None:
    """Reuse wide rule columns, reading all rows including gaps between rule boxes.

    Narrow currency/spacer subdivisions belong to the next wide column. This is
    deliberately equity-only: arbitrary investment grids need their own schema.
    """
    if not tables:
        return None
    first = tables[0]
    major = [cell for cell in first.rows[0].cells if cell and cell[2] - cell[0] >= 15]
    if len(major) < 3 or major[0][2] - major[0][0] < page.width * 0.25:
        return None
    boundaries = [cell[2] for cell in major[:-1]]
    words = page.extract_words(x_tolerance=1, y_tolerance=2)
    lines = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if not lines or abs(lines[-1][0]["top"] - word["top"]) > 2:
            lines.append([])
        lines[-1].append(word)
    result = []
    started = False
    for line in lines:
        line.sort(key=lambda w: w["x0"])
        text = " ".join(w["text"] for w in line)
        if "unaudited" in text.lower() or "in millions" in text.lower() or "in thousands" in text.lower():
            started = True
            result = []
            continue
        if not started:
            # Without a unit note, only use rows near the known first data box.
            if line[0]["top"] < first.bbox[1] - 45:
                continue
            started = True
        if text.lower().startswith(("see accompanying", "notes to ")):
            break
        if line[0]["top"] > max(t.bbox[3] for t in tables) + 15:
            break
        row = [""] * len(major)
        if line[0]["top"] < first.bbox[1]:
            groups = []
            for word in line:
                if groups and word["x0"] - groups[-1]["x1"] <= 4:
                    groups[-1]["text"] += " " + word["text"]
                    groups[-1]["x1"] = word["x1"]
                else:
                    groups.append(dict(word))
            line = groups
        for word in line:
            col = bisect_right(boundaries, word["x0"] if word["top"] < first.bbox[1]
                               else (word["x0"] + word["x1"]) / 2)
            row[col] = (row[col] + " " + word["text"]).strip()
        result.append(row)
    # Must have real multiple-component balances, not just a matching title.
    count = sum(sum(parse_numeric_token(v).status == "NUMERIC" for v in row[1:]) >= 3 for row in result)
    return result if count >= 2 else None
