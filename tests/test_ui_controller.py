import subprocess
import sys
import threading

import pytest

from financial_statement_extract.ui.controller import ExtractionController
from financial_statement_extract.ui.state import WorkspaceState


def test_worker_uses_snapshot_and_reports_success_without_calling_ui(tmp_path):
    entered = threading.Event()
    release = threading.Event()
    received = []
    result = object()
    output = tmp_path / "output.xlsx"

    def runner(source, pages, metadata, destination):
        entered.set()
        assert release.wait(5), "Test did not release worker"
        received.append((source, pages, metadata.copy(), destination, threading.get_ident()))
        metadata["client_name"] = "runner mutation"
        return result, output

    state = WorkspaceState(input_path=str(tmp_path / "filing.pdf"), client_name="Original")
    request = state.to_request()
    controller = ExtractionController(runner)
    controller.start(request)
    try:
        assert entered.wait(5)
        assert controller.is_running
        assert controller.worker.daemon
        state.client_name = "Next run"
        with pytest.raises(RuntimeError, match="already running"):
            controller.start(state.to_request())
    finally:
        release.set()
        controller.worker.join(5)

    assert not controller.is_running
    assert controller.work_queue.get_nowait() == ("pdf_success", result, output)
    assert controller.work_queue.empty()
    assert received[0][:4] == (request.input_path, "auto", request.metadata, str(tmp_path))
    assert received[0][4] != threading.get_ident()
    assert controller.last_request is request
    assert request.metadata["client_name"] == "Original"


def test_worker_reports_errors_and_can_run_again(tmp_path):
    calls = []
    output = tmp_path / "output.xlsx"
    result = object()

    def runner(*args):
        calls.append(args)
        if len(calls) == 1:
            raise PermissionError("Output folder is not writable")
        return result, output

    controller = ExtractionController(runner)
    request = WorkspaceState(input_path=str(tmp_path / "filing.html")).to_request()
    controller.start(request)
    controller.worker.join(5)
    assert not controller.is_running
    assert controller.work_queue.get_nowait() == ("pdf_error", "Output folder is not writable", "PermissionError")

    controller.start(request)
    controller.worker.join(5)
    assert not controller.is_running
    assert controller.work_queue.get_nowait() == ("pdf_success", result, output)
    assert len(calls) == 2


def test_ui_entry_points_keep_extraction_stack_lazy():
    completed = subprocess.run(
        [sys.executable, "-c", (
            "import sys; import app; import financial_statement_extract.gui as gui; "
            "from financial_statement_extract.ui.workspace import FinancialExtractorApp, main; "
            "assert app.main is gui.main is main; "
            "assert app.FinancialExtractorApp is FinancialExtractorApp; "
            "assert not {'pipeline', 'pandas', 'pdfplumber', 'camelot'} & sys.modules.keys()"
        )],
        capture_output=True, text=True, timeout=20,
    )
    assert completed.returncode == 0, completed.stderr


def test_worker_start_failure_is_not_silently_queued_and_allows_retry(tmp_path, monkeypatch):
    request = WorkspaceState(input_path=str(tmp_path / "synthetic.pdf")).to_request()
    controller = ExtractionController(lambda *_args: (object(), tmp_path / "not-created.xlsx"))
    original_start = threading.Thread.start

    def fail_start(_thread):
        raise RuntimeError("Thread could not start")

    monkeypatch.setattr(threading.Thread, "start", fail_start)
    with pytest.raises(RuntimeError, match="Thread could not start"):
        controller.start(request)
    assert not controller.is_running
    assert controller.work_queue.empty()
    monkeypatch.setattr(threading.Thread, "start", original_start)
    controller.start(request)
    controller.worker.join(5)
    assert controller.work_queue.get_nowait()[0] == "pdf_success"


def test_progress_is_enqueued_in_order_on_worker_thread_before_error(tmp_path):
    from financial_statement_extract.progress import ExtractionStage, ProgressEvent

    thread_ids = []
    event = ProgressEvent(ExtractionStage.PARSING, "Synthetic progress")
    def runner(*args, progress):
        thread_ids.append(threading.get_ident())
        progress(event)
        raise ValueError("Synthetic failure")

    controller = ExtractionController(runner, reports_progress=True)
    request = WorkspaceState(input_path=str(tmp_path / "sample.pdf")).to_request()
    controller.start(request)
    controller.worker.join(5)
    assert controller.work_queue.get_nowait() == ("progress", event, request)
    assert controller.work_queue.get_nowait() == ("pdf_error", "Synthetic failure", "ValueError")
    assert controller.work_queue.empty()
    assert thread_ids != [threading.get_ident()]


def test_review_resume_keeps_progress_bound_to_its_request(tmp_path):
    from dataclasses import replace
    from financial_statement_extract.page_selection import build_page_plan
    from financial_statement_extract.progress import ExtractionStage, ProgressEvent
    from models import PageSelectionReviewRequired

    plan = build_page_plan("sample.pdf", [], list(range(1, 14)), "manual")
    def runner(*args, progress, page_policy="review"):
        if page_policy == "review":
            progress(ProgressEvent(ExtractionStage.DETECTING_PAGES))
            raise PageSelectionReviewRequired(plan)
        progress(ProgressEvent(ExtractionStage.EXTRACTING_TABLES))
        return object(), tmp_path / "not-created.xlsx"

    controller = ExtractionController(runner, reports_progress=True)
    original = WorkspaceState(input_path=str(tmp_path / "sample.pdf"), pages="1-13").to_request()
    controller.start(original)
    controller.worker.join(5)
    first = controller.work_queue.get_nowait()
    assert first[0] == "progress" and first[2] is original
    assert controller.work_queue.get_nowait() == ("page_review", plan, original)
    resumed = replace(original, page_policy="exact")
    controller.start(resumed)
    controller.worker.join(5)
    second = controller.work_queue.get_nowait()
    assert second[0] == "progress" and second[2] is resumed
    assert second[1].stage is ExtractionStage.EXTRACTING_TABLES
    assert controller.work_queue.get_nowait()[0] == "pdf_success"
