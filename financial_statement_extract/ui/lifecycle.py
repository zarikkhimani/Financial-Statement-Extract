"""Widget-independent single-job lifecycle, owned by the UI thread.

Worker completion is not UI completion: RUNNING lasts until its queued outcome
is consumed, including time spent reviewing PDF pages. No cancellation of a
running extractor is implied by declining a preflight review.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from financial_statement_extract.progress import ProgressEvent

from .inputs import HTML_SUFFIXES
from .state import JobRequest, WorkspaceState


class JobPhase(str, Enum):
    EMPTY = "EMPTY"
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    ERROR = "ERROR"


@dataclass
class JobLifecycle:
    phase: JobPhase = JobPhase.EMPTY
    request: JobRequest | None = None
    submitted_draft: tuple[str, ...] | None = None
    error: str = ""
    awaiting_review: bool = False
    progress: ProgressEvent | None = None
    _draft: tuple[str, ...] | None = None

    @property
    def active(self) -> bool:
        return self.phase is JobPhase.RUNNING

    def sync_draft(self, draft: WorkspaceState):
        key = draft.draft_key()
        if key != self._draft:
            self._draft = key
            if not self.active:
                self.phase = JobPhase.READY if draft.input_path.strip() else JobPhase.EMPTY

    def disabled_reason(self, draft: WorkspaceState) -> str:
        """Cheap action validation: never probe a file or import the pipeline."""
        if self.active:
            return ("Review the selected PDF pages before continuing." if self.awaiting_review else
                    "An extraction is in progress. Setup edits apply to the next run.")
        if not draft.input_path.strip():
            return ""  # Choose filing is the available primary action.
        try:
            request = draft.to_request()
            if Path(request.input_path).suffix.lower() not in {".pdf", *HTML_SUFFIXES}:
                return "Choose a PDF or local HTML filing using Browse."
        except ValueError as exc:
            return str(exc)
        return ""

    def begin(self, request: JobRequest, draft_key: tuple[str, ...]):
        if self.active:
            raise RuntimeError("An extraction is already running.")
        self.request = request
        self.submitted_draft = draft_key
        self._draft = draft_key
        self.error = ""
        self.progress = None
        self.awaiting_review = False
        self.phase = JobPhase.RUNNING

    def _require_running(self):
        if not self.active:
            raise RuntimeError("No extraction is awaiting an outcome.")

    def require_review(self):
        self._require_running()
        self.awaiting_review = True

    def resume_review(self, request: JobRequest):
        self._require_running()
        if not self.awaiting_review:
            raise RuntimeError("No page review is pending.")
        self.request = request
        self.progress = None
        self.awaiting_review = False

    def decline_review(self, draft: WorkspaceState):
        self._require_running()
        if not self.awaiting_review:
            raise RuntimeError("No page review is pending.")
        self.awaiting_review = False
        self.phase = JobPhase.READY if draft.input_path.strip() else JobPhase.EMPTY

    def succeed(self):
        self._require_running()
        self.awaiting_review = False
        self.phase = JobPhase.SUCCEEDED

    def fail(self, message: str):
        self._require_running()
        self.awaiting_review = False
        self.error = message
        self.phase = JobPhase.ERROR
