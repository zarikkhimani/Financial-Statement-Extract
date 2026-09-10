from normalization import parse_numeric_token


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
