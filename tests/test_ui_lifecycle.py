"""Fast lifecycle transitions: no Tk, documents, worker sleeps, or extraction."""

from dataclasses import replace

import pytest

from financial_statement_extract.ui.lifecycle import JobLifecycle, JobPhase
from financial_statement_extract.ui.state import WorkspaceState


def test_every_phase_and_retry_keeps_frozen_request(tmp_path):
    draft = WorkspaceState()
    job = JobLifecycle()
    job.sync_draft(draft)
    assert job.phase is JobPhase.EMPTY
    assert job.disabled_reason(draft) == ""
    draft.input_path = str(tmp_path / "sample.pdf")
    job.sync_draft(draft)
    assert job.phase is JobPhase.READY
    request = draft.to_request()
    job.begin(request, draft.draft_key())
    draft.client_name = "Next run"
    job.sync_draft(draft)
    assert job.phase is JobPhase.RUNNING
    assert "in progress" in job.disabled_reason(draft)
    with pytest.raises(RuntimeError, match="already running"):
        job.begin(draft.to_request(), draft.draft_key())
    assert job.request is request
    assert job.request.client_name == ""
    job.fail("Output folder denied")
    assert job.phase is JobPhase.ERROR
    assert job.error == "Output folder denied"
    job.sync_draft(draft)  # A redraw cannot erase an outcome.
    assert job.phase is JobPhase.ERROR
    assert job.disabled_reason(draft) == ""
    assert draft.client_name == "Next run"
    retry = draft.to_request()
    job.begin(retry, draft.draft_key())
    assert job.error == ""
    job.succeed()
    assert job.phase is JobPhase.SUCCEEDED
    assert job.request is retry
    job.sync_draft(draft)
    assert job.phase is JobPhase.SUCCEEDED
    draft.input_path = ""
    job.sync_draft(draft)
    assert job.phase is JobPhase.EMPTY


@pytest.mark.parametrize("policy", ["suggested", "exact", None])
def test_review_is_part_of_one_active_job(tmp_path, policy):
    draft = WorkspaceState(input_path=str(tmp_path / "sample.pdf"), pages="1-30")
    job = JobLifecycle()
    request = draft.to_request()
    job.begin(request, draft.draft_key())
    submitted = job.submitted_draft
    job.require_review()
    assert job.phase is JobPhase.RUNNING
    assert "Review" in job.disabled_reason(draft)
    draft.pages = "4"
    job.sync_draft(draft)
    if policy:
        job.resume_review(replace(request, page_policy=policy))
        assert job.phase is JobPhase.RUNNING
        assert job.request.pages == "1-30"
        assert job.request.page_policy == policy
        assert job.submitted_draft == submitted
        job.succeed()
    else:
        job.decline_review(draft)
        assert job.phase is JobPhase.READY
    assert not job.awaiting_review
    assert draft.pages == "4"


@pytest.mark.parametrize("transition", ["succeed", "require_review", "fail", "resume_review", "decline_review"])
def test_outcomes_require_active_job(transition):
    job = JobLifecycle()
    args = {"fail": ("error",), "resume_review": (None,), "decline_review": (WorkspaceState(),)}
    with pytest.raises(RuntimeError, match="No extraction"):
        getattr(job, transition)(*args.get(transition, ()))


def test_disabled_reasons_are_pure_and_recompute_after_edits(tmp_path, monkeypatch):
    from pathlib import Path

    def no_probe(*_args):
        raise AssertionError("Lifecycle must not inspect files")

    monkeypatch.setattr(Path, "is_file", no_probe)
    job = JobLifecycle()
    draft = WorkspaceState(input_path=str(tmp_path / "sample.pdf"), output_dir="//server/share")
    job.sync_draft(draft)
    assert job.phase is JobPhase.READY
    assert job.disabled_reason(draft)
    draft.output_dir = str(tmp_path)
    assert job.disabled_reason(draft) == ""
    draft.input_path = str(tmp_path / "sample.txt")
    assert "PDF or local HTML" in job.disabled_reason(draft)
