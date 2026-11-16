"""Require complete collection evidence and code checks before local acceptance.

No publication, remote Git actions, or in-place baseline updates. A promotion
creates a new sealed baseline and optionally switches an explicit reference file.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import shutil
import subprocess
import sys
import time
import tomllib
from uuid import uuid4
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import regression_gate as gate  # noqa: E402
from scripts import regression_runner as runner  # noqa: E402


def require(condition, message):
    if not condition:
        raise gate.EvidenceError(message)


def inventory(paths):
    return [{"path": p.relative_to(ROOT).as_posix(), "sha256": gate.sha(p)} for p in sorted(set(paths))]


def tree_inventory(folder):
    return [{"path": p.relative_to(folder).as_posix(), "sha256": gate.sha(p)}
            for p in sorted(folder.rglob("*")) if p.is_file()]


def validation_inventory():
    paths = runner.source_files() + list((ROOT / "scripts").glob("*.py"))
    paths += [p for p in (ROOT / "tests").rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    paths += list((ROOT / "docs").rglob("*.md"))
    paths += [ROOT / name for name in ("README.md", "AGENTS.md", "MANIFEST.in", ".github/workflows/ci.yml")]
    return inventory(paths)


def load_reference(path):
    reference = gate.read_json(path)
    require(reference.get("schema_version") == 1, "Unsupported release reference schema")
    baseline = (ROOT / reference["baseline"]).resolve()
    index, entries = gate.verify_baseline(baseline, reference["baseline_manifest_sha256"])
    inputs_path = (ROOT / reference["input_inventory"]).resolve()
    require(gate.sha(inputs_path) == reference["input_inventory_sha256"], "Input inventory changed")
    inputs = [e for e in gate.read_json(inputs_path) if Path(e["original"]).suffix.lower() == ".pdf"]
    paths = [str(Path(e["original"]).resolve()) for e in inputs]
    require(len(paths) == len(set(paths)) and inputs, "Duplicate or empty PDF inventory")
    declared = {str(Path(e["original"]).resolve()): e["sha256"] for e in inputs}
    covered = set()
    for entry in entries.values():
        job = entry["job"]
        source = str(Path(job["source_path"]).resolve())
        require(declared.get(source) == job["input_sha256"], "Job PDF is absent from the input inventory")
        covered.add(source)
    for exception in index["summary"].get("input_exceptions", []):
        matches = [p for p, digest in declared.items() if digest.startswith(exception["filing_id"])]
        require(len(matches) == 1 and matches[0] not in covered, "Input exception is ambiguous or already selected")
        covered.add(matches[0])
    require(covered == set(declared), "Some PDFs have neither prepared jobs nor a recorded exception")
    for entry in inputs:
        require(gate.sha(entry["original"]) == entry["sha256"], f"Source PDF changed: {entry['original']}")
    return reference, baseline, index, entries, inputs


def verify_live_program(session, plan):
    runner.verify_snapshot(session, plan)
    live = inventory(runner.source_files())
    require(live == plan["source_files"] and gate.digest(live) == plan["program_sha256"],
            "Current extractor differs from the tested snapshot; start a new full session")
    require(gate.digest(plan["source_files"]) == plan["program_sha256"], "Invalid program fingerprint")
    require(gate.digest(plan["environment"]) == plan["environment_sha256"], "Invalid environment fingerprint")


def verified_attempts(session, plan, entries):
    require(plan["full_collection"] and len(plan["runs"]) == len(set(plan["runs"]))
            and set(plan["runs"]) == set(entries), "Release acceptance requires the entire collection")
    attempts = {}
    for run_id in plan["runs"]:
        attempt = runner.latest_attempt(session, plan, run_id)
        require(attempt is not None, f"Missing or interrupted latest attempt: {run_id}")
        receipt = gate.read_json(attempt / "receipt.json")
        require(not receipt["infrastructure_error"], f"Infrastructure failure: {run_id}")
        require(receipt["status"] in {"completed", "failed"}, f"Unverified outcome: {run_id}")
        attempts[run_id] = attempt
    return attempts


def numeric_cells(path, statement_count):
    """Count numeric storage cells, including numeric period headings, not accuracy."""
    with ZipFile(path) as archive:
        sheets = ET.fromstring(archive.read("xl/workbook.xml")).findall("s:sheets/s:sheet", gate.NS)
        relationships = {e.get("Id"): e.get("Target") for e in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))}
        total = 0
        for sheet in sheets[:statement_count]:
            target = relationships[sheet.get(f"{{{gate.REL}}}id")]
            target = target.lstrip("/") if target.startswith("/") else "xl/" + target
            root = ET.fromstring(archive.read(target))
            total += sum(c.get("t", "n") == "n" and c.find("s:v", gate.NS) is not None
                         and c.find("s:f", gate.NS) is None for c in root.findall(".//s:sheetData/s:row/s:c", gate.NS))
    return total


def copy_candidate(output, attempts):
    rows = []
    for run_id, attempt in attempts.items():
        record, payload, workbook = gate.run_files(attempt / "capture", run_id)
        receipt = gate.read_json(attempt / "receipt.json")
        target = gate.contained(output / "candidate", run_id)
        target.mkdir(parents=True)
        count = 0
        if workbook:
            shutil.copy2(workbook, target / workbook.name)
            shutil.copy2(attempt / "capture" / run_id / "extraction.json.gz", target / "extraction.json.gz")
            record["workbook"] = str(target / workbook.name)
            count = numeric_cells(workbook, len(payload["statements"]))
        gate.write_json(target / "result.json", record)
        rows.append({"run_id": run_id, "status": record["status"], "entity": record["job"]["entity"],
                     "numeric_storage_cells": count, "statement_count": len(payload["statements"]) if payload else 0,
                     "elapsed_seconds": receipt["elapsed_seconds"], "attempt": str(attempt),
                     "receipt_sha256": gate.sha(attempt / "receipt.json"),
                     "manual_cleanup_minutes": None})
    return rows


def quality_commands(output):
    scratch = ROOT / "tmp" / ("release-" + uuid4().hex)
    scratch.mkdir(parents=True)
    return [
        ("dependencies", [sys.executable, "-m", "pip", "check"]),
        ("lint", [sys.executable, "-m", "ruff", "check", "."]),
        ("tests", [sys.executable, "-m", "pytest", "--basetemp", str(scratch / "pytest")]),
        ("cli", [sys.executable, "-m", "financial_statement_extract", "--help"]),
        ("build", [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(output / "dist")]),
        ("diff", ["git", "diff", "--check"]),
    ]


def run_checks(output):
    import os
    scratch = ROOT / "tmp"
    scratch.mkdir(exist_ok=True)
    env = dict(os.environ, TEMP=str(scratch), TMP=str(scratch), PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    checks = []
    for name, command in quality_commands(output):
        print(f"Checking {name}", flush=True)
        start = time.monotonic()
        log = output / f"{name}.log"
        with log.open("wb") as handle:
            completed = subprocess.run(command, cwd=ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT, timeout=1200)
        checks.append({"name": name, "command": command, "exit_code": completed.returncode,
                       "elapsed_seconds": round(time.monotonic() - start, 3), "log_sha256": gate.sha(log)})
        gate.write_json(output / "checks.json", checks)
        if completed.returncode:
            break
    return checks


def smoke_wheel(output):
    wheels = list((output / "dist").glob("*.whl"))
    require(len(wheels) == 1, "Build must produce one wheel")
    wheel = wheels[0]
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    modules = {name.replace(".", "/") + ".py" for name in project["tool"]["setuptools"]["py-modules"]}
    with ZipFile(wheel) as archive:
        for path in runner.source_files():
            relative = path.relative_to(ROOT).as_posix()
            if relative in modules or (relative.startswith("financial_statement_extract/") and path.suffix == ".py"):
                require(archive.read(relative) == path.read_bytes(), f"Built wheel differs from tested code: {relative}")
    code = (f"import sys; sys.path.insert(0, {str(wheel)!r}); import financial_statement_extract as package; "
            f"assert package.__file__.startswith({str(wheel)!r}); "
            "from financial_statement_extract.cli import main; main(['--help'])")
    with (output / "wheel-smoke.log").open("wb") as handle:
        result = subprocess.run([sys.executable, "-I", "-c", code], cwd=output, stdout=handle,
                                stderr=subprocess.STDOUT, timeout=60)
    require(result.returncode == 0, "Built wheel smoke check failed")
    return {"path": str(wheel), "sha256": gate.sha(wheel), "smoke_exit_code": result.returncode}


def promote(output, target, reference, index, entries, inputs, report, reason):
    require(not target.exists(), "Promotion target exists; baselines are never overwritten")
    require(reason.strip(), "A baseline update needs a recorded reason")
    target.mkdir(parents=True)
    promoted = []
    metrics = {r["run_id"]: r for r in gate.read_json(output / "acceptance.json")["runs"]}
    for run_id, entry in entries.items():
        result, _, workbook = gate.run_files(output / "candidate", run_id)
        directory = gate.contained(target, run_id)
        directory.mkdir(parents=True)
        if workbook:
            shutil.copy2(workbook, directory / workbook.name)
            shutil.copy2(output / "candidate" / run_id / "extraction.json.gz", directory / "extraction.json.gz")
            result["workbook"] = str(directory / workbook.name)
        result["elapsed_seconds"] = metrics[run_id]["elapsed_seconds"]
        gate.write_json(directory / "result.json", result)
        promoted.append({"job": entry["job"], "scope": entry["scope"], "run": result})
    summary = {"executed_runs": len(promoted), "input_exceptions": index["summary"].get("input_exceptions", []),
               "status": "accepted_regression_reference_with_known_limitations", "accuracy_certified": False}
    gate.write_json(target / "baseline-index.json", {"summary": summary, "runs": promoted})
    gate.write_json(target / "input-inventory.json", inputs)
    gate.write_json(target / "reviewed-cases.json", {"cases": report["baseline_known_cases"],
        "note": "Historical source cases are retained. Accepted corrections below supersede the affected old values only.",
        "accepted_changes": [e for r in report["runs"] for e in r["events"] if e["severity"] == "reviewed_change"]})
    gate.write_json(target / "promotion.json", {"created_utc": runner.utc(), "reason": reason,
        "previous_reference": reference, "acceptance_report": str(output / "acceptance.json"),
        "acceptance_sha256": gate.sha(output / "acceptance.json"),
        "comparison_sha256": gate.sha(output / "comparison.json"), "accuracy_certified": False})
    artifacts = [{"path": p.relative_to(target).as_posix(), "sha256": gate.sha(p)}
                 for p in sorted(target.rglob("*")) if p.is_file()]
    gate.write_json(target / "manifest.json", {"schema_version": 1, "artifacts": artifacts})
    digest = gate.sha(target / "manifest.json")
    gate.verify_baseline(target, digest)
    return {"schema_version": 1, "baseline": target.relative_to(ROOT).as_posix(),
            "baseline_manifest_sha256": digest,
            "input_inventory": (target / "input-inventory.json").relative_to(ROOT).as_posix(),
            "input_inventory_sha256": gate.sha(target / "input-inventory.json")}


def execute(args):
    reference_path = args.reference.resolve()
    reference_sha = gate.sha(reference_path)
    reference, baseline, index, entries, inputs = load_reference(reference_path)
    output, session = args.output.resolve(), args.session.resolve()
    require(not output.exists(), "Use a new acceptance output directory")
    require(output.is_relative_to(ROOT / "outputs"), "Acceptance output must be inside project outputs")
    require(not any(output.is_relative_to(p) or p.is_relative_to(output) for p in (baseline, session)),
            "Acceptance output must be separate from the baseline and session")
    if args.promote_to:
        target = args.promote_to.resolve()
        require(target.is_relative_to(ROOT / "outputs") and not target.exists() and args.reason,
                "Promotion requires a new project outputs directory and a reason")
        require(not any(target.is_relative_to(p) or p.is_relative_to(target) for p in (baseline, session, output)),
                "New baseline must be separate from existing evidence")
    active_path, active_sha = None, None
    if args.activate_reference:
        active_path = args.activate_reference.resolve()
        require(active_path.is_relative_to(ROOT) and active_path.suffix == ".json"
                and not any(active_path.is_relative_to(p) for p in (baseline, session, output, target)),
                "Active reference must be a project JSON file outside the evidence directories")
        if active_path.exists():
            active = gate.read_json(active_path)
            require(active.get("schema_version") == 1 and "baseline_manifest_sha256" in active,
                    "Refusing to overwrite a file that is not a release reference")
            active_sha = gate.sha(active_path)
    execution = None
    if args.command == "run":
        command = ["--session", str(session), "--workers", str(args.workers)]
        if args.resume:
            saved = gate.read_json(session / "session.json")
            verify_live_program(session, saved)
            require(saved["baseline_manifest_sha256"] == reference["baseline_manifest_sha256"],
                    "Session uses an older reference; check completed outputs or start a new session")
            command.append("--resume")
        else:
            command += ["--baseline", str(baseline), "--baseline-sha256", reference["baseline_manifest_sha256"]]
        if args.decisions:
            command += ["--decisions", str(args.decisions)]
        code = runner.main(command)
        if code:
            return code
        execution = gate.read_json(session / "latest-report.json")["execution"]
    plan = gate.read_json(session / "session.json")
    plan_sha = gate.sha(session / "session.json")
    with runner.session_lock(session):
        verify_live_program(session, plan)
        attempts = verified_attempts(session, plan, entries)
        code_inventory = validation_inventory()
        output.mkdir(parents=True)
        gate.write_json(output / "validation-inputs.json", code_inventory)
        gate.write_json(output / "reference.json", reference)
        decisions = gate.read_json(args.decisions) if args.decisions else None
        if decisions is not None:
            gate.write_json(output / "review-decisions.json", decisions)
        records = copy_candidate(output, attempts)
        candidate_inventory = tree_inventory(output / "candidate")
        start = time.monotonic()
        report = gate.compare_collection(baseline, output / "candidate", expected_sha=reference["baseline_manifest_sha256"],
            decisions=decisions, progress=lambda n, total, key: print(f"Compared {n}/{total}", flush=True) if n % 20 == 0 or n == total else None)
        comparison_seconds = round(time.monotonic() - start, 3)
        gate.write_json(output / "comparison.json", report)
        (output / "comparison.md").write_text(gate.markdown(report), encoding="utf-8")
        checks = run_checks(output) if report["exit_code"] == 0 else []
        successful_checks = bool(checks) and all(r["exit_code"] == 0 for r in checks)
        wheel = smoke_wheel(output) if successful_checks else None
        verify_live_program(session, plan)
        require(validation_inventory() == code_inventory, "Code, tests or documentation changed during acceptance")
        require(gate.sha(reference_path) == reference_sha, "Active reference changed during acceptance")
        require(gate.sha(session / "session.json") == plan_sha, "Session plan changed during acceptance")
        require(tree_inventory(output / "candidate") == candidate_inventory, "Candidate changed during acceptance")
        load_reference(reference_path)
        for row in records:
            require(gate.sha(Path(row["attempt"]) / "receipt.json") == row["receipt_sha256"], "Attempt changed during acceptance")
            runner.verify_receipt(Path(row["attempt"]), plan, row["run_id"])
        by_run = {r["run_id"]: r for r in report["runs"]}
        for row in records:
            events = by_run[row["run_id"]]["events"]
            row["outcome"] = ("unverified" if row["status"] != "completed" else
                              "worse_or_unreviewed" if any(e["severity"] in {"block", "error"} for e in events) else
                              "reviewed_change" if any(e["severity"] == "reviewed_change" for e in events) else "unchanged")
        code = report["exit_code"] or (0 if successful_checks else 2)
        result = {"schema_version": 1, "created_utc": runner.utc(), "status": "accepted" if code == 0 else "not_accepted",
                  "exit_code": code, "scope": "entire_collection", "runs_compared": len(records),
                  "source_pdfs_accounted_for": len(inputs), "prepared_pdf_count": len({e['job']['input_sha256'] for e in entries.values()}),
                  "input_exceptions": report["input_exceptions"], "known_failures_unchanged": report["known_failures_unchanged"],
                  "outcomes": dict(Counter(r["outcome"] for r in records)), "event_counts": report["event_counts"],
                  "numeric_storage_cells": sum(r["numeric_storage_cells"] for r in records),
                  "worker_seconds": round(sum(r["elapsed_seconds"] for r in records), 3),
                  "comparison_seconds": comparison_seconds, "manual_cleanup_minutes": None,
                  "collection_execution": execution or {"launched_runs": 0, "reused_runs": len(records), "complete": True},
                  "verified_session": str(session),
                  "program_sha256": plan["program_sha256"], "environment_sha256": plan["environment_sha256"],
                  "session_manifest_sha256": plan_sha, "candidate_sha256": gate.digest(candidate_inventory),
                  "validation_inputs_sha256": gate.digest(code_inventory), "checks": checks, "wheel": wheel,
                  "accuracy_certified": False, "public_release_authorized": False, "runs": records}
        gate.write_json(output / "acceptance.json", result)
        (output / "ACCEPTANCE.md").write_text(
            f"# Local collection acceptance\n\nStatus: **{result['status']}**. All {len(records)} prepared runs compared.\n\n"
            f"PDFs accounted for: {len(inputs)}. Outcomes: {result['outcomes']}. Events: {report['event_counts']}.\n\n"
            f"Saved numeric cells: {result['numeric_storage_cells']} (includes numeric headings; not an accuracy percentage). "
            f"Worker time: {result['worker_seconds']} seconds summed across concurrent jobs. "
            "Manual cleanup time was not measured.\n\n"
            "Existing defects, known failures and input exceptions remain. This accepts the extractor against its "
            "collection reference; public release, UI/accessibility and other release-readiness checks are separate.\n\n"
            "[Exact comparison](comparison.md) | [Decision and checks](acceptance.json)\n", encoding="utf-8")
        if code == 0 and args.promote_to:
            updated = promote(output, target, reference, index, entries, inputs, report, args.reason)
            gate.write_json(output / "promoted-reference.json", updated)
            if active_path:
                require((gate.sha(active_path) if active_path.exists() else None) == active_sha,
                        "Active reference changed before promotion")
                if active_path.exists():
                    shutil.copy2(active_path, output / "previous-active-reference.json")
                runner.atomic_json(active_path, updated)
        print(f"Local acceptance exit {code}: {output / 'ACCEPTANCE.md'}", flush=True)
        return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "check"))
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", type=Path, default=ROOT / "regression-reference.json")
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--promote-to", type=Path)
    parser.add_argument("--reason", default="")
    parser.add_argument("--activate-reference", type=Path)
    args = parser.parse_args(argv)
    try:
        require(not args.activate_reference or args.promote_to, "Reference activation requires baseline promotion")
        require(args.command == "run" or not args.resume, "--resume belongs to the run command")
        return execute(args)
    except KeyboardInterrupt:
        print("Acceptance interrupted; no acceptance or promotion is implied", file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"Acceptance blocked: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
