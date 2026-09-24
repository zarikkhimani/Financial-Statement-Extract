from pathlib import Path

import pytest

from app import (
    PAGE_WARNING_LIMIT,
    PAGES_HELP_TEXT,
    PAGES_PLACEHOLDER,
    FinancialExtractorApp,
    count_requested_pages,
    effective_pages_value,
    normalize_dropped_path,
    select_dropped_filing,
)
from financial_statement_extract.ui.controller import ExtractionController
from financial_statement_extract.ui.lifecycle import JobLifecycle
from financial_statement_extract.ui.state import WorkspaceState


class FakeVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeStatus:
    def __init__(self):
        self.text = ""

    def delete(self, *_args):
        self.text = ""

    def insert(self, _position, value):
        self.text += value


def test_pages_placeholder_uses_auto_but_manual_pages_override_it():
    assert effective_pages_value(PAGES_PLACEHOLDER, True) == "auto"
    assert effective_pages_value("", False) == "auto"
    assert effective_pages_value("12,14-16", False) == "12,14-16"


def test_pages_ui_distinguishes_pdf_pages_from_printed_10k_pages():
    assert "PDF page numbers" in PAGES_PLACEHOLDER
    assert "not printed 10-K page numbers" in PAGES_PLACEHOLDER
    assert "PDF viewer's page numbers" in PAGES_HELP_TEXT


@pytest.mark.parametrize(
    ("selection", "expected"),
    [
        ("auto", None),
        ("1-20", 20),
        ("1-10,15-25", 21),
        ("1-10,5-15,20", 16),
        ("3,3,4", 2),
    ],
)
def test_count_requested_pages_counts_distinct_manual_pdf_pages(selection, expected):
    assert count_requested_pages(selection) == expected


def test_large_manual_pdf_selection_requires_confirmation(monkeypatch):
    from types import SimpleNamespace
    from financial_statement_extract.page_selection import build_page_plan

    prompts = []
    monkeypatch.setattr("app.messagebox.askyesnocancel", lambda *args, **kwargs: prompts.append((args, kwargs)) or None)

    app = FinancialExtractorApp.__new__(FinancialExtractorApp)
    app.controller = ExtractionController()
    app.closing = False
    app.root = object()
    app.state = WorkspaceState(
        input_path=r"C:\Reports\Company 10-K.pdf",
        pages=f"1-{PAGE_WARNING_LIMIT + 1}",
    )

    app.progress = SimpleNamespace(stop=lambda: None, grid_remove=lambda: None)
    app.pdf_run_button = SimpleNamespace(configure=lambda **kwargs: None)
    app.pdf_status = FakeStatus()
    app.result_context = FakeVar()
    app._refresh_setup = lambda: None
    app.shell = SimpleNamespace(set_status=lambda *_args: None)
    app.results = SimpleNamespace(show_note=lambda *_args: None)
    request = app.state.to_request()
    app.lifecycle = JobLifecycle()
    app.lifecycle.begin(request, app.state.draft_key())
    plan = build_page_plan(request.input_path, [], list(range(1, PAGE_WARNING_LIMIT + 2)), "manual")
    app._review_page_selection(plan, request)

    assert len(prompts) == 1
    assert "No: use exactly the entered pages" in prompts[0][0][1]
    assert prompts[0][1]["default"] == "cancel"
    assert app.controller.worker is None


def test_drop_path_supports_windows_file_urls_and_selects_pdf():
    path = normalize_dropped_path("file:///C:/Reports/Annual%20Report.pdf")
    assert path.name == "Annual Report.pdf"
    assert select_dropped_filing(("notes.txt", r"{C:\Reports\Company 10-K.PDF}")) == Path(r"C:\Reports\Company 10-K.PDF")
    assert select_dropped_filing(("notes.txt", r"{C:\Reports\Company Filing.HTM}")) == Path(r"C:\Reports\Company Filing.HTM")


@pytest.mark.parametrize(
    "value",
    [
        "file://server/share/report.pdf",
        "file://localhost/C:/Reports/report.pdf",
        r"\\server\share\report.pdf",
        "//server/share/report.pdf",
        r"\\?\C:\Reports\report.pdf",
        r"\\?\UNC\server\share\report.pdf",
        r"\\.\PhysicalDrive0\report.pdf",
        r"\??\C:\Reports\report.pdf",
        r"\Device\HarddiskVolume1\report.pdf",
        "file:///%5C%5Cserver%5Cshare%5Creport.pdf",
        "file:///%5C%5C%3F%5CC:%5CReports%5Creport.pdf",
    ],
)
def test_drop_path_rejects_network_and_windows_device_paths(value):
    with pytest.raises(ValueError):
        normalize_dropped_path(value)
    assert select_dropped_filing((value,)) is None


def test_drop_selection_skips_nonlocal_candidate_and_accepts_local_candidate():
    local = r"C:\Reports\Company 10-K.pdf"
    assert select_dropped_filing(("file://server/share/report.pdf", local)) == Path(local)


def test_nonlocal_drop_is_rejected_before_filesystem_probe(monkeypatch):
    def unexpected_probe(_path):
        raise AssertionError("filesystem was probed")

    monkeypatch.setattr(Path, "is_file", unexpected_probe)
    monkeypatch.setattr("app.messagebox.showerror", lambda *_args: None)
    app = FinancialExtractorApp.__new__(FinancialExtractorApp)

    assert app._set_pdf_path(r"\\server\share\report.pdf") is False


def test_setting_dropped_pdf_populates_path_output_folder_and_status(tmp_path):
    from types import SimpleNamespace
    pdf = tmp_path / "Dropped Report.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    app = FinancialExtractorApp.__new__(FinancialExtractorApp)
    app.pdf_path = FakeVar()
    app.output_dir = FakeVar()
    app.pdf_status = FakeStatus()
    app.result_context = FakeVar()
    app._has_result = False
    app.lifecycle = JobLifecycle()
    app.results = SimpleNamespace(show_note=lambda *_args: None)

    assert app._set_pdf_path(pdf) is True
    assert app.pdf_path.get() == str(pdf)
    assert app.output_dir.get() == str(tmp_path)
    assert str(pdf) in app.pdf_status.text

def test_setting_dropped_html_populates_path_output_folder_and_status(tmp_path):
    from types import SimpleNamespace
    html = tmp_path / "Company 10-K.htm"
    html.write_text("<html><body></body></html>", encoding="utf-8")
    app = FinancialExtractorApp.__new__(FinancialExtractorApp)
    app.pdf_path = FakeVar()
    app.output_dir = FakeVar()
    app.pdf_status = FakeStatus()
    app.result_context = FakeVar()
    app._has_result = False
    app.lifecycle = JobLifecycle()
    app.results = SimpleNamespace(show_note=lambda *_args: None)

    assert app._set_pdf_path(html) is True
    assert app.pdf_path.get() == str(html)
    assert app.output_dir.get() == str(tmp_path)
    assert "Loaded filing" in app.pdf_status.text
