from __future__ import annotations

from dataclasses import dataclass, asdict, field
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
    internal_id: str = ""
    analytical_family: str = ""
    relationship: str = "unmapped"

    @property
    def is_mapped(self) -> bool:
        return self.rule != "unmapped"


@dataclass(frozen=True)
class StatementPage:
    page: int
    role: str
    statement_type: str = ""
    source_title: str = ""
    confidence: float = 0.0
    evidence: tuple[str, ...] = ()
    statement_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class StatementPagePlan:
    source_path: str
    detection_source: str
    requested_pages: tuple[int, ...]
    selected_pages: tuple[int, ...]
    suggested_pages: tuple[int, ...]
    pages: tuple[StatementPage, ...]
    review_required: bool = False
    warnings: tuple[str, ...] = ()
    include_investment_schedules: bool = True
    guidance_source: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class PageSelectionReviewRequired(ValueError):
    def __init__(self, plan: StatementPagePlan):
        self.plan = plan
        super().__init__(
            f"Review the {len(plan.requested_pages)} selected PDF pages before extraction. "
            + (" ".join(plan.warnings) if plan.detection_source.startswith("auto") else
               "The suggested selection preserves schedules and removes only clearly blank/footer-only pages.")
        )


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
    page_plan: StatementPagePlan | None = field(default=None)
    statement_tables: list[dict] = field(default_factory=list)
    experimental_raw_table_cells: list[dict] = field(default_factory=list)
    experimental_normalized_table_cells: list[dict] = field(default_factory=list)
    experimental_audit_rows: list[dict] = field(default_factory=list)
