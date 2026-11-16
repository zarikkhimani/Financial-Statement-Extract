from copy import deepcopy
from types import SimpleNamespace

import pytest

from financial_statement_extract.income_periods import prepare_income_parser_rows, resolve_income_periods
from income_geometry_case import CASE, PFX_CASE
from income_period_cases import CASES
from statements import parse_financial_statements


def fake_pdf(monkeypatch, data):
    class Page:
        width = data["width"]

        def extract_text_lines(self):
            return deepcopy(data["lines"])

        def crop(self, bounds):
            words = data["header_words"] if bounds[1] == data["lines"][0]["top"] else data["row_words"]
            return SimpleNamespace(extract_words=lambda: deepcopy(words))

    class PDF:
        pages = [Page()] * data["source_page"]

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    monkeypatch.setattr("pdfplumber.open", lambda _: PDF())


def test_offset_dashes_keep_original_period_positions_and_next_row(monkeypatch):
    data = deepcopy(CASE)
    fake_pdf(monkeypatch, data)
    original = deepcopy(data["input_rows"])
    rows = prepare_income_parser_rows("fixture.pdf", original)
    assert original == data["input_rows"]
    frame = parse_financial_statements(rows)[0]["IncomeStatement"]
    values = frame.set_index("RawItem")[frame.attrs["period_labels"]]
    first = values.loc["Interest income from non-controlled, affiliated investments"]
    assert first.iloc[0] == 3086 and first.iloc[2] == 6080
    assert first.isna().tolist() == [False, True, False, True]
    assert values.loc["Payment-in-kind interest income from non-controlled, non- affiliated investments"].tolist() == [
        2501, 2063, 6774, 2369]
    evidence = frame.attrs["period_row_evidence"][0]
    assert evidence["original_text"] == [r["raw_text"] for r in data["input_rows"][-4:-2]]
    assert evidence["source_lines"] == [12, 13]


def test_partial_row_preserves_source_blank_and_following_row(monkeypatch):
    data = deepcopy(PFX_CASE)
    fake_pdf(monkeypatch, data)
    original = deepcopy(data["input_rows"])
    rows = prepare_income_parser_rows("fixture.pdf", original)
    assert original == data["input_rows"]
    recovered = next(r for r in rows if r.get("income_value_tokens"))
    assert recovered["income_value_tokens"] == ["582,491", "", "1,884,957", "-"]
    frame = parse_financial_statements(rows)[0]["IncomeStatement"]
    values = frame.set_index("RawItem")[frame.attrs["period_labels"]]
    for label, expected in [("Cash", [582491, 1884957]), ("Payment in-kind", [314673, 764594])]:
        row = values.loc[label]
        assert row.iloc[[0, 2]].tolist() == expected
        assert row.isna().tolist() == [False, True, False, True]


def test_adjacent_currency_keeps_distinct_source_loss_rows():
    text = ("Consolidated Statements of Operations\n"
            "December 31, 2025December 31, 2024 December 31, 2023\n"
            "Net realized loss on controlled investments $ (1,132,576)$ \u2014 $ \u2014\n"
            "Net realized loss on non-controlled, affiliated investments (6,314,327) \u2014 \u2014")
    original = [{"source_page": 193, "line_no": i, "raw_text": line}
                for i, line in enumerate(text.splitlines(), 1)]
    rows = prepare_income_parser_rows("no_pdf_geometry_needed.pdf", deepcopy(original))
    assert [r["raw_text"] for r in rows] == [r["raw_text"] for r in original]
    frame = parse_financial_statements(rows)[0]["IncomeStatement"]
    assert frame["RawItem"].tolist() == ["Net realized loss on controlled investments",
                                       "Net realized loss on non-controlled, affiliated investments"]
    values = frame[frame.attrs["period_labels"]]
    assert values.iloc[:, 0].tolist() == [-1132576, -6314327]
    assert values.iloc[:, 1:].isna().all().all()


@pytest.mark.parametrize("fault", ["duplicate_column", "missing_dash", "separate_physical_row", "missing_year"])
def test_ambiguous_dash_geometry_stays_explicit(monkeypatch, fault):
    data = deepcopy(CASE)
    if fault == "duplicate_column":
        for word in data["row_words"]:
            if word["text"] == "6,080":
                word["x0"], word["x1"] = 340, 350
    elif fault == "missing_dash":
        data["row_words"] = [w for w in data["row_words"] if w["text"] != "-"]
    elif fault == "separate_physical_row":
        data["lines"][-1]["top"] += 30
        data["lines"][-1]["bottom"] += 30
    else:
        data["header_words"].pop()
    fake_pdf(monkeypatch, data)
    rows = prepare_income_parser_rows("fixture.pdf", data["input_rows"])
    assert [r["raw_text"] for r in rows] == [r["raw_text"] for r in data["input_rows"]]
    assert any(r.get("income_row_warning") for r in rows)
    _, _, issues, _ = parse_financial_statements(rows)
    assert any(i["Check"] == "Period-count alignment" and "Incomplete source row" in i["Detail"] for i in issues)


@pytest.mark.parametrize("fault", ["missing", "wrong_year", "ambiguous_anchor"])
def test_transition_periods_require_valid_source_positions(fault):
    rows = deepcopy(next(c for c in CASES if c["id"] == "icmb")["input_rows"])
    words = rows[1]["income_header_words"]
    if fault == "missing":
        rows[1].pop("income_header_words")
    elif fault == "wrong_year":
        next(w for w in words if w["text"] == "2025")["text"] = "2022"
    else:
        for word in words:
            if word["text"] == "Six":
                word["x0"], word["x1"] = 450, 460
    layout = resolve_income_periods(rows)
    assert layout.warning
    assert layout.labels == ["2025", "2024", "2023"]


def test_body_years_cannot_complete_an_ambiguous_header():
    rows = [{"raw_text": t} for t in ["Consolidated Statements of Operations", "Three Months Six Months",
            "June 30, June 30,", "2026 2025", "Income from 2026 notes 100 90 200 180"]]
    result = resolve_income_periods(rows)
    assert len(result.labels) <= 2
    assert all("notes" not in label for label in result.labels)


def test_mixed_wrapped_month_days_require_review():
    rows = [{"raw_text": t} for t in ["Consolidated Statements of Operations",
            "Three Months Ended January Six Months Ended March 31,", "30, 2026 2025 2026 2025",
            "Income 10 20 30 40"]]
    assert resolve_income_periods(rows).warning


@pytest.mark.parametrize("heading, body", [
    ("CONSOLIDATED STATEMENTS OF CHANGES IN NET ASSETS AND TEMPORARY EQUITY",
     "Balance as of December 31, 2025 500 600\nNet realized losses (83,042) (83,042)"),
    # TSLX June 2026 PDF pages 7-8, SHA256 908833123331ac6cfb93958f1ae6b16a559301fa807563c57a8209aea59853d7.
    ("Consolidated Schedule of Investments as of June 30, 2026",
     "BCTO Ignition Purchaser, Inc. 56,734 57,437 3.7%\nCrewline Buyer, Inc. 57,248 56,296 3.6%"),
])
def test_mixed_unclassified_statement_keeps_existing_numbers_with_warning(heading, body):
    text = ("Consolidated Statements of Operations\nThree Months Ended June 30, Six Months Ended June 30,\n"
            "2026 2025 2026 2025\nNet income 10 20 30 40\n" + heading +
            "\n" + body)
    frames, _, issues, _ = parse_financial_statements(text)
    old = parse_financial_statements(text, recover_income_periods=False)[0]["IncomeStatement"]
    assert frames["IncomeStatement"].equals(old)
    assert frames["IncomeStatement"].attrs == old.attrs
    assert any(i["Check"] == "Statement period detection" and "another financial statement title" in i["Detail"]
               for i in issues)
