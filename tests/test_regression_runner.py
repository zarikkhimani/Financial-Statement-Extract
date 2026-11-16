"""Exercise orchestration with real isolated child processes and synthetic workbooks."""
from pathlib import Path
import os
import subprocess
import sys
import time

import pytest

from scripts import regression_gate as gate
from scripts import regression_runner as runner
from test_regression_gate import corpus as corpus


CORE = "core/sample-1"
FULL = "full/sample-1"


@pytest.fixture
def harness(corpus, tmp_path, monkeypatch):
    worker = tmp_path / "fake_capture.py"
    worker.write_text('''
from pathlib import Path
import hashlib, json, os, shutil, sys, time
baseline, capture, key = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
if os.environ.get("RUNNER_TEST_MODE") == "hang":
    time.sleep(30)
if os.environ.get("RUNNER_TEST_MODE") == "crash":
    raise SystemExit(9)
target = capture / key
shutil.copytree(baseline / key, target)
result = json.loads((target / "result.json").read_text())
if result["status"] == "completed":
    path = target / "workbook.xlsx"
    result["workbook"] = str(path)
    if os.environ.get("RUNNER_TEST_MODE") == "change_number":
        from openpyxl import load_workbook
        book = load_workbook(path)
        book.worksheets[0]["D9"] = 1251
        book.save(path)
        book.close()
        result["workbook_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
(target / "result.json").write_text(json.dumps(result))
print("Finished synthetic capture", flush=True)
raise SystemExit(0 if result["status"] == "completed" else 1)
''', encoding="utf-8")
    monkeypatch.setattr(runner, "command_for", lambda session, plan, key, attempt: [
        sys.executable, str(worker), str(corpus[0]), str(attempt / "capture"), key])
    session = tmp_path / "session"
    args = ["--session", str(session), "--baseline", str(corpus[0]), "--baseline-sha256", corpus[2], "--workers", "2"]
    return session, args


def attempts(session, key):
    return sorted((session / "attempts" / key).glob("*/receipt.json"))


def test_full_run_and_resume_reuses_both_successes_and_known_failures(harness):
    session, args = harness
    assert runner.main(args) == 0
    first = gate.read_json(session / "latest-report.json")
    assert first["scope"] == "entire_collection"
    assert first["execution"]["launched_runs"] == 2
    assert first["known_failures_unchanged"] == 1
    assert first["status_counts"] == {"completed": 1, "failed": 1}
    receipts = {str(p): gate.sha(p) for p in session.glob("attempts/*/*/*/receipt.json")}
    assert runner.main(["--session", str(session), "--resume"]) == 0
    second = gate.read_json(session / "latest-report.json")
    assert second["execution"]["launched_runs"] == 0
    assert second["execution"]["reused_runs"] == 2
    assert first["report_directory"] != second["report_directory"]
    assert receipts == {str(p): gate.sha(p) for p in session.glob("attempts/*/*/*/receipt.json")}
    assert Path(first["report_directory"]).is_dir()


def test_bounded_run_is_incomplete_then_resumes(harness):
    session, args = harness
    assert runner.main(args + ["--max-new-runs", "1"]) == 3
    assert gate.read_json(session / "progress.json")["status"] == "incomplete"
    assert not (session / "latest-report.json").exists()
    assert runner.main(["--session", str(session), "--resume"]) == 0
    result = gate.read_json(session / "latest-report.json")
    assert result["execution"]["launched_runs"] == 1
    assert result["execution"]["reused_runs"] == 1


def test_retry_failed_preserves_earlier_attempt_and_completed_work(harness):
    session, args = harness
    assert runner.main(args) == 0
    old_receipt = attempts(session, FULL)[0]
    old_hash = gate.sha(old_receipt)
    assert runner.main(["--session", str(session), "--resume", "--retry-failed"]) == 0
    assert len(attempts(session, CORE)) == 1
    assert len(attempts(session, FULL)) == 2
    assert gate.sha(old_receipt) == old_hash


@pytest.mark.parametrize("mode", ["hang", "crash"])
def test_timeout_and_process_crash_are_infrastructure_errors_and_retry_on_resume(harness, monkeypatch, mode):
    session, args = harness
    monkeypatch.setenv("RUNNER_TEST_MODE", mode)
    timeout = "0.1" if mode == "hang" else "30"
    assert runner.main(args + ["--run", CORE, "--timeout-seconds", timeout]) == 2
    first = gate.read_json(session / "latest-report.json")
    assert first["infrastructure_errors"] == 1
    assert first["status_counts"] == {"process_failed": 1}
    monkeypatch.delenv("RUNNER_TEST_MODE")
    assert runner.main(["--session", str(session), "--resume"]) == 0
    assert len(attempts(session, CORE)) == 2


def test_new_numeric_difference_blocks_collection(harness, monkeypatch):
    session, args = harness
    monkeypatch.setenv("RUNNER_TEST_MODE", "change_number")
    assert runner.main(args) == 1
    report = gate.read_json(session / "latest-report.json")
    assert report["event_counts"]["block"] == 1
    assert report["known_failures_unchanged"] == 1


def test_changed_cached_workbook_is_rejected_not_silently_reused(harness):
    session, args = harness
    assert runner.main(args) == 0
    receipt = attempts(session, CORE)[0]
    workbook = next(receipt.parent.rglob("*.xlsx"))
    workbook.write_bytes(b"damaged")
    assert runner.main(["--session", str(session), "--resume"]) == 2
    assert len(attempts(session, CORE)) == 1


def test_newer_interrupted_attempt_does_not_fall_back_to_old_success(harness):
    session, args = harness
    assert runner.main(args) == 0
    interrupted = session / "attempts" / CORE / "0002"
    interrupted.mkdir()
    (interrupted / "partial.txt").write_text("Interrupted output")
    assert runner.main(["--session", str(session), "--resume"]) == 0
    assert [p.parent.name for p in attempts(session, CORE)] == ["0001", "0003"]
    assert (interrupted / "partial.txt").read_text() == "Interrupted output"


def test_keyboard_interrupt_preserves_partial_attempt_and_resume_retries(harness, monkeypatch):
    session, args = harness
    def interrupt(_):
        raise KeyboardInterrupt
    with monkeypatch.context() as patch:
        patch.setattr(runner.time, "sleep", interrupt)
        assert runner.main(args + ["--run", CORE]) == 130
    assert gate.read_json(session / "progress.json")["status"] == "interrupted"
    assert not attempts(session, CORE)
    assert runner.main(["--session", str(session), "--resume"]) == 0
    assert [p.parent.name for p in attempts(session, CORE)] == ["0002"]


def test_snapshot_tampering_prevents_resume(harness):
    session, args = harness
    assert runner.main(args + ["--max-new-runs", "1"]) == 3
    with (session / "source/config.py").open("a") as handle:
        handle.write("\n# tampered\n")
    assert runner.main(["--session", str(session), "--resume"]) == 2
    assert not attempts(session, FULL)


def test_environment_drift_prevents_resume(harness, monkeypatch):
    session, args = harness
    assert runner.main(args + ["--max-new-runs", "1"]) == 3
    monkeypatch.setattr(runner, "environment", lambda: {"version": "changed"})
    assert runner.main(["--session", str(session), "--resume"]) == 2


def test_source_pdf_change_prevents_resume(harness, corpus):
    session, args = harness
    assert runner.main(args + ["--max-new-runs", "1"]) == 3
    result = gate.read_json(corpus[0] / CORE / "result.json")
    Path(result["job"]["source_path"]).write_bytes(b"replacement")
    assert runner.main(["--session", str(session), "--resume"]) == 2


def test_existing_session_is_not_overwritten(harness):
    session, args = harness
    assert runner.main(args) == 0
    original = gate.sha(session / "session.json")
    assert runner.main(args) == 2
    assert gate.sha(session / "session.json") == original


def test_subset_cannot_be_presented_as_entire_collection(harness):
    session, args = harness
    assert runner.main(args + ["--scope", "core"]) == 0
    summary = gate.read_json(session / "latest-report.json")
    assert summary["scope"] == "selected_runs"
    assert summary["expected_runs"] == 1 and summary["all_baseline_runs"] == 2


def test_cannot_change_selection_when_resuming(harness):
    session, args = harness
    assert runner.main(args + ["--run", CORE]) == 0
    assert runner.main(["--session", str(session), "--resume", "--scope", "full"]) == 2


def test_lock_excludes_second_coordinator(harness):
    session, args = harness
    assert runner.main(args + ["--max-new-runs", "1"]) == 3
    with runner.session_lock(session):
        assert runner.main(["--session", str(session), "--resume"]) == 2


@pytest.mark.parametrize("extra", [["--workers", "0"], ["--workers", "17"], ["--timeout-seconds", "0"],
                                  ["--max-new-runs", "0"], ["--run", "unknown"], ["--run", CORE, "--run", CORE]])
def test_invalid_execution_options_fail_before_work(harness, extra):
    session, args = harness
    assert runner.main(args + extra) == 2
    assert not session.exists()


def test_owned_process_stops_actual_child(tmp_path):
    log = (tmp_path / "child.log").open("wb")
    child = runner.OwnedProcess([sys.executable, "-c", "import time; time.sleep(30)"],
                                cwd=tmp_path, env=os.environ.copy(), log=log)
    assert child.process.poll() is None
    child.close()
    log.close()
    assert child.process.poll() is not None


@pytest.mark.skipif(os.name != "nt", reason="Windows job-object parent-exit guarantee")
def test_parent_crash_terminates_owned_worker(tmp_path):
    # A separate coordinator dies without calling close; its kernel job owns the child.
    marker = tmp_path / "should-not-appear.txt"
    parent = tmp_path / "parent.py"
    parent.write_text('''
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from scripts.regression_runner import OwnedProcess
log = open(sys.argv[2], "wb")
child = OwnedProcess([sys.executable, "-c", "import time,pathlib;time.sleep(1);pathlib.Path(sys.argv[1]).write_text('orphan')", sys.argv[3]], cwd=Path.cwd(), env=os.environ.copy(), log=log)
os._exit(0)
'''.replace("import time,pathlib;", "import time,pathlib,sys;"), encoding="utf-8")
    subprocess.run([sys.executable, str(parent), str(runner.ROOT), str(tmp_path / "log"), str(marker)], check=True)
    time.sleep(1.5)
    assert not marker.exists()
