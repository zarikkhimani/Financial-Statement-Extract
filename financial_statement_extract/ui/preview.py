"""Phase 2 review harness. All values are synthetic; no extraction or file I/O."""

from __future__ import annotations

import argparse
import tkinter as tk
from tkinter import ttk

from .window_icon import apply_window_icon

from .components import WorkspaceVariables
from .shell import WorkspaceShell
from .state import WorkspaceState
from .theme import COLORS, MIN_WINDOW_SIZE, apply_workspace_theme

SCENARIOS = ("Empty", "Ready", "Running", "Completed", "Warning", "Error", "Long labels")
SAMPLE_ROWS = (
    ("Revenue", "12,450", "11,200", "42"),
    ("Cost of revenue", "(7,350)", "(6,810)", "42"),
    ("Gross profit", "5,100", "4,390", "42"),
    ("Research and development", "(860)", "(850)", "42"),
    ("Selling, general and administrative", "(1,940)", "(1,810)", "42"),
    ("Total operating expenses", "(2,800)", "(2,660)", "42"),
    ("Operating income", "2,300", "1,730", "42"),
    ("Interest income", "40", "30", "42"),
    ("Interest expense", "(170)", "(155)", "42"),
    ("Other expense, net", "(25)", "(15)", "42"),
    ("Income before income taxes", "2,145", "1,590", "42"),
    ("Income tax expense", "(445)", "(320)", "42"),
    ("Net income", "1,700", "1,270", "42"),
    ("Basic earnings per share", "6.94", "5.18", "43"),
    ("Diluted earnings per share", "6.80", "5.08", "43"),
    ("Weighted-average basic shares", "245", "245", "43"),
    ("Weighted-average diluted shares", "250", "250", "43"),
)


class PreviewApp:
    def __init__(self, root: tk.Tk, *, scenario: str = "Completed", size: str = "1120x820", text_scale: float = 1.0):
        if scenario not in SCENARIOS:
            raise ValueError(f"Unknown preview scenario: {scenario}")
        self.root = root
        self.theme = apply_workspace_theme(root, text_scale=text_scale)
        root.title("Financial Statement Extract — Design preview")
        root.geometry(size)
        root.minsize(*MIN_WINDOW_SIZE)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)
        self._simulation_timer = None
        self.state = WorkspaceState(
            input_path=r"C:\Sample filings\Northstar_Industries_10K_2025.pdf",
            output_dir=r"C:\Extracted statements", client_name="Northstar Industries", year="2025", period="Annual")
        self.variables = WorkspaceVariables(root, self.state)
        self.scenario = tk.StringVar(master=root, value=scenario)
        self._build_preview_toolbar()
        self.shell = WorkspaceShell(root, self.variables, self.theme)
        self.shell.grid(row=1, column=0, sticky="nsew")
        self._build_surface()
        self._build_secondary_actions()
        self._draft_baseline = self._draft_values()
        for field in self.shell.setup_entries:
            getattr(self.variables, field).trace_add("write", self._draft_changed)
        self.scenario.trace_add("write", self._scenario_changed)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Alt-s>", lambda _event: self.shell.toggle_setup())
        self.show_scenario(scenario)

    def _build_preview_toolbar(self):
        t = self.theme
        toolbar = ttk.Frame(self.root, style="Workspace.TFrame", padding=(t.space("lg"), t.space("sm")))
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(0, weight=1)
        ttk.Label(toolbar, text="DESIGN PREVIEW  ·  Sample data only", style="Caption.TLabel").grid(row=0, column=0, sticky="w")
        self.scenario_select = ttk.Combobox(toolbar, textvariable=self.scenario, values=SCENARIOS,
                                           state="readonly", width=12, style="Workspace.TCombobox")
        self.scenario_select.grid(row=0, column=1, padx=(t.space("sm"), 0))
        self.size_select = ttk.Combobox(toolbar, values=("Wide window", "Narrow window"),
                                        state="readonly", width=14, style="Workspace.TCombobox")
        self.size_select.set("Wide window")
        self.size_select.grid(row=0, column=2, padx=(t.space("sm"), 0))
        self.size_select.bind("<<ComboboxSelected>>", self._resize_preview)

    def _resize_preview(self, _event=None):
        self.root.geometry("720x820" if self.size_select.get() == "Narrow window" else "1120x820")

    def _build_surface(self):
        t = self.theme
        surface = self.shell.surface
        surface.columnconfigure(0, weight=1)
        surface.rowconfigure(3, weight=1)
        self.surface_title = ttk.Label(surface, text="Income statement", style="Empty.TLabel")
        self.surface_title.grid(row=0, column=0, sticky="w")
        self.surface_detail = ttk.Label(surface, text="Illustrative values · USD millions, except per-share data",
                                         style="Muted.TLabel", wraplength=500)
        self.surface_detail.grid(row=1, column=0, sticky="ew", pady=(t.space("xs"), t.space("md")))
        self.surface_detail.bind("<Configure>", self.shell._wrap_label)
        self.notice = ttk.Label(surface, style="Warning.TLabel", padding=t.space("sm"), wraplength=500)
        self.notice.grid(row=2, column=0, sticky="ew", pady=(0, t.space("md")))
        self.notice.bind("<Configure>", self.shell._wrap_label)
        self.content = ttk.Frame(surface, style="Surface.TFrame")
        self.content.grid(row=3, column=0, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)
        self.table_frame = ttk.Frame(self.content, style="Surface.TFrame")
        self.table_frame.grid(row=0, column=0, sticky="nsew")
        self.table_frame.columnconfigure(0, weight=1)
        self.table_frame.rowconfigure(0, weight=1)
        self.table = ttk.Treeview(self.table_frame, columns=("item", "current", "prior", "page"),
                                  show="headings", selectmode="extended", style="Workspace.Treeview", height=6)
        for key, title, width, minimum, anchor in (
            ("item", "Line item", 290, 210, "w"), ("current", "2025", 90, 80, "e"),
            ("prior", "2024", 90, 80, "e"), ("page", "PDF page", 76, 70, "e"),
        ):
            self.table.heading(key, text=title, anchor=anchor)
            self.table.column(key, width=t.px(width), minwidth=t.px(minimum), anchor=anchor, stretch=key == "item")
        self.table.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.table.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(self.table_frame, orient="horizontal", command=self.table.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.table.tag_configure("total", background=COLORS["surface-subtle"], font=t.fonts["section"])
        for index, values in enumerate(SAMPLE_ROWS):
            self.table.insert("", "end", iid=str(index), values=values,
                              tags=("total",) if index in {2, 6, 12} else ())
        self.table.bind("<<TreeviewSelect>>", self._selection_changed)
        self.overlay = ttk.Frame(self.content, style="Surface.TFrame")
        self.overlay.columnconfigure(0, weight=1)
        self.overlay.rowconfigure(0, weight=1)
        self.overlay.rowconfigure(3, weight=1)
        self.overlay_title = ttk.Label(self.overlay, style="Empty.TLabel", anchor="center", justify="center", wraplength=400)
        self.overlay_title.grid(row=1, column=0, sticky="ew", padx=t.space("lg"))
        self.overlay_detail = ttk.Label(self.overlay, style="Muted.TLabel", anchor="center", justify="center", wraplength=400)
        self.overlay_detail.grid(row=2, column=0, sticky="ew", padx=t.space("lg"), pady=(t.space("sm"), t.space("lg")))
        self.overlay_title.bind("<Configure>", self.shell._wrap_label)
        self.overlay_detail.bind("<Configure>", self.shell._wrap_label)
        self.progress = ttk.Progressbar(surface, mode="indeterminate", style="Workspace.Horizontal.TProgressbar")
        self.progress.grid(row=4, column=0, sticky="ew", pady=(t.space("sm"), 0))

    def _build_secondary_actions(self):
        self.copy_button = ttk.Button(self.shell.secondary_actions, text="Copy rows", command=self._copy_rows,
                                       style="Workspace.TButton")
        self.copy_button.pack()

    def _draft_values(self):
        return tuple(getattr(self.variables, name).get() for name in self.shell.setup_entries)

    def _draft_changed(self, *_args):
        self.shell.set_setup_modified(self._draft_values() != self._draft_baseline)

    def _scenario_changed(self, *_args):
        self.show_scenario(self.scenario.get())

    def show_scenario(self, scenario: str):
        if scenario not in SCENARIOS:
            raise ValueError(f"Unknown preview scenario: {scenario}")
        if self._simulation_timer is not None:
            self.root.after_cancel(self._simulation_timer)
            self._simulation_timer = None
        self.progress.stop()
        self.progress.grid_remove()
        self.notice.grid_remove()
        has_result = scenario in {"Completed", "Warning", "Long labels"}
        self.variables.pdf_path.set(
            "" if scenario == "Empty" else
            r"C:\Sample filings\Northstar_Industries_and_International_Holdings_Consolidated_Annual_Report_2025.pdf"
            if scenario == "Long labels" else r"C:\Sample filings\Northstar_Industries_10K_2025.pdf")
        self.shell.source_detail.set("No filing selected · PDF or local HTML" if scenario == "Empty" else
                                     "PDF · Annual filing · Sample source pages 42–43")
        self.surface_title.configure(text="Income statement" if has_result else "Extraction overview")
        self.surface_detail.configure(text="Illustrative values · USD millions, except per-share data" if has_result else
                                        "Set up a filing and review the extracted statements here.")
        self.table.item("4", values=(
            "Selling, general and administrative expenses, including international operations and shared services"
            if scenario == "Long labels" else SAMPLE_ROWS[4][0], *SAMPLE_ROWS[4][1:]))
        if has_result:
            self.overlay.grid_remove()
            self.table_frame.grid()
            self.copy_button.pack()
            self.shell.set_primary_action("Preview workbook", self._preview_workbook)
            self.shell.set_status("Sample result ready · No workbook has been created", "success")
            if scenario == "Warning":
                self.notice.configure(text="Review needed: two sample checks require reconciliation with the source.")
                self.notice.grid()
                self.shell.set_status("Sample result includes warnings · Review the source before use", "warning")
        else:
            self.table_frame.grid_remove()
            self.overlay.grid(row=0, column=0, sticky="nsew")
            self.copy_button.pack_forget()
            heading, detail = {
                "Empty": ("Add a financial filing", "Start with a PDF or local HTML filing. Statements and checks will appear in this workspace."),
                "Ready": ("Ready to extract", "The filing and settings are ready. Your results will appear here when extraction completes."),
                "Running": ("Extracting statements", "Reading the sample statement pages. Your setup stays available while the job runs."),
                "Error": ("The workbook could not be saved", "The sample output folder is unavailable. Review the folder in setup, then retry."),
            }[scenario]
            self.overlay_title.configure(text=heading)
            self.overlay_detail.configure(text=detail)
            if scenario == "Empty":
                self.shell.set_primary_action("Add sample filing", lambda: self.scenario.set("Ready"))
                self.shell.set_status("Preview only · No files are read or written")
            elif scenario == "Ready":
                self.shell.set_primary_action("Extract to Excel", self._simulate_extraction)
                self.shell.set_status("Ready · The preview will simulate extraction")
            elif scenario == "Running":
                self.shell.set_primary_action("Extracting…", self._simulate_extraction, enabled=False,
                                              reason="A sample job is running. Wait for it to finish before starting another.")
                self.progress.grid()
                self.progress.start(14)
                self.shell.set_status("Simulated extraction in progress · No document is being processed")
            else:
                self.shell.set_primary_action("Retry sample", self._simulate_extraction)
                self.shell.set_status("Sample error · Your setup values have been preserved", "error")
        self._selection_changed()

    def _selection_changed(self, _event=None):
        has_result = self.scenario.get() in {"Completed", "Warning", "Long labels"}
        count = len(self.table.selection()) if has_result else 0
        self.shell.action_info.set(f"{len(SAMPLE_ROWS)} rows · {count} selected" if has_result else "No result loaded")
        # Only display this contextual action when a selection makes it useful.
        if count:
            self.copy_button.pack()
        else:
            self.copy_button.pack_forget()

    def _copy_rows(self):
        values = [self.table.item(iid, "values") for iid in self.table.selection()]
        if values:
            self.root.clipboard_clear()
            self.root.clipboard_append("\n".join("\t".join(row) for row in values))
            self.shell.set_status(f"Copied {len(values)} sample rows to the clipboard")

    def _simulate_extraction(self):
        self.scenario.set("Running")
        self._simulation_timer = self.root.after(1800, lambda: self.scenario.set("Completed"))

    def _preview_workbook(self):
        self.shell.set_status("This table is the sample workbook preview · No file was created or opened")

    def close(self):
        if self._simulation_timer is not None:
            self.root.after_cancel(self._simulation_timer)
        self.progress.stop()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description="Review the Phase 2 workspace using synthetic data only.")
    parser.add_argument("--scenario", choices=SCENARIOS, default="Completed")
    parser.add_argument("--size", default="1120x820", help="Tk window geometry, for example 720x820")
    parser.add_argument("--text-scale", type=float, default=1.0)
    args = parser.parse_args()
    root = tk.Tk()
    apply_window_icon(root)
    PreviewApp(root, scenario=args.scenario, size=args.size, text_scale=args.text_scale)
    root.mainloop()


if __name__ == "__main__":
    main()
