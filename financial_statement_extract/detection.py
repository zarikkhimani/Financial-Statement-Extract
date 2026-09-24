"""Evidence-based statement blocks; never fill the span between distant pages.

Classification keys are internal only. Source headings remain verbatim.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

from models import StatementPage, StatementPagePlan
from normalization import normalize_financial_text
from structure import detect_statement_heading_type

CORE = {"IncomeStatement", "BalanceSheet", "CashFlowStatement"}
NUMBER = r"(?:[$€£]?\s*\(?[-+]?\d[\d,]*(?:\.\d+)?\)?%?|[—–-])"
TRAILING_VALUES = re.compile(rf"(?:\s+{NUMBER})+\s*$")
BOUNDARY = re.compile(
    r"^(?:notes? to (?:the )?(?:(?:condensed|consolidated|combined) )*(?:financial statements|financials)|"
    r"notes? to (?:the )?schedule[s]? of investments|"
    r"(?:report of |independent ).*(?:auditor|accounting firm)|"
    r"management[’']?s discussion|financial highlights|"
    r"(?:item\s+\d+[a-z]?\.?\s+)?(?:controls and procedures|signatures)|"
    r"note\s+\d+[.:\s]|\d+\.\s+(?:organization|significant accounting policies))", re.I,
)
CUES = {
    "IncomeStatement": r"income|earnings|revenue|expenses?|profit|loss|per share|weighted.average",
    "BalanceSheet": r"assets?|liabilit|equity|capital|receivable|payable|cash|debt",
    "CashFlowStatement": r"cash|operating activities|investing activities|financing activities|depreciation|supplemental|reinvestment|distributions|PIK|interest paid",
    "PartnersCapital": r"net assets|capital|contributions|distributions|balance|operations",
    "StockholdersEquityStatement": r"equity|shares|capital|balance|earnings|repurchases|dividends",
    "ScheduleOfInvestments": r"fair value|principal|maturity|interest rate|portfolio|investments|cost|\d[.]\d+%",
}


def is_section_boundary(line: str) -> bool:
    return bool(BOUNDARY.search(normalize_financial_text(line)))


def financial_rows(text: str) -> list[str]:
    result = []
    for line in text.splitlines():
        candidate = re.sub(r"\s+Note\s+\d+\s*$", "", line, flags=re.I)
        candidate = re.sub(r"\s+(?:\(\d+\)){1,}\s*$", "", candidate)
        match = TRAILING_VALUES.search(candidate)
        if not match or not re.search(r"[A-Za-z]", line[:match.start()]):
            continue
        prefix = line[:match.start()].strip()
        if re.search(r"years? ended|months? ended|december|january|june|september|march|as of", prefix, re.I):
            # Dates embedded in equity row labels are genuine data.
            if not re.search(r"net assets|balance|capital", prefix, re.I):
                continue
        if len(prefix.split()) > 28 or re.search(r"\b(?:we|our|the company)\b.*\b(?:was|were|increased|decreased)\b", prefix, re.I):
            continue
        result.append(line)
    return result


def fingerprint(line: str) -> str:
    return re.sub(r"[^a-z0-9-]", "", line.casefold().replace(",", "").replace("—", "-"))


def source_headings(lines: list[str]) -> list[tuple[int, str, str]]:
    result = []
    covered = -1
    for index, line in enumerate(lines[:40]):
        if index <= covered or line.rstrip().endswith("."):
            continue
        for size in range(1, 4):
            parts = lines[index:index + size]
            if len(parts) != size:
                break
            title = "\n".join(parts)
            kind = detect_statement_heading_type(title)
            if kind:
                result.append((index, kind, title))
                covered = index + size - 1
                break
    return result


@dataclass
class PageEvidence:
    page: int
    lines: list[str]
    headings: list[tuple[int, str, str]]
    rows: list[str]
    boundary: bool
    blank: bool
    unreadable: bool

    def supports(self, kind: str, *, heading: bool = False, guided: set[str] | None = None) -> bool:
        if self.boundary or self.unreadable or not self.rows:
            return False
        if guided and len({fingerprint(row) for row in self.rows} & guided) >= 2:
            return True
        cue_text = self.lines[:20] + self.rows if kind == "ScheduleOfInvestments" else self.rows
        cue = bool(re.search(CUES.get(kind, r"(?!)"), "\n".join(cue_text), re.I))
        if heading:
            return len(self.rows) >= 2 or cue
        density = len(self.rows) / max(1, len(self.lines))
        return len(self.rows) >= 2 and (cue or (kind not in CORE and density >= .45))


def page_evidence(page: int, text: str, unreadable: bool) -> PageEvidence:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    headings = source_headings(lines)
    first_heading = headings[0][0] if headings else len(lines)
    boundary_at = next((i for i, line in enumerate(lines) if is_section_boundary(line)), len(lines))
    toc = any(re.search(r"^(?:table of contents|index to (?:consolidated )?financial statements)$", line, re.I)
              for line in lines[:8])
    # SEC print-to-PDF files repeat a "Table of Contents" navigation link on
    # every page. It is not a TOC boundary when a real statement heading follows.
    boundary = (toc and not headings) or (boundary_at < len(lines) and boundary_at <= first_heading)
    # A note section beginning after a statement on the same page cannot make
    # the preceding statement disappear or provide continuation evidence.
    data_lines = lines[:boundary_at]
    blank = not unreadable and (not lines or (len(lines) == 1 and bool(re.fullmatch(r"\d{1,4}|[—–_.-]+", lines[0]))))
    return PageEvidence(page, lines, headings, financial_rows("\n".join(data_lines)), boundary, blank, unreadable)


def detect_statement_plan(
    texts: list[str], source_path: str = "", *, unreadable_pages: set[int] | None = None,
    guidance: dict[str, set[str]] | None = None, guidance_source: str = "",
    guidance_warnings: tuple[str, ...] = (),
) -> StatementPagePlan:
    guidance = guidance or {}
    evidence = [page_evidence(i, text, i in (unreadable_pages or set())) for i, text in enumerate(texts, 1)]
    records = {p.page: StatementPage(p.page, "unknown" if p.unreadable else "blank" if p.blank else "excluded",
                                   evidence=("No statement evidence",)) for p in evidence}
    blocks: list[list[StatementPage]] = []
    current: list[StatementPage] = []
    kind = title = ""
    gaps: list[PageEvidence] = []
    warnings = list(guidance_warnings)
    for index, page in enumerate(evidence):
        if page.boundary:
            kind = title = ""
            current = []
            gaps = []
            records[page.page] = StatementPage(page.page, "supporting", evidence=("TOC, notes, auditor or narrative section boundary",))
            continue
        headings = page.headings
        page_keys = {fingerprint(row) for row in page.rows}
        overlaps = sorted(((len(page_keys & keys), t) for t, keys in guidance.items()), reverse=True)
        guided_kind = overlaps[0][1] if overlaps and overlaps[0][0] >= 2 and (
            len(overlaps) == 1 or overlaps[0][0] > overlaps[1][0]) else ""
        if headings or guided_kind:
            new_kind, new_title = (headings[0][1], headings[0][2]) if headings else (guided_kind, "")
            supported = page.supports(new_kind, heading=True, guided=guidance.get(new_kind))
            prose = sum(len(line) > 100 for line in page.lines)
            footnotes = any(re.match(r"^\(\d+\)\s+\w", line) and len(line) > 80 for line in page.lines)
            if new_kind == "ScheduleOfInvestments" and footnotes and len(page.rows) / max(1, len(page.lines)) < .15:
                records[page.page] = StatementPage(page.page, "supporting", new_kind, new_title, .85,
                                                  ("Schedule explanatory footnotes without a statement table",))
                kind = title = ""
                current = []
                gaps = []
                continue
            if not supported:
                # A title-only page may lead a statement across conversion blanks.
                for following in ([] if prose > 2 else evidence[index + 1:index + 4]):
                    if following.boundary or following.unreadable:
                        break
                    if following.blank:
                        continue
                    supported = (not following.headings or following.headings[0][1] == new_kind) and following.supports(new_kind)
                    break
            if not supported:
                kind = title = ""
                current = []
                gaps = []
                continue
            if new_kind != kind or not current:
                current = []
                blocks.append(current)
            title = new_title or (title if new_kind == kind else "")
            kind = new_kind
            reason = "Source heading and statement data" if headings else "Matched HTML statement rows and PDF data"
            if guided_kind:
                reason += "; corroborated by matching HTML"
            item = StatementPage(page.page, "data" if page.rows else "title", kind, title, .95, (reason,),
                                 tuple(dict.fromkeys(t for _, t, _ in headings)) or (kind,))
        elif kind == "ScheduleOfInvestments" and any(re.match(r"^\(\d+\)\s+\w", line) for line in page.lines[:8]) and len(page.rows) / max(1, len(page.lines)) < .15:
            records[page.page] = StatementPage(page.page, "supporting", kind, title, .85,
                                              ("Schedule explanatory footnotes; retained as section context, not table input",))
            gaps = []
            continue
        elif kind and (page.blank or page.unreadable) and len(gaps) < 2:
            gaps.append(page)
            continue
        elif kind and page.supports(kind, guided=guidance.get(kind)):
            item = StatementPage(page.page, "data", kind, title, .8, ("Contiguous statement-like table continuation",))
        elif kind and len(page.lines) >= 2 and all(re.fullmatch(r"[\d.,()$€£%\s—–-]+", line) for line in page.lines):
            item = StatementPage(page.page, "unknown", kind, title, .2,
                                 ("Numeric-only continuation lacks labels; review required",))
        else:
            kind = title = ""
            current = []
            gaps = []
            continue
        for gap in gaps:
            if gap.unreadable:
                unknown = StatementPage(gap.page, "unknown", kind, title, 0., ("Unreadable page between statement pages; review required",))
                current.append(unknown)
                records[gap.page] = unknown
            else:
                records[gap.page] = StatementPage(gap.page, "blank", kind, title, .9, ("Conversion gap between statement pages; excluded",))
        gaps = []
        current.append(item)
        records[page.page] = item
        if any(is_section_boundary(line) for line in page.lines):
            kind = title = ""
            current = []

    # Score contiguous groups, not individual core pages. A 200-page investment
    # schedule does not separate its surrounding balance sheet and cash flows.
    groups: list[list[StatementPage]] = []
    for block in blocks:
        if not block:
            continue
        between = range(groups[-1][-1].page + 1, block[0].page) if groups else ()
        linked = groups and all(records[p].role == "blank" or
                                (records[p].role == "supporting" and records[p].statement_type == "ScheduleOfInvestments")
                                for p in between)
        if groups and (block[0].page - groups[-1][-1].page <= 4 or linked):
            groups[-1].extend(block)
        else:
            groups.append(list(block))
    def score(group):
        kinds = {kind for item in group for kind in (item.statement_types or (item.statement_type,))}
        corroborated = sum("HTML" in " ".join(item.evidence) for item in group)
        return (len(kinds & CORE), len(kinds), min(corroborated, 5), min(len(group), 10))
    groups.sort(key=score, reverse=True)
    chosen = groups[0] if groups else []
    ambiguous = len(groups) > 1 and score(groups[1]) == score(chosen)
    if ambiguous:
        warnings.append("Equally supported statement sections found at pages " + ", ".join(str(group[0].page) for group in groups if score(group) == score(chosen)) + "; review the proposed selection.")
    selected = tuple(sorted({item.page for item in chosen}))
    for number, item in records.items():
        if item.role in {"title", "data"} and number not in selected:
            records[number] = replace(item, role="excluded", evidence=item.evidence + ("Outside the best-supported statement section",))
    if any(item.role == "unknown" for item in chosen):
        warnings.append("Unreadable or unclassified numeric pages interrupt a statement; OCR or manual review is required.")
    chosen_types = {kind for item in chosen for kind in (item.statement_types or (item.statement_type,))}
    missing = CORE - chosen_types
    if missing:
        warnings.append("Not all core statement types were detected: " + ", ".join(sorted(missing)) + ". Verify completeness.")
    return StatementPagePlan(source_path, "auto_html_guided" if guidance_source else "auto", selected, selected, selected,
                             tuple(records.values()), ambiguous or any(item.role == "unknown" for item in chosen),
                             tuple(warnings), guidance_source=guidance_source)
