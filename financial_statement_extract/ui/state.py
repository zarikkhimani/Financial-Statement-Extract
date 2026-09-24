"""Widget-independent draft settings and immutable extraction requests."""

from dataclasses import dataclass

from path_policy import normalize_path


@dataclass(frozen=True)
class JobRequest:
    """A snapshot of one run. All stored values are immutable strings."""

    input_path: str
    pages: str
    output_dir: str
    client_name: str = ""
    year: str = ""
    period: str = "Auto"
    audit_status: str = "Audited"
    page_policy: str = "review"

    @property
    def metadata(self) -> dict[str, str]:
        # Give each runner its own mutable dictionary, never the stored request.
        return {
            "client_name": self.client_name,
            "year": self.year,
            "period": self.period,
            "audit_status": self.audit_status,
        }


@dataclass
class WorkspaceState:
    """Current editable draft, independent of Tk variables and running jobs.

    Pages stores the effective value ("auto" for the UI placeholder). Other
    fields retain the user's draft text until a request is created. This is
    in-memory state only; no session persistence or job history is implied.
    """

    input_path: str = ""
    output_dir: str = ""
    pages: str = "auto"
    client_name: str = ""
    year: str = ""
    period: str = "Auto"
    audit_status: str = "Audited"

    def draft_key(self) -> tuple[str, ...]:
        """Compare UI drafts without filesystem access or extraction imports.

        Keep the saved PDF page draft even while an HTML source is selected.
        This key tracks entered settings, independently of preflight page policy.
        """
        return (self.input_path.strip(), self.output_dir.strip(), self.pages.strip() or "auto",
                *self.metadata().values())

    def metadata(self) -> dict[str, str]:
        return {
            "client_name": self.client_name.strip(),
            "year": self.year.strip(),
            "period": self.period.strip(),
            "audit_status": self.audit_status.strip(),
        }

    def to_request(self) -> JobRequest:
        """Normalize local paths and copy the draft at the moment of submission."""
        if not self.input_path.strip():
            raise ValueError("Choose or drop a PDF or HTML filing first.")
        source = normalize_path(self.input_path.strip())
        destination = normalize_path(self.output_dir.strip() or source.parent)
        return JobRequest(
            input_path=str(source),
            pages=self.pages.strip() or "auto",
            output_dir=str(destination),
            **self.metadata(),
        )
