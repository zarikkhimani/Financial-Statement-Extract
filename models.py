from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass(frozen=True)
class ParsedToken:
    raw_text: str
    normalized_text: str
    value: Optional[float]
    status: str
    currency: str = ""
    is_percent: bool = False
    is_ratio: bool = False
    precision: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class MappingResult:
    raw_item: str
    standard_item: str
    category: str
    subcategory: str
    confidence: float
    rule: str

    @property
    def is_mapped(self) -> bool:
        return self.rule != "unmapped"


@dataclass
class ExtractionResult:
    metadata: dict
    raw_text_rows: list[dict]
    raw_table_cells: list[dict]
    normalized_table_cells: list[dict]
    extraction_audit_rows: list[dict]
    statements: dict
    parsed_cells: list[dict]
    financial_audit_rows: list[dict]
    unmapped_rows: list[dict]
