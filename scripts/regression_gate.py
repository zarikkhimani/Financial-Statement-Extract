"""Read-only collection regression gate and single-filing candidate capture.

Exit 0: no unreviewed changes within the stated scope, not financial certification.
Exit 1: regressions or changes requiring source review. Exit 2: invalid/incomplete evidence.
Requires the project's dev dependencies. No production parser is imported by compare.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from difflib import SequenceMatcher
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import traceback
import unicodedata
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
PHASE3_SHA256 = "064bca779faac8f3ee88585baed69dbf526e9346626afabe692bf68c0d54219c"
ORDER = ["IncomeStatement", "CashFlowStatement", "BalanceSheet", "PartnersCapital", "ScheduleOfInvestments"]
CONTEXT_FIELDS = ("period_labels", "unit_label", "scale_factor", "currency", "unit_exceptions", "raw_unit_note")
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CONTEXT = re.compile(r"\b(?:thousands?|millions?|billions?|dollars?|usd|eur|gbp|months? ended|years? ended|"
                     r"quarters? ended|six months|three months|twelve months|per share|percent)\b", re.I)
SECTIONS = re.compile(r"^(?:(?:net )?cash (?:flows? )?(?:from |used in |provided by )?)?"
                      r"(?:operating|investing|financing) activit|^(?:assets|liabilities|equity|net assets)$", re.I)
DASHES = {"-", "\u2013", "\u2014"}
CURRENCIES = {"$", "\u20ac", "\u00a3", "\u00a5"}
NUMERIC_SYMBOLS = {"%", "(", ")", "+", "\u2212"}


class EvidenceError(ValueError):
    pass


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def read_json(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value):
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "wt", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=True, allow_nan=False, indent=2 if path.suffix != ".gz" else None)


def normalized(value):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value))).strip().casefold()


def label_key(value):
    return re.sub(r"[^\w]", "", normalized(value))


def contained(root, relative):
    root = Path(root).resolve()
    result = (root / relative).resolve()
    if not result.is_relative_to(root) or result == root:
        raise EvidenceError(f"Artifact escapes its directory: {relative}")
    return result


def verify_baseline(folder, expected_sha=PHASE3_SHA256):
    folder = Path(folder).resolve()
    manifest_path = folder / "manifest.json"
    if sha(manifest_path) != expected_sha:
        raise EvidenceError("Baseline manifest does not match the pinned SHA-256")
    manifest = read_json(manifest_path)
    entries = manifest.get("artifacts", [])
    paths = [entry["path"] for entry in entries]
    if len(paths) != len(set(paths)):
        raise EvidenceError("Duplicate baseline artifact paths")
    for entry in entries:
        path = contained(folder, entry["path"])
        if not path.is_file() or sha(path) != entry["sha256"]:
            raise EvidenceError(f"Baseline artifact changed: {entry['path']}")
    if "baseline-index.json" not in paths or "reviewed-cases.json" not in paths:
        raise EvidenceError("Baseline index or reviewed cases are not sealed")
    index = read_json(folder / "baseline-index.json")
    runs = {}
    for entry in index["runs"]:
        key = f'{entry["scope"]}/{entry["job"]["job_id"]}'
        if key in runs:
            raise EvidenceError(f"Duplicate baseline run: {key}")
        runs[key] = entry
        for name in ("result.json",):
            if f"{key}/{name}" not in paths:
                raise EvidenceError(f"Unsealed run artifact: {key}/{name}")
        if entry["run"]["status"] == "completed":
            required = [f"{key}/extraction.json.gz", f"{key}/{Path(entry['run']['workbook']).name}"]
            if any(name not in paths for name in required):
                raise EvidenceError(f"Unsealed completed run: {key}")
    if len(runs) != index["summary"]["executed_runs"]:
        raise EvidenceError("Baseline run count is inconsistent")
    return index, runs


def cell_value(cell):
    value = cell.value
    if cell.data_type in {"f", "e", "b"}:
        return [cell.column, cell.data_type, str(value), cell.number_format]
    if isinstance(value, (int, float, Decimal)):
        number = Decimal(str(value))
        if not number.is_finite():
            raise EvidenceError(f"Nonfinite workbook value at {cell.coordinate}")
        return [cell.column, "number", format(number.normalize(), "f"), cell.number_format]
    if isinstance(value, (datetime, date)):
        return [cell.column, "date", value.isoformat(), cell.number_format]
    text = normalized(value)
    if text in DASHES:
        return [cell.column, "dash", "-", ""]
    if text in CURRENCIES or text in NUMERIC_SYMBOLS:
        return [cell.column, "numeric_symbol", text, ""]
    if re.search(r"\d", text) or CONTEXT.search(text):
        return [cell.column, "context", text, ""]
    return [cell.column, "text", label_key(text), ""]


def canonical_row(cells, captions=()):
    populated = [c for c in cells if c.value not in (None, "")]
    if not populated:
        return None
    values = [cell_value(c) for c in populated]
    texts = [str(c.value) for c in populated if c.data_type == "s"]
    title = len(populated) == 1 and normalized(populated[0].value) in captions
    sensitive = any(c[1] not in {"text", "dash"} for c in values)
    sensitive |= len(values) > 1 and any(c[1] == "text" for c in values)
    sensitive |= any(SECTIONS.search(normalized(text)) for text in texts)
    if title and not any(c[1] != "text" for c in values):
        sensitive = False
    # Match labels and field positions, never choose a row because its amounts agree.
    anchor = tuple((c.column, "".join(re.findall(r"[a-z]+", normalized(c.value))))
                   for c in populated if c.data_type == "s" and re.search(r"[A-Za-z]", str(c.value)))
    if not anchor:
        anchor = (("unlabelled", tuple((v[0], v[1]) for v in values)),)
    return {"row": populated[0].row, "label": " | ".join(texts), "key": anchor,
            "critical": bool(sensitive), "cells": values}


def layout_issues(archive):
    issues = []
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {r.attrib["Id"]: r.attrib["Target"] for r in rels}
    for sheet in workbook.findall("s:sheets/s:sheet", NS):
        name = sheet.get("name")
        target = targets[sheet.get(f"{{{REL}}}id")]
        member = target.lstrip("/") if target.startswith("/") else "xl/" + target
        root = ET.fromstring(archive.read(member))
        found = []
        if sheet.get("state", "visible") != "visible":
            found.append("hidden_sheet")
        if root.find("s:mergeCells", NS) is not None:
            found.append("merged_cells")
        if root.find("s:sheetViews/s:sheetView/s:pane", NS) is not None:
            found.append("freeze_or_split_panes")
        defaults = root.find("s:sheetFormatPr", NS)
        if defaults is not None:
            if defaults.get("zeroHeight") in {"1", "true"} or float(defaults.get("defaultRowHeight", "1")) == 0:
                found.append("hidden_or_zero_height_default_rows")
            if float(defaults.get("defaultColWidth", "1")) == 0:
                found.append("zero_width_default_columns")
        columns = root.findall("s:cols/s:col", NS)
        if any(c.get("hidden") in {"1", "true"} or float(c.get("width", "1")) == 0 for c in columns):
            found.append("hidden_or_zero_width_column")
        for col in (1, 2):
            dim = next((c for c in columns if int(c.get("min")) <= col <= int(c.get("max"))), None)
            if dim is None or abs(float(dim.get("width", "0")) - 1.7109375) > 0.000001:
                found.append(f"left_margin_width_{col}")
        for row in root.findall("s:sheetData/s:row", NS):
            if row.get("hidden") in {"1", "true"} or float(row.get("ht", "1")) == 0:
                found.append("hidden_or_zero_height_row")
            for cell in row:
                populated = any(cell.find(f"s:{tag}", NS) is not None for tag in ("v", "f", "is"))
                if populated and (int(row.get("r")) <= 3 or re.match(r"^(?:A|B)\d+$", cell.get("r", ""))):
                    found.append("nonempty_margin")
                if cell.get("t") == "e":
                    found.append("excel_error_cell")
        issues.extend({"sheet": name, "problem": value} for value in sorted(set(found)))
    return issues


def statement_context(frame):
    attrs = frame.get("attrs", {})
    result = {key: attrs.get(key) for key in CONTEXT_FIELDS}
    result["source_pages"] = sorted({t["source_page"] for t in attrs.get("source_tables", []) if t.get("source_page") is not None})
    return result


def workbook_snapshot(path, payload):
    statements = payload["statements"]
    order = [kind for kind in ORDER if kind in statements]
    order.extend(kind for kind in statements if kind not in order)
    result = {"statements": {}, "layout": [], "auxiliary_sheets": []}
    with ZipFile(path) as archive:
        result["layout"] = layout_issues(archive)
    book = load_workbook(path, read_only=True, data_only=False)
    try:
        if len(book.sheetnames) < len(order):
            raise EvidenceError("Workbook has fewer sheets than its statement metadata")
        for kind, sheet in zip(order, book):
            frame = statements[kind]
            attrs = frame.get("attrs", {})
            captions = {normalized(attrs.get(key, "")) for key in ("company_name", "statement_title")}
            rows = [value for row in sheet.iter_rows() if (value := canonical_row(row, captions)) is not None]
            result["statements"][kind] = {"sheet": sheet.title, "rows": rows, "context": statement_context(frame)}
        result["auxiliary_sheets"] = book.sheetnames[len(order):]
    finally:
        book.close()
    return result


def event(run_id, code, location, before, after, *, severity="block"):
    content = {"run_id": run_id, "code": code, "location": location, "before": before, "after": after}
    return {"issue_id": digest(content), "severity": severity, **content}


def compare_rows(run_id, kind, before, after):
    result = []
    left_keys, right_keys = [r["key"] for r in before], [r["key"] for r in after]
    operations = [("equal", 0, len(before), 0, len(after))] if left_keys == right_keys else SequenceMatcher(
        None, left_keys, right_keys, autojunk=False).get_opcodes()
    for tag, a, b, c, d in operations:
        if tag == "equal":
            for old, new in zip(before[a:b], after[c:d]):
                if old["cells"] != new["cells"]:
                    result.append(event(run_id, "ROW_VALUES_OR_FIELDS_CHANGED", f'{kind}:row:{old["row"]}',
                                        {"label": old["label"], "cells": old["cells"]},
                                        {"label": new["label"], "cells": new["cells"]},
                                        severity="block" if old["critical"] or new["critical"] else "warning"))
        else:
            old, new = before[a:b], after[c:d]
            sensitive = any(r["critical"] for r in old + new)
            # Pure headings can change without making a number-based release fail.
            result.append(event(run_id, "ROWS_REMOVED_ADDED_OR_REORDERED", f"{kind}:rows:{a}:{b}",
                                [{"label": r["label"], "cells": r["cells"]} for r in old],
                                [{"label": r["label"], "cells": r["cells"]} for r in new],
                                severity="block" if sensitive else "warning"))
    return result


def compare_snapshots(run_id, before, after):
    changes = []
    old, new = before["statements"], after["statements"]
    for kind in sorted(old.keys() | new.keys()):
        if kind not in old or kind not in new:
            changes.append(event(run_id, "STATEMENT_SET_CHANGED", kind, kind in old, kind in new))
            continue
        if old[kind]["context"] != new[kind]["context"]:
            changes.append(event(run_id, "PERIOD_UNIT_OR_SOURCE_CONTEXT_CHANGED", kind, old[kind]["context"], new[kind]["context"]))
        if old[kind]["sheet"] != new[kind]["sheet"]:
            changes.append(event(run_id, "SHEET_TITLE_CHANGED", kind, old[kind]["sheet"], new[kind]["sheet"], severity="warning"))
        changes.extend(compare_rows(run_id, kind, old[kind]["rows"], new[kind]["rows"]))
    if after["layout"]:
        changes.append(event(run_id, "WORKBOOK_RULE_VIOLATION", "workbook", before["layout"], after["layout"], severity="error"))
    if before["auxiliary_sheets"] != after["auxiliary_sheets"]:
        changes.append(event(run_id, "AUXILIARY_SHEETS_CHANGED", "workbook", before["auxiliary_sheets"], after["auxiliary_sheets"], severity="warning"))
    return changes


def run_files(root, run_id, *, baseline=False):
    directory = contained(root, run_id)
    result = read_json(directory / "result.json")
    payload, path = None, None
    if result["status"] == "completed":
        recorded = Path(result["workbook"])
        path = directory / recorded.name if baseline else recorded.resolve()
        if not path.is_relative_to(directory.resolve()) or not path.is_file():
            raise EvidenceError("Candidate workbook must exist inside its own run directory; stale external paths are rejected")
        if sha(path) != result["workbook_sha256"]:
            raise EvidenceError("Workbook hash does not match its result record")
        if result.get("process_exit_code", 0) != 0:
            raise EvidenceError("Completed run has a nonzero process exit code")
        payload = read_json(directory / "extraction.json.gz")
        if not isinstance(payload.get("statements"), dict) or not payload["statements"]:
            raise EvidenceError("Completed run has no statement metadata")
        plan = payload.get("page_plan") or {}
        if plan.get("selected_pages") != result.get("selected_pages"):
            raise EvidenceError("Saved page plan disagrees with the run result")
    elif result["status"] not in {"failed", "process_failed", "timeout"}:
        raise EvidenceError(f"Run is not complete: {result['status']}")
    return result, payload, path


def compare_run(baseline, candidate, run_id, entry, source_hashes):
    events = []
    before, old_payload, old_path = run_files(baseline, run_id, baseline=True)
    after, new_payload, new_path = run_files(candidate, run_id)
    expected = entry["job"]
    if before["job"] != expected or before["scope"] != entry["scope"]:
        raise EvidenceError("Baseline index and saved run disagree")
    fields = ("job_id", "filing_id", "input_sha256", "entity", "filing_type", "reporting_period")
    if any(after["job"].get(key) != expected.get(key) for key in fields) or after["scope"] != before["scope"]:
        raise EvidenceError("Candidate input identity, entity, period or scope differs from the baseline job")
    source = Path(after["job"]["source_path"]).resolve()
    if source not in source_hashes:
        source_hashes[source] = sha(source)
    if source_hashes[source] != expected["input_sha256"]:
        raise EvidenceError("Actual source PDF hash differs from the baseline")
    if after.get("pages") != before.get("pages"):
        events.append(event(run_id, "REQUESTED_PAGES_CHANGED", "request", before.get("pages"), after.get("pages")))
    if after["status"] != "completed":
        old_failure = {k: before.get(k) for k in ("status", "error_type", "error")}
        new_failure = {k: after.get(k) for k in ("status", "error_type", "error")}
        if before["status"] != "completed" and old_failure == new_failure:
            return {"run_id": run_id, "status": "known_failure_unchanged", "events": events, "statements_compared": 0}
        events.append(event(run_id, "NEW_OR_CHANGED_RUN_FAILURE", "execution", old_failure, new_failure))
    elif before["status"] != "completed":
        snapshot = workbook_snapshot(new_path, new_payload)
        events.append(event(run_id, "RECOVERED_RUN_REQUIRES_SOURCE_REVIEW", "execution", before["status"],
                            {"status": "completed", "content_sha256": digest(snapshot)}))
        if snapshot["layout"]:
            events.append(event(run_id, "WORKBOOK_RULE_VIOLATION", "workbook", [], snapshot["layout"], severity="error"))
    else:
        if before["selected_pages"] != after["selected_pages"]:
            events.append(event(run_id, "SELECTED_PAGES_CHANGED", "pages", before["selected_pages"], after["selected_pages"]))
        old = workbook_snapshot(old_path, old_payload)
        new = old if old_path == new_path and old_payload == new_payload else workbook_snapshot(new_path, new_payload)
        events.extend(compare_snapshots(run_id, old, new))
    return {"run_id": run_id, "status": "compared", "events": events,
            "statements_compared": len(old_payload["statements"]) if old_payload and new_payload else 0,
            "candidate_workbook_sha256": after.get("workbook_sha256")}


def compare_collection(baseline, candidate, *, expected_sha=PHASE3_SHA256, selected=None, decisions=None, progress=None):
    baseline, candidate = Path(baseline).resolve(), Path(candidate).resolve()
    index, entries = verify_baseline(baseline, expected_sha)
    selection = sorted(set(selected or entries))
    if selected and len(selected) != len(set(selected)):
        raise EvidenceError("Repeated run selection")
    if not selection or any(key not in entries for key in selection):
        raise EvidenceError("Unknown or empty run selection")
    expected_keys = set(selection)
    candidate_keys = {f"{scope}/{p.parent.name}" for scope in ("core", "full") for p in (candidate / scope).glob("*/result.json")}
    results, source_hashes = [], {}
    for run_id in selection:
        try:
            result = compare_run(baseline, candidate, run_id, entries[run_id], source_hashes)
        except (OSError, ValueError, KeyError, TypeError, ET.ParseError, BadZipFile) as error:
            result = {"run_id": run_id, "status": "invalid_evidence", "statements_compared": 0,
                      "events": [event(run_id, "INVALID_OR_MISSING_EVIDENCE", "input", None, str(error), severity="error")]}
        results.append(result)
        if progress:
            progress(len(results), len(selection), run_id)
    if not selected and candidate_keys - expected_keys:
        results.append({"run_id": "collection", "status": "invalid_evidence", "statements_compared": 0,
                        "events": [event("collection", "UNEXPECTED_RUNS", "coverage", [], sorted(candidate_keys - expected_keys), severity="error")]})
    accepted = {}
    if decisions:
        if decisions.get("baseline_manifest_sha256") != expected_sha:
            raise EvidenceError("Review decisions belong to a different baseline")
        for decision in decisions.get("accepted_changes", []):
            if not decision.get("reason", "").strip() or not decision.get("source_evidence", "").strip():
                raise EvidenceError("Every accepted change needs a reason and specific source evidence")
            identifier = decision["issue_id"]
            if identifier in accepted:
                raise EvidenceError("Duplicate review decision")
            accepted[identifier] = decision
    events = [e for result in results for e in result["events"]]
    eligible = {e["issue_id"] for e in events if e["severity"] == "block"}
    if accepted.keys() - eligible:
        raise EvidenceError("Review decisions contain stale, unknown or non-waivable issues")
    for item in events:
        if item["issue_id"] in accepted:
            item["severity"] = "reviewed_change"
            item["review"] = accepted[item["issue_id"]]
    counts = Counter(e["severity"] for e in events)
    exit_code = 2 if counts["error"] else 1 if counts["block"] else 0
    known_cases = read_json(baseline / "reviewed-cases.json")["cases"]
    return {"schema_version": 1, "baseline_manifest_sha256": expected_sha, "baseline": str(baseline),
            "candidate": str(candidate), "scope": "selected_runs" if selected else "entire_collection",
            "self_comparison": baseline == candidate, "expected_runs": len(selection),
            "all_baseline_runs": len(entries), "unselected_runs": len(entries) - len(selection),
            "input_exceptions": index["summary"].get("input_exceptions", []),
            "baseline_known_cases": known_cases, "known_failures_unchanged": sum(r["status"] == "known_failure_unchanged" for r in results),
            "event_counts": dict(counts), "exit_code": exit_code,
            "verdict": "INVALID_EVIDENCE" if exit_code == 2 else "CHANGES_REQUIRE_REVIEW" if exit_code == 1 else "NO_UNREVIEWED_REGRESSIONS",
            "accuracy_certified": False, "runs": results,
            "limits": "Protects finished statement values, labels, field positions, periods, units and workbook rules. Raw-method values and complete source accuracy are not certified. Review decisions are recorded assertions, not automatic PDF validation."}


def markdown(report):
    lines = ["# Collection regression comparison", "", f'Verdict: **{report["verdict"]}**. Exit code: {report["exit_code"]}.', "",
             f'Scope: {report["scope"]}, {report["expected_runs"]}/{report["all_baseline_runs"]} baseline runs. '
             f'Unselected runs: {report["unselected_runs"]}.', "",
             f'Known run failures unchanged: {report["known_failures_unchanged"]}. '
             f'Events: {json.dumps(report["event_counts"], sort_keys=True)}.', "",
             "This measures changes from the observed baseline. Existing defects remain visible; numerical accuracy is not certified.", ""]
    if report["self_comparison"]:
        lines += ["This is a baseline identity control, not a fresh extraction test.", ""]
    lines += ["| Run | Result | Blocking | Invalid | Warnings | Reviewed |", "| --- | --- | ---: | ---: | ---: | ---: |"]
    for run in report["runs"]:
        c = Counter(e["severity"] for e in run["events"])
        lines.append(f'| {run["run_id"]} | {run["status"]} | {c["block"]} | {c["error"]} | {c["warning"]} | {c["reviewed_change"]} |')
    lines += ["", "Exact before/after values, issue IDs, reviewed-change evidence and baseline known cases are in comparison.json.", "",
              "Exit 0 means no unreviewed regression in the stated scope. Exit 1 requires source review. Exit 2 means invalid or incomplete evidence.", ""]
    return "\n".join(lines)


def serialize(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize(v) for v in value]
    if is_dataclass(value):
        return serialize(asdict(value))
    if hasattr(value, "columns") and hasattr(value, "to_dict"):
        return serialize({"columns": list(value.columns), "attrs": value.attrs, "rows": value.to_dict(orient="records")})
    if hasattr(value, "item"):
        return serialize(value.item())
    return str(value)


def capture(baseline, run_id, candidate, expected_sha=PHASE3_SHA256):
    _, entries = verify_baseline(baseline, expected_sha)
    if run_id not in entries:
        raise EvidenceError("Unknown baseline run")
    baseline, candidate = Path(baseline).resolve(), Path(candidate).resolve()
    if candidate.is_relative_to(baseline) or baseline.is_relative_to(candidate):
        raise EvidenceError("Candidate capture must be separate from the sealed baseline")
    directory = contained(candidate, run_id)
    if directory.exists():
        raise FileExistsError("Candidate run already exists; use a new directory")
    entry = entries[run_id]
    job, scope = entry["job"], entry["scope"]
    if sha(job["source_path"]) != job["input_sha256"]:
        raise EvidenceError("Source PDF changed")
    sys.path.insert(0, str(ROOT))
    from financial_statement_extract import extract_filing

    directory.mkdir(parents=True)
    request = {"job": job, "scope": scope, "source_root": str(ROOT), "python": sys.executable,
               "started_utc": datetime.now(timezone.utc).isoformat(), "pages": job[f"{scope}_pages"]}
    write_json(directory / "request.json", request)
    result = dict(request)
    try:
        extraction, workbook = extract_filing(
            job["source_path"], pages=job[f"{scope}_pages"], output_dir=directory,
            page_policy="exact", table_strategy="adaptive",
            metadata={"client_name": job["entity"], "year": job["reporting_period"].split()[-1], "period": job["filing_type"]},
            progress=lambda e: print(f"{e.stage.value}: {e.detail}", flush=True),
        )
        write_json(directory / "extraction.json.gz", serialize(vars(extraction)))
        result.update(status="completed", workbook=str(workbook.resolve()), workbook_sha256=sha(workbook),
                      selected_pages=list(extraction.page_plan.selected_pages), input_sha256=job["input_sha256"], process_exit_code=0)
    except Exception as error:
        result.update(status="failed", error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc(), process_exit_code=1)
        traceback.print_exc()
    result["finished_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(directory / "result.json", result)
    return 0 if result["status"] == "completed" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("compare", "capture"):
        p = commands.add_parser(name)
        p.add_argument("--baseline", type=Path, default=ROOT / "outputs/regression-phase3")
        p.add_argument("--baseline-sha256", default=PHASE3_SHA256)
        p.add_argument("--candidate", type=Path, required=True)
        if name == "compare":
            p.add_argument("--run", action="append", dest="selected", help="Explicit subset: core/JOB_ID or full/JOB_ID")
            p.add_argument("--decisions", type=Path)
            p.add_argument("--report-dir", type=Path, required=True)
        else:
            p.add_argument("--run", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "capture":
            return capture(args.baseline, args.run, args.candidate, args.baseline_sha256)
        report_dir = args.report_dir.resolve()
        roots = [args.baseline.resolve(), args.candidate.resolve()]
        if report_dir.exists() or any(report_dir.is_relative_to(p) or p.is_relative_to(report_dir) for p in roots):
            raise EvidenceError("Use a new report directory separate from baseline and candidate inputs")
        report = compare_collection(args.baseline, args.candidate, expected_sha=args.baseline_sha256,
                                    selected=args.selected, decisions=read_json(args.decisions) if args.decisions else None,
                                    progress=lambda n, total, key: print(f"Compared {n}/{total}: {key}", flush=True) if n % 20 == 0 or n == total else None)
        report_dir.mkdir(parents=True)
        write_json(report_dir / "comparison.json", report)
        (report_dir / "comparison.md").write_text(markdown(report), encoding="utf-8")
        print(f'{report["verdict"]}: {report_dir / "comparison.md"}', flush=True)
        return report["exit_code"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Invalid evidence: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
