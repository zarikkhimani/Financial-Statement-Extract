from __future__ import annotations

from collections.abc import Mapping
from os import PathLike
from pathlib import Path

from models import ExtractionResult


def extract_filing(
    input_path: str | PathLike[str],
    *,
    pages: str = "auto",
    metadata: Mapping[str, object] | None = None,
    output_dir: str | PathLike[str] | None = None,
    allow_nonlocal_paths: bool = False,
) -> tuple[ExtractionResult, Path]:
    """Extract a PDF or HTML filing and write a reviewable Excel workbook.

    Nonlocal paths are rejected by default. Set ``allow_nonlocal_paths`` only
    when the caller has an explicit, separately enforced network-path policy.
    """
    from pipeline import extract_filing_to_workbook

    return extract_filing_to_workbook(
        str(input_path),
        pages,
        dict(metadata or {}),
        str(output_dir) if output_dir is not None else None,
        allow_nonlocal_paths=allow_nonlocal_paths,
    )


extract_to_excel = extract_filing
