from __future__ import annotations

import re
from typing import Optional

from models import ParsedToken

DASH_TOKENS = {"-", "\u2013", "\u2014", "\u2212"}
NA_TOKENS = {"n/a", "na", "n.a.", "n.a", "not applicable"}
NM_TOKENS = {"nm", "n.m.", "n.m", "not meaningful"}
CURRENCY_SYMBOLS = "$€£¥"


def normalize_financial_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\u00a0", " ").replace("\u202f", " ")
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _decimal_precision(text: str) -> Optional[int]:
    match = re.search(r"\.(\d+)", text)
    return len(match.group(1)) if match else 0


def parse_numeric_token(value: object) -> ParsedToken:
    raw = "" if value is None else str(value)
    text = normalize_financial_text(value)

    if text == "":
        return ParsedToken(raw, text, None, "BLANK")

    lower = text.lower()
    if lower in DASH_TOKENS:
        return ParsedToken(raw, text, None, "DASH")
    if lower in NA_TOKENS:
        return ParsedToken(raw, text, None, "NA")
    if lower in NM_TOKENS:
        return ParsedToken(raw, text, None, "NM")

    currency = ""
    # Support both $(1,250) and ($1,250).
    if text and text[0] in CURRENCY_SYMBOLS:
        currency = text[0]
        text = text[1:].strip()
    elif text.startswith("S ") or (text.startswith("S") and len(text) > 1 and text[1].isdigit()):
        # Common OCR artifact where "$" becomes "S". We flag the source token but do not infer a currency.
        text = text[1:].strip()

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1].strip()

    if text and text[0] in CURRENCY_SYMBOLS:
        currency = currency or text[0]
        text = text[1:].strip()

    is_percent = text.endswith("%")
    is_ratio = text.lower().endswith("x")
    if is_percent or is_ratio:
        text = text[:-1].strip()

    text = text.replace(",", "").replace(" ", "")
    text = text.replace("\u2212", "-")

    if text in DASH_TOKENS:
        return ParsedToken(raw, normalize_financial_text(value), None, "DASH", currency, is_percent, is_ratio)

    try:
        number = float(text)
        if negative:
            number = -abs(number)
        if is_percent:
            number /= 100.0
        return ParsedToken(
            raw_text=raw,
            normalized_text=normalize_financial_text(value),
            value=number,
            status="NUMERIC",
            currency=currency,
            is_percent=is_percent,
            is_ratio=is_ratio,
            precision=_decimal_precision(text),
        )
    except ValueError:
        return ParsedToken(raw, normalize_financial_text(value), None, "PARSE_ERROR", currency, is_percent, is_ratio)


def classify_unit_note(text: str) -> dict:
    normalized = normalize_financial_text(text).lower()
    # A share-count exception must not override the statement's monetary scale.
    # Keep the exception separately; reported numeric values are never rescaled.
    clauses = re.split(r"\bexcept\b", normalized, maxsplit=1)
    monetary_note = clauses[0]
    scale_patterns = (
        (r"\bthousands\b|\$000\b|\b000s\b", "thousands", 1_000),
        (r"\bmillions\b|\$mm\b", "millions", 1_000_000),
        (r"\bbillions\b|\$bn\b", "billions", 1_000_000_000),
    )
    scales = [(label, factor) for pattern, label, factor in scale_patterns
              if re.search(pattern, monetary_note)]
    scale_label = "reported units"
    scale_factor = 1
    if len(scales) == 1:
        scale_label, scale_factor = scales[0]

    currency = ""
    if "usd" in normalized or "$" in text:
        currency = "USD"
    elif "eur" in normalized or "€" in text:
        currency = "EUR"
    elif "gbp" in normalized or "£" in text:
        currency = "GBP"

    result = {"unit_label": scale_label, "scale_factor": scale_factor, "currency": currency}
    if len(clauses) == 2:
        result["unit_exceptions"] = clauses[1].strip().rstrip(')')
        share_scale = re.search(
            r"\b(?:number of shares|share counts|shares outstanding|shares)"
            r"(?:\s*,?\s*(?:which are|are)?\s*(?:reflected|reported|expressed))?"
            r"\s+in\s+(thousands|millions|billions)\b", clauses[1],
        )
        if share_scale:
            label = share_scale.group(1)
            result["share_unit_label"] = label
            result["share_scale_factor"] = next(factor for _, unit, factor in scale_patterns if unit == label)
    return result
