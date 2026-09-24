"""Tk draft bindings and source-faithful result-summary rendering."""

from collections.abc import Callable
import tkinter as tk

from .inputs import effective_pages_value
from .state import WorkspaceState


class WorkspaceVariables:
    """Bind draft edits to plain state; callers render state through these variables.

    The view owns the Tk variables. Their write traces synchronously update the
    draft, including typing, dialog selections and drag/drop. Workers never read
    these variables. Programmatic UI changes should use set() as well.
    """

    def __init__(self, root: tk.Tk, state: WorkspaceState):
        self._listeners = []
        self.pdf_path = self._bind(root, state, "input_path")
        self.output_dir = self._bind(root, state, "output_dir")
        self.pages = self._bind(root, state, "pages", effective_pages_value)
        self.client_name = self._bind(root, state, "client_name")
        self.year = self._bind(root, state, "year")
        self.period = self._bind(root, state, "period")
        self.audit_status = self._bind(root, state, "audit_status")

    def subscribe(self, callback: Callable):
        """Notify the view after the plain draft has received each variable edit."""
        self._listeners.append(callback)

    def _bind(self, root, state, field, normalize=str):
        variable = tk.StringVar(master=root, value=getattr(state, field))

        def update(*_args):
            setattr(state, field, normalize(variable.get()))
            for callback in self._listeners:
                callback()

        variable.trace_add("write", update)
        return variable


def render_summary(status, result, output):
    status.delete("1.0", tk.END)
    status.insert(tk.END, f"Saved workbook: {output}\n\n")
    selected_pages = result.metadata.get("pages_selected")
    if selected_pages:
        status.insert(tk.END, f"Source pages: {selected_pages}\n\n")
    status.insert(tk.END, "Parsed statements:\n")
    for index, df in enumerate(result.statements.values(), start=1):
        periods = df.attrs.get("period_labels", [])
        name = df.attrs.get("statement_title") or f"Statement {index} (source title unavailable)"
        status.insert(tk.END, f"  {name}: {len(df)} rows, periods={periods}\n")
    if not result.statements:
        status.insert(tk.END, "  None\n")
    if result.page_plan:
        for warning in result.page_plan.warnings:
            status.insert(tk.END, f"Page selection: {warning}\n")
    status.insert(tk.END, "\nFinancial audit:\n")
    for row in result.financial_audit_rows:
        status.insert(tk.END, f"  [{row.get('Status')}] {row.get('Check')} | {row.get('Scope')}: {row.get('Detail')}\n")
    status.insert(tk.END, "\nExtraction audit:\n")
    for row in result.extraction_audit_rows:
        status.insert(tk.END, f"  [{row.get('Status')}] {row.get('Check')} | {row.get('Scope')}: {row.get('Detail')}\n")
