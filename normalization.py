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
    scale_label = "reported units"
    scale_factor = 1
    if "in thousands" in normalized or "$000" in normalized or "000s" in normalized:
        scale_label = "thousands"
        scale_factor = 1_000
    elif "in millions" in normalized or "$mm" in normalized or "millions" in normalized:
        scale_label = "millions"
        scale_factor = 1_000_000
    elif "in billions" in normalized or "$bn" in normalized or "billions" in normalized:
        scale_label = "billions"
        scale_factor = 1_000_000_000

    currency = ""
    if "usd" in normalized or "$" in text:
        currency = "USD"
    elif "eur" in normalized or "€" in text:
        currency = "EUR"
    elif "gbp" in normalized or "£" in text:
        currency = "GBP"

    return {"unit_label": scale_label, "scale_factor": scale_factor, "currency": currency}
