from dataclasses import FrozenInstanceError

import pytest

from financial_statement_extract.ui.state import WorkspaceState


def test_request_normalizes_paths_and_snapshots_draft_without_mutating_it(tmp_path):
    state = WorkspaceState(
        input_path=f"  {tmp_path / 'Company 10-K.pdf'}  ",
        pages=" 12,14-16 ",
        client_name="  Example Company  ",
        year=" 2026 ",
        period=" Annual ",
        audit_status=" Draft ",
    )

    request = state.to_request()
    state.client_name = "Next company"
    state.pages = "42"
    metadata = request.metadata
    metadata["client_name"] = "Changed by runner"

    assert request.input_path == str(tmp_path / "Company 10-K.pdf")
    assert request.output_dir == str(tmp_path)
    assert request.pages == "12,14-16"
    assert request.metadata == {
        "client_name": "Example Company", "year": "2026", "period": "Annual", "audit_status": "Draft",
    }
    assert state.year == " 2026 "
    assert state.output_dir == ""
    with pytest.raises(FrozenInstanceError):
        request.pages = "1"


def test_default_request_keeps_auto_pages_and_explicit_output(tmp_path):
    state = WorkspaceState(input_path=str(tmp_path / "filing.htm"), output_dir=str(tmp_path / "outputs"))
    request = state.to_request()
    assert request.output_dir == str(tmp_path / "outputs")
    assert request.pages == "auto"
    assert request.metadata == {"client_name": "", "year": "", "period": "Auto", "audit_status": "Audited"}


@pytest.mark.parametrize("field", ["input_path", "output_dir"])
def test_draft_rejects_nonlocal_paths_before_submission(field, tmp_path):
    state = WorkspaceState(input_path=str(tmp_path / "filing.pdf"))
    setattr(state, field, r"\\server\share\filing.pdf")
    with pytest.raises(ValueError):
        state.to_request()


def test_empty_draft_explains_missing_source():
    with pytest.raises(ValueError, match="Choose or drop"):
        WorkspaceState().to_request()
