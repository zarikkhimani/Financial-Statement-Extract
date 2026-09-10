from pathlib import Path

import pytest

from app import PAGES_PLACEHOLDER, FinancialExtractorApp, effective_pages_value, normalize_dropped_path, select_dropped_filing


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
    pdf = tmp_path / "Dropped Report.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    app = FinancialExtractorApp.__new__(FinancialExtractorApp)
    app.pdf_path = FakeVar()
    app.output_dir = FakeVar()
    app.pdf_status = FakeStatus()

    assert app._set_pdf_path(pdf) is True
    assert app.pdf_path.get() == str(pdf)
    assert app.output_dir.get() == str(tmp_path)
    assert str(pdf) in app.pdf_status.text

def test_setting_dropped_html_populates_path_output_folder_and_status(tmp_path):
    html = tmp_path / "Company 10-K.htm"
    html.write_text("<html><body></body></html>", encoding="utf-8")
    app = FinancialExtractorApp.__new__(FinancialExtractorApp)
    app.pdf_path = FakeVar()
    app.output_dir = FakeVar()
    app.pdf_status = FakeStatus()

    assert app._set_pdf_path(html) is True
    assert app.pdf_path.get() == str(html)
    assert app.output_dir.get() == str(tmp_path)
    assert "Loaded filing" in app.pdf_status.text
