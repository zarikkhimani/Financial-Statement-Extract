"""Adversarial regression controls, independent of the production extractor."""
from copy import deepcopy
from pathlib import Path
import shutil

from openpyxl import load_workbook
import pytest
import xlsxwriter

from scripts import regression_gate as gate


RUN = "core/sample-1"
FAILURE = "full/sample-1"


def make_book(path):
    with xlsxwriter.Workbook(path) as book:
        sheet = book.add_worksheet("Income Statement")
        sheet.set_column(0, 1, 1)
        amount = book.add_format({"num_format": "#,##0;(#,##0)"})
        for address, value in {
            "C4": "Sample BDC", "C5": "Consolidated Statements of Operations",
            "C6": "Amounts in thousands", "D8": "2025", "E8": "2024",
            "C9": "Interest income", "C10": "Expenses", "C11": "Net income",
        }.items():
            sheet.write(address, value)
        for address, value in {"D9": 1250, "E9": 900, "D10": -250, "E10": -200,
                               "D11": 1000, "E11": 700}.items():
            sheet.write(address, value, amount)
        raw = book.add_worksheet("Raw Table Data")
        raw.set_column(0, 1, 1)
        raw.write("C4", "Unreviewed diagnostic data")
        raw.write("D5", 1250)


def record(folder, value, name="result.json"):
    gate.write_json(folder / name, value)


def reseal(baseline):
    artifacts = [{"path": str(p.relative_to(baseline)).replace("\\", "/"), "sha256": gate.sha(p)}
                 for p in sorted(baseline.rglob("*")) if p.is_file() and p.name != "manifest.json"]
    record(baseline, {"artifacts": artifacts}, "manifest.json")
    return gate.sha(baseline / "manifest.json")


@pytest.fixture
def corpus(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"Synthetic source identity for gate tests, not a parsed PDF")
    baseline = tmp_path / "baseline"
    directory = baseline / RUN
    directory.mkdir(parents=True)
    make_book(directory / "workbook.xlsx")
    job = {"job_id": "sample-1", "filing_id": "sample", "input_sha256": gate.sha(source),
           "source_path": str(source), "entity": "Sample BDC", "filing_type": "10-K",
           "reporting_period": "December 31, 2025", "core_pages": "2-3", "full_pages": "2-5"}
    result = {"job": job, "scope": "core", "status": "completed", "pages": "2-3",
              "selected_pages": [2, 3], "workbook": str(directory / "workbook.xlsx"),
              "workbook_sha256": gate.sha(directory / "workbook.xlsx"), "process_exit_code": 0}
    record(directory, result)
    payload = {"page_plan": {"selected_pages": [2, 3]}, "statements": {"IncomeStatement": {
        "attrs": {"company_name": "Sample BDC", "statement_title": "Consolidated Statements of Operations",
                  "period_labels": ["2025", "2024"], "unit_label": "thousands", "scale_factor": 1000,
                  "currency": "USD", "unit_exceptions": [], "raw_unit_note": "Amounts in thousands",
                  "source_tables": [{"source_page": 2}, {"source_page": 3}]}, "rows": []}}}
    record(directory, payload, "extraction.json.gz")
    failed = baseline / FAILURE
    failed.mkdir(parents=True)
    failure_result = {"job": job, "scope": "full", "status": "failed", "pages": "2-5",
                      "error_type": "ValueError", "error": "Known overlapping tables", "process_exit_code": 1}
    record(failed, failure_result)
    record(baseline, {"summary": {"executed_runs": 2, "input_exceptions": [{"status": "wrong_document"}]},
                      "runs": [{"job": job, "scope": "core", "run": result},
                               {"job": job, "scope": "full", "run": failure_result}]}, "baseline-index.json")
    record(baseline, {"cases": [{"case": "existing missing row", "status": "known_defect"}]}, "reviewed-cases.json")
    sealed_sha = reseal(baseline)
    candidate = tmp_path / "candidate"
    shutil.copytree(baseline, candidate)
    result["workbook"] = str(candidate / RUN / "workbook.xlsx")
    record(candidate / RUN, result)
    return baseline, candidate, sealed_sha


def compare(corpus, **kwargs):
    baseline, candidate, sealed_sha = corpus
    return gate.compare_collection(baseline, candidate, expected_sha=sealed_sha, **kwargs)


def mutate_book(corpus, mutation, *, update_hash=True):
    directory = corpus[1] / RUN
    path = directory / "workbook.xlsx"
    book = load_workbook(path)
    mutation(book)
    book.save(path)
    book.close()
    if update_hash:
        result = gate.read_json(directory / "result.json")
        result["workbook_sha256"] = gate.sha(path)
        record(directory, result)


def change_cell(address, value):
    def mutate(book):
        book.worksheets[0][address] = value
    return mutate


def events(report):
    return [item for run in report["runs"] for item in run["events"]]


def test_complete_collection_keeps_known_defects_and_failures_visible(corpus):
    result = compare(corpus)
    assert result["exit_code"] == 0
    assert result["scope"] == "entire_collection"
    assert result["expected_runs"] == 2
    assert result["known_failures_unchanged"] == 1
    assert result["baseline_known_cases"][0]["status"] == "known_defect"
    assert result["input_exceptions"] == [{"status": "wrong_document"}]
    assert result["accuracy_certified"] is False


@pytest.mark.parametrize("address,value", [
    ("D9", 1251), ("D9", 125.0), ("D10", 250), ("D9", "1,250"),
    ("D9", None), ("D9", 0), ("D9", "-"), ("D9", "=1250"),
    ("D8", "2023"), ("C6", "Amounts in millions"), ("C9", "Dividend income"),
    ("D9", 1250.000001), ("C9", "Interest income (unaudited 2023)"),
])
def test_numeric_sign_decimal_period_units_and_label_changes_block(corpus, address, value):
    mutate_book(corpus, change_cell(address, value))
    result = compare(corpus)
    assert result["exit_code"] == 1
    assert result["event_counts"]["block"] >= 1


@pytest.mark.parametrize("mutation", [
    lambda b: b.worksheets[0].delete_rows(10),
    lambda b: b.worksheets[0].append([None, None, "Expenses", -250, -200]),
    lambda b: b.worksheets[0].move_range("D9:D11", cols=2),
    lambda b: setattr(b.worksheets[0]["D9"], "number_format", "0%"),
])
def test_rows_duplicates_columns_and_display_scaling_block(corpus, mutation):
    mutate_book(corpus, mutation)
    assert compare(corpus)["exit_code"] == 1


@pytest.mark.parametrize("mutation", [
    change_cell("C5", "Consolidated statement of operations typo"),
    change_cell("C9", " INTEREST   INCOME "),
    lambda b: setattr(b.worksheets[0], "title", "Statement 1"),
    lambda b: b.worksheets[0].insert_rows(10),
])
def test_cosmetics_do_not_fail_numeric_gate(corpus, mutation):
    mutate_book(corpus, mutation)
    assert compare(corpus)["exit_code"] == 0


@pytest.mark.parametrize("field,value", [
    ("period_labels", ["2024", "2025"]), ("scale_factor", 1000000), ("currency", "EUR"),
    ("unit_exceptions", ["shares in thousands"]), ("source_tables", [{"source_page": 1}]),
])
def test_context_metadata_changes_block_even_when_workbook_is_unchanged(corpus, field, value):
    directory = corpus[1] / RUN
    payload = gate.read_json(directory / "extraction.json.gz")
    payload["statements"]["IncomeStatement"]["attrs"][field] = value
    record(directory, payload, "extraction.json.gz")
    result = compare(corpus)
    assert result["exit_code"] == 1
    assert "PERIOD_UNIT_OR_SOURCE_CONTEXT_CHANGED" in {e["code"] for e in events(result)}


@pytest.mark.parametrize("mutation", [
    lambda b: setattr(b.worksheets[1], "freeze_panes", "D9"),
    lambda b: b.worksheets[1].merge_cells("D7:E7"),
    lambda b: setattr(b.worksheets[1].row_dimensions[8], "hidden", True),
    lambda b: setattr(b.worksheets[1].column_dimensions["D"], "hidden", True),
    lambda b: setattr(b.worksheets[1].column_dimensions["A"], "width", 3),
    lambda b: setattr(b.worksheets[1]["A1"], "value", "unexpected margin data"),
    lambda b: setattr(b.worksheets[1]["D8"], "value", "#REF!"),
    lambda b: setattr(b.worksheets[1].sheet_format, "zeroHeight", True),
])
def test_workbook_rules_apply_to_auxiliary_sheets_and_cannot_be_waived(corpus, mutation):
    mutate_book(corpus, mutation)
    result = compare(corpus)
    assert result["exit_code"] == 2
    assert "WORKBOOK_RULE_VIOLATION" in {e["code"] for e in events(result)}


def test_saved_excel_is_read_instead_of_stale_cached_cells(corpus):
    record(corpus[1] / RUN, {"old": 1250}, "workbook-cells.json.gz")
    mutate_book(corpus, change_cell("D9", 1))
    result = compare(corpus)
    assert result["exit_code"] == 1
    assert any("1250" in str(e["before"]) and "'1'" in str(e["after"]) for e in events(result))


def test_stale_workbook_hash_is_invalid_evidence(corpus):
    mutate_book(corpus, change_cell("D9", 1), update_hash=False)
    assert compare(corpus)["exit_code"] == 2


def test_missing_filing_cannot_hide_behind_aggregate_results(corpus):
    (corpus[1] / FAILURE / "result.json").unlink()
    result = compare(corpus)
    assert result["expected_runs"] == 2
    assert result["exit_code"] == 2


def test_explicit_subset_is_labelled_incomplete_collection(corpus):
    (corpus[1] / FAILURE / "result.json").unlink()
    result = compare(corpus, selected=[RUN])
    assert result["exit_code"] == 0
    assert result["scope"] == "selected_runs"
    assert result["unselected_runs"] == 1


@pytest.mark.parametrize("key,value", [("entity", "Other BDC"), ("input_sha256", "wrong"), ("reporting_period", "2024")])
def test_identity_mismatch_is_invalid(corpus, key, value):
    directory = corpus[1] / RUN
    result = gate.read_json(directory / "result.json")
    result["job"][key] = value
    record(directory, result)
    assert compare(corpus)["exit_code"] == 2


def test_changed_actual_source_is_invalid(corpus):
    result = gate.read_json(corpus[1] / RUN / "result.json")
    Path(result["job"]["source_path"]).write_bytes(b"different source")
    assert compare(corpus)["exit_code"] == 2


def test_new_failure_and_changed_known_failure_block(corpus):
    directory = corpus[1] / RUN
    result = gate.read_json(directory / "result.json")
    result.update(status="failed", error_type="ValueError", error="New failure", process_exit_code=1)
    record(directory, result)
    assert compare(corpus)["exit_code"] == 1
    failed = gate.read_json(corpus[1] / FAILURE / "result.json")
    failed["error"] = "Different problem"
    record(corpus[1] / FAILURE, failed)
    assert compare(corpus)["event_counts"]["block"] == 2


def test_known_failure_on_different_pages_is_not_unchanged(corpus):
    failed = gate.read_json(corpus[1] / FAILURE / "result.json")
    failed["pages"] = "2"
    record(corpus[1] / FAILURE, failed)
    assert compare(corpus)["exit_code"] == 1


def test_recovery_requires_source_review(corpus):
    directory = corpus[1] / FAILURE
    shutil.copy2(corpus[1] / RUN / "workbook.xlsx", directory / "workbook.xlsx")
    shutil.copy2(corpus[1] / RUN / "extraction.json.gz", directory / "extraction.json.gz")
    result = gate.read_json(corpus[1] / RUN / "result.json")
    result.update(scope="full", pages="2-5", workbook=str(directory / "workbook.xlsx"))
    record(directory, result)
    report = compare(corpus)
    assert report["exit_code"] == 1
    assert "RECOVERED_RUN_REQUIRES_SOURCE_REVIEW" in {e["code"] for e in events(report)}


def test_approval_is_bound_to_exact_values_and_does_not_waive_future_changes(corpus):
    mutate_book(corpus, change_cell("D9", 1251))
    first = compare(corpus)
    issue = next(e for e in events(first) if e["severity"] == "block")
    decisions = {"baseline_manifest_sha256": corpus[2], "accepted_changes": [
        {"issue_id": issue["issue_id"], "reason": "Corrected amount", "source_evidence": "Synthetic PDF page 2, interest income 2025 = 1,251"}]}
    accepted = compare(corpus, decisions=decisions)
    assert accepted["exit_code"] == 0
    assert accepted["event_counts"]["reviewed_change"] == 1
    mutate_book(corpus, change_cell("D9", 1252))
    with pytest.raises(gate.EvidenceError, match="stale"):
        compare(corpus, decisions=decisions)


@pytest.mark.parametrize("bad_decision", [
    {"baseline_manifest_sha256": "wrong", "accepted_changes": []},
    {"accepted_changes": [{"issue_id": "blanket waiver", "reason": "", "source_evidence": ""}]},
    {"accepted_changes": [{"issue_id": "unknown", "reason": "reason", "source_evidence": "page 2"}]},
])
def test_invalid_review_decisions_are_rejected(corpus, bad_decision):
    decision = {"baseline_manifest_sha256": corpus[2], **bad_decision}
    with pytest.raises(gate.EvidenceError):
        compare(corpus, decisions=decision)


def test_changed_baseline_is_rejected_before_comparing(corpus):
    (corpus[0] / RUN / "workbook.xlsx").write_bytes(b"corrupt")
    with pytest.raises(gate.EvidenceError, match="artifact changed"):
        compare(corpus)


def test_manifest_pin_cannot_be_bypassed_by_resealing(corpus):
    record(corpus[0], {"cases": []}, "reviewed-cases.json")
    reseal(corpus[0])
    with pytest.raises(gate.EvidenceError, match="pinned SHA"):
        compare(corpus)


def test_external_baseline_workbook_path_rejected_for_candidate(corpus):
    directory = corpus[1] / RUN
    result = gate.read_json(directory / "result.json")
    result["workbook"] = str(corpus[0] / RUN / "workbook.xlsx")
    record(directory, result)
    assert compare(corpus)["exit_code"] == 2


def test_cli_reports_and_never_overwrites_existing_reports(corpus, tmp_path):
    target = tmp_path / "report"
    args = ["compare", "--baseline", str(corpus[0]), "--baseline-sha256", corpus[2],
            "--candidate", str(corpus[1]), "--report-dir", str(target)]
    assert gate.main(args) == 0
    assert gate.read_json(target / "comparison.json")["scope"] == "entire_collection"
    first = gate.sha(target / "comparison.json")
    assert gate.main(args) == 2
    assert gate.sha(target / "comparison.json") == first


def test_statement_removed_from_metadata_blocks(corpus):
    directory = corpus[1] / RUN
    payload = gate.read_json(directory / "extraction.json.gz")
    payload["statements"]["BalanceSheet"] = payload["statements"].pop("IncomeStatement")
    record(directory, payload, "extraction.json.gz")
    assert compare(corpus)["exit_code"] == 1


def test_identical_duplicate_row_removed_is_detected(corpus):
    before = [{"row": 9, "label": "Interest", "key": ((3, "interest"),), "critical": True,
               "cells": [[3, "text", "interest", ""], [4, "number", "1", "General"]]}] * 2
    after = deepcopy(before[:1])
    found = gate.compare_rows(RUN, "IncomeStatement", before, after)
    assert len(found) == 1 and found[0]["severity"] == "block"


def test_blank_zero_and_dash_are_distinct():
    from openpyxl import Workbook
    book = Workbook()
    sheet = book.active
    rows = []
    for row, value in enumerate([None, 0, "-"], 1):
        sheet.cell(row, 3, "A balance")
        sheet.cell(row, 4, value)
        rows.append(gate.canonical_row(sheet[row]))
    assert gate.compare_rows(RUN, "BalanceSheet", [rows[0]], [rows[1]])[0]["severity"] == "block"
    assert gate.compare_rows(RUN, "BalanceSheet", [rows[1]], [rows[2]])[0]["severity"] == "block"
    book.close()


def test_split_parenthesis_sign_change_is_not_ignored_as_punctuation():
    from openpyxl import Workbook
    book = Workbook()
    sheet = book.active
    for row, sign in [(1, "("), (2, ")")]:
        sheet.cell(row, 3, "Split amount")
        sheet.cell(row, 4, sign)
        sheet.cell(row, 5, 67502)
    before, after = gate.canonical_row(sheet[1]), gate.canonical_row(sheet[2])
    assert gate.compare_rows(RUN, "Equity", [before], [after])[0]["severity"] == "block"
    book.close()


def test_dash_typography_does_not_change_missing_value_semantics():
    from openpyxl import Workbook
    book = Workbook()
    sheet = book.active
    for row, value in enumerate(["-", "\u2013", "\u2014"], 1):
        sheet.cell(row, 3, "A balance")
        sheet.cell(row, 4, value)
    rows = [gate.canonical_row(sheet[row]) for row in range(1, 4)]
    assert not gate.compare_rows(RUN, "BalanceSheet", [rows[0]], [rows[1]])
    assert not gate.compare_rows(RUN, "BalanceSheet", [rows[0]], [rows[2]])
    book.close()


def test_unexpected_run_prevents_collection_pass(corpus):
    extra = corpus[1] / "core/unexpected"
    extra.mkdir()
    record(extra, {})
    result = compare(corpus)
    assert result["exit_code"] == 2
    assert "UNEXPECTED_RUNS" in {e["code"] for e in events(result)}


def test_rule_violation_cannot_be_approved(corpus):
    mutate_book(corpus, lambda b: setattr(b.worksheets[0], "freeze_panes", "D9"))
    issue = next(e for e in events(compare(corpus)) if e["severity"] == "error")
    decisions = {"baseline_manifest_sha256": corpus[2], "accepted_changes": [
        {"issue_id": issue["issue_id"], "reason": "Approve everything", "source_evidence": "page 2"}]}
    with pytest.raises(gate.EvidenceError, match="non-waivable"):
        compare(corpus, decisions=decisions)


def test_invalid_workbook_archive_returns_evidence_error(corpus):
    directory = corpus[1] / RUN
    workbook = directory / "workbook.xlsx"
    workbook.write_bytes(b"not a workbook")
    result = gate.read_json(directory / "result.json")
    result["workbook_sha256"] = gate.sha(workbook)
    record(directory, result)
    assert compare(corpus)["exit_code"] == 2


def test_capture_never_overwrites_existing_run_or_baseline(corpus):
    with pytest.raises(FileExistsError):
        gate.capture(corpus[0], RUN, corpus[1], corpus[2])
    with pytest.raises(gate.EvidenceError, match="separate"):
        gate.capture(corpus[0], RUN, corpus[0], corpus[2])
