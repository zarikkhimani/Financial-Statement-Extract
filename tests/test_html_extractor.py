from openpyxl import load_workbook

from html_extractor import extract_html_filing
from pipeline import extract_filing_to_workbook


SEC_HTML = """<!doctype html>
<html>
<head><title>acme-20261231</title><script>ignore me</script></head>
<body>
<ix:hidden>
  <ix:nonNumeric name="dei:EntityRegistrantName">Wrong Hidden Company</ix:nonNumeric>
</ix:hidden>
<div>
  <ix:nonNumeric name="dei:EntityRegistrantName">Acme Corporation</ix:nonNumeric>
  <ix:nonNumeric name="dei:DocumentType">10-K</ix:nonNumeric>
  <ix:nonNumeric name="dei:DocumentFiscalYearFocus">2026</ix:nonNumeric>
  <ix:nonNumeric name="dei:DocumentFiscalPeriodFocus">FY</ix:nonNumeric>
</div>
<h2>Consolidated Statements of Income</h2>
<table>
<tr><th>Years Ended December 31</th><th>2026</th><th>2025</th></tr>
<tr><td>Revenue</td><td><ix:nonfraction name="us-gaap:Revenue">300</ix:nonfraction></td><td>250</td></tr>
<tr><td>Cost of sales</td><td>180</td><td>150</td></tr>
<tr><td>Gross profit</td><td>120</td><td>100</td></tr>
<tr><td>Operating income</td><td>50</td><td>40</td></tr>
<tr><td>Net income</td><td>30</td><td>20</td></tr>
<tr><td>Diluted earnings per share</td><td>1.50</td><td>1.10</td></tr>
</table>
<h2>Consolidated Statements of Cash Flows</h2>
<table>
<tr><th>Years Ended December 31</th><th>2026</th><th>2025</th></tr>
<tr><td>Net income</td><td>30</td><td>20</td></tr>
<tr><td>Depreciation and amortization</td><td>10</td><td>8</td></tr>
<tr><td>Net cash provided by operating activities</td><td>40</td><td>28</td></tr>
<tr><td>Capital expenditures</td><td>(15)</td><td>(12)</td></tr>
<tr><td>Net cash used for investing activities</td><td>(15)</td><td>(12)</td></tr>
<tr><td>Net cash provided by financing activities</td><td>5</td><td>4</td></tr>
<tr><td>Cash and cash equivalents at beginning of period</td><td>70</td><td>50</td></tr>
<tr><td>Cash and cash equivalents at end of period</td><td>100</td><td>70</td></tr>
</table>
<h2>Consolidated Balance Sheets</h2>
<table>
<tr><th>As of December 31</th><th>2026</th><th>2025</th></tr>
<tr><td>Assets</td><td></td><td></td></tr>
<tr><td>Cash and cash equivalents</td><td>100</td><td>70</td></tr>
<tr><td>Total assets</td><td>500</td><td>450</td></tr>
<tr><td>Liabilities</td><td></td><td></td></tr>
<tr><td>Total liabilities</td><td>300</td><td>280</td></tr>
<tr><td>Stockholders' equity</td><td>200</td><td>170</td></tr>
<tr><td>Total liabilities and equity</td><td>500</td><td>450</td></tr>
</table>
</body>
</html>
"""


FUND_HTML = """<!doctype html>
<html><body>
<ix:nonNumeric name="dei:EntityRegistrantName">Example Fund, L.P.</ix:nonNumeric>
<ix:nonNumeric name="dei:DocumentType">10-K</ix:nonNumeric>
<ix:nonNumeric name="dei:DocumentFiscalYearFocus">2025</ix:nonNumeric>
<ix:nonNumeric name="dei:DocumentFiscalPeriodFocus">FY</ix:nonNumeric>
<table>
  <tr><th></th><th>December 31, 2025</th><th>December 31, 2024</th></tr>
  <tr><td>Assets</td><td></td><td></td></tr>
  <tr><td>Investments, at fair value</td><td>980</td><td>-</td></tr>
  <tr><td>Cash and cash equivalents</td><td>369</td><td>100</td></tr>
  <tr><td>Total Assets</td><td>1,349</td><td>100</td></tr>
  <tr><td>Liabilities</td><td></td><td></td></tr>
  <tr><td>Total Liabilities</td><td>64</td><td>-</td></tr>
  <tr><td>Net Assets</td><td>1,285</td><td>100</td></tr>
</table>
<table>
  <tr><th></th><th>December 31, 2025</th><th>December 31, 2024</th></tr>
  <tr><td>Investment Income</td><td></td><td></td></tr>
  <tr><td>Interest income</td><td>8</td><td>-</td></tr>
  <tr><td>Expenses</td><td></td><td></td></tr>
  <tr><td>Total Expenses</td><td>50</td><td>-</td></tr>
  <tr><td>Net Investment Loss</td><td>(42)</td><td>-</td></tr>
  <tr><td>Net Increase in Net Assets Resulting from Operations</td><td>141</td><td>-</td></tr>
</table>
<table>
  <tr><th>Class A-B</th><th>Class A-I</th><th>Total</th></tr>
  <tr><td>Net Assets at December 31, 2024</td><td>-</td><td>100</td><td>100</td></tr>
  <tr><td>Capital Unit Transactions</td><td></td><td></td><td></td></tr>
  <tr><td>Contributions for units issued</td><td>228</td><td>648</td><td>876</td></tr>
  <tr><td>Net increase in net assets resulting from operations</td><td>27</td><td>78</td><td>105</td></tr>
  <tr><td>Net Assets at December 31, 2025</td><td>255</td><td>726</td><td>981</td></tr>
</table>
<table>
  <tr><th></th><th>December 31, 2025</th><th>December 31, 2024</th></tr>
  <tr><td>Operating Activities</td><td></td><td></td></tr>
  <tr><td>Net increase in net assets resulting from operations</td><td>141</td><td>-</td></tr>
  <tr><td>Net cash used in operating activities</td><td>(793)</td><td>-</td></tr>
  <tr><td>Financing Activities</td><td></td><td></td></tr>
  <tr><td>Net cash provided by financing activities</td><td>1,162</td><td>100</td></tr>
  <tr><td>Cash and cash equivalents, end of period</td><td>369</td><td>100</td></tr>
</table>
<table>
  <tr><th>Investment</th><th>Asset</th><th>Geography</th><th>Fair Value</th><th>Fair Value as a Percentage of Net Assets</th></tr>
  <tr><td>Portfolio Companies</td><td></td><td></td><td></td><td></td></tr>
  <tr><td>Company A</td><td>Equity</td><td>Americas</td><td>600</td><td>46.7</td><td>%</td></tr>
  <tr><td>Company B</td><td>Equity</td><td>Europe</td><td>380</td><td>29.6</td><td>%</td></tr>
</table>
<table>
  <tr><th>Cash Equivalents</th><th>Geography</th><th>Fair Value</th><th>Fair Value as a Percentage of Net Assets</th></tr>
  <tr><td>Money Market Fund</td><td>N/A</td><td>369</td><td>28.7</td><td>%</td></tr>
  <tr><td>Total Investments and Cash Equivalents</td><td></td><td>1,349</td><td>105.1</td><td>%</td></tr>
</table>
<table>
  <tr><th>Investments</th><th>Fair Value</th><th>Valuation Techniques</th><th>Unobservable Inputs</th></tr>
  <tr><td>Portfolio Companies</td><td>980</td><td>Discounted Cash Flow</td><td>13.0%</td></tr>
  <tr><td>Other</td><td>50</td><td>Transaction Price</td><td>5.0%</td></tr>
</table>
</body></html>
"""


def test_html_extractor_detects_ixbrl_metadata_and_statement_tables(tmp_path):
    source = tmp_path / "acme-20261231.htm"
    source.write_text(SEC_HTML, encoding="utf-8")

    text_rows, raw_cells, normalized_cells, audit, metadata = extract_html_filing(source)

    assert metadata == {
        "client_name": "Acme Corporation",
        "document_type": "10-K",
        "year": "2026",
        "period": "Annual",
    }
    assert "Wrong Hidden Company" not in {row["raw_text"] for row in text_rows}
    assert {row["table_id"] for row in raw_cells} == {"HTML_0001", "HTML_0002", "HTML_0003"}
    assert len(normalized_cells) == len(raw_cells)
    assert audit[0]["Status"] == "PASS"


def test_html_filing_runs_through_existing_excel_pipeline(tmp_path):
    source = tmp_path / "acme-20261231.htm"
    source.write_text(SEC_HTML, encoding="utf-8")

    result, output = extract_filing_to_workbook(str(source), metadata={"period": "Auto"}, output_dir=str(tmp_path))

    assert output.name == "FY26_10K_Acme_Corporation.xlsx"
    assert set(result.statements) == {"IncomeStatement", "CashFlowStatement", "BalanceSheet"}
    assert result.statements["IncomeStatement"].attrs["period_labels"] == ["2026", "2025"]
    assert result.metadata["input_type"] == "HTML"

    workbook = load_workbook(output, read_only=True)
    try:
        assert workbook.sheetnames == ["Income Statement", "Cash Flow", "Balance Sheet"]
        assert workbook["Income Statement"]["A1"].value == "Acme Corporation"
    finally:
        workbook.close()


def test_fund_html_detects_all_statements_and_preserves_structured_columns(tmp_path):
    source = tmp_path / "fund-20251231.htm"
    source.write_text(FUND_HTML, encoding="utf-8")

    result, output = extract_filing_to_workbook(str(source), output_dir=str(tmp_path))

    assert set(result.statements) == {
        "BalanceSheet",
        "IncomeStatement",
        "PartnersCapital",
        "CashFlowStatement",
        "ScheduleOfInvestments",
    }
    partners = result.statements["PartnersCapital"]
    assert partners.attrs["period_labels"] == ["Class A-B", "Class A-I", "Total"]
    assert not any(str(item).startswith("Class A-B Class A-I") for item in partners["RawItem"])
    assert partners.loc[partners["RawItem"] == "Net Assets at December 31, 2025", "Total"].iloc[0] == 981

    schedule = result.statements["ScheduleOfInvestments"]
    assert schedule.attrs["period_labels"] == ["Fair Value", "% of Net Assets"]
    assert not any("Fair Value as a Percentage" in str(item) for item in schedule["RawItem"])
    assert "Discounted Cash Flow" not in " ".join(schedule["RawItem"])
    assert schedule.loc[schedule["RawItem"].str.contains("Total Investments"), "Fair Value"].iloc[0] == 1349

    workbook = load_workbook(output, read_only=True)
    try:
        assert workbook.sheetnames == [
            "Income Statement",
            "Cash Flow",
            "Balance Sheet",
            "Partners Capital",
            "Schedule of Investments",
        ]
        schedule_sheet = workbook["Schedule of Investments"]
        percent_column = next(
            cell.column
            for cell in schedule_sheet[5]
            if cell.value == "% of Net Assets"
        )
        percent_cell = next(
            schedule_sheet.cell(row=row, column=percent_column)
            for row in range(6, schedule_sheet.max_row + 1)
            if schedule_sheet.cell(row=row, column=percent_column).value is not None
        )
        assert percent_cell.number_format == "0.0%;(0.0%);-"
    finally:
        workbook.close()
