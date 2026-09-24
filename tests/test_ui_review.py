"""Phase 8 live-pipeline acceptance checks; only generated review data is used."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from openpyxl import load_workbook
import pytest

from financial_statement_extract.ui.lifecycle import JobPhase
from financial_statement_extract.ui.review import create_session
from financial_statement_extract.ui.review_samples import CASES
from test_ui_workspace import make_workspace as _workspace_fixture

make_workspace = _workspace_fixture


def test_review_sessions_are_unique_and_preserve_existing_files(tmp_path):
    marker = tmp_path / "user-notes.txt"
    marker.write_text("Keep this", encoding="utf-8")
    first, paths = create_session(tmp_path)
    second, _ = create_session(tmp_path)
    assert first != second
    assert first.parent == second.parent == tmp_path
    assert marker.read_text(encoding="utf-8") == "Keep this"
    assert {name: path.read_text(encoding="utf-8") for name, path in paths.items()} == CASES


@pytest.mark.parametrize("case,phase,count", [("corporate", "SUCCEEDED", 3), ("fund", "SUCCEEDED", 2), ("invalid", "ERROR", 0)])
def test_fresh_process_review_uses_real_pipeline_and_exits_cleanly(tmp_path, case, phase, count):
    completed = subprocess.run([
        sys.executable, "-m", "financial_statement_extract.ui.review", "--case", case, "--smoke",
        "--size", "640x700", "--text-scale", "2", "--review-dir", str(tmp_path),
    ], capture_output=True, text=True, timeout=45)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    assert result["phase"] == phase and result["passed"]
    assert result["statements"] == count
    assert result["callback_errors"] == []
    assert Path(result["source"]).read_text(encoding="utf-8") == CASES[case]
    if phase == "ERROR":
        assert result["error"] == "No financial statements were extracted; no workbook was created."
        assert not list(tmp_path.rglob("*.xlsx"))
        return
    assert Path(result["output"]).is_file()
    book = load_workbook(result["output"])
    try:
        cells = [cell for sheet in book for row in sheet for cell in row]
        values = {cell.value for cell in cells}
        assert not any(cell.data_type == "f" for cell in cells)
        if case == "corporate":
            assert {"Consolidated Statements of Income", "Consolidated Statements of Cash Flows",
                    "Consolidated Balance Sheets", "Revenue", 300} <= values
        else:
            assert {"Statements of Stockholders’ Equity", "Schedule of Investments", "Geography", "N/A", "—"} <= values
            assert any(str(value).startswith("Synthetic issuer 60") for value in values)
            assert any(cell.value == 0.125 and "%" in cell.number_format for cell in cells)
    finally:
        book.close()


def test_real_write_failure_retry_and_repeat_do_not_lose_draft_or_overwrite(make_workspace, tmp_path):
    source = tmp_path / "Synthetic corporate.html"
    source.write_text(CASES["corporate"], encoding="utf-8")
    blocked = tmp_path / "a-file-not-a-folder"
    blocked.write_text("Keep this blocker", encoding="utf-8")
    app, dialogs = make_workspace(None)
    app._set_pdf_path(source)
    app.client_name.set("Review draft — keep this")
    app.pages.set("12,14-16")
    app.output_dir.set(str(blocked))

    def finish():
        app.controller.worker.join(15)
        assert not app.controller.is_running
        app._poll_queue()
        app.root.update()

    app.pdf_run_button.invoke()
    finish()
    assert app.lifecycle.phase is JobPhase.ERROR
    assert app.pdf_run_button.cget("text") == "Retry"
    assert not list(tmp_path.rglob("*.xlsx"))
    assert app.state.client_name == "Review draft — keep this"
    assert app.state.pages == "12,14-16"
    app.output_dir.set(str(tmp_path))
    app.pdf_run_button.invoke()
    finish()
    assert app.lifecycle.phase is JobPhase.SUCCEEDED
    original = app._result_output
    original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
    assert app.results.summary.needs_review  # Missing checks remain explicit.
    assert len(app.results.summary.statements) == 3
    app.result_action.invoke()  # Extract again, not Open workbook.
    finish()
    assert app.lifecycle.phase is JobPhase.SUCCEEDED
    assert app._result_output != original
    assert hashlib.sha256(original.read_bytes()).hexdigest() == original_hash
    assert len(list(tmp_path.glob("*.xlsx"))) == 2
    assert blocked.read_text(encoding="utf-8") == "Keep this blocker"
    assert not dialogs


def test_review_import_is_light_and_interactive_close_is_clean(tmp_path):
    completed = subprocess.run([sys.executable, "-c", """
import sys
from financial_statement_extract.ui import review
assert not {'pipeline', 'pandas', 'pdfplumber', 'camelot'} & sys.modules.keys()
original = review.FinancialExtractorApp.__init__
def init(self, root, **kwargs):
    original(self, root, **kwargs)
    root.after(150, self._on_close)
review.FinancialExtractorApp.__init__ = init
assert review.main(['--review-dir', sys.argv[1]]) == 0
""", str(tmp_path)], capture_output=True, text=True, timeout=15)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_invalid_smoke_does_not_mask_an_unrelated_worker_failure(tmp_path):
    completed = subprocess.run([sys.executable, "-c", """
import sys
from financial_statement_extract.ui import review
from financial_statement_extract.ui import controller
def broken(*args, **kwargs):
    raise ImportError('Synthetic missing dependency')
controller.run_extraction = broken
assert review.main(['--case', 'invalid', '--smoke', '--review-dir', sys.argv[1]]) == 1
""", str(tmp_path)], capture_output=True, text=True, timeout=15)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(completed.stdout.strip().splitlines()[-1])
    assert not report["passed"]
    assert report["error"] == "Synthetic missing dependency"
