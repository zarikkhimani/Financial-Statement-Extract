"""Read-only, same-directory HTML corroboration. Never fetch remote filings."""
from __future__ import annotations

from pathlib import Path

from financial_statement_extract.detection import CORE, financial_rows, fingerprint
from html_extractor import HTML_SUFFIXES, extract_html_filing


def matching_html_guidance(pdf_path: Path, texts: list[str]) -> tuple[dict[str, set[str]], str, tuple[str, ...]]:
    candidates = sorted(path for path in pdf_path.parent.iterdir() if path.suffix.lower() in HTML_SUFFIXES and path.is_file())
    exact = [path for path in candidates if path.stem.casefold() == pdf_path.stem.casefold()]
    candidates = exact or candidates
    if len(candidates) > 8:
        return {}, "", ("More than eight neighboring HTML files; no unambiguous companion. Using PDF evidence only.",)
    pdf_keys = {fingerprint(row) for text in texts for row in financial_rows(text)}
    matches = []
    warnings = []
    for path in candidates:
        try:
            rows, _, _, _, _ = extract_html_filing(path)
        except (OSError, ValueError) as exc:
            warnings.append(f"HTML guidance unavailable for {path.name}: {exc}. Using PDF evidence.")
            continue
        grouped: dict[str, set[str]] = {}
        for row in rows:
            kind = row.get("statement_type_hint")
            if kind and financial_rows(row["raw_text"]):
                grouped.setdefault(kind, set()).add(fingerprint(row["raw_text"]))
        overlap = {kind: keys & pdf_keys for kind, keys in grouped.items()}
        identity_types = (grouped.keys() & CORE) or grouped.keys()
        matched = sum(len(overlap[kind]) for kind in identity_types)
        total = sum(len(grouped[kind]) for kind in identity_types)
        # Filename alone is never identity evidence. Requiring numeric rows also
        # prevents a wrong-year filing with identical statement titles guiding us.
        strong = matched >= 3 if path in exact else matched >= 8 and sum(bool(keys) for keys in overlap.values()) >= 2
        if strong and matched / max(1, total) >= .35:
            matches.append((grouped, str(path)))
    if len(matches) == 1:
        return *matches[0], tuple(warnings)
    if len(matches) > 1:
        warnings.append("Multiple HTML companions match the PDF; using PDF-only detection rather than guessing.")
    elif candidates:
        warnings.append("Neighboring HTML did not sufficiently match PDF row labels and values; using PDF-only detection.")
    return {}, "", tuple(warnings)
