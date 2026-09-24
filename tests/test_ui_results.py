"""Result summaries and explicit file actions without opening external apps."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from financial_statement_extract.ui.file_actions import open_result_path
from financial_statement_extract.ui.results import recovery_hint, summarize_result
from models import ExtractionResult


class Frame:
    attrs = {"statement_title": "Consolidated Statements of Operations (unaudited)",
             "period_labels": ["Six months ended June 30, 2026", "2025"]}

    def __len__(self):
        return 18


def result(**kwargs):
    data = dict(metadata={"pages_selected": "12,14-16"}, raw_text_rows=[], raw_table_cells=[],
                normalized_table_cells=[], extraction_audit_rows=[], statements={"InternalName": Frame()},
                parsed_cells=[], financial_audit_rows=[], unmapped_rows=[])
    data.update(kwargs)
    return ExtractionResult(**data)


def test_summary_preserves_source_titles_periods_and_all_audit_groups():
    source = result(financial_audit_rows=[dict(Status="PASS", Check="Balance", Scope="2026", Detail="Passed")],
                    extraction_audit_rows=[dict(Status="WARN", Check="Coverage", Scope="Page 12", Detail="Review numeric coverage")],
                    page_plan=SimpleNamespace(warnings=("Uncertain page 16",), selected_pages=(12, 14, 15, 16)))
    summary = summarize_result(source)
    assert summary.statements == ((Frame.attrs["statement_title"], "18", ", ".join(Frame.attrs["period_labels"])),)
    assert "InternalName" not in str(summary)
    assert summary.pages == "12,14-16"
    assert summary.needs_review
    assert len(summary.checks) == 3
    assert "2 warnings" in summary.overview
    assert summary.checks[1] == ("WARN", "Coverage", "Extraction · Page 12", "Review numeric coverage")
    assert source.financial_audit_rows[0]["Status"] == "PASS"


@pytest.mark.parametrize("status,review", [("PASS", False), ("WARN", True), ("FAIL", True),
                                         ("ERROR", True), ("NOT_TESTED", True), ("UNRECOGNIZED", True)])
def test_result_tones_do_not_hide_failures_or_unperformed_checks(status, review):
    summary = summarize_result(result(financial_audit_rows=[dict(Status=status, Check="Check")]))
    assert summary.needs_review is review
    assert ("review required" in summary.headline) is review


def test_no_statements_no_checks_and_source_only_grids_are_explicit():
    summary = summarize_result(result(statements={}, metadata={"input_type": "HTML"}, statement_tables=[
        {"source_title": "Investment schedule — June 2026", "statement_type": "ScheduleOfInvestments"}]))
    assert summary.needs_review
    assert "No parsed statements" in summary.overview
    assert summary.statements == (("Investment schedule — June 2026", "Not parsed", "Source grid · review workbook"),)
    assert summary.pages == "Not applicable (HTML)"
    assert summarize_result(result()).needs_review  # No checks is not a PASS.


@pytest.mark.parametrize("kind,expected", [("PermissionError", "Check access"), ("FileCreateError", "Close any workbook"),
                                          ("FileNotFoundError", "no longer available"), ("ValueError", "PDF page selection"),
                                          ("Unknown", "Review diagnostics")])
def test_recovery_guidance_is_actionable(kind, expected):
    assert expected in recovery_hint("Original diagnostic", kind)


def test_no_statements_failure_explains_ocr_limit():
    assert "OCR workflow outside this app" in recovery_hint("No financial statements were extracted; no workbook was created.", "ValueError")


def test_native_open_actions_use_exact_local_path_and_no_shell(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("financial_statement_extract.ui.file_actions.os.startfile", lambda *args: calls.append(args))
    workbook = tmp_path / "Company & data (2026).xlsx"
    workbook.touch()
    open_result_path(workbook)
    open_result_path(tmp_path, folder=True)
    assert calls == [(str(workbook), "open"), (str(tmp_path), "open")]


@pytest.mark.parametrize("path", ["//server/share/book.xlsx", r"\\?\C:\book.xlsx", "file://server/share/book.xlsx"])
def test_open_rejects_nonlocal_paths_before_access(path, monkeypatch):
    monkeypatch.setattr(Path, "is_file", lambda *_args: pytest.fail("Unexpected filesystem access"))
    monkeypatch.setattr("financial_statement_extract.ui.file_actions.os.startfile", lambda *_args: pytest.fail("Unexpected launch"))
    with pytest.raises(ValueError):
        open_result_path(path)


def test_missing_or_non_workbook_result_is_not_launched(tmp_path, monkeypatch):
    monkeypatch.setattr("financial_statement_extract.ui.file_actions.os.startfile", lambda *_args: pytest.fail("Unexpected launch"))
    with pytest.raises(FileNotFoundError):
        open_result_path(tmp_path / "missing.xlsx")
    with pytest.raises(FileNotFoundError):
        open_result_path(tmp_path / "missing", folder=True)
    other = tmp_path / "not-a-workbook.exe"
    other.touch()
    with pytest.raises(ValueError):
        open_result_path(other)
