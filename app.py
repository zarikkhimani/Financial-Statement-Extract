from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from tkinterdnd2 import DND_FILES, TkinterDnD

from path_policy import normalize_path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

HTML_SUFFIXES = {".html", ".htm", ".xhtml"}
PAGES_PLACEHOLDER = "(Auto) Type page numbers to specify pages"


def run_extraction(input_path: str, pages: str, metadata: dict, output_dir: str):
    """Load the heavy extraction stack only after the user starts a job."""
    from pipeline import extract_filing_to_workbook

    return extract_filing_to_workbook(input_path, pages, metadata, output_dir)


def effective_pages_value(value: str, placeholder_active: bool = False) -> str:
    text = (value or "").strip()
    if placeholder_active or not text or text == PAGES_PLACEHOLDER:
        return "auto"
    return text


def normalize_dropped_path(value: str, *, allow_nonlocal_paths: bool = False) -> Path:
    text = (value or "").strip().strip('"').strip("{}")
    return normalize_path(text, allow_nonlocal_paths=allow_nonlocal_paths)


def select_dropped_filing(values: list[str] | tuple[str, ...]) -> Path | None:
    for value in values:
        try:
            path = normalize_dropped_path(value)
        except ValueError:
            continue
        if path.suffix.lower() == ".pdf" or path.suffix.lower() in HTML_SUFFIXES:
            return path
    return None


class FinancialExtractorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Financial Statement Extract")
        self.root.geometry("1120x820")
        self.work_queue: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.pdf_path = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.pages = tk.StringVar()
        self.pages_placeholder_active = True
        self.client_name = tk.StringVar()
        self.year = tk.StringVar()
        self.period = tk.StringVar(value="Auto")
        self.audit_status = tk.StringVar(value="Audited")
        self.closing = False
        self.pdf_tab = ttk.Frame(root, padding=10)
        self.pdf_tab.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_pdf_tab()
        self._register_drop_targets()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(150, self._poll_queue)

    def _build_pdf_tab(self):
        form = ttk.Frame(self.pdf_tab)
        form.pack(fill="x")
        fields = [
            ("PDF / HTML", self.pdf_path),
            ("Output Folder", self.output_dir),
            ("Pages", self.pages),
            ("Client Name", self.client_name),
            ("Fiscal Year (optional)", self.year),
            ("Period", self.period),
            ("Audit Status", self.audit_status),
        ]
        for row, (label, var) in enumerate(fields):
            ttk.Label(form, text=label + ":").grid(row=row, column=0, sticky="w", padx=4, pady=4)
            if label == "Period":
                widget = ttk.Combobox(form, textvariable=var, values=["Auto", "Annual", "Q1", "Q2", "Q3", "Q4", "Semi-Annual", "Monthly"], state="readonly")
            elif label == "Audit Status":
                widget = ttk.Combobox(form, textvariable=var, values=["Audited", "Reviewed", "Compiled", "Company Prepared", "Draft"], state="readonly")
            elif label == "Pages":
                widget = tk.Entry(form, textvariable=var, fg="#888888", relief="solid", bd=1)
                self.pages_entry = widget
                self._show_pages_placeholder()
                widget.bind("<FocusIn>", self._on_pages_focus_in)
                widget.bind("<FocusOut>", self._on_pages_focus_out)
            else:
                widget = ttk.Entry(form, textvariable=var)
            widget.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
            if label == "PDF / HTML":
                ttk.Button(form, text="Browse", command=self._choose_pdf).grid(row=row, column=2, padx=4)
            if label == "Output Folder":
                ttk.Button(form, text="Browse", command=self._choose_output_dir).grid(row=row, column=2, padx=4)
        form.columnconfigure(1, weight=1)

        ttk.Label(self.pdf_tab, text="Drop a PDF or local HTML filing anywhere in this window, or use Browse. The Pages field applies only to PDFs.").pack(anchor="w", pady=(10, 4))
        button_row = ttk.Frame(self.pdf_tab)
        button_row.pack(fill="x", pady=6)
        self.pdf_run_button = ttk.Button(button_row, text="Extract to Excel", command=self._start_pdf_extraction)
        self.pdf_run_button.pack(side="left")
        self.exit_button = ttk.Button(button_row, text="Exit", command=self._on_close)
        self.exit_button.pack(side="right")
        self.progress = ttk.Progressbar(self.pdf_tab, mode="indeterminate")
        self.progress.pack(fill="x", pady=4)
        self.pdf_status = scrolledtext.ScrolledText(self.pdf_tab, height=26, wrap="word")
        self.pdf_status.pack(fill="both", expand=True, pady=(6, 0))

    def _show_pages_placeholder(self):
        self.pages_placeholder_active = True
        self.pages.set(PAGES_PLACEHOLDER)
        self.pages_entry.configure(fg="#888888")

    def _on_pages_focus_in(self, _event=None):
        if self.pages_placeholder_active:
            self.pages_placeholder_active = False
            self.pages.set("")
            self.pages_entry.configure(fg="#000000")

    def _on_pages_focus_out(self, _event=None):
        if not self.pages.get().strip():
            self._show_pages_placeholder()

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
        if pdf.suffix.lower() not in ({".pdf"} | HTML_SUFFIXES) or not pdf.is_file():
            messagebox.showerror("Unsupported file", "Drop a valid PDF, HTML, HTM, or XHTML filing.")
            return False
        self.pdf_path.set(str(pdf))
        if not self.output_dir.get().strip():
            self.output_dir.set(str(pdf.parent))
        if hasattr(self, "pdf_status"):
            self.pdf_status.delete("1.0", tk.END)
            self.pdf_status.insert(tk.END, f"Loaded filing:\n{pdf}\n")
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
        path = filedialog.askopenfilename(title="Select Financial Filing", filetypes=[("Supported filings", "*.pdf *.html *.htm *.xhtml"), ("PDF files", "*.pdf"), ("HTML files", "*.html *.htm *.xhtml")])
        if path:
            self._set_pdf_path(path)

    def _choose_output_dir(self):
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            try:
                self.output_dir.set(str(normalize_path(path)))
            except ValueError as exc:
                messagebox.showerror("Unsupported path", str(exc))

    def _metadata(self) -> dict:
        return {
            "client_name": self.client_name.get().strip(),
            "year": self.year.get().strip(),
            "period": self.period.get().strip(),
            "audit_status": self.audit_status.get().strip(),
        }

    def _start_pdf_extraction(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Busy", "An extraction is already running.")
            return
        pdf_text = self.pdf_path.get().strip()
        if not pdf_text:
            messagebox.showerror("Missing filing", "Choose or drop a PDF or HTML filing first.")
            return
        try:
            pdf_path = normalize_path(pdf_text)
            output_path = normalize_path(self.output_dir.get().strip() or pdf_path.parent)
        except ValueError as exc:
            messagebox.showerror("Unsupported path", str(exc))
            return
        pdf = str(pdf_path)
        pages = effective_pages_value(self.pages.get(), self.pages_placeholder_active)
        output_dir = str(output_path)
        metadata = self._metadata()

        self.pdf_status.delete("1.0", tk.END)
        suffix = Path(pdf).suffix.lower()
        start_message = "Parsing HTML filing and detecting statement tables...\n" if suffix in HTML_SUFFIXES else "Scanning PDF and detecting statement pages...\n" if pages == "auto" else "Starting extraction...\n"
        self.pdf_status.insert(tk.END, start_message)
        self.pdf_run_button.configure(state="disabled")
        self.progress.start(10)

        def worker_target():
            try:
                result, output = run_extraction(pdf, pages, metadata, output_dir)
                self.work_queue.put(("pdf_success", result, output))
            except Exception as exc:
                logger.exception("Filing extraction failed")
                self.work_queue.put(("pdf_error", str(exc)))

        self.worker = threading.Thread(target=worker_target, daemon=True)
        self.worker.start()

    def _poll_queue(self):
        try:
            while True:
                event = self.work_queue.get_nowait()
                if event[0] == "pdf_success":
                    _, result, output = event
                    self.progress.stop()
                    self.pdf_run_button.configure(state="normal")
                    self._render_pdf_summary(result, output)
                    messagebox.showinfo("Extraction complete", f"Saved:\n{output}")
                elif event[0] == "pdf_error":
                    self.progress.stop()
                    self.pdf_run_button.configure(state="normal")
                    self.pdf_status.insert(tk.END, f"ERROR: {event[1]}\n")
                    messagebox.showerror("Extraction failed", event[1])
        except queue.Empty:
            pass
        finally:
            if not self.closing:
                self.root.after(150, self._poll_queue)

    def _render_pdf_summary(self, result, output):
        self.pdf_status.delete("1.0", tk.END)
        self.pdf_status.insert(tk.END, f"Saved workbook: {output}\n\n")
        selected_pages = result.metadata.get("pages_selected")
        if selected_pages:
            self.pdf_status.insert(tk.END, f"Source pages: {selected_pages}\n\n")
        self.pdf_status.insert(tk.END, "Parsed statements:\n")
        for name, df in result.statements.items():
            periods = df.attrs.get("period_labels", [])
            self.pdf_status.insert(tk.END, f"  {name}: {len(df)} rows, periods={periods}\n")
        if not result.statements:
            self.pdf_status.insert(tk.END, "  None\n")
        self.pdf_status.insert(tk.END, "\nFinancial audit:\n")
        for row in result.financial_audit_rows:
            self.pdf_status.insert(tk.END, f"  [{row.get('Status')}] {row.get('Check')} | {row.get('Scope')}: {row.get('Detail')}\n")

    def _on_close(self):
        if self.closing:
            return
        self.closing = True
        if self.worker and self.worker.is_alive():
            logger.warning("Application closed while extraction worker was still running.")
        self.progress.stop()
        self.root.quit()
        self.root.destroy()


def main():
    root = TkinterDnD.Tk()
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    FinancialExtractorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
