"""Recover complete, ruled PDF balance sheets without losing wrapped labels."""
from __future__ import annotations

from collections import Counter
import re

import pandas as pd
import pdfplumber

from normalization import parse_numeric_token
from structure import DATE_RE, detect_statement_unit_note, infer_company_name
from financial_statement_extract.table_layout import SINGLE_NUMBER


class BalanceLayoutError(ValueError):
    pass


def _tokens(text):
    return Counter(text.split())


def _validate_body(page, rows, kinds):
    """Check the complete source body independently of the table boundaries."""
    lines = (page.extract_text() or '').splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip().rstrip(':').lower() == 'assets']
    ends = [i for i, line in enumerate(lines) if re.match(r'^See (?:accompanying )?Notes\b', line, re.I)]
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise BalanceLayoutError("The complete balance-sheet source body cannot be bounded reliably.")
    if _tokens(' '.join(lines[starts[0]:ends[0]])) != _tokens(' '.join(v for row in rows for v in row)):
        raise BalanceLayoutError("Recovered balance-sheet rows do not preserve the complete source body.")
    if kinds.count('data') < 2:
        raise BalanceLayoutError("Too few balance-sheet rows to verify.")
    return lines[ends[0]]


def _recover_row_wide_grid(page, table, words):
    """Use date underlines and word positions when shading forms wide cells.

    Horizontal rules supply row boundaries, including wrapped descriptions.
    Only uniquely dated, non-overlapping header rules establish amount columns.
    Source numbers in the description never determine those column boundaries.
    """
    columns = {}
    for edge in page.edges:
        if (abs(edge['top'] - table.bbox[1]) > 1
                or abs(edge.get('bottom', edge['top']) - edge['top']) > 1
                or edge['x1'] - edge['x0'] < 15):
            continue
        header_words = [w for w in words if table.bbox[1] - 35 <= w['top'] < table.bbox[1]
                        and edge['x0'] <= w['x0'] and w['x1'] <= edge['x1']]
        header = ' '.join(w['text'] for w in sorted(header_words, key=lambda w: (w['top'], w['x0'])))
        if DATE_RE.fullmatch(header):
            columns[(round(edge['x0'], 3), round(edge['x1'], 3))] = header
    bounds = sorted(columns)
    periods = [columns[b] for b in bounds]
    if (len(bounds) < 2 or len(set(periods)) != len(periods)
            or bounds[0][0] - table.bbox[0] < page.width * .25
            or any(a[1] > b[0] for a, b in zip(bounds, bounds[1:]))):
        raise BalanceLayoutError("Row-wide balance-sheet cells need distinct, non-overlapping source date columns.")

    rows, kinds, sources = [], [], []
    extracted = table.extract()
    if len(extracted) != len(table.rows):
        raise BalanceLayoutError("Balance-sheet cells and row geometry disagree.")
    for values, physical in zip(extracted, table.rows):
        if len(values) != len(physical.cells):
            raise BalanceLayoutError("Balance-sheet cells and column geometry disagree.")
        row_words = []
        for value, cell in zip(values, physical.cells):
            if cell is None:
                if value and value.strip():
                    raise BalanceLayoutError("A balance-sheet cell has no source geometry.")
                continue
            cell_words = [w for w in words if cell[0] <= (w['x0'] + w['x1']) / 2 < cell[2]
                          and cell[1] <= (w['top'] + w['bottom']) / 2 < cell[3]]
            if _tokens(value or '') != _tokens(' '.join(w['text'] for w in cell_words)):
                raise BalanceLayoutError("A balance-sheet cell disagrees with its source words.")
            row_words.extend(cell_words)
        if not row_words:
            continue
        row_words.sort(key=lambda w: (w['top'], w['x0']))
        right_words = [w for w in row_words if w['x1'] > bounds[0][0]]
        # Full-width section captions can cross the amount area. Numeric or
        # missing-value tokens there must instead pass the full data-row checks.
        has_amount = any(parse_numeric_token(w['text']).status in {'NUMERIC', 'DASH', 'NA', 'NM'}
                         for w in right_words)
        row = [''] * (len(bounds) + 1)
        provenance = []
        for word in row_words:
            col = 0
            if has_amount and word['x1'] > bounds[0][0]:
                owners = [i + 1 for i, (left, right) in enumerate(bounds)
                          if left - 1 <= word['x0'] and word['x1'] <= right + 1]
                if len(owners) != 1:
                    raise BalanceLayoutError("A balance-sheet word crosses date columns.")
                col = owners[0]
            row[col] = (row[col] + ' ' + word['text']).strip()
            provenance.append(dict(column=col, text=word['text'],
                                   bbox=[word['x0'], word['top'], word['x1'], word['bottom']]))
        if has_amount:
            if not row[0]:
                raise BalanceLayoutError("An amount row has no complete source label.")
            if any(not value for value in row[1:]):
                raise BalanceLayoutError("A balance-sheet row has a missing date cell.")
            for value in row[1:]:
                token = parse_numeric_token(value)
                if token.status not in {'NUMERIC', 'DASH', 'NA', 'NM'} or (
                        token.status == 'NUMERIC' and not SINGLE_NUMBER.fullmatch(value)):
                    raise BalanceLayoutError("A balance-sheet amount contains ambiguous numeric text.")
        rows.append(row)
        kinds.append('data' if has_amount else 'section')
        sources.append(provenance)
    note = _validate_body(page, rows, kinds)
    return dict(rows=rows, row_kinds=kinds, row_sources=sources, spans=[],
                period_labels=periods, period_notes=[''] * len(periods),
                column_bounds=[[table.bbox[0], bounds[0][0]], *[list(b) for b in bounds]],
                source_note=note)


def balance_period_grid(page, found):
    """Collapse currency/spacer cells by coordinates, checking full source coverage."""
    candidates = []
    for table in found:
        major = [c for c in table.rows[0].cells if c and c[2] - c[0] >= 15]
        if len(major) >= 2 and major[0][2] - major[0][0] >= page.width * .25:
            candidates.append((table, major))
    if len(candidates) != 1:
        raise BalanceLayoutError("A single complete balance-sheet body could not be established.")
    table, major = candidates[0]
    words = page.extract_words(x_tolerance=1, y_tolerance=2)
    # Shaded rows can be detected as one cell covering all dates. Select a
    # separate verified recovery path; never relax the existing cell checks.
    if any(cell and cell[2] - cell[0] >= table.bbox[2] - table.bbox[0] - 1
           and value and re.search(r'\d', value)
           for physical, values in zip(table.rows, table.extract())
           for cell, value in zip(physical.cells, values)):
        return _recover_row_wide_grid(page, table, words)
    periods = []
    for column in major[1:]:
        header = " ".join(w['text'] for w in words
                          if table.bbox[1] - 35 <= w['top'] < table.bbox[1]
                          and column[0] <= (w['x0'] + w['x1']) / 2 <= column[2])
        dates = DATE_RE.findall(header)
        if len(dates) != 1:
            raise BalanceLayoutError("Each amount column must have one unambiguous source date.")
        periods.append(dates[0])
    if len(set(periods)) != len(periods):
        raise BalanceLayoutError("Balance-sheet source dates are not distinct.")

    rows, kinds, sources = [], [], []
    period_notes = [''] * len(periods)
    extracted = table.extract()
    if len(extracted) != len(table.rows):
        raise BalanceLayoutError("Balance-sheet cells and row geometry disagree.")
    for values, physical in zip(extracted, table.rows):
        if len(values) != len(physical.cells):
            raise BalanceLayoutError("Balance-sheet cells and column geometry disagree.")
        row = [''] * len(major)
        provenance = []
        for value, cell in zip(values, physical.cells):
            if not value or not value.strip():
                continue
            if cell is None:
                raise BalanceLayoutError("A balance-sheet cell has no source geometry.")
            owners = [i for i, col in enumerate(major) if cell[0] >= col[0] - 1 and cell[2] <= col[2] + 1]
            if len(owners) != 1:
                raise BalanceLayoutError("A balance-sheet cell crosses date columns.")
            col = owners[0]
            cell_words = [w for w in words if cell[0] <= (w['x0'] + w['x1']) / 2 <= cell[2]
                          and cell[1] <= (w['top'] + w['bottom']) / 2 <= cell[3]]
            if _tokens(value) != _tokens(' '.join(w['text'] for w in cell_words)):
                raise BalanceLayoutError("A balance-sheet cell disagrees with its source words.")
            row[col] = (row[col] + ' ' + ' '.join(value.split())).strip()
            provenance.append(dict(column=col, text=value, bbox=list(cell)))
        if not any(row):
            continue
        if not row[0] and all(v.lower() in {'', '(unaudited)', '(audited)'} for v in row[1:]):
            for i, value in enumerate(row[1:]):
                if period_notes[i] and value:
                    raise BalanceLayoutError("Repeated audit-status headers are ambiguous.")
                period_notes[i] = value or period_notes[i]
            continue
        if not row[0]:
            raise BalanceLayoutError("An amount row has no complete source label.")
        kind = 'section'
        if any(row[1:]):
            if any(not v for v in row[1:]):
                raise BalanceLayoutError("A balance-sheet row has a missing date cell.")
            for value in row[1:]:
                token = parse_numeric_token(value)
                if token.status not in {'NUMERIC', 'DASH', 'NA', 'NM'} or (token.status == 'NUMERIC' and not SINGLE_NUMBER.fullmatch(value)):
                    raise BalanceLayoutError("A balance-sheet amount contains ambiguous numeric text.")
            kind = 'data'
        rows.append(row)
        kinds.append(kind)
        sources.append(provenance)

    # Check all body tokens independently of table discovery, including text below
    # its bounding box. Wrapped stock labels interleave with amounts in page text,
    # so compare token multiplicity here and verify positions per cell above.
    note = _validate_body(page, rows, kinds)
    return dict(rows=rows, row_kinds=kinds, row_sources=sources, spans=[],
                period_labels=periods, period_notes=period_notes,
                column_bounds=[[c[0], c[2]] for c in major],
                source_note=note)


def recover_pdf_balance_tables(pdf_path, tables, statements, page_plan):
    eligible = [p for p in page_plan.pages if p.page in page_plan.selected_pages and p.statement_type == 'BalanceSheet']
    if not eligible:
        return tables, []
    issues, replacements = [], {}
    try:
        if len(eligible) != 1 or set(eligible[0].statement_types or ('BalanceSheet',)) != {'BalanceSheet'}:
            raise BalanceLayoutError("Balance-sheet page ownership or continuation is ambiguous.")
        record = eligible[0]
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[record.page - 1]
            grid = balance_period_grid(page, page.find_tables())
            text_rows = [{'raw_text': line} for line in page.extract_text().splitlines()]
        unit = detect_statement_unit_note(text_rows)
        grid.update(table_id=f'P{record.page:04d}_BALANCE_GEOMETRY', source_page=record.page, source_order=0,
                    statement_type='BalanceSheet', source_title=record.source_title, flavor='balance_geometry',
                    source_context=[unit['raw_unit_note']] if unit.get('raw_unit_note') else [],
                    source_table_ids=[t['table_id'] for t in tables if t['source_page'] == record.page and t['statement_type'] == 'BalanceSheet'])
        replacements[record.page] = grid
    except BalanceLayoutError as exc:
        return tables, [{'Check': 'Balance sheet layout', 'Scope': 'BalanceSheet', 'Status': 'WARN',
                         'Detail': f'{exc} Original grids retained; source review is required.'}]
    result = [t for t in tables if not (t['source_page'] in replacements and t['statement_type'] == 'BalanceSheet')]
    result.extend(replacements.values())
    result.sort(key=lambda t: (t.get('source_page') or 0, t.get('source_order') or 0))
    if 'BalanceSheet' not in statements:
        statements['BalanceSheet'] = pd.DataFrame()
    statements['BalanceSheet'].attrs.update(source_tables=[grid], statement_type='BalanceSheet',
                                            statement_title=record.source_title, company_name=infer_company_name(text_rows),
                                            period_labels=grid['period_labels'], **unit)
    issues.append({'Check': 'Balance sheet layout', 'Scope': f'Page {record.page}', 'Status': 'INFO',
                   'Detail': f"Recovered {grid['row_kinds'].count('data')} rows under {len(grid['period_labels'])} source dates. "
                   'Full body text and cell positions verified; raw tables retained.'})
    return result, issues
