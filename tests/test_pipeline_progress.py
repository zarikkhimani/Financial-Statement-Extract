"""Stage ordering and output-equivalence checks with small synthetic filings."""

from dataclasses import FrozenInstanceError

from openpyxl import load_workbook
from pandas.testing import assert_frame_equal
import pytest

import pipeline
from financial_statement_extract import extract_filing
from financial_statement_extract.progress import ExtractionStage as Stage, ProgressEvent, report
from models import PageSelectionReviewRequired


HTML = """<html><body><h2>Income Statements</h2><table>
<tr><th></th><th>2026</th><th>2025</th></tr>
<tr><td>Revenue</td><td>300</td><td>250</td></tr>
<tr><td>Cost of sales</td><td>180</td><td>150</td></tr>
<tr><td>Gross profit</td><td>120</td><td>100</td></tr>
<tr><td>Net income</td><td>30</td><td>20</td></tr>
</table></body></html>"""


def workbook_content(path):
    book = load_workbook(path)
    try:
        return [(sheet.title, [(cell.coordinate, cell.value, cell.number_format, cell.data_type)
                               for row in sheet for cell in row],
                 sorted(str(area) for area in sheet.merged_cells.ranges)) for sheet in book]
    finally:
        book.close()


def test_html_progress_reports_real_boundaries_and_preserves_output(tmp_path, monkeypatch):
    source = tmp_path / "sample.html"
    source.write_text(HTML, encoding="utf-8")
    events = []
    boundaries = [
        ("extract_html_filing", Stage.EXTRACTING_TABLES),
        ("parse_financial_statements", Stage.PARSING),
        ("run_financial_audits", Stage.AUDITING),
        ("write_extraction_workbook", Stage.WRITING),
    ]
    plain, plain_path = extract_filing(source, output_dir=tmp_path / "plain")
    for name, stage in boundaries:
        original = getattr(pipeline, name)

        def checked(*args, _original=original, _stage=stage, **kwargs):
            assert events[-1].stage is _stage
            return _original(*args, **kwargs)

        monkeypatch.setattr(pipeline, name, checked)
    reported, reported_path = extract_filing(source, output_dir=tmp_path / "reported", progress=events.append)
    assert [e.stage for e in events] == [Stage.VALIDATING, Stage.EXTRACTING_TABLES,
                                        Stage.PARSING, Stage.AUDITING, Stage.WRITING]
    assert workbook_content(plain_path) == workbook_content(reported_path)
    assert plain.statements.keys() == reported.statements.keys()
    for name in plain.statements:
        assert_frame_equal(plain.statements[name], reported.statements[name])
    for field in ("raw_text_rows", "raw_table_cells", "normalized_table_cells", "extraction_audit_rows",
                  "parsed_cells", "financial_audit_rows", "unmapped_rows", "statement_tables"):
        assert getattr(plain, field) == getattr(reported, field), field
    assert {k: v for k, v in plain.metadata.items() if k != "generated_at"} == {
        k: v for k, v in reported.metadata.items() if k != "generated_at"}


def test_preflight_review_stops_progress_before_expensive_table_work(tmp_path, monkeypatch):
    source = tmp_path / "review.pdf"
    source.touch()
    events = []
    review_page_count = 51
    monkeypatch.setattr(pipeline, "get_page_count", lambda _path: review_page_count)
    monkeypatch.setattr(pipeline, "extract_page_text_pdfplumber", lambda *_args: ([], []))
    monkeypatch.setattr(pipeline, "extract_tables_pdfplumber", lambda *_args: pytest.fail("tables ran before approval"))
    with pytest.raises(PageSelectionReviewRequired):
        pipeline.extract_pdf_to_workbook(str(source), f"1-{review_page_count}", progress=events.append)
    assert [event.stage for event in events] == [Stage.VALIDATING, Stage.DETECTING_PAGES]
    assert not list(tmp_path.glob("*.xlsx"))


@pytest.mark.parametrize("failing_function,stage", [
    ("parse_financial_statements", Stage.PARSING),
    ("run_financial_audits", Stage.AUDITING),
    ("write_extraction_workbook", Stage.WRITING),
])
def test_failure_does_not_emit_later_stages(tmp_path, monkeypatch, failing_function, stage):
    source = tmp_path / "sample.html"
    source.write_text(HTML, encoding="utf-8")
    events = []

    def fail(*_args, **_kwargs):
        raise PermissionError("Synthetic failure")

    monkeypatch.setattr(pipeline, failing_function, fail)
    with pytest.raises(PermissionError, match="Synthetic failure"):
        extract_filing(source, progress=events.append)
    assert events[-1].stage is stage
    assert not list(tmp_path.glob("*.xlsx"))


def test_missing_source_and_reporter_errors_fail_clearly(tmp_path):
    events = []
    with pytest.raises(FileNotFoundError):
        extract_filing(tmp_path / "missing.pdf", progress=events.append)
    assert [event.stage for event in events] == [Stage.VALIDATING]

    def broken_reporter(_event):
        raise RuntimeError("Reporter failed")

    with pytest.raises(RuntimeError, match="Reporter failed"):
        extract_filing(tmp_path / "missing.pdf", progress=broken_reporter)
    event = ProgressEvent(Stage.VALIDATING)
    with pytest.raises(FrozenInstanceError):
        event.detail = "changed"
    report(None, Stage.WRITING)  # Reporting is truly optional.
