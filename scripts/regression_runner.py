"""Resumable local collection extraction using the sealed regression gate.

Exit 0: no unreviewed regression; 1: source review required; 2: invalid evidence;
3: intentionally incomplete batch; 130: interrupted. No automatic baseline edits.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import csv
import ctypes
from datetime import datetime, timezone
import importlib.metadata
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import regression_gate as gate  # noqa: E402 - direct script entry point


def utc():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".partial")
    gate.write_json(temporary, value)
    os.replace(temporary, path)


@contextmanager
def session_lock(session):
    """OS-owned lock, automatically released if the coordinator exits."""
    with (session / ".runner.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise gate.EvidenceError("This session already has an active runner") from error
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def environment():
    return {"python": str(Path(sys.executable).resolve()), "version": sys.version,
            "machine": platform.machine(), "packages": sorted(
                (d.metadata["Name"].lower(), d.version) for d in importlib.metadata.distributions())}


def source_files():
    paths = list(ROOT.glob("*.py")) + [ROOT / "pyproject.toml"]
    paths += [p for p in (ROOT / "financial_statement_extract").rglob("*")
              if p.is_file() and "__pycache__" not in p.parts]
    paths += [ROOT / "scripts/regression_gate.py", ROOT / "scripts/regression_runner.py"]
    return sorted(set(paths))


def snapshot_source(session):
    inventory = []
    for path in source_files():
        relative = path.relative_to(ROOT).as_posix()
        target = gate.contained(session / "source", relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        inventory.append({"path": relative, "sha256": gate.sha(target)})
        if gate.sha(path) != inventory[-1]["sha256"]:
            raise gate.EvidenceError("Program changed while taking its snapshot")
    return inventory


def verify_snapshot(session, plan):
    actual = {p.relative_to(session / "source").as_posix() for p in (session / "source").rglob("*") if p.is_file()}
    if actual != {entry["path"] for entry in plan["source_files"]}:
        raise gate.EvidenceError("Snapshot file set changed")
    for entry in plan["source_files"]:
        if gate.sha(gate.contained(session / "source", entry["path"])) != entry["sha256"]:
            raise gate.EvidenceError(f"Snapshot changed: {entry['path']}")
    if gate.digest(environment()) != plan["environment_sha256"]:
        raise gate.EvidenceError("Python environment changed; start a new session")
    for name in ("regression_gate.py", "regression_runner.py"):
        if gate.sha(ROOT / "scripts" / name) != gate.sha(session / "source/scripts" / name):
            raise gate.EvidenceError("Runner or gate changed; start a new session")


def select_runs(entries, scope=None, selected=None):
    if selected is not None:
        if not selected or len(selected) != len(set(selected)) or any(key not in entries for key in selected):
            raise gate.EvidenceError("Unknown, empty or repeated run selection")
        if scope:
            raise gate.EvidenceError("Choose either --scope or --run")
        keys = selected
    else:
        keys = [key for key in entries if scope in (None, "all") or key.startswith(scope + "/")]
    # Core feedback first; longest jobs first within each scope avoids a long tail.
    return sorted(keys, key=lambda key: (key.split("/")[0], -entries[key]["run"].get("elapsed_seconds", 0), key))


def verify_inputs(entries, keys):
    seen = {}
    for key in keys:
        job = entries[key]["job"]
        path = Path(job["source_path"]).resolve()
        if path not in seen:
            seen[path] = gate.sha(path)
        if seen[path] != job["input_sha256"]:
            raise gate.EvidenceError(f"Source PDF changed: {path}")


class OwnedProcess:
    """Own the entire worker process tree, including after coordinator failure on Windows."""
    def __init__(self, command, *, cwd, env, log):
        self.job = None
        self.process = None
        if os.name == "nt":
            from ctypes import wintypes as w

            class Basic(ctypes.Structure):
                _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                            ("flags", w.DWORD), ("min_ws", ctypes.c_size_t), ("max_ws", ctypes.c_size_t),
                            ("active", w.DWORD), ("affinity", ctypes.c_size_t),
                            ("priority", w.DWORD), ("scheduling", w.DWORD)]

            class Extended(ctypes.Structure):
                _fields_ = [("basic", Basic), ("io", ctypes.c_ulonglong * 6),
                            ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                            ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]

            self.api = ctypes.WinDLL("kernel32", use_last_error=True)
            self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
            self.api.CreateJobObjectW.restype = w.HANDLE
            self.api.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
            self.api.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
            self.api.CloseHandle.argtypes = [w.HANDLE]
            self.job = self.api.CreateJobObjectW(None, None)
            limits = Extended()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not self.job or not self.api.SetInformationJobObject(self.job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                self.close()
                raise ctypes.WinError(ctypes.get_last_error())
        try:
            self.process = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                                            start_new_session=os.name != "nt")
            if self.job and not self.api.AssignProcessToJobObject(self.job, int(self.process._handle)):
                self.process.kill()
                self.process.wait()
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.job:
            self.api.CloseHandle(self.job)
            self.job = None
        elif self.process and os.name != "nt":
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if self.process:
            self.process.wait(timeout=15)


def command_for(session, plan, run_id, attempt):
    return [sys.executable, str(session / "source/scripts/regression_gate.py"), "capture",
            "--baseline", plan["baseline"], "--baseline-sha256", plan["baseline_manifest_sha256"],
            "--candidate", str(attempt / "capture"), "--run", run_id]


def new_attempt(session, run_id):
    parent = gate.contained(session / "attempts", run_id)
    parent.mkdir(parents=True, exist_ok=True)
    numbers = [int(p.name) for p in parent.iterdir() if p.is_dir() and p.name.isdigit()]
    directory = parent / f"{max(numbers, default=0) + 1:04d}"
    directory.mkdir()
    return directory


def verify_receipt(attempt, plan, run_id):
    receipt = gate.read_json(attempt / "receipt.json")
    if receipt["run_id"] != run_id or receipt["program_sha256"] != plan["program_sha256"]:
        raise gate.EvidenceError("Attempt receipt belongs to another run or program")
    paths = {entry["path"] for entry in receipt["artifacts"]}
    required = {f"capture/{run_id}/result.json", "run.log", "start.json"}
    if not required <= paths:
        raise gate.EvidenceError("Attempt receipt is missing required artifacts")
    for entry in receipt["artifacts"]:
        if gate.sha(gate.contained(attempt, entry["path"])) != entry["sha256"]:
            raise gate.EvidenceError(f"Saved attempt changed: {attempt / entry['path']}")
    result, _, workbook = gate.run_files(attempt / "capture", run_id)
    if workbook and not {f"capture/{run_id}/extraction.json.gz", workbook.relative_to(attempt).as_posix()} <= paths:
        raise gate.EvidenceError("Completed attempt is not fully hashed")
    if result["status"] != receipt["status"]:
        raise gate.EvidenceError("Attempt status disagrees with result")
    return receipt


def latest_attempt(session, plan, run_id):
    parent = gate.contained(session / "attempts", run_id)
    attempts = sorted(p for p in parent.glob("*") if p.is_dir() and p.name.isdigit())
    if not attempts:
        return None
    latest = attempts[-1]
    # An interrupted newer attempt must never fall back to an older successful one.
    if not (latest / "receipt.json").is_file():
        return None
    verify_receipt(latest, plan, run_id)
    return latest


def finish_attempt(task, plan, entry, *, infrastructure_error=None):
    task["owned"].close()
    task["log"].close()
    attempt, run_id = task["attempt"], task["run_id"]
    code = task["owned"].process.returncode
    directory = gate.contained(attempt / "capture", run_id)
    try:
        result, _, _ = gate.run_files(attempt / "capture", run_id)
        expected = 0 if result["status"] == "completed" else 1
        if code != expected:
            raise gate.EvidenceError(f"Worker exit {code} disagrees with result status {result['status']}")
    except (OSError, ValueError, KeyError, TypeError) as error:
        infrastructure_error = infrastructure_error or str(error)
    if infrastructure_error:
        directory.mkdir(parents=True, exist_ok=True)
        result_path = directory / "result.json"
        if result_path.exists():
            # Preserve a partial or inconsistent worker record before recording the failure.
            shutil.copy2(result_path, directory / "worker-result-unverified.json")
        result = {"job": entry["job"], "scope": entry["scope"],
                  "pages": entry["job"][f'{entry["scope"]}_pages'],
                  "status": "process_failed", "process_exit_code": code,
                  "error_type": "WorkerInfrastructureError", "error": infrastructure_error}
        atomic_json(result_path, result)
    receipt = {"run_id": run_id, "program_sha256": plan["program_sha256"], "status": result["status"],
               "infrastructure_error": infrastructure_error, "finished_utc": utc(),
               "elapsed_seconds": round(time.monotonic() - task["started"], 3), "process_exit_code": code,
               "artifacts": [{"path": p.relative_to(attempt).as_posix(), "sha256": gate.sha(p)}
                             for p in sorted(attempt.rglob("*")) if p.is_file()]}
    atomic_json(attempt / "receipt.json", receipt)
    return receipt


def run_queue(session, plan, entries, *, workers, timeout, retry_failed=False, max_new_runs=None):
    cached, pending = {}, []
    for run_id in plan["runs"]:
        attempt = latest_attempt(session, plan, run_id)
        receipt = gate.read_json(attempt / "receipt.json") if attempt else None
        if receipt and not receipt["infrastructure_error"] and (receipt["status"] == "completed" or not retry_failed):
            cached[run_id] = attempt
        else:
            pending.append(run_id)
    initial_cached = len(cached)
    allowed = pending[:max_new_runs] if max_new_runs is not None else pending[:]
    active, launched = {}, 0
    scratch = session / "temp"
    scratch.mkdir(exist_ok=True)
    child_env = dict(os.environ, PYTHONPATH=str(session / "source"), PYTHONNOUSERSITE="1",
                     PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", TEMP=str(scratch), TMP=str(scratch),
                     TMPDIR=str(scratch), OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    def progress(status):
        atomic_json(session / "progress.json", {"status": status, "updated_utc": utc(), "total_runs": len(plan["runs"]),
                    "verified_results": len(cached), "reused_runs": initial_cached, "launched_this_invocation": launched,
                    "active": sorted(active), "remaining_runs": [key for key in plan["runs"] if key not in cached]})
    print(f"Verified {initial_cached} saved runs; {len(allowed)} queued; workers={workers}", flush=True)
    heartbeat = time.monotonic()
    try:
        while allowed or active:
            while allowed and len(active) < workers:
                run_id = allowed.pop(0)
                attempt = new_attempt(session, run_id)
                atomic_json(attempt / "start.json", {"run_id": run_id, "started_utc": utc(),
                            "program_sha256": plan["program_sha256"], "timeout_seconds": timeout})
                log = (attempt / "run.log").open("wb")
                try:
                    owned = OwnedProcess(command_for(session, plan, run_id, attempt), cwd=session / "source", env=child_env, log=log)
                except BaseException:
                    log.close()
                    raise
                active[run_id] = {"owned": owned, "log": log, "attempt": attempt, "run_id": run_id, "started": time.monotonic()}
                launched += 1
                progress("running")
            for run_id, task in list(active.items()):
                finished = task["owned"].process.poll() is not None
                expired = not finished and time.monotonic() - task["started"] > timeout
                if finished or expired:
                    receipt = finish_attempt(task, plan, entries[run_id],
                                             infrastructure_error=f"Worker exceeded {timeout:g} seconds" if expired else None)
                    cached[run_id] = task["attempt"]
                    del active[run_id]
                    print(f"Finished {len(cached)}/{len(plan['runs'])}: {run_id} {receipt['status']}", flush=True)
                    progress("running")
            if time.monotonic() - heartbeat >= 30:
                print(f"Progress {len(cached)}/{len(plan['runs'])}; {len(active)} active", flush=True)
                heartbeat = time.monotonic()
            if active:
                time.sleep(0.2)
    except BaseException:
        for task in active.values():
            task["owned"].close()
            task["log"].close()
        progress("interrupted")
        raise
    complete = len(cached) == len(plan["runs"])
    progress("ready_to_compare" if complete else "incomplete")
    return cached, {"reused_runs": initial_cached, "launched_runs": launched, "complete": complete}


def compare_results(session, plan, entries, attempts, execution, decisions=None):
    folder = session / "comparisons" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8])
    candidate, report_dir = folder / "candidate", folder / "report"
    report_dir.mkdir(parents=True)
    records = []
    for run_id in plan["runs"]:
        attempt = attempts[run_id]
        receipt = verify_receipt(attempt, plan, run_id)
        result, payload, workbook = gate.run_files(attempt / "capture", run_id)
        target = gate.contained(candidate, run_id)
        target.mkdir(parents=True)
        if workbook:
            shutil.copy2(workbook, target / workbook.name)
            shutil.copy2(attempt / "capture" / run_id / "extraction.json.gz", target / "extraction.json.gz")
            result["workbook"] = str(target / workbook.name)
        gate.write_json(target / "result.json", result)
        records.append({"run_id": run_id, "entity": entries[run_id]["job"]["entity"],
                        "source_path": entries[run_id]["job"]["source_path"], "pages": result["pages"],
                        "status": result["status"], "workbook": result.get("workbook", ""), "attempt": str(attempt),
                        "infrastructure_error": receipt["infrastructure_error"],
                        "audit_status_counts": {key: dict(Counter(row.get("Status") for row in payload.get(key, [])))
                            for key in ("financial_audit_rows", "extraction_audit_rows", "experimental_audit_rows")} if payload else {}})
    report = gate.compare_collection(plan["baseline"], candidate, expected_sha=plan["baseline_manifest_sha256"],
                selected=None if plan["full_collection"] else plan["runs"], decisions=decisions,
                progress=lambda n, total, key: print(f"Compared {n}/{total}: {key}", flush=True) if n % 20 == 0 or n == total else None)
    gate.write_json(report_dir / "comparison.json", report)
    (report_dir / "comparison.md").write_text(gate.markdown(report), encoding="utf-8")
    infrastructure_errors = sum(bool(r["infrastructure_error"]) for r in records)
    exit_code = 2 if infrastructure_errors else report["exit_code"]
    by_run = {r["run_id"]: r for r in report["runs"]}
    for row in records:
        row["regression_status"] = by_run[row["run_id"]]["status"]
        row["events"] = dict(Counter(e["severity"] for e in by_run[row["run_id"]]["events"]))
    summary = {"completed_utc": utc(), "exit_code": exit_code, "scope": report["scope"],
               "expected_runs": len(plan["runs"]), "all_baseline_runs": len(entries),
               "program_sha256": plan["program_sha256"], "environment_sha256": plan["environment_sha256"],
               "execution": execution, "status_counts": dict(Counter(r["status"] for r in records)),
               "known_failures_unchanged": report["known_failures_unchanged"], "event_counts": report["event_counts"],
               "infrastructure_errors": infrastructure_errors, "input_exceptions": report["input_exceptions"],
               "accuracy_certified": False, "report_directory": str(report_dir), "runs": records}
    gate.write_json(report_dir / "collection.json", summary)
    with (report_dir / "collection.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fields = ["run_id", "entity", "status", "regression_status", "pages", "workbook", "attempt", "source_path"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    (report_dir / "SUMMARY.md").write_text(
        f"# Collection run\n\nScope: {report['scope']}. Compared {len(records)}/{len(entries)} runs. Exit: {exit_code}.\n\n"
        f"This invocation extracted {execution['launched_runs']} runs and reused {execution['reused_runs']} verified attempts.\n\n"
        f"Results: {summary['status_counts']}. Known failures unchanged: {report['known_failures_unchanged']}. "
        f"Events: {report['event_counts']}. Infrastructure errors: {infrastructure_errors}.\n\n"
        "Existing defects, input exceptions and untested financial checks remain. This is a regression comparison, not an accuracy certification.\n\n"
        "[Per-run comparison](comparison.md) | [Workbook index](collection.csv) | [Audit counts and provenance](collection.json)\n",
        encoding="utf-8")
    return summary


def execute(args):
    if args.workers < 1 or args.workers > 16 or args.timeout_seconds <= 0 or (args.max_new_runs is not None and args.max_new_runs < 1):
        raise gate.EvidenceError("Use 1-16 workers and positive timeout/batch limits")
    session = args.session.resolve()
    if args.resume:
        plan = gate.read_json(session / "session.json")
        if args.scope or args.selected:
            raise gate.EvidenceError("Resume uses the saved selection; omit --scope and --run")
        if args.baseline is not None or args.baseline_sha256 is not None:
            raise gate.EvidenceError("Resume uses the saved baseline; omit baseline options")
    else:
        baseline = (args.baseline or ROOT / "outputs/regression-phase3").resolve()
        if session.is_relative_to(baseline) or baseline.is_relative_to(session):
            raise gate.EvidenceError("Session must be separate from the sealed baseline")
        if session.exists():
            raise gate.EvidenceError("Session exists; use --resume or a new directory")
        _, entries = gate.verify_baseline(baseline, args.baseline_sha256 or gate.PHASE3_SHA256)
        keys = select_runs(entries, args.scope, args.selected)
        verify_inputs(entries, keys)
        session.mkdir(parents=True)
        plan = None
    with session_lock(session):
        if plan is None:
            inventory = snapshot_source(session)
            env = environment()
            plan = {"schema_version": 1, "created_utc": utc(), "baseline": str(baseline),
                    "baseline_manifest_sha256": args.baseline_sha256 or gate.PHASE3_SHA256,
                    "runs": keys, "full_collection": set(keys) == set(entries),
                    "source_files": inventory, "program_sha256": gate.digest(inventory),
                    "environment": env, "environment_sha256": gate.digest(env)}
            atomic_json(session / "session.json", plan)
        _, entries = gate.verify_baseline(plan["baseline"], plan["baseline_manifest_sha256"])
        if not plan["runs"] or any(key not in entries for key in plan["runs"]):
            raise gate.EvidenceError("Saved run selection is invalid")
        if plan["full_collection"] != (set(plan["runs"]) == set(entries)):
            raise gate.EvidenceError("Saved coverage claim disagrees with run selection")
        verify_snapshot(session, plan)
        verify_inputs(entries, plan["runs"])
        attempts, execution = run_queue(session, plan, entries, workers=args.workers, timeout=args.timeout_seconds,
                                       retry_failed=args.retry_failed, max_new_runs=args.max_new_runs)
        verify_snapshot(session, plan)
        verify_inputs(entries, plan["runs"])
        if not execution["complete"]:
            print("INCOMPLETE: verified results saved; resume this session to finish", flush=True)
            return 3
        summary = compare_results(session, plan, entries, attempts, execution,
                                  decisions=gate.read_json(args.decisions) if args.decisions else None)
        atomic_json(session / "latest-report.json", summary)
        atomic_json(session / "progress.json", {"status": "complete", "updated_utc": utc(),
                    "verified_results": len(attempts), "total_runs": len(plan["runs"]),
                    "exit_code": summary["exit_code"], "report_directory": summary["report_directory"]})
        print(f"Collection comparison exit {summary['exit_code']}: {summary['report_directory']}", flush=True)
        return summary["exit_code"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--baseline-sha256")
    parser.add_argument("--scope", choices=("core", "full", "all"))
    parser.add_argument("--run", action="append", dest="selected")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=900)
    parser.add_argument("--max-new-runs", type=int)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--decisions", type=Path)
    args = parser.parse_args(argv)
    try:
        return execute(args)
    except KeyboardInterrupt:
        print("Interrupted; active workers stopped and attempts preserved. Use --resume.", flush=True)
        return 130
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Invalid evidence: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
