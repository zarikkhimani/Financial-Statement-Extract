"""Read-only result presentation; no parsing, workbook writes, or file launches."""

from collections import Counter
from dataclasses import dataclass
import tkinter as tk
from tkinter import scrolledtext, ttk


@dataclass(frozen=True)
class ResultSummary:
    statements: tuple[tuple[str, str, str], ...]
    checks: tuple[tuple[str, str, str, str], ...]
    pages: str
    headline: str
    overview: str
    needs_review: bool


def summarize_result(result) -> ResultSummary:
    # Keep the desktop entry point light; extraction dependencies are loaded
    # only once a result is available.
    from financial_statement_extract.workbook_validation import balance_completeness_status

    statements = []
    for index, frame in enumerate(result.statements.values(), 1):
        title = frame.attrs.get("statement_title") or f"Statement {index} (source title unavailable)"
        periods = ", ".join(str(p) for p in frame.attrs.get("period_labels", [])) or "Not identified"
        statements.append((title, str(len(frame)), periods))
    # Source grids can exist without an analytical frame; do not silently omit
    # them or infer that their physical rows are parsed financial rows.
    for table in result.statement_tables:
        if table.get("statement_type") not in result.statements:
            statements.append((table.get("source_title") or "Source table (title unavailable)",
                               "Not parsed", "Source grid · review workbook"))
    checks = []
    for origin, rows in (("Financial", result.financial_audit_rows), ("Extraction", result.extraction_audit_rows)):
        for row in rows:
            checks.append((str(row.get("Status") or "UNKNOWN"), str(row.get("Check") or "Unnamed check"),
                           f"{origin} · {row.get('Scope') or 'Document'}", str(row.get("Detail") or "")))
    if result.page_plan:
        checks.extend(("WARN", "Page selection", "Extraction · Document", warning)
                      for warning in result.page_plan.warnings)
    counts = Counter(row[0].upper() for row in checks)
    warnings = counts["WARN"]
    failures = counts["FAIL"] + counts["ERROR"]
    not_tested = sum(count for status, count in counts.items() if status not in {"PASS", "INFO", "WARN", "FAIL", "ERROR"})
    review = bool(warnings or failures or not_tested or not result.financial_audit_rows or not result.statements)
    overview = (f"{len(result.statements)} parsed statements · {counts['PASS']} passed · "
                f"{warnings} warnings · {failures} failed · {not_tested} not tested/unknown")
    if not result.statements:
        overview += ". No parsed statements; output may be incomplete."
    elif not checks:
        overview += ". No checks reported."
    elif not result.financial_audit_rows:
        overview += ". No financial checks reported."
    pages = str(result.metadata.get("pages_selected") or "")
    if not pages and result.page_plan:
        pages = ", ".join(map(str, result.page_plan.selected_pages))
    pages = pages or ("Not applicable (HTML)" if result.metadata.get("input_type") == "HTML" else "Not reported")
    headline = "Workbook saved · review required" if review else "Workbook saved"
    completeness = balance_completeness_status(result.financial_audit_rows + result.extraction_audit_rows)
    if completeness == 'FAIL':
        headline = "Workbook saved · INCOMPLETE BALANCE SHEET"
        overview += ". The balance sheet is missing source content. See Checks for details."
    elif completeness == 'NOT_TESTED':
        headline = "Workbook saved · balance-sheet completeness unverified"
        overview += ". Balance-sheet completeness could not be established; review against the source."
    return ResultSummary(tuple(statements), tuple(checks), pages,
                         headline,
                         overview, review)


def recovery_hint(message: str, kind: str = "") -> str:
    """Conservative suggestions, not assertions about an unverified root cause."""
    if kind in {"PermissionError", "FileCreateError"}:
        return "Check access to the source and output folder. Close any workbook using the destination, or choose another output folder, then Retry."
    if kind == "FileNotFoundError":
        return "The source or output location is no longer available. Browse to the filing and check the output folder, then Retry."
    if "No financial statements were extracted" in message:
        return "Check the filing and PDF viewer page numbers. Try explicit statement pages. Image-only pages need an OCR workflow outside this app."
    if kind == "ValueError":
        return "Check the source format and PDF page selection. See diagnostics for the exact validation issue, adjust setup, then Retry."
    return "Your settings are retained. Review diagnostics, check the source and output folder, and Retry when ready."


class ReadOnlyText(scrolledtext.ScrolledText):
    """Selectable/copyable native text; application writes remain explicit."""

    def __init__(self, parent, theme, **kwargs):
        colors = theme.colors
        super().__init__(parent, width=1, height=3, wrap="word", font=theme.fonts["body"],
                         background=colors["surface"], foreground=colors["text-primary"],
                         relief="flat", borderwidth=0, highlightthickness=1,
                         highlightbackground=colors["border"], highlightcolor=colors["focus"],
                         state="disabled", takefocus=True, **kwargs)
        self.bind("<Tab>", lambda _event: self._traverse(False))
        self.bind("<Shift-Tab>", lambda _event: self._traverse(True))
        if self.tk.call("tk", "windowingsystem") == "x11":
            self.bind("<ISO_Left_Tab>", lambda _event: self._traverse(True))
        self.bind("<Control-a>", self._select_all)
        self.refresh_theme(theme)

    def _traverse(self, backwards):
        (self.tk_focusPrev() if backwards else self.tk_focusNext()).focus_set()
        return "break"

    def _select_all(self, _event=None):
        self.tag_add("sel", "1.0", "end-1c")
        return "break"

    def refresh_theme(self, theme):
        c = theme.colors
        self.configure(background=c["surface"], foreground=c["text-primary"],
                       highlightbackground=c["border"], highlightcolor=c["focus"],
                       selectbackground=c["selection"], selectforeground=c["selection-text"])

    def insert(self, *args):
        self.configure(state="normal")
        try:
            super().insert(*args)
        finally:
            self.configure(state="disabled")

    def delete(self, *args):
        self.configure(state="normal")
        try:
            super().delete(*args)
        finally:
            self.configure(state="disabled")


class ResultsView(ttk.Frame):
    def __init__(self, parent, theme):
        super().__init__(parent, style="Surface.TFrame")
        self.theme = theme
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self.diagnostics_visible = False
        self.has_summary = False
        self.summary = None
        self.headline = tk.StringVar(master=self, value="Extraction results")
        headline = ttk.Label(self, textvariable=self.headline, style="Section.TLabel", wraplength=400)
        headline.grid(row=0, column=0, sticky="ew")
        headline.bind("<Configure>", lambda event: headline.configure(wraplength=max(80, event.width - 4)))
        self.overview = ttk.Frame(self, style="Surface.TFrame")
        self.overview.columnconfigure(1, weight=1)
        self.output = tk.StringVar(master=self)
        self.pages = tk.StringVar(master=self)
        for row, (label, var) in enumerate((("Workbook", self.output), ("Source pages", self.pages))):
            ttk.Label(self.overview, text=label, style="Muted.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 8))
            ttk.Entry(self.overview, textvariable=var, state="readonly", width=1,
                      style="Workspace.TEntry", font=theme.fonts["body"]).grid(row=row, column=1, sticky="ew")
        self.body = ttk.Frame(self, style="Surface.TFrame")
        self.body.grid(row=2, column=0, sticky="nsew", pady=theme.space("sm"))
        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(0, weight=1)
        self.note = ReadOnlyText(self.body, theme)
        self.diagnostics = ReadOnlyText(self.body, theme)
        self.notebook = ttk.Notebook(self.body, style="Workspace.TNotebook")
        self.notebook.enable_traversal()
        self.tables = {}
        self.details = {}
        for name, headings in (("Statements", ("Source title", "Parsed rows", "Periods")),
                               ("Checks", ("Status", "Check", "Scope", "Detail"))):
            tab = ttk.Frame(self.notebook, style="Surface.TFrame")
            tab.columnconfigure(0, weight=1)
            tab.rowconfigure(0, weight=1)
            tree = ttk.Treeview(tab, columns=headings, show="headings", selectmode="browse",
                                height=3, style="Workspace.Treeview")
            for index, heading in enumerate(headings):
                tree.heading(heading, text=heading)
                tree.column(heading, width=theme.px(240 if index == 0 and name == "Statements" else 140), minwidth=70)
            tree.grid(row=0, column=0, sticky="nsew")
            vertical = ttk.Scrollbar(tab, orient="vertical", command=tree.yview)
            vertical.grid(row=0, column=1, sticky="ns")
            horizontal = ttk.Scrollbar(tab, orient="horizontal", command=tree.xview)
            horizontal.grid(row=1, column=0, sticky="ew")
            tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
            detail = ReadOnlyText(tab, theme)
            detail.bind("<Control-Tab>", lambda _event: self._cycle_tab(1))
            detail.bind("<Control-Shift-Tab>", lambda _event: self._cycle_tab(-1))
            detail.grid(row=2, column=0, columnspan=2, sticky="ew")
            tree.bind("<<TreeviewSelect>>", lambda _event, n=name: self._selection(n))
            self.tables[name] = tree
            self.details[name] = detail
            self.notebook.add(tab, text=name)
        self.footer = ttk.Frame(self, style="Surface.TFrame")
        self.footer.grid(row=3, column=0, sticky="ew")
        self.footer.bind("<Configure>", lambda _event: self.reflow_footer())
        self.toggle = ttk.Button(self.footer, text="Show diagnostics", style="Workspace.TButton", command=self.toggle_diagnostics)
        self.toggle.pack(side="left")
        self.show_note("Add a filing", "Choose or drop a PDF or HTML filing. Results and checks will appear here.")

    def reflow_footer(self):
        buttons = [child for child in self.footer.winfo_children() if child.winfo_manager() == "pack"]
        stacked = sum(child.winfo_reqwidth() + self.theme.space("sm") for child in buttons) > self.footer.winfo_width()
        for button in buttons:
            button.pack_configure(side="top" if stacked else "left", anchor="w")

    def minimum_height(self):
        body = 60
        if self.has_summary:
            tree = self.tables[self.notebook.tab(self.notebook.select(), "text")]
            body = self.notebook.winfo_reqheight() - tree.winfo_reqheight() + 70
        return self.winfo_reqheight() - self.body.winfo_reqheight() + body

    def _cycle_tab(self, direction):
        self.notebook.select((self.notebook.index(self.notebook.select()) + direction) % 2)
        self.focus_content()
        return "break"

    def refresh_theme(self):
        for widget in (self.note, self.diagnostics, *self.details.values()):
            widget.refresh_theme(self.theme)
        for tree in self.tables.values():
            for column in tree["columns"]:
                tree.column(column, minwidth=self.theme.px(70))

    def focus_content(self):
        target = self.diagnostics if self.diagnostics_visible else (
            self.tables[self.notebook.tab(self.notebook.select(), "text")] if self.has_summary else self.note)
        target.focus_set()

    def _selection(self, name):
        tree = self.tables[name]
        selected = tree.selection()
        if selected:
            values = tree.item(selected[0], "values")
            text = "\n".join(f"{heading}: {value}" for heading, value in zip(tree["columns"], values))
            self.details[name].delete("1.0", tk.END)
            self.details[name].insert(tk.END, text)

    def _display(self):
        for widget in (self.note, self.notebook, self.diagnostics):
            widget.grid_remove()
        target = self.diagnostics if self.diagnostics_visible else self.notebook if self.has_summary else self.note
        target.grid(row=0, column=0, sticky="nsew")
        self.toggle.configure(text="Hide diagnostics" if self.diagnostics_visible else "Show diagnostics")
        self.event_generate("<<WorkspaceContentChanged>>", when="tail")

    def toggle_diagnostics(self):
        focused = self.focus_get()
        if focused is not None and str(focused).startswith(str(self.body) + "."):
            self.toggle.focus_set()
        self.diagnostics_visible = not self.diagnostics_visible
        self._display()

    def show_note(self, title, message):
        self.has_summary = False
        self.summary = None
        self.headline.set(title)
        self.overview.grid_remove()
        self.note.delete("1.0", tk.END)
        self.note.insert(tk.END, message)
        self._display()

    def show_result(self, result, output):
        self.summary = summarize_result(result)
        self.has_summary = True
        self.headline.set(self.summary.headline)
        self.output.set(str(output))
        self.pages.set(self.summary.pages)
        self.overview.grid(row=1, column=0, sticky="ew", pady=(self.theme.space("sm"), 0))
        for name, rows in (("Statements", self.summary.statements), ("Checks", self.summary.checks)):
            tree = self.tables[name]
            tree.delete(*tree.get_children())
            for index, row in enumerate(rows):
                tree.insert("", "end", iid=str(index), values=row)
            self.details[name].delete("1.0", tk.END)
            self.details[name].insert(tk.END, self.summary.overview + "\nSelect a row for full details. Reconcile the workbook to the source.")
        self.notebook.select(1 if self.summary.needs_review and self.summary.checks else 0)
        self.diagnostics_visible = False
        self._display()
