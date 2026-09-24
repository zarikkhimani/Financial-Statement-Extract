"""Tk event handling and composition for the current extraction workspace."""

from __future__ import annotations

import logging
import queue
import tkinter as tk
from dataclasses import replace
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from tkinterdnd2 import DND_FILES, TkinterDnD

from path_policy import normalize_path

from .components import WorkspaceVariables, render_summary
from .accessibility import WorkspaceAccessibility
from .controller import ExtractionController, ExtractionRunner
from .desktop import require_interactive_desktop
from .inputs import HTML_SUFFIXES, select_dropped_filing
from .lifecycle import JobLifecycle, JobPhase
from .file_actions import open_result_path
from .results import ResultsView, recovery_hint
from .setup import FilingSetupPanel
from .shell import WorkspaceShell
from .state import WorkspaceState
from .theme import MIN_WINDOW_SIZE, WINDOW_GEOMETRY, WINDOW_TITLE, apply_workspace_theme
from .window_icon import apply_window_icon

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class FinancialExtractorApp:
    def __init__(self, root: tk.Tk, *, runner: ExtractionRunner | None = None, reports_progress: bool = False,
                 text_scale: float = 1.0, system_colors: bool = False):
        self.root = root
        apply_window_icon(self.root)
        self.root.title(WINDOW_TITLE)
        self.root.geometry(WINDOW_GEOMETRY)
        self.root.minsize(*MIN_WINDOW_SIZE)
        self.theme = apply_workspace_theme(root, text_scale=text_scale, system_colors=system_colors)
        self.state = WorkspaceState()
        self.controller = ExtractionController(runner, reports_progress=reports_progress)
        self.variables = WorkspaceVariables(root, self.state)
        self.pdf_path = self.variables.pdf_path
        self.output_dir = self.variables.output_dir
        self.pages = self.variables.pages
        self.client_name = self.variables.client_name
        self.year = self.variables.year
        self.period = self.variables.period
        self.audit_status = self.variables.audit_status
        self.pages_placeholder_active = True
        self.closing = False
        self._confirming_close = False
        self.lifecycle = JobLifecycle()
        self._has_result = False
        self._result_output = None
        self._baseline = self.state.draft_key()
        self._baseline_metadata = self.state.metadata()

        self._build_pdf_tab()
        self.variables.subscribe(self._refresh_setup)
        self._refresh_setup()
        self.accessibility = WorkspaceAccessibility(self)
        self._register_drop_targets()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(150, self._poll_queue)

    def _build_pdf_tab(self):
        self.shell = WorkspaceShell(self.root, self.variables, self.theme, setup_factory=FilingSetupPanel)
        self.shell.pack(fill="both", expand=True)
        self.pdf_tab = self.shell
        self.shell.enable_filing_controls(self._choose_pdf, self._choose_output_dir)
        self.pages_entry = self.shell.setup_panel.entries["pages"]
        self.pages_entry.bind("<FocusIn>", self._on_pages_focus_in)
        self.pages_entry.bind("<FocusOut>", self._on_pages_focus_out)
        self.pdf_run_button = self.shell.primary_button
        self.exit_button = ttk.Button(self.shell.secondary_actions, text="Exit", style="Workspace.TButton", command=self._on_close)
        self.exit_button.pack(side="right")
        self.result_action = ttk.Button(self.shell.secondary_actions, style="Workspace.TButton")
        surface = self.shell.surface
        surface.columnconfigure(0, weight=1)
        surface.rowconfigure(1, weight=1)
        self.result_context = tk.StringVar(master=self.root, value="Choose or drop a PDF or local HTML filing to begin.")
        context = ttk.Entry(surface, textvariable=self.result_context, style="Workspace.TEntry", state="readonly", width=1,
                            font=self.theme.fonts["body"])
        context.grid(row=0, column=0, sticky="ew", pady=(0, self.theme.space("sm")))
        self.results = ResultsView(surface, self.theme)
        self.results.grid(row=1, column=0, sticky="nsew")
        self.shell.minimum_surface_height = lambda: (
            surface.winfo_reqheight() - self.results.winfo_reqheight() + self.results.minimum_height())
        self.pdf_status = self.results.diagnostics
        self.folder_button = ttk.Button(self.results.footer, text="Open output folder", style="Workspace.TButton",
                                        command=self._open_output_folder)
        self.progress = ttk.Progressbar(surface, mode="indeterminate", style="Workspace.Horizontal.TProgressbar")
        self.progress.grid(row=2, column=0, sticky="ew", pady=(self.theme.space("sm"), 0))
        self.progress.grid_remove()
        self.pdf_status.insert(tk.END, "Add a filing to set up an extraction.\nResults and checks will appear here.\n")
        self._show_pages_placeholder()

    def _show_pages_placeholder(self):
        self.pages_placeholder_active = True
        self.pages.set("auto")

    def _on_pages_focus_in(self, _event=None):
        if self.pages.get().strip().lower() == "auto":
            self.pages_placeholder_active = False
            self.pages.set("")

    def _on_pages_focus_out(self, _event=None):
        if not self.pages.get().strip():
            self._show_pages_placeholder()

    def _refresh_setup(self):
        """Called after Tk variable edits have updated the plain draft."""
        self.lifecycle.sync_draft(self.state)
        source = self.state.input_path.strip()
        suffix = Path(source).suffix.lower()
        kind = "pdf" if suffix == ".pdf" else "html" if suffix in HTML_SUFFIXES else "empty"
        self.shell.setup_panel.set_source_kind(kind)
        self.shell.source_detail.set(
            ("PDF · Automatic page detection" if self.state.pages.strip().lower() in {"", "auto"}
             else "PDF · Manual page selection (large selections are reviewed before extraction)")
            if kind == "pdf" else "HTML · PDF page selection is not used" if kind == "html"
            else "Choose or drop a PDF, HTML, HTM, or XHTML filing"
        )
        modified = self.state.draft_key() != self._baseline
        self.shell.set_setup_modified(modified)
        self.shell.setup_panel.set_details_modified(self.state.metadata() != self._baseline_metadata)
        self.shell.draft_notice.set("Changes not yet extracted" if modified else "")
        self.shell.action_info.set("Changes not yet extracted" if modified else
                                   "Settings match last extraction" if self._has_result else
                                   "Ready to extract" if source else "No filing selected")
        reason = self.lifecycle.disabled_reason(self.state)
        if self._job_active:
            label = "Review pages…" if self.lifecycle.awaiting_review else "Extracting…"
            self.shell.set_primary_action(label, self._start_pdf_extraction, enabled=False, reason=reason)
        elif self.lifecycle.phase is JobPhase.SUCCEEDED and self._result_output is not None:
            self.shell.set_primary_action("Open workbook", self._open_workbook)
        elif not source:
            self.shell.set_primary_action("Choose filing", self._choose_pdf)
        else:
            self.shell.set_primary_action("Retry" if self.lifecycle.phase is JobPhase.ERROR else "Extract to Excel", self._start_pdf_extraction,
                                          enabled=not reason, reason=reason)
        self.result_action.pack_forget()
        self.folder_button.pack_forget()
        if self._has_result and not self._job_active:
            primary_open = self.lifecycle.phase is JobPhase.SUCCEEDED
            self.result_action.configure(text="Extract again" if primary_open else "Open workbook",
                                         command=self._start_pdf_extraction if primary_open else self._open_workbook)
            self.result_action.state(["!disabled"])
            self.result_action.pack(side="left")
            self.folder_button.pack(side="left", padx=(self.theme.space("sm"), 0))
        self.results.reflow_footer()
        self.shell._flow_actions()
        if self.lifecycle.phase is JobPhase.EMPTY:
            self.shell.set_status("Choose a filing to begin")
        elif self.lifecycle.phase is JobPhase.READY:
            self.shell.set_status("Check setup · " + reason if reason else "Ready · Extract using the current settings")

    @property
    def _job_active(self):
        return self.lifecycle.active

    def _finish_job(self):
        self.progress.stop()
        self.progress.grid_remove()
        self._refresh_setup()

    def _register_drop_targets(self):
        pending = [self.root]
        while pending:
            widget = pending.pop()
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_file_drop)
            pending.extend(widget.winfo_children())

    def _set_pdf_path(self, path: str | Path) -> bool:
        try:
            pdf = normalize_path(path)
        except ValueError as exc:
            messagebox.showerror("Unsupported path", str(exc))
            return False
        try:
            valid = pdf.suffix.lower() in ({".pdf"} | HTML_SUFFIXES) and pdf.is_file()
        except OSError as exc:
            messagebox.showerror("Cannot access filing", str(exc))
            return False
        if not valid:
            messagebox.showerror("Unsupported file", "Drop a valid PDF, HTML, HTM, or XHTML filing.")
            return False
        self.pdf_path.set(str(pdf))
        if not self.output_dir.get().strip():
            self.output_dir.set(str(pdf.parent))
        if hasattr(self, "pdf_status") and not self._has_result and not self._job_active:
            self.pdf_status.delete("1.0", tk.END)
            self.pdf_status.insert(tk.END, f"Loaded filing:\n{pdf}\n")
            self.result_context.set("Ready to extract · Results and checks will appear below.")
            self.results.show_note("Ready to extract", "Review setup, then choose Extract to Excel. Existing output files are not overwritten.")
        return True

    def _on_file_drop(self, event):
        try:
            values = self.root.tk.splitlist(event.data)
        except tk.TclError:
            values = (event.data,)
        pdf = select_dropped_filing(values)
        if pdf is None:
            messagebox.showerror("Unsupported file", "Drop a PDF, HTML, HTM, or XHTML filing.")
        else:
            self._set_pdf_path(pdf)
        return getattr(event, "action", None) or "copy"

    def _choose_pdf(self):
        path = filedialog.askopenfilename(parent=self.root, title="Select Financial Filing", filetypes=[("Supported filings", "*.pdf *.html *.htm *.xhtml"), ("PDF files", "*.pdf"), ("HTML files", "*.html *.htm *.xhtml")])
        if path:
            self._set_pdf_path(path)

    def _choose_output_dir(self):
        path = filedialog.askdirectory(parent=self.root, title="Select output folder")
        if path:
            try:
                self.output_dir.set(str(normalize_path(path)))
            except ValueError as exc:
                messagebox.showerror("Unsupported path", str(exc))

    def _metadata(self) -> dict:
        return self.state.metadata()

    def _start_pdf_extraction(self):
        if self._job_active or self.controller.is_running:
            messagebox.showinfo("Busy", "An extraction is already running.")
            return
        if not self.state.input_path.strip():
            messagebox.showerror("Missing filing", "Choose or drop a PDF or HTML filing first.")
            return
        try:
            request = self.state.to_request()
        except ValueError as exc:
            messagebox.showerror("Unsupported path", str(exc))
            return
        pages = request.pages
        suffix = Path(request.input_path).suffix.lower()
        try:
            if suffix not in {".pdf", *HTML_SUFFIXES} or not Path(request.input_path).is_file():
                messagebox.showerror("Unsupported file", "Choose an existing PDF, HTML, HTM, or XHTML filing.")
                return
        except OSError as exc:
            messagebox.showerror("Cannot access filing", str(exc))
            return

        self.lifecycle.begin(request, self.state.draft_key())
        self._has_result = False
        self._result_output = None
        self.results.show_note("Extracting filing", "Please keep this window open. Setup edits apply to the next run.")

        self.pdf_status.delete("1.0", tk.END)
        start_message = "Parsing HTML filing and detecting statement tables...\n" if suffix in HTML_SUFFIXES else "Scanning PDF and detecting statement pages...\n" if pages == "auto" else "Reviewing selected PDF pages...\n"
        self.pdf_status.insert(tk.END, start_message)
        self.result_context.set(f"Extracting: {request.input_path}")
        self.shell.set_status("Extraction in progress · Setup edits apply to the next run")
        self._refresh_setup()
        self.progress.grid()
        self.progress.start(10)

        try:
            self.controller.start(request)
        except Exception as exc:
            logger.exception("Could not start extraction")
            self._job_failed(str(exc), type(exc).__name__)

    def _job_failed(self, message, kind=""):
        self.lifecycle.fail(message)
        self._finish_job()
        self.pdf_status.insert(tk.END, f"ERROR: {message}\n")
        self.pdf_status.insert(tk.END, f"Error type: {kind or 'Unknown'}\n")
        self.results.show_note("Extraction failed", recovery_hint(message, kind))
        self.results.diagnostics_visible = False
        self.results._display()
        self.result_context.set(f"Failed extraction: {self.lifecycle.request.input_path}")
        self.shell.set_status("Extraction failed · Your settings are retained; adjust them or extract again", "error")

    def _poll_queue(self):
        if self.closing:
            return
        try:
            while not self.closing:
                event = self.controller.work_queue.get_nowait()
                if event[0] == "progress":
                    _, progress, request = event
                    if self.lifecycle.active and not self.lifecycle.awaiting_review and request is self.lifecycle.request:
                        self.lifecycle.progress = progress
                        text = progress.stage.value + (" · " + progress.detail if progress.detail else "")
                        self.shell.set_status(text)
                        self.pdf_status.insert(tk.END, text + "\n")
                        self.results.note.delete("1.0", tk.END)
                        self.results.note.insert(tk.END, text + "\n\nSetup edits apply to the next run. Keep this window open until completion.")
                elif event[0] == "pdf_success":
                    _, result, output = event
                    self.lifecycle.succeed()
                    self._baseline = self.lifecycle.submitted_draft
                    self._baseline_metadata = self.lifecycle.request.metadata
                    self._has_result = True
                    self._result_output = Path(output)
                    self._render_pdf_summary(result, output)
                    self._finish_job()
                    self.result_context.set(f"Result from: {self.lifecycle.request.input_path}")
                    self.shell.set_status(self.results.summary.headline + " · Reconcile to the source filing",
                                          "warning" if self.results.summary.needs_review else "success")
                elif event[0] == "pdf_error":
                    self._job_failed(event[1], event[2])
                elif event[0] == "page_review":
                    self._review_page_selection(event[1], event[2])
        except queue.Empty:
            pass
        finally:
            if not self.closing:
                self.root.after(150, self._poll_queue)

    def _render_pdf_summary(self, result, output):
        render_summary(self.pdf_status, result, output)
        self.results.show_result(result, output)

    def _open_workbook(self):
        self._open_result(folder=False)

    def _open_output_folder(self):
        self._open_result(folder=True)

    def _open_result(self, *, folder):
        if self._result_output is None or self._job_active:
            return
        path = self._result_output.parent if folder else self._result_output
        try:
            open_result_path(path, folder=folder)
        except (OSError, ValueError) as exc:
            self.pdf_status.insert(tk.END, f"Could not open {path}: {exc}\n")
            self.shell.set_status("Could not open result · See diagnostics; the extraction result is retained", "error")
            messagebox.showerror("Could not open result", f"{exc}\n\nCheck the saved location and your default Excel application. "
                                 "The result and settings are retained.", parent=self.root)

    def _review_page_selection(self, plan, request):
        self.lifecycle.require_review()
        self.progress.stop()
        self._refresh_setup()
        self.shell.set_status("Waiting for PDF page review · No extraction will resume without your choice")
        from extractors import format_page_numbers
        suggested = format_page_numbers(list(plan.suggested_pages))
        choice = messagebox.askyesnocancel(
            "Review PDF pages",
            f"You selected {len(plan.requested_pages)} pages.\n"
            f"Suggested selection ({len(plan.suggested_pages)} pages): {suggested or '(none)'}\n\n"
            + ("\n".join(plan.warnings) + "\n\n" if plan.detection_source.startswith("auto") else
               "The suggestion retains investment schedules and uncertain pages. It removes only "
               "clearly blank/footer-only pages.\n\n") +
            "Yes: use suggested pages\nNo: use exactly the entered pages\nCancel: return without extracting",
            default=messagebox.CANCEL, parent=self.root,
        )
        if self.closing:
            return
        if choice is None:
            self.lifecycle.decline_review(self.state)
            self._finish_job()
            self.result_context.set("Page review cancelled · Settings retained for another attempt.")
            self.results.show_note("Page review cancelled", "No workbook was created. Adjust the selected pages and extract again when ready.")
            self.pdf_status.insert(tk.END, "Page review cancelled; no workbook created.\n")
            self.shell.set_status("Page review cancelled · No workbook created")
            return
        resolved = replace(request, page_policy="suggested" if choice else "exact")
        self.lifecycle.resume_review(resolved)
        self._refresh_setup()
        self.shell.set_status("Extraction in progress · Setup edits apply to the next run")
        self.progress.grid()
        self.progress.start(10)
        # The completion event can arrive just before its worker exits.
        def resume():
            if self.closing:
                return
            if self.controller.is_running:
                self.root.after(50, resume)
            else:
                try:
                    self.controller.start(resolved)
                except Exception as exc:
                    logger.exception("Could not resume extraction")
                    self._job_failed(str(exc), type(exc).__name__)
        resume()

    def _on_close(self):
        if self.closing or self._confirming_close:
            return
        if self.controller.is_running or self.lifecycle.active:
            self._confirming_close = True
            try:
                confirmed = messagebox.askyesno(
                    "Close during extraction?",
                    "An extraction is still pending. Closing now may interrupt it and leave an incomplete workbook.\n\n"
                    "Keep this window open until extraction finishes. Close anyway?",
                    default=messagebox.NO, icon=messagebox.WARNING, parent=self.root,
                )
            finally:
                self._confirming_close = False
            if not confirmed:
                return
            logger.warning("Application closed while extraction worker was still running.")
        self.closing = True
        self.progress.stop()
        self.root.quit()
        self.root.destroy()


def main():
    # Refuse service/sandbox launches before creating any windows or workers.
    require_interactive_desktop()
    root = TkinterDnD.Tk()
    app = None
    try:
        app = FinancialExtractorApp(root)
        root.deiconify()
        root.lift()
        root.update_idletasks()
        if not root.winfo_viewable():
            raise RuntimeError("The application window could not be displayed.")
        root.mainloop()
    except Exception as exc:
        logger.exception("Desktop application failed")
        messagebox.showerror("Financial Statement Extract could not stay open", str(exc), parent=root)
        raise
    finally:
        # Covers initialization failures and quit() as well as the normal X/Exit
        # handler. Extraction uses a daemon thread, so it cannot keep this
        # standalone GUI process alive after the window has been destroyed.
        if app is not None:
            app.closing = True
        try:
            root.destroy()
        except tk.TclError:
            pass  # The normal close handler already destroyed the interpreter.


if __name__ == "__main__":
    main()
