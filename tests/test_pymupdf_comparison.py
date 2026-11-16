import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

from financial_statement_extract.pymupdf_comparison import require_pymupdf, token_metrics


def test_comparison_counts_repeated_amounts_without_combining_strategies():
    source = [dict(source_page=1, raw_text="Revenue 100 100 2026"),
              dict(source_page=2, raw_text="Other 999")]
    cells = [dict(source_page=1, table_id="one", row_index=0, raw_text="Revenue 100 2026")]
    metric = token_metrics(source, cells, 1, "pymupdf_lines")
    assert metric["numeric_token_recall"] == 2 / 3
    assert metric["missing_numeric_tokens"] == {"100": 1}
    assert metric["tables"] == metric["rows"] == 1
    assert token_metrics([], cells, 1, "pymupdf_lines")["numeric_token_recall"] is None


def test_missing_optional_dependency_fails_with_installation_guidance(monkeypatch):
    monkeypatch.setitem(sys.modules, "pymupdf", None)
    with pytest.raises(ValueError, match=r"pip install.*pymupdf"):
        require_pymupdf()


def test_optional_comparison_is_forwarded_only_when_requested(monkeypatch):
    import pipeline
    from financial_statement_extract import extract_filing
    from financial_statement_extract.cli import main

    calls = []
    def runner(*args, **kwargs):
        calls.append(kwargs)
        return None, Path("example.xlsx")
    monkeypatch.setattr(pipeline, "extract_filing_to_workbook", runner)
    extract_filing("example.pdf")
    extract_filing("example.pdf", compare_pymupdf=True)
    main(["example.pdf", "--compare-pymupdf"])
    assert "compare_pymupdf" not in calls[0]
    assert calls[1]["compare_pymupdf"] is True
    assert calls[2]["compare_pymupdf"] is True


def test_html_comparison_is_rejected(tmp_path):
    from financial_statement_extract import extract_filing
    with pytest.raises(ValueError, match="requires a PDF"):
        extract_filing(tmp_path / "source.html", compare_pymupdf=True)
    assert not list(tmp_path.glob("*.xlsx"))


@pytest.mark.skipif(importlib.util.find_spec("pymupdf") is None, reason="optional PyMuPDF extra not installed")
def test_real_comparison_preserves_baseline_and_workbook_rules(tmp_path):
    # Keep native PDF engines isolated from the Windows Tk test interpreter.
    completed = subprocess.run([sys.executable, "-c", r'''
from pathlib import Path
import sys
import pymupdf
from openpyxl import load_workbook
from pandas.testing import assert_frame_equal
from financial_statement_extract import extract_filing
from financial_statement_extract.pymupdf_comparison import extract_comparison

folder = Path(sys.argv[1])
source = folder / "comparison.pdf"
with pymupdf.open() as document:
    page = document.new_page()
    page.insert_text((50, 50), "Example Company")
    page.insert_text((50, 70), "Income Statements")
    page.insert_text((50, 90), "Years Ended December 31, 2026 2025")
    xs, ys = [50, 300, 400, 500], [110, 140, 170, 200, 230, 260]
    for x in xs:
        page.draw_line((x, ys[0]), (x, ys[-1]))
    for y in ys:
        page.draw_line((xs[0], y), (xs[-1], y))
    for r, row in enumerate([["", "2026", "2025"], ["Revenue", "$300", "$250"],
                              ["Tax", "(30)", "N/A"], ["Net income", "270", "250"],
                              ["=1+1", "", "-"]]):
        for c, value in enumerate(row):
            page.insert_text((xs[c] + 5, ys[r] + 20), value)
    document.new_page()  # blank page: no OCR and no fabricated table
    document.new_page().insert_text((50, 50), "Unselected page 999")
    document.save(source)

plain, _ = extract_filing(source, pages="1", output_dir=folder / "baseline")
events = []
compared, path = extract_filing(source, pages="1", output_dir=folder / "comparison",
                                compare_pymupdf=True, progress=events.append)
for name in plain.statements:
    assert_frame_equal(plain.statements[name], compared.statements[name])
assert plain.page_plan == compared.page_plan
assert plain.statement_tables == compared.statement_tables
assert plain.raw_table_cells == compared.raw_table_cells
assert plain.parsed_cells == compared.parsed_cells
assert plain.financial_audit_rows == compared.financial_audit_rows
assert plain.extraction_audit_rows == compared.extraction_audit_rows
assert plain.experimental_raw_table_cells == compared.experimental_raw_table_cells
assert not plain.pymupdf_comparison
comparison = compared.pymupdf_comparison
assert comparison["version"] == pymupdf.__version__
assert {c["flavor"] for c in comparison["raw_table_cells"]} == {"pymupdf_lines", "pymupdf_text"}
assert {c["source_page"] for c in comparison["raw_table_cells"]} == {1}
assert not any(c["selected"] for c in comparison["raw_table_cells"])
assert not any(a["Status"] == "ERROR" for a in comparison["audit_rows"])
assert any(c["raw_text"] == "$300" for c in comparison["raw_table_cells"])
assert any(c["raw_text"] == "(30)" for c in comparison["raw_table_cells"])
assert any(c["raw_text"] == "N/A" for c in comparison["raw_table_cells"])
assert any(c["raw_text"] == "" for c in comparison["raw_table_cells"])
assert any(c["parsed_value"] == -30 for c in comparison["normalized_table_cells"])
assert any("PyMuPDF" in e.detail for e in events)

book = load_workbook(path)
try:
    assert {"PyMuPDF", "PyMuPDF Text", "PyMuPDF Review"} <= set(book.sheetnames)
    assert book.sheetnames[-1] == "Lattice"
    assert any(c.value == "=1+1" and c.data_type == "s" for row in book["PyMuPDF"] for c in row)
    for sheet in book:
        assert not sheet.merged_cells.ranges
        assert sheet.freeze_panes is None
        assert all(c.value is None for row in sheet.iter_rows(max_row=3) for c in row)
        assert all(c.value is None for row in sheet.iter_rows(max_col=2) for c in row)
        assert all(not d.hidden and (d.height is None or d.height > 0) for d in sheet.row_dimensions.values())
        assert all(not d.hidden and d.width > 0 for d in sheet.column_dimensions.values())
        assert 0.9 <= sheet.column_dimensions["A"].width <= 1.8
finally:
    book.close()

blank = extract_comparison(source, "2", [], [])
assert not blank["raw_table_cells"]
assert any(a["Status"] == "OCR_REQUIRED" for a in blank["audit_rows"])
assert sum(a["Status"] == "NO_TABLE_FOUND" for a in blank["audit_rows"]) == 2

original = pymupdf.Page.find_tables
def broken(self, *args, **kwargs):
    if self.number == 0:
        raise RuntimeError("Deliberate page failure")
    return original(self, *args, **kwargs)
pymupdf.Page.find_tables = broken
failed = extract_comparison(source, "1-2", [], [])
assert sum(a["Status"] == "ERROR" for a in failed["audit_rows"]) == 2
assert any(a["Scope"] == "Page 2" and a["Status"] == "NO_TABLE_FOUND" for a in failed["audit_rows"])
''', str(tmp_path)], capture_output=True, text=True, timeout=180)
    assert completed.returncode == 0, completed.stdout + completed.stderr
