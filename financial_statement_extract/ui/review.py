"""Live Phase 8 review harness. Generates synthetic inputs, then uses the real UI."""

import argparse
import json
from pathlib import Path
import tempfile
import time
import traceback
from tkinter import ttk, Menu

from tkinterdnd2 import TkinterDnD

from path_policy import normalize_path
from .review_samples import CASES
from .workspace import FinancialExtractorApp


def create_session(parent):
    """Keep each review's files in a new directory; never delete review workbooks."""
    parent = normalize_path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="session-", dir=parent))
    paths = {}
    for name, html in CASES.items():
        path = directory / f"Synthetic {name} filing for workspace review.html"
        with path.open("x", encoding="utf-8") as stream:
            stream.write(html)
        paths[name] = path
    return directory, paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, default="corporate")
    parser.add_argument("--source", type=Path, help="Optional existing local filing, instead of a generated sample.")
    parser.add_argument("--pages", default="auto", help="PDF page draft, e.g. 119-122,272-273. Normal preflight rules still apply.")
    parser.add_argument("--review-dir", type=Path, default=Path("tmp/ui-review"))
    parser.add_argument("--size", choices=("640x700", "720x820", "1120x820"), default="1120x820")
    parser.add_argument("--text-scale", type=float, choices=(1, 1.25, 1.5, 1.75, 2), default=1)
    parser.add_argument("--smoke", action="store_true", help="Extract once, report JSON, and exit; 30-second limit. No file launches.")
    args = parser.parse_args(argv)
    source = normalize_path(args.source) if args.source else None
    if source is not None and (not source.is_file() or source.suffix.lower() not in {".pdf", ".html", ".htm", ".xhtml"}):
        parser.error("Source must be an existing local PDF or HTML filing.")
    directory, paths = create_session(args.review_dir)
    root = TkinterDnD.Tk()
    errors = []

    def callback_error(kind, value, tb):
        errors.append(str(value))
        traceback.print_exception(kind, value, tb)

    root.report_callback_exception = callback_error
    app = FinancialExtractorApp(root, text_scale=args.text_scale)
    root.title("Financial Statement Extract — Phase 8 review")
    root.geometry(args.size)

    def load_case(name):
        app._set_pdf_path(paths[name])
        app.output_dir.set(str(directory))

    review = Menu(app.accessibility.menu, tearoff=False)
    for name in CASES:
        review.add_command(label=f"Load synthetic {name}", command=lambda value=name: load_case(value))
    app.accessibility.menu.add_cascade(label="Review cases", menu=review)
    # Keep the safety label outside the scrolling content. This is the live app,
    # not the older Phase 2 simulation; Extract really writes a workbook.
    banner = ttk.Label(root, text="REVIEW SESSION · Extract writes real workbooks to a new review folder.",
                       style="Status.TLabel", wraplength=560)
    banner.pack(side="bottom", fill="x", before=app.shell)
    app._set_pdf_path(source or paths[args.case])
    app.pages.set(args.pages)
    app.output_dir.set(str(directory))
    result = {}
    if args.smoke:
        expected = "ERROR" if source is None and args.case == "invalid" else "SUCCEEDED"
        started = time.monotonic()

        def check():
            elapsed = time.monotonic() - started
            phase = app.lifecycle.phase.value
            if phase in {"SUCCEEDED", "ERROR"} or errors or elapsed > 30 or app.lifecycle.awaiting_review:
                expected_error = "No financial statements were extracted; no workbook was created."
                passed = phase == expected and not errors and elapsed <= 30
                if expected == "ERROR":
                    passed = passed and app.lifecycle.error == expected_error
                else:
                    passed = passed and app._result_output is not None and app._result_output.is_file()
                result.update(phase=phase, expected=expected, passed=bool(passed), error=app.lifecycle.error,
                              elapsed_seconds=round(elapsed, 3), callback_errors=errors,
                              source=app.state.input_path, output=str(app._result_output or ""),
                              pages=app.state.pages,
                              headline=app.results.headline.get(),
                              statements=len(app.results.summary.statements) if app.results.summary else 0,
                              checks=len(app.results.summary.checks) if app.results.summary else 0)
                root.quit()
            else:
                root.after(25, check)

        # Review is never auto-approved by an unattended smoke run.
        def decline_review(plan, request):
            app._job_failed("Page review requires an interactive run.", "ValueError")
        app._review_page_selection = decline_review
        root.after(0, app._start_pdf_extraction)
        root.after(25, check)
    try:
        root.mainloop()
    finally:
        if not app.closing:
            app.closing = True
            root.destroy()
    if args.smoke:
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("passed") else 1
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
