from pathlib import Path
import shutil
import sys
from zipfile import ZipFile

import pytest

from scripts import regression_gate as gate
from scripts import regression_release as release
from scripts import regression_runner as runner
from test_regression_gate import corpus as corpus, reseal, RUN
from test_regression_runner import harness as harness


@pytest.fixture
def project(corpus, harness, tmp_path, monkeypatch):
    root = tmp_path / "project"
    (root / "scripts").mkdir(parents=True)
    (root / "financial_statement_extract").mkdir()
    (root / "tests").mkdir()
    (root / "docs").mkdir()
    for name in ("regression_gate.py", "regression_runner.py", "regression_release.py"):
        shutil.copy2(release.ROOT / "scripts" / name, root / "scripts" / name)
    for name in ("app.py", "pyproject.toml", "README.md", "AGENTS.md", "MANIFEST.in", ".github/workflows/ci.yml"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# synthetic release fixture\n")
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(release, "ROOT", root)
    excluded = tmp_path / "excluded.pdf"
    excluded.write_bytes(b"Synthetic wrong-document exception")
    index = gate.read_json(corpus[0] / "baseline-index.json")
    index["summary"]["input_exceptions"][0]["filing_id"] = gate.sha(excluded)[:16]
    gate.write_json(corpus[0] / "baseline-index.json", index)
    baseline_sha = reseal(corpus[0])
    inputs = root / "inputs.json"
    source = Path(index["runs"][0]["job"]["source_path"])
    gate.write_json(inputs, [{"original": str(p), "sha256": gate.sha(p)} for p in (source, excluded)])
    reference = root / "reference.json"
    gate.write_json(reference, {"schema_version": 1, "baseline": str(corpus[0]), "baseline_manifest_sha256": baseline_sha,
                               "input_inventory": str(inputs), "input_inventory_sha256": gate.sha(inputs)})
    session, capture_args = harness
    capture_args[capture_args.index("--baseline-sha256") + 1] = baseline_sha
    output = root / "outputs/acceptance"
    arguments = ["check", "--session", str(session), "--reference", str(reference), "--output", str(output)]
    # Exercise real child processes and exit handling without recursively running pytest.
    monkeypatch.setattr(release, "quality_commands", lambda output: [
        (name, [sys.executable, "-c", "print('Synthetic quality command')"])
        for name in ("dependencies", "lint", "tests", "cli", "build", "diff")])
    monkeypatch.setattr(release, "smoke_wheel", lambda output: {"synthetic_test": True})
    return dict(root=root, session=session, capture_args=capture_args, output=output, args=arguments,
                reference=reference, inputs=inputs, source=source, excluded=excluded, baseline=corpus[0], sha=baseline_sha)


def capture(project):
    assert runner.main(project["capture_args"]) == 0


def test_acceptance_requires_complete_evidence_and_reports_limits(project):
    capture(project)
    assert release.main(project["args"]) == 0
    result = gate.read_json(project["output"] / "acceptance.json")
    assert result["status"] == "accepted"
    assert result["runs_compared"] == 2
    assert result["source_pdfs_accounted_for"] == 2
    assert result["outcomes"] == {"unchanged": 1, "unverified": 1}
    assert result["known_failures_unchanged"] == 1
    assert result["numeric_storage_cells"] == 6
    assert result["manual_cleanup_minutes"] is None
    assert result["accuracy_certified"] is False
    assert result["public_release_authorized"] is False
    assert result["collection_execution"] == {"launched_runs": 0, "reused_runs": 2, "complete": True}
    assert [c["name"] for c in result["checks"]] == ["dependencies", "lint", "tests", "cli", "build", "diff"]
    assert not (project["root"] / "regression-reference.json").exists()


@pytest.mark.parametrize("problem", ["partial", "interrupted", "missing", "corrupt", "code", "environment", "input", "excluded_input"])
def test_invalid_evidence_cannot_be_accepted(project, monkeypatch, problem):
    capture(project)
    plan_path = project["session"] / "session.json"
    attempt = project["session"] / "attempts" / RUN / "0001"
    if problem == "partial":
        plan = gate.read_json(plan_path)
        plan.update(full_collection=False, runs=[RUN])
        gate.write_json(plan_path, plan)
    elif problem == "interrupted":
        attempt.with_name("0002").mkdir()
    elif problem == "missing":
        (attempt / "receipt.json").unlink()
    elif problem == "corrupt":
        (attempt / "capture" / RUN / "workbook.xlsx").write_bytes(b"broken workbook")
    elif problem == "code":
        (project["root"] / "app.py").write_text("# changed after extraction\n")
    elif problem == "environment":
        before = runner.environment()
        monkeypatch.setattr(runner, "environment", lambda: {**before, "version": "changed"})
    elif problem == "input":
        project["source"].write_bytes(b"different source")
    else:
        project["excluded"].write_bytes(b"different excluded source")
    # A forged success pointer cannot substitute for verified attempts.
    gate.write_json(project["session"] / "latest-report.json", {"exit_code": 0, "scope": "entire_collection"})
    assert release.main(project["args"]) == 2
    assert not (project["output"] / "acceptance.json").exists()


@pytest.mark.parametrize("name", ["dependencies", "lint", "tests", "cli", "build", "diff"])
def test_failed_quality_check_prevents_promotion(project, monkeypatch, name):
    capture(project)
    commands = release.quality_commands(project["output"])
    commands = [(n, [sys.executable, "-c", "raise SystemExit(7)"] if n == name else cmd) for n, cmd in commands]
    monkeypatch.setattr(release, "quality_commands", lambda output: commands)
    target = project["root"] / "outputs/new-baseline"
    assert release.main(project["args"] + ["--promote-to", str(target), "--reason", "Test only"]) == 2
    assert gate.read_json(project["output"] / "acceptance.json")["status"] == "not_accepted"
    assert not target.exists()


@pytest.mark.parametrize("change", ["candidate", "tests"])
def test_changes_during_validation_invalidate_acceptance(project, monkeypatch, change):
    capture(project)
    original = release.run_checks
    def changed(output):
        result = original(output)
        if change == "candidate":
            (output / "candidate" / RUN / "workbook.xlsx").write_bytes(b"changed after comparison")
        else:
            (project["root"] / "tests/changed.py").write_text("# newly changed test\n")
        return result
    monkeypatch.setattr(release, "run_checks", changed)
    assert release.main(project["args"]) == 2
    assert not (project["output"] / "acceptance.json").exists()


def test_unreviewed_number_change_is_blocked_even_if_other_checks_would_pass(project, monkeypatch):
    monkeypatch.setenv("RUNNER_TEST_MODE", "change_number")
    assert runner.main(project["capture_args"]) == 1
    target = project["root"] / "outputs/new-baseline"
    assert release.main(project["args"] + ["--promote-to", str(target), "--reason", "Test only"]) == 1
    result = gate.read_json(project["output"] / "acceptance.json")
    assert result["checks"] == [] and result["outcomes"]["worse_or_unreviewed"] == 1
    assert not target.exists()


def test_reviewed_correction_promotes_new_reference_and_blocks_rollback(project, monkeypatch):
    monkeypatch.setenv("RUNNER_TEST_MODE", "change_number")
    assert runner.main(project["capture_args"]) == 1
    summary = gate.read_json(project["session"] / "latest-report.json")
    comparison = gate.read_json(Path(summary["report_directory"]) / "comparison.json")
    events = [e for r in comparison["runs"] for e in r["events"]]
    decisions = project["root"] / "review.json"
    gate.write_json(decisions, {"baseline_manifest_sha256": project["sha"], "accepted_changes": [
        {"issue_id": e["issue_id"], "reason": "Synthetic source correction", "source_evidence": "Synthetic fixture D9 = 1251"}
        for e in events]})
    target = project["root"] / "outputs/approved"
    active = project["root"] / "regression-reference.json"
    assert release.main(project["args"] + ["--decisions", str(decisions), "--promote-to", str(target),
        "--reason", "Reviewed synthetic correction", "--activate-reference", str(active)]) == 0
    reference, _, index, entries, _ = release.load_reference(active)
    assert gate.sha(project["baseline"] / "manifest.json") == project["sha"]
    assert len(entries) == 2 and index["summary"]["input_exceptions"]
    assert len(gate.read_json(target / "reviewed-cases.json")["accepted_changes"]) == 1
    rollback = gate.compare_collection(target, project["baseline"], expected_sha=reference["baseline_manifest_sha256"])
    assert rollback["exit_code"] == 1
    assert any(e["code"] == "ROW_VALUES_OR_FIELDS_CHANGED" for r in rollback["runs"] for e in r["events"])


def test_default_quality_commands_include_all_required_checks(tmp_path):
    names = [name for name, _ in release.quality_commands(tmp_path)]
    assert names == ["dependencies", "lint", "tests", "cli", "build", "diff"]


def test_existing_acceptance_or_baseline_cannot_be_overwritten(project):
    capture(project)
    project["output"].mkdir(parents=True)
    marker = project["output"] / "keep.txt"
    marker.write_text("keep")
    assert release.main(project["args"]) == 2
    assert marker.read_text() == "keep"


def test_reference_inventory_rejects_unaccounted_or_missing_pdf(project):
    reference = gate.read_json(project["reference"])
    inputs = gate.read_json(project["inputs"])
    gate.write_json(project["inputs"], inputs[:-1])
    reference["input_inventory_sha256"] = gate.sha(project["inputs"])
    gate.write_json(project["reference"], reference)
    with pytest.raises(gate.EvidenceError, match="exception"):
        release.load_reference(project["reference"])


def test_run_command_executes_collection_before_accepting(project):
    arguments = list(project["args"])
    arguments[0] = "run"
    assert release.main(arguments) == 0
    result = gate.read_json(project["output"] / "acceptance.json")
    assert result["collection_execution"]["launched_runs"] == 2


@pytest.mark.parametrize("mismatch", [False, True])
def test_wheel_checks_declared_modules_and_ignores_unshipped_legacy_code(tmp_path, monkeypatch, mismatch):
    root = tmp_path / "root"
    package = root / "financial_statement_extract"
    package.mkdir(parents=True)
    (root / "app.py").write_text("# packaged module\n")
    (root / "z27.py").write_text("# preserved legacy code, not shipped\n")
    (root / "pyproject.toml").write_text('[tool.setuptools]\npy-modules = ["app"]\n')
    (package / "__init__.py").write_text("")
    (package / "cli.py").write_text('def main(argv):\n    print("synthetic CLI")\n')
    output = root / "output"
    (output / "dist").mkdir(parents=True)
    paths = [root / "app.py", root / "z27.py", package / "__init__.py", package / "cli.py"]
    with ZipFile(output / "dist/synthetic.whl", "w") as archive:
        for path in paths:
            if path.name != "z27.py":
                archive.writestr(path.relative_to(root).as_posix(), b"# wrong source" if mismatch and path.name == "app.py" else path.read_bytes())
    monkeypatch.setattr(release, "ROOT", root)
    monkeypatch.setattr(runner, "source_files", lambda: paths)
    if mismatch:
        with pytest.raises(gate.EvidenceError, match="differs"):
            release.smoke_wheel(output)
    else:
        assert release.smoke_wheel(output)["smoke_exit_code"] == 0
