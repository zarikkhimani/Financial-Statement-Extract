"""Reusable workspace layout; no job, document, or filesystem operations."""

from collections.abc import Callable
import tkinter as tk
from tkinter import ttk

from .components import WorkspaceVariables
from .theme import CONTROL_HEIGHT, NARROW_BREAKPOINT, SETUP_WIDTH, WorkspaceTheme, responsive_text_tier
from .viewport import WorkspaceViewport


class WorkspaceShell(ttk.Frame):
    """Compose persistent context and controls around a replaceable work surface.

    Callers populate `surface` and `secondary_actions`. They own the meanings of
    draft changes, status, and action availability; this class only displays them.
    """

    def __init__(self, parent, variables: WorkspaceVariables, theme: WorkspaceTheme, *, setup_factory: Callable | None = None):
        super().__init__(parent, style="Workspace.TFrame")
        self.theme = theme
        self.variables = variables
        self.setup_visible = True
        self.setup_modified = False
        self._setup_preferences = {False: True, True: False}
        self.narrow = False
        self.text_size_tier = "normal"
        self._layout_ready = False
        self.minimum_surface_height = lambda: 0
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self._build_header()
        self.viewport = WorkspaceViewport(self, theme)
        self.viewport.grid(row=1, rowspan=2, column=0, sticky="nsew", padx=theme.space("lg"))
        self.main = self.viewport.content
        self.main.columnconfigure(0, weight=1)
        self.main.rowconfigure(1, weight=1)
        self._build_context()
        self.body = ttk.Frame(self.main, style="Surface.TFrame")
        self.body.grid(row=1, column=0, sticky="nsew")
        self.setup = ttk.Frame(self.body, style="Subtle.TFrame", padding=theme.space("md"))
        self.setup.columnconfigure(0, weight=1)
        self.setup_title = ttk.Label(self.setup, text="Extraction setup", style="SetupTitle.TLabel")
        self.setup_title.grid(row=0, column=0, sticky="w", pady=(0, theme.space("md")))
        self.setup_panel = setup_factory(self.setup, variables, theme) if setup_factory else None
        if self.setup_panel is not None:
            self.setup_panel.grid(row=1, column=0, sticky="ew")
            self.setup_entries = self.setup_panel.entries
            self.pages_help = self.setup_panel.pages_help
        else:
            self.setup_form = ttk.Frame(self.setup, style="Subtle.TFrame")
            self.setup_form.grid(row=1, column=0, sticky="ew")
            self._build_fields()
            self.pages_help = ttk.Label(
                self.setup, text="Use PDF viewer page numbers, not the page numbers printed in the filing.",
                style="SetupMuted.TLabel", wraplength=theme.px(230), justify="left")
            self.pages_help.grid(row=2, column=0, sticky="ew", pady=(theme.space("xs"), 0))
            self.pages_help.bind("<Configure>", self._wrap_label)
        self.surface = ttk.Frame(self.body, style="Surface.TFrame", padding=theme.space("lg"))
        self.viewport.minimum_height = self._minimum_body_height
        self.setup.bind("<Configure>", self.viewport.sync)
        self.surface.bind("<Configure>", self.viewport.sync)
        self.context.bind("<Configure>", self.viewport.sync)
        self._build_actions()
        self._build_status()
        self.bind("<Configure>", self._on_resize)
        self._layout(False)

    def _build_header(self):
        t = self.theme
        header = ttk.Frame(self, style="Workspace.TFrame", padding=(t.space("lg"), t.space("md")))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        self.title_label = ttk.Label(header, text="Financial Statement Extract", style="Title.TLabel", wraplength=600)
        self.title_label.grid(row=0, column=0, sticky="ew")
        self.title_label.bind("<Configure>", self._wrap_label)
        self.caption = ttk.Label(header, text="Filing workspace", style="Caption.TLabel")
        self.caption.grid(row=1, column=0, sticky="w", pady=(t.space("xs"), 0))
        self.setup_toggle = ttk.Button(header, text="Hide setup", style="Workspace.TButton", command=self.toggle_setup)
        self.setup_toggle.grid(row=0, column=1, rowspan=2, sticky="e", padx=(t.space("md"), 0))

    def _build_context(self):
        t = self.theme
        context = ttk.Frame(self.main, style="Surface.TFrame", padding=(t.space("lg"), t.space("md")))
        self.context = context
        context.grid(row=0, column=0, sticky="ew", pady=(0, t.space("sm")))
        context.columnconfigure(1, weight=1)
        ttk.Label(context, text="Source filing", style="Muted.TLabel").grid(row=0, column=0, sticky="w", padx=(0, t.space("md")))
        self.source_entry = ttk.Entry(context, textvariable=self.variables.pdf_path, state="readonly", width=1,
                                      style="Workspace.TEntry", font=t.fonts["body"])
        self.source_entry.grid(row=0, column=1, sticky="ew")
        self.source_detail = tk.StringVar(master=self, value="PDF or local HTML")
        self.source_detail_label = ttk.Label(context, textvariable=self.source_detail, style="Muted.TLabel", wraplength=600)
        self.source_detail_label.grid(row=1, column=1, sticky="ew", pady=(t.space("xs"), 0))
        self.source_detail_label.bind("<Configure>", self._wrap_label)

    def enable_filing_controls(self, choose_source: Callable, choose_output: Callable):
        """Add live file/folder controls without making the shell perform file I/O."""
        t = self.theme
        self.source_browse = ttk.Button(self.context, text="Filing…", command=choose_source, style="Workspace.TButton")
        self.source_browse.grid(row=0, column=2, padx=(t.space("sm"), 0))
        ttk.Label(self.context, text="Output folder", style="Muted.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, t.space("md")), pady=(t.space("sm"), 0))
        self.output_entry = ttk.Entry(self.context, textvariable=self.variables.output_dir, width=1,
                                      style="Workspace.TEntry", font=t.fonts["body"])
        self.output_entry.grid(row=2, column=1, sticky="ew", pady=(t.space("sm"), 0))
        self.output_browse = ttk.Button(self.context, text="Folder…", command=choose_output, style="Workspace.TButton")
        self.output_browse.grid(row=2, column=2, padx=(t.space("sm"), 0), pady=(t.space("sm"), 0))
        self.draft_notice = tk.StringVar(master=self)
        notice = ttk.Label(self.context, textvariable=self.draft_notice, style="Muted.TLabel", wraplength=500)
        notice.grid(row=3, column=1, columnspan=2, sticky="ew", pady=(t.space("xs"), 0))
        notice.bind("<Configure>", self._wrap_label)

    def _build_fields(self):
        self.fields = []
        self.setup_entries = {}
        for key, label, variable, choices in (
            ("pages", "PDF pages", self.variables.pages, None),
            ("output_dir", "Output folder", self.variables.output_dir, None),
            ("client_name", "Client name", self.variables.client_name, None),
            ("year", "Fiscal year (optional)", self.variables.year, None),
            ("period", "Period", self.variables.period, ("Auto", "Annual", "Q1", "Q2", "Q3", "Q4", "Semi-Annual", "Monthly")),
            ("audit_status", "Audit status", self.variables.audit_status, ("Audited", "Reviewed", "Compiled", "Company Prepared", "Draft")),
        ):
            field = ttk.Frame(self.setup_form, style="Subtle.TFrame")
            field.columnconfigure(0, weight=1)
            field.rowconfigure(1, minsize=self.theme.px(CONTROL_HEIGHT))
            ttk.Label(field, text=label, style="SetupLabel.TLabel").grid(
                row=0, column=0, sticky="w", pady=(0, self.theme.px(2)))
            if choices:
                control = ttk.Combobox(field, textvariable=variable, values=choices, state="readonly",
                                       width=1, style="Workspace.TCombobox", font=self.theme.fonts["body"])
            else:
                control = ttk.Entry(field, textvariable=variable, width=1, style="Workspace.TEntry",
                                    font=self.theme.fonts["body"])
            control.grid(row=1, column=0, sticky="nsew")
            self.fields.append(field)
            self.setup_entries[key] = control

    def _build_actions(self):
        t = self.theme
        ttk.Separator(self).grid(row=3, column=0, sticky="ew", padx=t.space("lg"))
        self.action_bar = ttk.Frame(self, style="Surface.TFrame", padding=(t.space("lg"), t.space("md")))
        self.action_bar.grid(row=4, column=0, sticky="ew", padx=t.space("lg"))
        self.action_bar.columnconfigure(0, weight=1)
        self.action_info = tk.StringVar(master=self, value="No result loaded")
        self.action_info_label = ttk.Label(self.action_bar, textvariable=self.action_info, style="Muted.TLabel", wraplength=300)
        self.action_info_label.grid(row=0, column=0, sticky="ew", padx=(0, t.space("sm")))
        self.action_info_label.bind("<Configure>", self._wrap_label)
        self.secondary_actions = ttk.Frame(self.action_bar, style="Surface.TFrame")
        self.secondary_actions.grid(row=0, column=1, padx=(0, t.space("sm")))
        self.primary_button = ttk.Button(self.action_bar, text="Extract to Excel", style="Accent.TButton",
                                         default="active" if t.system_colors else "normal")
        self.primary_button.grid(row=0, column=2, sticky="e")
        self.disabled_reason = tk.StringVar(master=self)
        self.reason_label = ttk.Label(self.action_bar, textvariable=self.disabled_reason, style="Muted.TLabel", wraplength=500)
        self.reason_label.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(t.space("sm"), 0))
        self.reason_label.bind("<Configure>", self._wrap_label)
        self.reason_label.grid_remove()

    def _build_status(self):
        t = self.theme
        self.status_text = tk.StringVar(master=self, value="Ready")
        self.status_label = ttk.Label(self, textvariable=self.status_text, style="Status.TLabel",
                                      padding=(t.space("lg"), t.space("sm")), wraplength=700)
        self.status_label.grid(row=5, column=0, sticky="ew")
        self.status_label.bind("<Configure>", self._wrap_label)

    def set_primary_action(self, text: str, command: Callable, *, enabled: bool = True, reason: str = ""):
        if not enabled and not reason:
            raise ValueError("A disabled primary action needs a visible explanation.")
        self.primary_button.configure(text=text, command=command)
        self.primary_button.state(["!disabled"] if enabled else ["disabled"])
        self.disabled_reason.set(reason if not enabled else "")
        if enabled:
            self.reason_label.grid_remove()
        else:
            self.reason_label.grid()
        self._flow_actions()

    def set_status(self, text: str, tone: str = "neutral"):
        style = {"neutral": "Status", "warning": "Warning", "error": "Error", "success": "Success"}[tone]
        self.status_text.set(text)
        self.status_label.configure(style=f"{style}.TLabel")

    def set_setup_modified(self, modified: bool):
        self.setup_modified = modified
        self._update_toggle()

    def _update_toggle(self):
        label = "Hide setup" if self.setup_visible else "Show setup"
        self.setup_toggle.configure(text=label + (" (modified)" if self.setup_modified else ""))

    def toggle_setup(self):
        self.set_setup_visible(not self.setup_visible)

    def set_setup_visible(self, visible: bool):
        if not visible:
            self._move_focus_from_setup()
        self.setup_visible = visible
        self._setup_preferences[self.narrow] = visible
        self._update_toggle()
        self._layout(self.narrow)

    def _move_focus_from_setup(self):
        focused = self.focus_get()
        if focused is not None and str(focused).startswith(str(self.setup) + "."):
            self.setup_toggle.focus_set()

    @staticmethod
    def _wrap_label(event):
        event.widget.configure(wraplength=max(80, event.width - 12))

    def _on_resize(self, event):
        if event.widget is self:
            tier, scale = responsive_text_tier(event.width)
            if self.theme.set_responsive_text_scale(scale):
                self.text_size_tier = tier
            self._flow_actions()
            narrow = event.width < self.theme.px(NARROW_BREAKPOINT)
            if not self._layout_ready or narrow != self.narrow:
                self.setup_visible = self._setup_preferences[narrow]
                if not self.setup_visible:
                    self._move_focus_from_setup()
                self._update_toggle()
                self._layout(narrow)

    def _minimum_body_height(self):
        # At normal size retain the compact layout. Enlarged text gets an
        # explicitly scrollable work region, never clipped or shrunk fonts.
        context = self.context.winfo_reqheight() + self.theme.space("sm")
        if self.theme.text_scale == 1.0:
            surface = self.minimum_surface_height()
            setup = self.setup.winfo_reqheight() if self.setup_visible else 0
            return context + (surface + setup if self.narrow else max(surface, setup))
        surface = max(self.theme.px(230), self.surface.winfo_reqheight())
        setup = self.setup.winfo_reqheight() if self.setup_visible else 0
        return context + (surface + setup if self.narrow else max(surface, setup))

    def _flow_actions(self):
        compact = (self.theme.text_scale >= 1.5 or self.secondary_actions.winfo_reqwidth() + self.primary_button.winfo_reqwidth()
                   + self.theme.space("lg") * 4 + 100 > self.winfo_width())
        large_header = self.theme.text_scale > 1.0 and self.winfo_width() < self.theme.px(650)
        self.title_label.grid_configure(columnspan=2 if large_header else 1)
        self.setup_toggle.grid_configure(row=1 if large_header else 0, rowspan=1 if large_header else 2)
        if large_header:
            self.caption.grid_remove()
        else:
            self.caption.grid()
        self.action_info_label.grid_configure(row=1 if compact else 0, column=0, columnspan=3 if compact else 1)
        self.secondary_actions.grid_configure(row=0, column=0 if compact else 1, sticky="w")
        self.primary_button.grid_configure(row=0, column=2)
        self.reason_label.grid_configure(row=2 if compact else 1)
        if not self.disabled_reason.get():
            self.reason_label.grid_remove()
        self.action_bar.columnconfigure(0, weight=1)

    def refresh_theme(self):
        self._layout_ready = False
        self._on_resize(type("Resize", (), {"widget": self, "width": self.winfo_width()})())
        self.viewport.canvas.configure(background=self.theme.colors["surface"])
        self.primary_button.configure(default="active" if self.theme.system_colors else "normal")
        self.viewport.sync()

    def _layout(self, narrow: bool):
        self.narrow = narrow
        self._layout_ready = True
        t = self.theme
        self.setup.configure(padding=t.space("sm") if narrow else t.space("md"))
        if narrow:
            self.setup_title.grid_remove()
        else:
            self.setup_title.grid()
        self.setup.grid_remove()
        self.surface.grid_remove()
        self.body.columnconfigure(0, weight=1 if narrow else 0, minsize=0 if narrow or not self.setup_visible else t.px(SETUP_WIDTH))
        self.body.columnconfigure(1, weight=0 if narrow else 1, minsize=0)
        self.body.rowconfigure(0, weight=0 if narrow and self.setup_visible else 1)
        self.body.rowconfigure(1, weight=1 if narrow and self.setup_visible else 0)
        if narrow:
            if self.setup_visible:
                self.setup.grid(row=0, column=0, sticky="ew")
            self.surface.grid(row=1 if self.setup_visible else 0, column=0, sticky="nsew")
        else:
            if self.setup_visible:
                self.setup.grid(row=0, column=0, sticky="nsew")
            self.surface.grid(row=0, column=1, sticky="nsew")
        if self.setup_panel is not None:
            self.surface.configure(padding=t.space("sm") if narrow else t.space("lg"))
            self.setup_panel.reflow(narrow)
            self.viewport.sync()
            return
        columns = 3 if narrow else 1
        for col in (0, 1, 2):
            self.setup_form.columnconfigure(col, weight=1 if col < columns else 0,
                                            uniform="setup" if col < columns else "")
        for index, field in enumerate(self.fields):
            field.grid(row=index // columns, column=index % columns, sticky="ew",
                       padx=(0, t.space("md") if narrow and index % columns < columns - 1 else 0),
                       pady=(0, t.space("sm")))
