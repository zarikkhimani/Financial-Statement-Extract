from pathlib import Path

import financial_statement_extract
import pipeline


def test_package_exposes_a_small_stable_api():
    assert financial_statement_extract.__version__ == "0.1.0"
    assert financial_statement_extract.extract_to_excel is financial_statement_extract.extract_filing


def test_extract_filing_delegates_to_the_pipeline(monkeypatch, tmp_path):
    expected = (object(), tmp_path / "output.xlsx")
    received = {}

    def fake_extract(input_path, pages, metadata, output_dir, *, allow_nonlocal_paths):
        received.update(
            {
                "input_path": input_path,
                "pages": pages,
                "metadata": metadata,
                "output_dir": output_dir,
                "allow_nonlocal_paths": allow_nonlocal_paths,
            }
        )
        return expected

    monkeypatch.setattr(pipeline, "extract_filing_to_workbook", fake_extract)

    actual = financial_statement_extract.extract_filing(
        Path("filing.pdf"),
        pages="4-6",
        metadata={"client_name": "Example Bank"},
        output_dir=tmp_path,
        allow_nonlocal_paths=True,
    )

    assert actual == expected
    assert received == {
        "input_path": "filing.pdf",
        "pages": "4-6",
        "metadata": {"client_name": "Example Bank"},
        "output_dir": str(tmp_path),
        "allow_nonlocal_paths": True,
    }
