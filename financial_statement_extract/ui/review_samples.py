"""Small synthetic filings for repeatable UI review; no client or market data."""

from html import escape


def table(title, headers, rows):
    def row(values, tag):
        return "<tr>" + "".join(f"<{tag}>{escape(str(value))}</{tag}>" for value in values) + "</tr>"
    return f"<h2>{escape(title)}</h2><table>" + row(headers, "th") + "".join(row(values, "td") for values in rows) + "</table>"


CORPORATE = """<html><body><h1>Synthetic Northstar Manufacturing Corporation</h1>
<ix:nonNumeric name="dei:EntityRegistrantName">Synthetic Northstar Manufacturing Corporation</ix:nonNumeric>
<ix:nonNumeric name="dei:DocumentFiscalYearFocus">2026</ix:nonNumeric>""" + table(
    "Consolidated Statements of Income", ("Years ended December 31", "2026", "2025"), (
        ("Revenue", "300", "250"), ("Cost of sales", "180", "150"), ("Gross profit", "120", "100"),
        ("Operating income", "50", "40"), ("Net income", "30", "20"), ("Diluted earnings per share", "1.50", "1.10"),
    )) + table("Consolidated Statements of Cash Flows", ("Years ended December 31", "2026", "2025"), (
        ("Net income", "30", "20"), ("Depreciation and amortization", "10", "8"),
        ("Net cash provided by operating activities", "40", "28"),
        ("Net cash used for investing activities", "(15)", "(12)"),
        ("Net cash provided by financing activities", "5", "4"),
        ("Cash and cash equivalents at beginning of period", "70", "50"),
        ("Cash and cash equivalents at end of period", "100", "70"),
    )) + table("Consolidated Balance Sheets", ("As of December 31", "2026", "2025"), (
        ("Assets", "", ""), ("Cash and cash equivalents", "100", "70"), ("Total assets", "500", "450"),
        ("Liabilities", "", ""), ("Total liabilities", "300", "280"),
        ("Stockholders' equity", "200", "170"), ("Total liabilities and equity", "500", "450"),
    )) + "</body></html>"

FUND = """<html><body><h1>Synthetic Long-Horizon Investment Partnership — Review Sample</h1>
<ix:nonNumeric name="dei:EntityRegistrantName">Synthetic Long-Horizon Investment Partnership</ix:nonNumeric>
<ix:nonNumeric name="dei:DocumentFiscalYearFocus">2026</ix:nonNumeric>
<h2>Statements of Stockholders’ Equity</h2><table>
<tr><th rowspan="2"></th><th colspan="2">Common Stock</th><th rowspan="2">Retained earnings (deficit)</th></tr>
<tr><th>Shares</th><th>Amount</th></tr>
<tr><td>Balance at December 31, 2025</td><td>100</td><td>$1.00</td><td>20</td></tr>
<tr><td>Net increase in net assets from operations (3)</td><td>—</td><td>N/A</td><td>5</td></tr>
<tr><td>Balance at June 30, 2026</td><td>100</td><td>$1.00</td><td>25</td></tr>
</table>""" + table("Schedule of Investments", ("Investment", "Asset", "Cost", "Fair Value"), (
    (f"Synthetic issuer {i:02d} — restricted, non-controlling interest (1); long source description for review",
     "Preferred stock" if i % 2 else "Debt", str(i * 2), str(i * 2 + 1)) for i in range(1, 61)
)) + table("Schedule of Investments", ("Investment", "Geography", "% of net assets"), (
    ("Synthetic issuer 01", "Europe", "12.50%"), ("Synthetic issuer 02", "Americas", "0%"),
)) + "</body></html>"

CASES = {
    "corporate": CORPORATE,
    "fund": FUND,
    "invalid": "<html><body><h1>Synthetic failure case</h1><p>No financial statements or tables.</p></body></html>",
}
