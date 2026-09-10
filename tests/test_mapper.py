from mapper import map_concept


def test_deferred_tax_asset_uses_context():
    result = map_concept("BalanceSheet", "Deferred income taxes", "NONCURRENT_ASSET")
    assert result.standard_item == "Deferred Income Taxes (Assets)"
    assert result.confidence >= 0.9


def test_deferred_tax_liability_uses_context():
    result = map_concept("BalanceSheet", "Deferred income taxes", "NONCURRENT_LIABILITY")
    assert result.standard_item == "Deferred Income Taxes (Liabilities)"
    assert result.confidence >= 0.9


def test_gross_margin_is_not_gross_profit():
    result = map_concept("IncomeStatement", "Gross margin", "GENERAL")
    assert result.standard_item == "Gross Margin"
