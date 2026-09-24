"""Background extraction transport. This module never imports or calls Tk."""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from pathlib import Path

from models import ExtractionResult, PageSelectionReviewRequired
from financial_statement_extract.progress import ProgressReporter

from .state import JobRequest

logger = logging.getLogger(__name__)
ExtractionRunner = Callable[[str, str, dict[str, str], str], tuple[ExtractionResult, Path]]


def run_extraction(input_path: str, pages: str, metadata: dict, output_dir: str, *,
                   page_policy: str = "review", progress: ProgressReporter | None = None):
    """Load the heavy extraction stack only after the user starts a job."""
    from pipeline import extract_filing_to_workbook

    return extract_filing_to_workbook(input_path, pages, metadata, output_dir,
                                     page_policy=page_policy, progress=progress)


class ExtractionController:
    """Own the existing single daemon worker and its completion queue.

    start() is called by the UI thread. The worker receives only a frozen
    request and puts success/error events on the queue; the UI consumes them
    on the Tk thread. A runner may be supplied for inexpensive isolated tests.
    """

    def __init__(self, runner: ExtractionRunner | None = None, *, reports_progress: bool = False):
        self.runner = runner if runner is not None else run_extraction
        # Keep four-argument injected runners compatible. Progress-capable
        # custom runners explicitly opt in to the additional keyword argument.
        self.reports_progress = runner is None or reports_progress
        self.work_queue: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.last_request: JobRequest | None = None

    @property
    def is_running(self) -> bool:
        return self.worker is not None and self.worker.is_alive()

    def start(self, request: JobRequest) -> None:
        if self.is_running:
            raise RuntimeError("An extraction is already running.")

        def worker_target():
            try:
                options = {"page_policy": request.page_policy} if request.page_policy != "review" else {}
                if self.reports_progress:
                    options["progress"] = lambda event: self.work_queue.put(("progress", event, request))
                result, output = self.runner(
                    request.input_path, request.pages, request.metadata, request.output_dir, **options
                )
                self.work_queue.put(("pdf_success", result, output))
            except PageSelectionReviewRequired as exc:
                self.work_queue.put(("page_review", exc.plan, request))
            except Exception as exc:
                logger.exception("Filing extraction failed")
                self.work_queue.put(("pdf_error", str(exc), type(exc).__name__))

        self.last_request = request
        self.worker = threading.Thread(target=worker_target, daemon=True)
        self.worker.start()
