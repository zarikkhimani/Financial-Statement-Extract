from pathlib import Path

import pandas as pd

from pipeline import build_output_filename


def statement(company="Acme Corp.", periods=None):
    frame = pd.DataFrame({"Raw Item": ["Revenue"]})
    frame.attrs["company_name"] = company
    frame.attrs["period_labels"] = ["2026", "2025"] if periods is None else periods
    return {"IncomeStatement": frame}


def test_public_10k_name_uses_fiscal_year_document_type_and_client():
    name = build_output_filename("Acme 2026 10-K.pdf", {}, statement())
    assert name == "FY26_10K_Acme_Corp.xlsx"


def test_compact_public_filing_name_and_manual_overrides_are_supported():
    name = build_output_filename(
        "lmt10k.pdf",
        {"year": "2024", "client_name": "Lockheed Martin Corporation"},
        {},
    )
    assert name == "FY24_10K_Lockheed_Martin_Corporation.xlsx"


def test_10q_name_includes_quarter_when_available():
    name = build_output_filename("Acme_Q2_10-Q.pdf", {}, statement())
    assert name == "FY26_Q2_10Q_Acme_Corp.xlsx"


def test_detected_document_type_overrides_a_misleading_source_filename():
    name = build_output_filename(
        "2-10k.pdf",
        {"document_type": "10Q"},
        statement("Comerica Incorporated", ["2025", "2024"]),
    )
    assert name == "FY25_10Q_Comerica_Incorporated.xlsx"


def test_private_audited_financials_use_private_document_name():
    name = build_output_filename(
        "Fund statements.pdf",
        {"audit_status": "Audited"},
        statement("Fund Alpha, L.P.", ["December 31, 2025", "December 31, 2024"]),
    )
    assert name == "FY25_AuditedFinancials_Fund_Alpha_L_P.xlsx"


def test_simplified_names_are_used_when_document_type_is_missing():
    assert build_output_filename("document.pdf", {}, statement("Client", ["2025"])) == "FY25_Client.xlsx"
    assert build_output_filename("document.pdf", {}, statement("Client", [])) == "Client_Financials.xlsx"


def test_source_year_and_document_type_form_a_simplified_public_name():
    assert build_output_filename("2025_10-K.pdf", {}, {}) == "FY25_10K.xlsx"

def test_final_failsafe_name_is_stable():
    assert build_output_filename(Path("document.pdf"), {}, {}) == "Extracted_Financials.xlsx"
