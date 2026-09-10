from __future__ import annotations

import re
from difflib import SequenceMatcher

from config import RULES_BY_STATEMENT, ConceptRule
from models import MappingResult
from normalization import normalize_financial_text


def _norm(text: str) -> str:
    text = normalize_financial_text(text).lower()
    text = text.replace("’", "'")
    text = re.sub(r"[^a-z0-9%/()'& -]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _context_matches(rule: ConceptRule, context: str) -> bool:
    if not rule.contexts:
        return True
    ctx = context.upper().strip()
    return any(allowed in ctx for allowed in rule.contexts)


def map_concept(statement_type: str, raw_item: str, context: str = "") -> MappingResult:
    rules = RULES_BY_STATEMENT.get(statement_type, ())
    raw_norm = _norm(raw_item)
    if not raw_norm:
        return MappingResult(raw_item, raw_item, "", "", 0.0, "unmapped")

    best = None
    best_score = 0.0
    best_rule_name = "unmapped"

    for rule in rules:
        context_ok = _context_matches(rule, context)
        if rule.contexts and not context_ok:
            continue

        for alias in rule.aliases:
            alias_norm = _norm(alias)
            if not alias_norm:
                continue

            score = 0.0
            rule_name = "unmapped"
            if raw_norm == alias_norm:
                score = 1.0
                rule_name = "exact_alias"
            elif not rule.exact_only:
                raw_tokens = set(raw_norm.split())
                alias_tokens = set(alias_norm.split())
                if alias_tokens and alias_tokens.issubset(raw_tokens):
                    score = 0.90 if context_ok else 0.82
                    rule_name = "token_subset_context" if context_ok else "token_subset"
                elif alias_norm in raw_norm:
                    score = 0.86 if context_ok else 0.78
                    rule_name = "substring_context" if context_ok else "substring"
                else:
                    ratio = SequenceMatcher(None, raw_norm, alias_norm).ratio()
                    if ratio >= 0.90:
                        score = min(0.79, ratio * 0.82)
                        rule_name = "fuzzy"

            if rule.contexts and context_ok and score > 0:
                score = min(1.0, score + 0.03)

            if score > best_score:
                best_score = score
                best = rule
                best_rule_name = rule_name

    if best is None or best_score < 0.70:
        return MappingResult(raw_item, raw_item, "", "", 0.0, "unmapped")

    return MappingResult(
        raw_item=raw_item,
        standard_item=best.standard_name,
        category=best.category,
        subcategory=best.subcategory,
        confidence=round(best_score, 3),
        rule=best_rule_name,
    )
