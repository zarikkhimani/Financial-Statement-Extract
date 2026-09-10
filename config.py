from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConceptRule:
    aliases: tuple[str, ...]
    standard_name: str
    category: str
    subcategory: str
    contexts: tuple[str, ...] = ()
    exact_only: bool = False


STATEMENT_TITLES = {
    "BalanceSheet": (
        "balance sheet",
        "balance sheets",
        "statement of financial position",
        "statements of financial position",
        "statement of assets and liabilities",
        "statements of assets and liabilities",
    ),
    "IncomeStatement": (
        "income statement",
        "income statements",
        "statement of income",
        "statements of income",
        "statement of income (loss)",
        "statements of income (loss)",
        "statement of operations",
        "statements of operations",
        "statement of operations and comprehensive income",
        "statements of operations and comprehensive income",
        "statement of earnings",
        "statements of earnings",
        "statement of comprehensive income",
        "statements of comprehensive income",
    ),
    "CashFlowStatement": (
        "statement of cash flows",
        "statements of cash flows",
        "cash flow statement",
        "cash flow statements",
    ),
    # Recognize public-company equity roll-forwards as document boundaries so
    # they cannot be absorbed into an adjacent core statement. They are not
    # currently emitted as output worksheets.
    "StockholdersEquityStatement": (
        "statement of stockholders' equity",
        "statements of stockholders' equity",
        "statement of stockholders’ equity",
        "statements of stockholders’ equity",
        "statement of shareholders' equity",
        "statements of shareholders' equity",
        "statement of shareholders’ equity",
        "statements of shareholders’ equity",
        "statement of changes in stockholders' equity",
        "statements of changes in stockholders' equity",
        "statement of changes in shareholders' equity",
        "statements of changes in shareholders' equity",
    ),
    "PartnersCapital": (
        "statement of changes in partners' capital",
        "statements of changes in partners' capital",
        "statement of changes in partners’ capital",
        "statements of changes in partners’ capital",
        "statement of changes in net assets",
        "statements of changes in net assets",
        "statement of changes in members' capital",
        "statements of changes in members' capital",
    ),
    "ScheduleOfInvestments": (
        "schedule of investments",
        "schedule of portfolio investments",
        "portfolio of investments",
    ),
}

SECTION_HINTS = {
    "ASSETS": "ASSET",
    "CURRENT ASSETS": "CURRENT_ASSET",
    "NONCURRENT ASSETS": "NONCURRENT_ASSET",
    "LIABILITIES": "LIABILITY",
    "CURRENT LIABILITIES": "CURRENT_LIABILITY",
    "NONCURRENT LIABILITIES": "NONCURRENT_LIABILITY",
    "LIABILITIES AND EQUITY": "LIABILITY",
    "EQUITY": "EQUITY",
    "STOCKHOLDERS' EQUITY": "EQUITY",
    "STOCKHOLDERS’ EQUITY": "EQUITY",
    "SHAREHOLDERS' EQUITY": "EQUITY",
    "SHAREHOLDERS’ EQUITY": "EQUITY",
    "NET ASSETS": "EQUITY",
    "NET ASSETS CONSIST OF": "EQUITY",
    "PARTNERS' CAPITAL": "PARTNERS_CAPITAL",
    "PARTNERS’ CAPITAL": "PARTNERS_CAPITAL",
    "OPERATING ACTIVITIES": "OPERATING_ACTIVITY",
    "INVESTING ACTIVITIES": "INVESTING_ACTIVITY",
    "FINANCING ACTIVITIES": "FINANCING_ACTIVITY",
    "REVENUES": "REVENUE",
    "NET SALES": "REVENUE",
    "INVESTMENT INCOME": "REVENUE",
    "INTEREST INCOME": "REVENUE",
    "INTEREST EXPENSE": "INTEREST_EXPENSE",
    "NONINTEREST INCOME": "OTHER_INCOME",
    "NONINTEREST EXPENSES": "OPEX",
    "COST OF SALES": "COGS",
    "OPERATING EXPENSES": "OPEX",
    "EXPENSES": "OPEX",
    "NET REALIZED AND UNREALIZED GAIN (LOSS) ON INVESTMENTS": "INVESTMENT_RESULTS",
    "EARNINGS PER COMMON SHARE": "PER_SHARE",
    "CASH AND CASH EQUIVALENTS": "SUMMARY_CASH_FLOW",
    "SUPPLEMENTAL DISCLOSURE OF NON-CASH FINANCING ACTIVITIES": "SUPPLEMENTAL",
}

BALANCE_SHEET_RULES = (
    ConceptRule(("cash and cash equivalents",), "Cash and Cash Equivalents", "Assets", "Current Asset"),
    ConceptRule(("cash",), "Cash", "Assets", "Current Asset", ("ASSET", "CURRENT_ASSET"), exact_only=True),
    ConceptRule(("short-term investments", "short term investments"), "Short-Term Investments", "Assets", "Current Asset"),
    ConceptRule(("accounts receivable, net", "accounts receivable", "receivables, net"), "Accounts Receivable, Net", "Assets", "Current Asset"),
    ConceptRule(("contract assets",), "Contract Assets", "Assets", "Current Asset"),
    ConceptRule(("inventories", "inventory"), "Inventories", "Assets", "Current Asset"),
    ConceptRule(("other current assets",), "Other Current Assets", "Assets", "Current Asset"),
    ConceptRule(("total current assets",), "Total Current Assets", "Assets", "Total Current Assets"),
    ConceptRule(("content assets, net", "content assets net"), "Content Assets, Net", "Assets", "Noncurrent Asset"),
    ConceptRule(("property, plant and equipment, net", "property plant and equipment net", "property and equipment, net"), "Property, Plant and Equipment, Net", "Assets", "Noncurrent Asset"),
    ConceptRule(("goodwill",), "Goodwill", "Assets", "Noncurrent Asset"),
    ConceptRule(("intangible assets, net", "intangible assets"), "Intangible Assets, Net", "Assets", "Noncurrent Asset"),
    ConceptRule(("deferred income taxes", "deferred tax assets", "deferred income tax assets"), "Deferred Income Taxes (Assets)", "Assets", "Noncurrent Asset", ("ASSET", "CURRENT_ASSET", "NONCURRENT_ASSET")),
    ConceptRule(("other noncurrent assets", "other long-term assets"), "Other Noncurrent Assets", "Assets", "Noncurrent Asset"),
    ConceptRule(("total assets",), "Total Assets", "Assets", "Total Assets"),
    ConceptRule(("accounts payable",), "Accounts Payable", "Liabilities", "Current Liability"),
    ConceptRule(("current content liabilities",), "Current Content Liabilities", "Liabilities", "Current Liability"),
    ConceptRule(("accrued expenses and other liabilities",), "Accrued Expenses and Other Liabilities", "Liabilities", "Current Liability"),
    ConceptRule(("deferred revenue",), "Deferred Revenue", "Liabilities", "Current Liability"),
    ConceptRule(("short-term debt", "short term debt"), "Short-Term Debt", "Liabilities", "Current Liability"),
    ConceptRule(("current portion of long-term debt", "current maturities of long-term debt"), "Current Portion of Long-Term Debt", "Liabilities", "Current Liability"),
    ConceptRule(("other current liabilities",), "Other Current Liabilities", "Liabilities", "Current Liability"),
    ConceptRule(("total current liabilities", "current liabilities"), "Total Current Liabilities", "Liabilities", "Total Current Liabilities"),
    ConceptRule(("long-term debt, net", "long-term debt", "long term debt"), "Long-Term Debt", "Liabilities", "Noncurrent Liability"),
    ConceptRule(("deferred income taxes", "deferred tax liabilities", "deferred income tax liabilities"), "Deferred Income Taxes (Liabilities)", "Liabilities", "Noncurrent Liability", ("LIABILITY", "CURRENT_LIABILITY", "NONCURRENT_LIABILITY")),
    ConceptRule(("non-current content liabilities", "noncurrent content liabilities"), "Noncurrent Content Liabilities", "Liabilities", "Noncurrent Liability"),
    ConceptRule(("other noncurrent liabilities", "other non-current liabilities", "other long-term liabilities"), "Other Noncurrent Liabilities", "Liabilities", "Noncurrent Liability"),
    ConceptRule(("total liabilities and equity", "total liabilities and stockholders' equity", "total liabilities and stockholders’ equity", "total liabilities and partners' capital", "total liabilities and partners’ capital"), "Total Liabilities and Equity", "Summary", "Total Liabilities and Equity"),
    ConceptRule(("total liabilities",), "Total Liabilities", "Liabilities", "Total Liabilities"),
    ConceptRule(("preferred stock",), "Preferred Stock", "Equity", "Equity Item"),
    ConceptRule(("common stock",), "Common Stock", "Equity", "Equity Item"),
    ConceptRule(("treasury stock",), "Treasury Stock", "Equity", "Equity Item"),
    ConceptRule(("accumulated other comprehensive income", "accumulated other comprehensive income (loss)"), "Accumulated Other Comprehensive Income (Loss)", "Equity", "Equity Item"),
    ConceptRule(("additional paid-in capital", "additional paid in capital"), "Additional Paid-In Capital", "Equity", "Equity Item"),
    ConceptRule(("retained earnings", "accumulated deficit"), "Retained Earnings (Accumulated Deficit)", "Equity", "Equity Item"),
    ConceptRule(("total stockholders' equity", "total stockholders’ equity", "total shareholders' equity", "total equity", "partners' capital", "partners’ capital", "net assets"), "Total Equity", "Equity", "Total Equity"),
    ConceptRule(("investments at fair value", "investment securities at fair value"), "Investments at Fair Value", "Assets", "Investment Asset"),
    ConceptRule(("investments at cost",), "Investments at Cost", "Assets", "Investment Asset"),
    ConceptRule(("unfunded commitments", "unfunded commitment"), "Unfunded Commitments", "Commitments", "Off Balance Sheet"),
)

INCOME_STATEMENT_RULES = (
    ConceptRule(("net sales",), "Net Sales", "Revenue", "Revenue"),
    ConceptRule(("sales",), "Sales", "Revenue", "Revenue", exact_only=True),
    ConceptRule(("revenue", "revenues"), "Revenue", "Revenue", "Revenue"),
    ConceptRule(("total revenues",), "Total Revenues", "Revenue", "Total Revenue"),
    ConceptRule(("cost of goods sold", "cost of sales", "cost of revenues"), "Cost of Revenues", "Cost of Sales", "COGS"),
    ConceptRule(("gross profit",), "Gross Profit", "Profit", "Gross Profit"),
    ConceptRule(("gross margin",), "Gross Margin", "Ratio", "Margin", exact_only=True),
    ConceptRule(("research and development", "research and development expenses"), "Research and Development Expense", "Operating Expenses", "Opex"),
    ConceptRule(("selling, general and administrative", "selling general and administrative expenses"), "Selling, General and Administrative Expense", "Operating Expenses", "Opex"),
    ConceptRule(("operating income", "operating loss"), "Operating Income (Loss)", "Profit", "Operating Income"),
    ConceptRule(("interest expense",), "Interest Expense", "Non-Operating", "Expense"),
    ConceptRule(("interest income",), "Interest Income", "Non-Operating", "Income"),
    ConceptRule(("income before income taxes", "earnings before income taxes"), "Income Before Income Taxes", "Profit", "Pre-Tax Income"),
    ConceptRule(("provision for income taxes", "income tax expense"), "Income Tax Expense", "Taxes", "Tax"),
    ConceptRule(("net income", "net earnings", "net loss"), "Net Income (Loss)", "Profit", "Net Income"),
    ConceptRule(("net realized gain", "net realized gain (loss)", "realized gain (loss)"), "Net Realized Gain (Loss)", "Investment Results", "Realized Gain Loss"),
    ConceptRule(("net change in unrealized appreciation", "net change in unrealized appreciation (depreciation)", "change in unrealized appreciation"), "Net Change in Unrealized Appreciation (Depreciation)", "Investment Results", "Unrealized Gain Loss"),
    ConceptRule(("management fees", "management fee"), "Management Fees", "Fund Expenses", "Expense"),
    ConceptRule(("carried interest", "incentive allocation", "performance allocation"), "Carried Interest / Incentive Allocation", "Fund Expenses", "Carry"),
)

CASH_FLOW_RULES = (
    ConceptRule(("net income", "net earnings"), "Net Income (Loss)", "Operating Activities", "Starting Point"),
    ConceptRule(("depreciation and amortization",), "Depreciation and Amortization", "Operating Activities", "Adjustment"),
    ConceptRule(("stock-based compensation", "share-based compensation"), "Stock-Based Compensation", "Operating Activities", "Adjustment"),
    ConceptRule(("deferred income taxes",), "Deferred Income Taxes", "Operating Activities", "Adjustment"),
    ConceptRule(("accounts receivable",), "Changes in Accounts Receivable", "Operating Activities", "Working Capital"),
    ConceptRule(("inventories", "inventory"), "Changes in Inventories", "Operating Activities", "Working Capital"),
    ConceptRule(("accounts payable",), "Changes in Accounts Payable", "Operating Activities", "Working Capital"),
    ConceptRule(("net cash provided by operating activities", "net cash used in operating activities", "net cash used for operating activities"), "Net Cash Provided by (Used for) Operating Activities", "Operating Activities", "Total Operating"),
    ConceptRule(("capital expenditures", "purchases of property, plant and equipment", "purchases of property and equipment"), "Capital Expenditures", "Investing Activities", "Investing Use"),
    ConceptRule(("acquisitions, net of cash acquired",), "Acquisitions, Net of Cash Acquired", "Investing Activities", "Investing Use"),
    ConceptRule(("net cash used for investing activities", "net cash provided by investing activities"), "Net Cash Provided by (Used for) Investing Activities", "Investing Activities", "Total Investing"),
    ConceptRule(("proceeds from issuance of long-term debt", "borrowings under long-term debt"), "Proceeds from Long-Term Debt", "Financing Activities", "Financing Source"),
    ConceptRule(("repayment of long-term debt", "payments of long-term debt"), "Repayment of Long-Term Debt", "Financing Activities", "Financing Use"),
    ConceptRule(("dividends paid", "distributions paid"), "Dividends / Distributions Paid", "Financing Activities", "Financing Use"),
    ConceptRule(("net cash used for financing activities", "net cash provided by financing activities"), "Net Cash Provided by (Used for) Financing Activities", "Financing Activities", "Total Financing"),
    ConceptRule(("net increase in cash and cash equivalents", "net decrease in cash and cash equivalents", "net change in cash and cash equivalents"), "Net Increase (Decrease) in Cash and Cash Equivalents", "Summary Cash Flow", "Net Change Cash"),
    ConceptRule(("cash and cash equivalents at beginning of period", "cash at beginning of period", "cash cash equivalents and restricted cash beginning of year", "cash and cash equivalents and restricted cash beginning of year"), "Cash and Cash Equivalents at Beginning of Period", "Summary Cash Flow", "Beginning Cash"),
    ConceptRule(("cash and cash equivalents at end of period", "cash at end of period", "cash cash equivalents and restricted cash end of year", "cash and cash equivalents and restricted cash end of year"), "Cash and Cash Equivalents at End of Period", "Summary Cash Flow", "Ending Cash"),
    ConceptRule(("capital contributions", "contributions from partners", "partner contributions"), "Capital Contributions", "Financing Activities", "Partner Flow"),
    ConceptRule(("distributions to partners", "partner distributions"), "Distributions to Partners", "Financing Activities", "Partner Flow"),
)

PARTNERS_CAPITAL_RULES = (
    ConceptRule(("beginning balance", "partners' capital, beginning", "partners’ capital, beginning", "net assets, beginning"), "Beginning Partners' Capital / Net Assets", "Partners' Capital", "Beginning Balance"),
    ConceptRule(("capital contributions", "contributions"), "Capital Contributions", "Partners' Capital", "Contributions"),
    ConceptRule(("distributions",), "Distributions", "Partners' Capital", "Distributions"),
    ConceptRule(("net income", "net increase in net assets from operations"), "Net Income / Increase in Net Assets from Operations", "Partners' Capital", "Operations"),
    ConceptRule(("carried interest", "incentive allocation"), "Carried Interest / Incentive Allocation", "Partners' Capital", "Carry"),
    ConceptRule(("ending balance", "partners' capital, ending", "partners’ capital, ending", "net assets, ending"), "Ending Partners' Capital / Net Assets", "Partners' Capital", "Ending Balance"),
)

SCHEDULE_INVESTMENTS_RULES = (
    ConceptRule(("fair value",), "Fair Value", "Investment Schedule", "Valuation"),
    ConceptRule(("cost",), "Cost", "Investment Schedule", "Valuation"),
    ConceptRule(("principal amount", "par amount"), "Principal / Par Amount", "Investment Schedule", "Debt Amount"),
    ConceptRule(("interest rate", "coupon"), "Interest Rate", "Investment Schedule", "Debt Terms"),
    ConceptRule(("maturity", "maturity date"), "Maturity Date", "Investment Schedule", "Debt Terms"),
)

RULES_BY_STATEMENT = {
    "BalanceSheet": BALANCE_SHEET_RULES,
    "IncomeStatement": INCOME_STATEMENT_RULES,
    "CashFlowStatement": CASH_FLOW_RULES,
    "PartnersCapital": PARTNERS_CAPITAL_RULES,
    "ScheduleOfInvestments": SCHEDULE_INVESTMENTS_RULES,
}
