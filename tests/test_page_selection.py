from dataclasses import replace

import pytest

from financial_statement_extract.page_selection import (
    MANUAL_REVIEW_LIMIT, build_page_plan, resolve_page_plan, strict_page_numbers,
)
from models import PageSelectionReviewRequired


def text_row(page, text, **extra):
    return {"source_page": page, "line_no": 1, "raw_text": text, **extra}


@pytest.mark.parametrize("spec", ["0", "21", "3-2", "1-99999999999", "1,", "no", "1--2"])
def test_invalid_page_ranges_fail_clearly(spec):
    with pytest.raises(ValueError):
        strict_page_numbers(spec, 20)


def test_strict_selection_deduplicates_and_sorts():
    assert strict_page_numbers("4, 2-4,1", 4) == [1, 2, 3, 4]
    assert strict_page_numbers("all", 3) == [1, 2, 3]


def test_plan_keeps_schedules_titles_scans_and_uncertain_pages():
    title = "Consolidated Schedule of Investments"
    rows = [
        text_row(1, title), text_row(2, "Company A 100 200"),
        text_row(3, "3"), text_row(4, "", page_status="OCR_REQUIRED"),
        text_row(5, "Notes to Financial Statements"), text_row(6, "Mix"),
        text_row(7, "100\n200"), text_row(8, "20"),
    ]
    plan = build_page_plan("fund.pdf", rows, list(range(1, 10)), "manual")
    assert plan.include_investment_schedules
    assert plan.pages[0].source_title == title
    assert plan.pages[0].statement_type == "ScheduleOfInvestments"
    assert plan.pages[0].role == "title"
    assert plan.pages[1].role == "unknown"
    assert plan.pages[2].role == "blank"
    assert plan.pages[3].role == "unknown"
    assert plan.pages[4].role == "supporting"
    assert plan.suggested_pages == (1, 2, 4, 5, 6, 7, 8, 9)
    assert resolve_page_plan(plan, "exact").selected_pages == tuple(range(1, 10))
    assert resolve_page_plan(plan, "suggested").selected_pages == plan.suggested_pages
    assert plan.to_dict()["pages"][0]["source_title"] == title


def test_disjoint_pages_do_not_inherit_statement_context():
    rows = [text_row(1, "Balance Sheets"), text_row(8, "Uncertain 100 200")]
    plan = build_page_plan("filing.pdf", rows, [1, 8], "manual")
    assert plan.pages[1].statement_type == ""


def test_manual_review_warning_starts_above_fifty_pages():
    at_limit = build_page_plan("filing.pdf", [], list(range(1, MANUAL_REVIEW_LIMIT + 1)), "manual")
    over_limit = build_page_plan("filing.pdf", [], list(range(1, MANUAL_REVIEW_LIMIT + 2)), "manual")
    assert not at_limit.review_required
    assert over_limit.review_required


def test_large_review_requires_explicit_choice_and_never_truncates_schedule():
    requested = list(range(1, MANUAL_REVIEW_LIMIT + 2))
    plan = build_page_plan("fund.pdf", [text_row(1, "Schedule of Investments")], requested, "manual")
    with pytest.raises(PageSelectionReviewRequired) as error:
        resolve_page_plan(plan, "review")
    assert error.value.plan is plan
    assert len(resolve_page_plan(plan, "suggested").selected_pages) == MANUAL_REVIEW_LIMIT + 1
    assert not resolve_page_plan(plan, "exact").review_required
    assert plan.review_required  # Resolving does not mutate the original plan.
    with pytest.raises(ValueError, match="Unknown page policy"):
        resolve_page_plan(plan, "silently_trim")


def test_auto_plan_exposes_missing_statements():
    from financial_statement_extract.detection import detect_statement_plan
    plan = detect_statement_plan(["Unclassified document"])
    assert any("Not all core" in warning for warning in plan.warnings)


def test_empty_suggestion_fails_clearly():
    plan = build_page_plan("fund.pdf", [text_row(1, "1")], [1], "manual")
    with pytest.raises(ValueError, match="No pages remain"):
        resolve_page_plan(plan, "suggested")


def test_pipeline_pauses_before_expensive_extraction(tmp_path, monkeypatch):
    import pipeline

    source = tmp_path / "filing.pdf"
    source.touch()
    monkeypatch.setattr(pipeline, "get_page_count", lambda path: 295)
    monkeypatch.setattr(pipeline, "extract_page_text_pdfplumber", lambda *a: ([], []))

    def forbidden(*args, **kwargs):
        pytest.fail("Table extraction or workbook generation happened before review")

    monkeypatch.setattr(pipeline, "extract_tables_camelot", forbidden)
    monkeypatch.setattr(pipeline, "extract_tables_pdfplumber", forbidden)
    monkeypatch.setattr(pipeline, "extract_tables_pdfplumber_experimental", lambda *args: ([], [], []))
    monkeypatch.setattr(pipeline, "write_extraction_workbook", forbidden)
    with pytest.raises(PageSelectionReviewRequired) as error:
        pipeline.extract_pdf_to_workbook(str(source), "1-295")
    assert len(error.value.plan.requested_pages) == 295
    assert not list(tmp_path.glob("*.xlsx"))


@pytest.mark.parametrize("policy, expected", [("exact", "1-13"), ("suggested", "1-12")])
def test_pipeline_sends_only_resolved_pages_to_tables(tmp_path, monkeypatch, policy, expected):
    import pipeline

    source = tmp_path / "filing.pdf"
    source.touch()
    monkeypatch.setattr(pipeline, "get_page_count", lambda path: 13)
    monkeypatch.setattr(pipeline, "get_pdf_document_type", lambda path: "")
    rows = [text_row(1, "Income Statements"), text_row(1, "2026 2025"),
            text_row(1, "Revenue 300 250"), text_row(1, "Net income 30 20"), text_row(13, "13")]
    monkeypatch.setattr(pipeline, "extract_page_text_pdfplumber", lambda *a: (rows, []))
    calls = []

    def tables(path, pages):
        calls.append(pages)
        return [], [], []

    monkeypatch.setattr(pipeline, "extract_tables_camelot", tables)
    monkeypatch.setattr(pipeline, "extract_tables_pdfplumber", tables)
    monkeypatch.setattr(pipeline, "extract_tables_pdfplumber_experimental", lambda *args: ([], [], []))
    result, output = pipeline.extract_pdf_to_workbook(str(source), "1-13", page_policy=policy)
    assert calls == [expected, expected]
    assert output.exists()
    assert result.metadata["pages_selected"] == expected
    assert result.metadata["statement_page_plan"] == result.page_plan.to_dict()
    assert result.page_plan.requested_pages == tuple(range(1, 14))


def test_cli_review_is_actionable_and_exact_policy_is_forwarded(monkeypatch, capsys):
    from financial_statement_extract import cli

    plan = build_page_plan("filing.pdf", [], list(range(1, 14)), "manual")
    calls = []

    def extract(path, **kwargs):
        calls.append(kwargs["page_policy"])
        if kwargs["page_policy"] == "review":
            raise PageSelectionReviewRequired(plan)
        return None, "output.xlsx"

    monkeypatch.setattr(cli, "extract_filing", extract)
    with pytest.raises(SystemExit) as error:
        cli.main(["filing.pdf", "--pages", "1-13"])
    assert error.value.code == 2
    assert "--page-policy exact" in capsys.readouterr().err
    assert cli.main(["filing.pdf", "--pages", "1-13", "--page-policy", "exact"]) == 0
    assert calls == ["review", "exact"]


def test_controller_delivers_review_then_accepts_explicit_policy(tmp_path):
    from financial_statement_extract.ui.controller import ExtractionController
    from financial_statement_extract.ui.state import WorkspaceState

    plan = build_page_plan("filing.pdf", [], list(range(1, 14)), "manual")

    def runner(*args, page_policy="review"):
        if page_policy == "review":
            raise PageSelectionReviewRequired(plan)
        assert page_policy == "exact"
        return None, tmp_path / "output.xlsx"

    controller = ExtractionController(runner)
    request = WorkspaceState(input_path=str(tmp_path / "filing.pdf"), pages="1-13").to_request()
    controller.start(request)
    controller.worker.join(5)
    assert controller.work_queue.get_nowait() == ("page_review", plan, request)
    controller.start(replace(request, page_policy="exact"))
    controller.worker.join(5)
    assert controller.work_queue.get_nowait()[0] == "pdf_success"


def test_real_pdf_text_and_table_engines_complete_with_page_plan(tmp_path):
    """Minimal PDF fixture exercises the real engines without another dependency."""
    import subprocess
    import sys

    lines = ["Example Company", "Income Statements", "2026 2025",
             "Revenue 300 250", "Net income 30 20"]
    stream = ("BT /F1 12 Tf 50 740 Td 20 TL " +
              " T* ".join(f"({line}) Tj" for line in lines) + " ET").encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
    ]
    document = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(document))
        document.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    start = len(document)
    document.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode())
    document.extend(f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode())
    source = tmp_path / "real-engine-smoke.pdf"
    source.write_bytes(document)
    # Isolate native PDF engine execution from later Tk initialization. On this
    # Windows runtime their shared-process order can cause Tcl file-open errors.
    completed = subprocess.run([sys.executable, "-c", """
import sys
from pipeline import extract_pdf_to_workbook
from financial_statement_extract.progress import ExtractionStage as Stage
from openpyxl import load_workbook
from pandas.testing import assert_frame_equal
events = []
result, output = extract_pdf_to_workbook(sys.argv[1], 'auto', progress=events.append)
stages = [event.stage for event in events]
assert stages[:2] == [Stage.VALIDATING, Stage.DETECTING_PAGES]
assert stages[2] is Stage.EXTRACTING_TABLES
assert stages[-3:] == [Stage.PARSING, Stage.AUDITING, Stage.WRITING]
assert all(s is Stage.EXTRACTING_TABLES for s in stages[2:-3])
assert output.exists()
assert result.experimental_audit_rows[0]['Check'] == 'PDFPlumber Experimental table extraction'
assert result.page_plan.selected_pages == (1,)
assert result.page_plan.pages[0].source_title == 'Income Statements'
frame = result.statements['IncomeStatement']
assert frame.loc[frame.RawItem == 'Revenue', '2026'].iloc[0] == 300
assert {row['Check'] for row in result.extraction_audit_rows} >= {
    'Page machine readability', 'PDFPlumber table extraction',
}
plain, plain_output = extract_pdf_to_workbook(sys.argv[1], 'auto')
for name in result.statements:
    assert_frame_equal(result.statements[name], plain.statements[name])
assert result.page_plan == plain.page_plan
assert result.statement_tables == plain.statement_tables
assert result.extraction_audit_rows == plain.extraction_audit_rows
assert result.financial_audit_rows == plain.financial_audit_rows
def content(path):
    book = load_workbook(path)
    try:
        return [(s.title, [(c.coordinate, c.value, c.number_format, c.data_type)
                          for row in s for c in row]) for s in book]
    finally:
        book.close()
assert content(output) == content(plain_output)
""", str(source)], capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    # A separate process exercises the actual GUI worker and Tk event loop with
    # the same valid PDF. Do not load native PDF engines into the test Tk runtime.
    gui = subprocess.run([
        sys.executable, "-m", "financial_statement_extract.ui.review", "--smoke",
        "--source", str(source), "--pages", "1", "--review-dir", str(tmp_path / "gui-review"),
    ], capture_output=True, text=True, timeout=60)
    assert gui.returncode == 0, gui.stdout + gui.stderr
    import json
    report = json.loads(gui.stdout.strip().splitlines()[-1])
    assert report["phase"] == "SUCCEEDED"
    assert report["statements"] == 1
    assert report["callback_errors"] == []
    assert report["pages"] == "1"
