"""Contextual filing setup and a state-preserving metadata disclosure."""

from tkinter import ttk

from .components import WorkspaceVariables
from .theme import CONTROL_HEIGHT, WorkspaceTheme


class FilingSetupPanel(ttk.Frame):
    def __init__(self, parent, variables: WorkspaceVariables, theme: WorkspaceTheme):
        super().__init__(parent, style="Subtle.TFrame")
        self.theme = theme
        self.details_visible = False
        self.details_modified = False
        self.narrow = False
        self.source_kind = "empty"
        self.columnconfigure(0, weight=1)
        self.entries = {}
        self.pages_field = ttk.Frame(self, style="Subtle.TFrame")
        self.pages_field.columnconfigure(0, weight=1)
        self.pages_field.grid(row=0, column=0, sticky="ew")
        ttk.Label(self.pages_field, text="PDF pages", style="SetupLabel.TLabel").grid(row=0, column=0, sticky="w")
        self.entries["pages"] = ttk.Entry(self.pages_field, textvariable=variables.pages, width=1,
                                          style="Workspace.TEntry", font=theme.fonts["body"])
        self.entries["pages"].grid(row=1, column=0, sticky="ew", pady=(theme.space("xs"), 0))
        self.pages_help = ttk.Label(self, style="SetupMuted.TLabel", wraplength=theme.px(240), justify="left")
        self.pages_help.grid(row=1, column=0, sticky="ew", pady=(theme.space("sm"), theme.space("md")))
        self.pages_help.bind("<Configure>", self._wrap)
        self.details_toggle = ttk.Button(self, text="Show details", style="Workspace.TButton", command=self.toggle_details)
        self.details_toggle.grid(row=2, column=0, sticky="w")
        self.details_form = ttk.Frame(self, style="Subtle.TFrame")
        self.details_form.grid(row=3, column=0, sticky="ew", pady=(theme.space("sm"), 0))
        self.fields = []
        for key, label, choices in (
            ("client_name", "Client name", None),
            ("year", "Fiscal year (optional)", None),
            ("period", "Period", ("Auto", "Annual", "Q1", "Q2", "Q3", "Q4", "Semi-Annual", "Monthly")),
            ("audit_status", "Audit status", ("Audited", "Reviewed", "Compiled", "Company Prepared", "Draft")),
        ):
            field = ttk.Frame(self.details_form, style="Subtle.TFrame")
            field.columnconfigure(0, weight=1)
            field.rowconfigure(1, minsize=theme.px(CONTROL_HEIGHT))
            label_widget = ttk.Label(field, text=label, style="SetupLabel.TLabel", wraplength=theme.px(110))
            label_widget.grid(row=0, column=0, sticky="ew", pady=(0, theme.space("xs")))
            label_widget.bind("<Configure>", self._wrap)
            var = getattr(variables, key)
            if choices:
                control = ttk.Combobox(field, textvariable=var, values=choices, state="readonly", width=1,
                                       style="Workspace.TCombobox", font=theme.fonts["body"])
            else:
                control = ttk.Entry(field, textvariable=var, width=1, style="Workspace.TEntry", font=theme.fonts["body"])
            control.grid(row=1, column=0, sticky="nsew")
            self.entries[key] = control
            self.fields.append(field)
        self.reflow(False)
        self.set_details_visible(False)
        self.set_source_kind("empty")

    @staticmethod
    def _wrap(event):
        event.widget.configure(wraplength=max(60, event.width - 4))

    def set_source_kind(self, kind: str):
        self.source_kind = kind
        if kind == "pdf":
            self.pages_field.grid()
            self.pages_help.configure(text="Auto detects statement pages. For manual selection, use PDF viewer page numbers "
                                      "(e.g. 12,14-16), not printed 10-K page numbers.")
        else:
            focused = self.focus_get()
            if focused is self.entries["pages"]:
                self.details_toggle.focus_set()
            self.pages_field.grid_remove()
            self.pages_help.configure(text="Page selection does not apply to HTML filings. Your PDF page settings are retained."
                                      if kind == "html" else "Choose a PDF or local HTML filing to see its page options.")
        self._layout_pages()

    def _layout_pages(self):
        inline = self.narrow and self.source_kind == "pdf"
        self.columnconfigure(0, weight=0 if inline else 1, minsize=self.theme.px(140) if inline else 0)
        self.columnconfigure(1, weight=1 if inline else 0)
        self.pages_help.grid_configure(row=0 if inline else 1, column=1 if inline else 0,
                                       padx=(self.theme.space("md") if inline else 0, 0))
        self.details_toggle.grid_configure(columnspan=2 if inline else 1)
        self.details_form.grid_configure(columnspan=2 if inline else 1)

    def set_details_modified(self, modified: bool):
        self.details_modified = modified
        self._update_details_label()

    def _update_details_label(self):
        self.details_toggle.configure(text=("Hide details" if self.details_visible else "Show details")
                                      + (" (modified)" if self.details_modified else ""))

    def toggle_details(self):
        self.set_details_visible(not self.details_visible)

    def set_details_visible(self, visible: bool):
        self.details_visible = visible
        if visible:
            self.details_form.grid()
        else:
            focused = self.focus_get()
            if focused is not None and str(focused).startswith(str(self.details_form) + "."):
                self.details_toggle.focus_set()
            self.details_form.grid_remove()
        self._update_details_label()

    def reflow(self, narrow: bool):
        self.narrow = narrow
        self._layout_pages()
        columns = (2 if self.theme.text_scale >= 1.5 else 4) if narrow else 2
        for index in range(4):
            self.details_form.columnconfigure(index, weight=1 if index < columns else 0,
                                               uniform="details" if index < columns else "")
        for index, field in enumerate(self.fields):
            field.grid(row=index // columns, column=index % columns, sticky="new",
                       padx=(0, self.theme.space("sm") if index % columns < columns - 1 else 0),
                       pady=(0, self.theme.space("sm")))
