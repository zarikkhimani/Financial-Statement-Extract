import pytest

from normalization import classify_unit_note, parse_numeric_token


def test_parentheses_are_negative():
    token = parse_numeric_token("($1,250.50)")
    assert token.status == "NUMERIC"
    assert token.value == -1250.50
    assert token.currency == "$"


def test_standard_parentheses_are_negative():
    token = parse_numeric_token("(1,250.50)")
    assert token.status == "NUMERIC"
    assert token.value == -1250.50


def test_dash_is_not_zero():
    token = parse_numeric_token("-")
    assert token.status == "DASH"
    assert token.value is None


def test_em_dash_is_not_zero():
    token = parse_numeric_token("\u2014")
    assert token.status == "DASH"
    assert token.value is None


def test_percent_is_decimal_and_flagged():
    token = parse_numeric_token("15.2%")
    assert token.status == "NUMERIC"
    assert abs(token.value - 0.152) < 1e-12
    assert token.is_percent


def test_na_and_nm_are_preserved():
    assert parse_numeric_token("N/A").status == "NA"
    assert parse_numeric_token("NM").status == "NM"


@pytest.mark.parametrize('note, label, factor', [
    ('(In millions, except number of shares, which are reflected in thousands, and par value)', 'millions', 1_000_000),
    ('(In billions, except shares reported in millions and per-share data)', 'billions', 1_000_000_000),
    ('(In thousands, except share and per share data)', 'thousands', 1_000),
    ('Amounts in millions, except per-share amounts', 'millions', 1_000_000),
    ('$000', 'thousands', 1_000), ('$mm', 'millions', 1_000_000), ('$bn', 'billions', 1_000_000_000),
    ('(Except number of shares in thousands)', 'reported units', 1),
    ('(In millions or billions)', 'reported units', 1),
])
def test_monetary_units_are_not_taken_from_exceptions(note, label, factor):
    result = classify_unit_note(note)
    assert result['unit_label'] == label
    assert result['scale_factor'] == factor


def test_explicit_share_scale_is_recorded_separately_without_inferring_unspecified_scale():
    result = classify_unit_note('(In millions, except number of shares, which are reflected in thousands, and par value)')
    assert result['share_unit_label'] == 'thousands'
    assert result['share_scale_factor'] == 1_000
    assert 'par value' in result['unit_exceptions']
    unspecified = classify_unit_note('(In thousands, except share and per share data)')
    assert 'share_scale_factor' not in unspecified
