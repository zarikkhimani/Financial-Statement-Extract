"""Checks against the source grids used by the workbook, without changing data."""
from __future__ import annotations

from collections import Counter
import math
import re

import pandas as pd

from normalization import parse_numeric_token
from financial_statement_extract.table_layout import SINGLE_NUMBER


RECOVERED = {'BalanceSheet': 'balance_geometry', 'CashFlowStatement': 'cash_flow_text',
             'PartnersCapital': 'equity_geometry', 'StockholdersEquityStatement': 'equity_geometry'}

BALANCE_COMPLETENESS = 'Balance sheet completeness'


def balance_completeness_status(rows):
    """Shared presentation state; arithmetic passes cannot override missing content."""
    statuses = {row.get('Status') for row in rows if row.get('Check') == BALANCE_COMPLETENESS}
    if statuses & {'FAIL', 'ERROR'}:
        return 'FAIL'
    if statuses - {'PASS'}:
        return 'NOT_TESTED'
    return 'PASS' if statuses else None


def _body_tokens(text):
    # Physical currency-only columns and whitespace wrapping are presentation,
    # not omitted content. Preserve numbers, signs, punctuation and multiplicity.
    return Counter(re.findall(r'[$€£¥]|[^\s$€£¥]+', str(text).casefold()))


def _balance_sections(lines):
    labels = {
        'assets': r'(?:total )?assets',
        'liabilities': r'(?:total )?liabilities',
        'equity/net assets': r'(?:total )?(?:(?:(?:share|stock)holders[’\']? )?equity|net assets)',
    }
    return {name for name, pattern in labels.items()
            if any(re.match(r'^' + pattern + r'(?:\s*:|\s+[$€£¥(\d]|\s*$)',
                            re.sub(r'\s+', ' ', str(line)).strip(), re.I) for line in lines)}


def audit_balance_completeness(result, frame, page):
    """Check the displayed PDF grid against an independently bounded text body.

    This is a content-coverage check, not row/column alignment or arithmetic
    certification. Unsupported boundaries remain explicitly unverified.
    """
    scope = f'Page {page} / BalanceSheet'
    tables = frame.attrs.get('source_tables', []) if frame is not None else []
    tables = [table for table in tables if table.get('source_page') == page]
    if not tables:
        return issue(BALANCE_COMPLETENESS, scope, 'FAIL',
                     'Incomplete balance sheet: no source table is attached to the exported sheet for this page.')
    lines = [str(row.get('raw_text') or '').strip() for row in getattr(result, 'raw_text_rows', [])
             if row.get('source_page') == page]
    starts = [i for i, line in enumerate(lines) if re.fullmatch(r'assets\s*:?', line, re.I)]
    ends = [i for i, line in enumerate(lines) if re.match(r'^See (?:accompanying )?Notes\b', line, re.I)]
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        return issue(BALANCE_COMPLETENESS, scope, 'NOT_TESTED',
                     'Balance-sheet completeness is unverified: a unique Assets-to-Notes source body could not be established. '
                     'Review the source, including any continuation pages.')
    body = lines[starts[0]:ends[0]]
    required = {'assets', 'liabilities', 'equity/net assets'}
    if _balance_sections(body) != required:
        return issue(BALANCE_COMPLETENESS, scope, 'NOT_TESTED',
                     'Balance-sheet completeness is unverified: assets, liabilities and equity/net assets '
                     'could not all be identified in the source body.')
    rows = [row for table in tables for row in table.get('rows', [])]
    missing_sections = required - _balance_sections([row[0] for row in rows if row])
    expected = _body_tokens(' '.join(body))
    actual = _body_tokens(' '.join(str(cell) if cell is not None else '' for row in rows for cell in row))
    missing = expected - actual
    failures = []
    if missing_sections:
        failures.append('Missing required sections: ' + ', '.join(sorted(missing_sections)) + '.')
    if missing:
        examples = ', '.join(f'{token} ({count})' for token, count in list(missing.items())[:20])
        failures.append(f'{sum(missing.values())}/{sum(expected.values())} source-body tokens are missing from the exported grid. '
                        f'Missing content examples (occurrences): {examples}.')
    if failures:
        return issue(BALANCE_COMPLETENESS, scope, 'FAIL', 'Incomplete balance sheet. ' + ' '.join(failures))
    return issue(BALANCE_COMPLETENESS, scope, 'PASS',
                 f'Assets, liabilities and equity/net assets are present; all {sum(expected.values())} source-body tokens '
                 'are covered, including wrapped labels and repeated content. '
                 'This checks content coverage only; amount alignment, duplicates and arithmetic require separate checks.')


def recovered_tables(frame, kind):
    if kind not in RECOVERED:
        return []
    tables = frame.attrs.get('source_tables', []) if frame is not None else []
    return tables if tables and all(t.get('flavor') == RECOVERED.get(kind) for t in tables) else []


def issue(check, scope, status, detail):
    return dict(Check=check, Scope=scope, Status=status, Detail=detail)


def label_key(text):
    return re.sub(r'\s+', ' ', re.sub(r'\(\s*(?:Note\s+)?\d+\s*\)', '', text, flags=re.I)).strip().casefold()


def number(text, *, movement=False):
    token = parse_numeric_token(text)
    if token.status == 'NUMERIC' and math.isfinite(token.value) and SINGLE_NUMBER.fullmatch(str(text).strip()):
        return token.value
    # A source dash explicitly denotes no movement for rollforward arithmetic.
    # Blanks, NA/NM and unavailable balances are never turned into zero.
    return 0.0 if movement and token.status == 'DASH' else None


def equation(check, scope, actual, expected, detail=''):
    if actual is None or expected is None:
        return issue(check, scope, 'NOT_TESTED', 'Required source rows are missing, ambiguous or nonnumeric. ' + detail)
    # Reported integer statements are rounded to units, not to a percentage of
    # their size. A large balance must not hide a several-unit discrepancy.
    tolerance = 1.0
    diff = actual - expected
    return issue(check, scope, 'PASS' if abs(diff) <= tolerance else 'FAIL',
                 f'Reported={actual:,.6f}; calculated={expected:,.6f}; difference={diff:,.6f}; tolerance={tolerance:g}. ' + detail)


def total(values):
    return None if not values or any(v is None for v in values) else sum(values)


def data_rows(table):
    return [row for row, kind in zip(table.get('rows', []), table.get('row_kinds', [])) if kind == 'data']


def unique_value(rows, pattern, column):
    found = [r for r in rows if re.fullmatch(pattern, label_key(r[0]))]
    return number(found[0][column]) if len(found) == 1 and len(found[0]) > column else None


def validate_grid(table):
    scope = table.get('table_id', 'Source table')
    rows, kinds = table.get('rows', []), table.get('row_kinds', [])
    headers = table.get('period_labels', table.get('component_labels', []))
    failures = []
    if not headers or any(not str(h).strip() for h in headers) or len(set(headers)) != len(headers):
        failures.append('Missing or duplicate date/component headings.')
    if len(rows) != len(kinds) or len(rows) != len(table.get('row_sources', [])):
        failures.append('Row content, row classification and source provenance have different counts.')
    for i, (row, kind) in enumerate(zip(rows, kinds), 1):
        if kind == 'data':
            if i <= len(table.get('row_sources', [])) and not table['row_sources'][i-1]:
                failures.append(f'Row {i} has no source position.')
            if len(row) != len(headers) + 1 or not row[0]:
                failures.append(f'Row {i} does not match its date/component columns.')
                continue
            for value in row[1:]:
                token = parse_numeric_token(value)
                if token.status not in {'DASH', 'NA', 'NM'} and number(value) is None:
                    failures.append(f'Row {i} has a blank, invalid or combined amount.')
        if any('\ufffd' in str(value) for value in row):
            failures.append(f'Row {i} contains a replacement character.')
    if not data_rows(table):
        failures.append('No financial rows are available.')
    # Equal values at different source positions are legitimate. Reusing the
    # same physical source row is a duplication regardless of its amounts.
    sources = [repr(s) for s, k in zip(table.get('row_sources', []), kinds) if k == 'data' and s]
    if any(count > 1 for count in Counter(sources).values()):
        failures.append('The same source position is used by multiple financial rows.')
    return issue('Export column and row integrity', scope, 'FAIL' if failures else 'PASS',
                 ' '.join(dict.fromkeys(failures)) or f'{len(data_rows(table))} financial rows; {len(headers)} distinct columns; source positions retained. This is a structural check, not proof of complete source coverage.')


EQUITY_LABEL = r'(?:(?:share|stock)holders[’\']? )?equity'


def _balance_section_sum(table, heading, total_label, column):
    """Sum only an unambiguous, uninterrupted source-defined section."""
    rows, kinds = table['rows'], table['row_kinds']
    starts = [i for i, (row, kind) in enumerate(zip(rows, kinds))
              if kind == 'section' and re.fullmatch(heading + r':?', label_key(row[0]))]
    ends = [i for i, (row, kind) in enumerate(zip(rows, kinds))
            if kind == 'data' and re.fullmatch(total_label, label_key(row[0]))]
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0] - 1:
        return None
    indices = range(starts[0] + 1, ends[0])
    if any(kinds[i] != 'data' or label_key(rows[i][0]).startswith('total ') for i in indices):
        return None  # Nested totals need their own source-defined hierarchy.
    return total([number(rows[i][column]) if len(rows[i]) > column else None for i in indices])


def audit_corporate_balance_grid(table):
    rows, checks = data_rows(table), []
    equity_total = r'total ' + EQUITY_LABEL
    for c, date in enumerate(table['period_labels'], 1):
        for name in ('current assets', 'non-current assets', 'current liabilities', 'non-current liabilities'):
            checks.append(equation('Balance sheet: ' + name, date,
                                   unique_value(rows, 'total ' + name, c),
                                   _balance_section_sum(table, name, 'total ' + name, c)))
        for name in ('assets', 'liabilities'):
            checks.append(equation('Balance sheet: total ' + name, date,
                                   unique_value(rows, 'total ' + name, c),
                                   total([unique_value(rows, 'total current ' + name, c),
                                          unique_value(rows, 'total non-current ' + name, c)])))
        # Multiple reported equity/net-asset totals are ambiguous; never choose
        # the first value or silently ignore noncontrolling-interest subtotals.
        equity = unique_value(rows, '(?:' + equity_total + r'|total net assets)', c)
        checks.append(equation('Balance sheet: total equity', date, equity,
                               _balance_section_sum(table, EQUITY_LABEL, equity_total, c)))
        reported = unique_value(rows, r'total liabilities and (?:' + EQUITY_LABEL + r'|(?:total )?net assets)', c)
        checks.append(equation('Balance sheet: liabilities plus equity', date, reported,
                               total([unique_value(rows, r'total liabilities', c), equity])))
        checks.append(equation('Balance sheet: assets equal liabilities plus equity', date,
                               reported, unique_value(rows, r'total assets', c)))
    return checks


def audit_balance_grid(table):
    if any(re.fullmatch(r'(?:total |total liabilities and )?' + EQUITY_LABEL + r':?', label_key(row[0]))
           for row in table['rows'] if row):
        return audit_corporate_balance_grid(table)
    rows, checks = data_rows(table), []
    for c, date in enumerate(table['period_labels'], 1):
        assets = unique_value(rows, r'total assets', c)
        liabilities = unique_value(rows, r'total liabilities', c)
        net_assets = unique_value(rows, r'total net assets', c)
        reported = unique_value(rows, r'total liabilities and (?:total )?net assets', c)
        checks.append(equation('Assets = liabilities + net assets', date, assets, total([liabilities, net_assets])))
        checks.append(equation('Assets = reported liabilities and net assets', date, assets, reported))
    return checks


def audit_cash_grids(tables):
    checks = []
    periods = list(dict.fromkeys(p for t in tables for p in t['period_labels']))
    for period in periods:
        rows = [[row[0], row[t['period_labels'].index(period)+1]] for t in tables
                if period in t['period_labels'] for row in data_rows(t)]
        if 'ended' not in period.lower():
            # Reconciliation table is a separate as-of balance, not another year
            # of operating cash flows. Every component is already source-bound.
            totals = [r for r in rows if label_key(r[0]).startswith('total cash')]
            components = [r for r in rows if not label_key(r[0]).startswith('total cash')]
            if len(totals) == 1:
                checks.append(equation('Cash reconciliation components', period, number(totals[0][1]),
                                       total([number(r[1], movement=True) for r in components]),
                                       'Source dashes contribute no amount; blanks/NA remain untested.'))
            continue
        begin = unique_value(rows, r'cash.*beginning of (?:period|year)', 1)
        end = unique_value(rows, r'cash.*end of (?:period|year)', 1)
        change = unique_value(rows, r'net (?:change|increase(?: \(decrease\))?|decrease) in cash.*', 1)
        fx_rows = [r for r in rows if re.fullmatch(r'effect of (?:foreign currency )?exchange rates(?:.*)', label_key(r[0]))]
        fx = number(fx_rows[0][1], movement=True) if len(fx_rows) == 1 else 0 if not fx_rows else None
        checks.append(equation('Cash beginning + change + FX = ending', period, end, total([begin, change, fx]),
                               'Exchange-rate effect is included when separately reported.'))
    return checks


def audit_equity_grid(table):
    checks = []
    sections = table.get('period_sections', [])
    if not sections:
        return [issue('Equity component rollforwards', table.get('table_id', 'Equity'), 'NOT_TESTED',
                      'Source-defined beginning, movement and ending sections are not available.')]
    rows = table['rows']
    for section in sections:
        start, end = section['start'], section['end']
        if not 0 <= start < end-2 < end <= len(rows) or not re.match(r'^Balance (?:at|as of)\b', rows[start][0], re.I) or not re.match(r'^Balance (?:at|as of)\b', rows[end-1][0], re.I) or not rows[end-2][0].lower().startswith('total '):
            checks.append(issue('Equity component rollforwards', section['caption'], 'FAIL', 'Invalid opening/change/closing source rows.'))
            continue
        for c, component in enumerate(table['component_labels'], 1):
            scope = f"{section['caption']} / {component}"
            opening, change, closing = [number(rows[i][c]) for i in (start, end-2, end-1)]
            checks.append(equation('Equity beginning + change = ending', scope, closing, total([opening, change])))
            checks.append(equation('Equity movement subtotal', scope, change,
                                   total([number(rows[i][c], movement=True) for i in range(start+1, end-2)
                                          if table['row_kinds'][i] == 'data']),
                                   'Source dashes contribute no movement; blanks/NA remain untested.'))
    return checks


def audit_recovered_statement(kind, tables):
    checks = [validate_grid(t) for t in tables]
    if any(r['Status'] == 'FAIL' for r in checks):
        return checks + [issue('Source-grid financial checks', kind, 'NOT_TESTED', 'Resolve the export row/column integrity failures first.')]
    if kind == 'BalanceSheet':
        checks.extend(r for t in tables for r in audit_balance_grid(t))
    elif kind == 'CashFlowStatement':
        checks.extend(audit_cash_grids(tables))
    else:
        checks.extend(r for t in tables for r in audit_equity_grid(t))
    return checks


def audit_selected_page_coverage(result):
    plan = result.page_plan
    if plan is None:
        return [issue('Selected statement page coverage', 'Document', 'NOT_TESTED', 'No PDF page plan is available; selected-page completeness was not checked.')]
    checks = []
    for page in plan.pages:
        if page.page not in plan.selected_pages:
            continue
        kinds = page.statement_types or (page.statement_type,)
        for kind in kinds:
            if not kind:
                checks.append(issue('Selected statement page coverage', f'Page {page.page}', 'WARN', 'Selected page has no recognized statement owner. Review it for omitted content.'))
                continue
            frame = result.statements.get(kind)
            present = frame is not None and any(t.get('source_page') == page.page for t in frame.attrs.get('source_tables', []))
            checks.append(issue('Selected statement page coverage', f'Page {page.page} / {kind}', 'PASS' if present else 'FAIL',
                                'A statement table is attached to the exported sheet; row completeness is checked separately.' if present else 'A selected statement page has no table attached to an exported sheet.'))
            if kind == 'BalanceSheet':
                checks.append(audit_balance_completeness(result, frame, page.page))
            elif present:
                checks.append(audit_text_row_coverage(result, frame, kind, page.page))
    if 'ScheduleOfInvestments' in result.statements:
        checks.append(issue('Investment schedule completeness', 'Selected pages', 'NOT_TESTED',
                            'Only the requested schedule pages were extracted. Full-portfolio coverage and totals are not established.'))
    return checks


def audit_text_row_coverage(result, frame, kind, page):
    """Compare source line vectors, preserving multiplicity; never certify a page."""
    from statements import _match_desc_first
    tables = [t for t in recovered_tables(frame, kind) if t.get('source_page') == page]
    actual = []
    widths = set()
    by_line = {}
    if tables:
        for t in tables:
            widths.add(len(t.get('period_labels', t.get('component_labels', []))))
            actual.extend(data_rows(t))
            for row, row_kind, sources in zip(t['rows'], t['row_kinds'], t['row_sources']):
                if row_kind == 'data':
                    for source in sources:
                        if source.get('line_no') is not None:
                            by_line.setdefault(source['line_no'], []).append(row)
    elif kind == 'IncomeStatement':
        periods = frame.attrs.get('period_labels', [])
        widths.add(len(periods))
        actual = [[str(r['RawItem']), *[str(r[p]) if not pd.isna(r[p]) else '' for p in periods]]
                  for _, r in frame.iterrows() if r.get('RowType') == 'Data' and r.get('SourcePage') == page]
    if len(widths) != 1 or 0 in widths or not actual:
        return issue('Source text amount-row coverage', f'Page {page}', 'NOT_TESTED',
                     'No supported stable amount-column schema. Review this page against the source; table counts alone do not prove coverage.')
    width = next(iter(widths))
    def key(row):
        return label_key(row[0]), tuple(number(v) for v in row[1:])
    expected = Counter()
    for record in result.raw_text_rows:
        if record.get('source_page') != page:
            continue
        matched = _match_desc_first(record.get('raw_text', ''), width)
        if matched and re.search(r'[A-Za-z]', matched[0]):
            source_key = key([matched[0], *matched[1]])
            # A wrapped amount line may contain only the end of its label.
            # Expand it only with an explicit source-line link, never fuzzy text.
            linked = [key(row) for row in by_line.get(record.get('line_no'), [])
                      if label_key(row[0]).endswith(source_key[0]) and key(row)[1] == source_key[1]]
            expected[linked[0] if len(linked) == 1 else source_key] += 1
    if not expected:
        return issue('Source text amount-row coverage', f'Page {page}', 'NOT_TESTED', 'No complete single-line financial rows could be checked independently of table discovery.')
    missing = expected - Counter(key(row) for row in actual)
    detail = (f'{sum(expected.values()) - sum(missing.values())}/{sum(expected.values())} source text rows match labels and complete amount vectors. '
              'Wrapped rows and text-extraction omissions remain outside this check.')
    if missing:
        detail += ' Unmatched source labels: ' + '; '.join(f'{label} ({count})' for (label, _), count in missing.items())
    return issue('Source text amount-row coverage', f'Page {page}', 'WARN' if missing else 'PASS', detail)


def audit_source_cross_statement(statements):
    from audit import _series_value
    from structure import DATE_RE
    checks = []
    cash = statements.get('CashFlowStatement')
    balance = statements.get('BalanceSheet')
    income = statements.get('IncomeStatement')
    cash_tables = recovered_tables(cash, 'CashFlowStatement')
    balance_tables = recovered_tables(balance, 'BalanceSheet')
    if any(validate_grid(t)['Status'] == 'FAIL' for t in cash_tables + balance_tables):
        return [issue('Cross-statement source checks', 'Document', 'NOT_TESTED', 'Resolve source-grid integrity failures before comparing statements.')]

    def units_match(other):
        if other is None:
            return False
        a, b = cash.attrs, other.attrs
        return (a.get('unit_label') not in (None, '', 'reported units')
                and a.get('unit_label') == b.get('unit_label') and a.get('currency', '') == b.get('currency', ''))

    for table in cash_tables:
        rows = data_rows(table)
        for c, period in enumerate(table['period_labels'], 1):
            if 'ended' in period.lower():
                if not any(re.fullmatch(r'cash.*end of (?:period|year)', label_key(r[0])) for r in rows):
                    continue  # supplemental disclosures share a duration, not a rollforward
                actual = unique_value(rows, r'net (?:increase|decrease|increase \(decrease\)|decrease \(increase\)) in net assets (?:resulting )?from operations', c)
                if income is not None and actual is not None:
                    expected = _series_value(income, 'Investment-company change in net assets from operations', period) if units_match(income) else None
                    checks.append(equation('Income = cash-flow result from operations', period, actual, expected,
                                           'Requires the same full duration/date and unit scale.'))
                dates = DATE_RE.findall(period)
                reconciliations = [t for t in cash_tables if len(dates) == 1 and dates[0] in t['period_labels']]
                matching = [(t, t['period_labels'].index(dates[0])+1) for t in reconciliations]
                expected = unique_value(data_rows(matching[0][0]), r'total cash.*', matching[0][1]) if len(matching) == 1 else None
                actual_end = unique_value(rows, r'cash.*end of (?:period|year)', c)
                checks.append(equation('Cash ending = same-date reconciliation', period, actual_end, expected,
                                       'No comparison is made using year alone.'))
            else:
                matching = [t for t in balance_tables if period in t['period_labels']]
                for row in rows:
                    if label_key(row[0]).startswith('total cash'):
                        continue
                    expected = None
                    if len(matching) == 1 and units_match(balance):
                        candidates = [r for r in data_rows(matching[0]) if label_key(r[0]) == label_key(row[0])]
                        if len(candidates) == 1:
                            expected = number(candidates[0][matching[0]['period_labels'].index(period)+1])
                            # Matching source dashes establish preservation, not a numerical equation.
                            if parse_numeric_token(row[c]).status == parse_numeric_token(candidates[0][matching[0]['period_labels'].index(period)+1]).status == 'DASH':
                                checks.append(issue('Cash reconciliation = balance-sheet component', f'{period} / {row[0]}', 'PASS', 'Both source cells report a dash; no numeric value was inferred.'))
                                continue
                    checks.append(equation('Cash reconciliation = balance-sheet component', f'{period} / {row[0]}',
                                           number(row[c]), expected, 'Requires the same complete date, label and unit scale.'))
    return checks
