from pathlib import Path

import pytest

from path_policy import normalize_path
from pipeline import extract_filing_to_workbook


def test_local_paths_and_local_file_urls_remain_supported(tmp_path):
    local_path = tmp_path / "Annual Report.pdf"
    assert normalize_path(local_path) == local_path
    assert normalize_path(r"C:\Reports\Annual Report.pdf") == Path(
        r"C:\Reports\Annual Report.pdf"
    )
    assert normalize_path("file:///C:/Reports/Annual%20Report.pdf") == Path(
        r"C:\Reports\Annual Report.pdf"
    )


def test_nonlocal_paths_require_an_explicit_opt_in():
    network_path = r"\\server\share\report.pdf"
    with pytest.raises(ValueError, match="disabled by default"):
        normalize_path(network_path)
    assert normalize_path(network_path, allow_nonlocal_paths=True) == Path(network_path)


@pytest.mark.parametrize(
    "value",
    [
        "NUL.pdf",
        "CON.html",
        r"C:\Reports\AUX.pdf",
        r"C:\Reports\COM1.pdf",
        r"C:\Reports\LPT9.html",
        r"C:\Reports\CONIN$.pdf",
        r"C:\Reports\CONOUT$.html",
    ],
)
def test_reserved_dos_device_names_require_an_explicit_opt_in(value):
    with pytest.raises(ValueError, match="disabled by default"):
        normalize_path(value)
    assert normalize_path(value, allow_nonlocal_paths=True) == Path(value)


def test_pipeline_rejects_nonlocal_input_before_exists_probe(monkeypatch):
    def unexpected_probe(_path):
        raise AssertionError("filesystem was probed")

    monkeypatch.setattr(Path, "exists", unexpected_probe)
    with pytest.raises(ValueError, match="disabled by default"):
        extract_filing_to_workbook(r"\\server\share\report.pdf")
