"""Optional synchronous pipeline progress; no UI or extraction dependencies.

Events mark entry into work, not its completion or a percentage. Reporters run
on the caller's thread and should return promptly. Reporter exceptions propagate;
they are never silently ignored. GUI reporters must enqueue, not touch widgets.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum


class ExtractionStage(str, Enum):
    VALIDATING = "Validating filing"
    DETECTING_PAGES = "Detecting and reviewing PDF pages"
    EXTRACTING_TABLES = "Extracting tables"
    PARSING = "Parsing statements"
    AUDITING = "Running checks"
    WRITING = "Writing workbook"


@dataclass(frozen=True)
class ProgressEvent:
    stage: ExtractionStage
    detail: str = ""


ProgressReporter = Callable[[ProgressEvent], None]


def report(reporter: ProgressReporter | None, stage: ExtractionStage, detail: str = "") -> None:
    if reporter is not None:
        reporter(ProgressEvent(stage, detail))
