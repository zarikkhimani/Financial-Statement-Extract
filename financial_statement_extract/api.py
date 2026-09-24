from __future__ import annotations

from collections.abc import Mapping
from os import PathLike
from pathlib import Path

from models import ExtractionResult
from .progress import ProgressReporter


def extract_filing(
    input_path: str | PathLike[str],
    *,
    pages: str = "auto",
    metadata: Mapping[str, object] | None = None,
    output_dir: str | PathLike[str] | None = None,
    allow_nonlocal_paths: bool = False,
    page_policy: str = "review",
    table_strategy: str = "adaptive",
    progress: ProgressReporter | None = None,
) -> tuple[ExtractionResult, Path]:
    """Extract a PDF or HTML filing and write a reviewable Excel workbook.

    Manual PDF selections over 50 pages raise PageSelectionReviewRequired unless
    page_policy is explicitly "exact" or "suggested". The exception carries the
    text-only selection plan; expensive table extraction has not started.

    Nonlocal paths are rejected by default. Set ``allow_nonlocal_paths`` only
    when the caller has an explicit, separately enforced network-path policy.

    Optional ``progress`` receives immutable stage-entry events on the calling
    thread. It must return promptly; exceptions propagate. No percentages or
    completion guarantees are implied by a stage event.
    """
    from pipeline import extract_filing_to_workbook

    options = {"allow_nonlocal_paths": allow_nonlocal_paths}
    if page_policy != "review":
        options["page_policy"] = page_policy
    if table_strategy != "adaptive":
        options["table_strategy"] = table_strategy
    if progress is not None:
        options["progress"] = progress
    return extract_filing_to_workbook(
        str(input_path),
        pages,
        dict(metadata or {}),
        str(output_dir) if output_dir is not None else None,
        **options,
    )


extract_to_excel = extract_filing
