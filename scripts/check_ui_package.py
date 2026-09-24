"""Run with an isolated wheel installation, never the editable source environment."""

import importlib
from importlib.metadata import entry_points
from pathlib import Path
import sys
import traceback

from tkinterdnd2 import TkinterDnD
from financial_statement_extract.ui.workspace import FinancialExtractorApp


prefix = Path(sys.prefix).resolve()
for name in ("workspace", "review", "review_samples", "accessibility", "viewport"):
    module = importlib.import_module(f"financial_statement_extract.ui.{name}")
    assert Path(module.__file__).resolve().is_relative_to(prefix), module.__file__
assert not {"pipeline", "pandas", "pdfplumber", "camelot"} & sys.modules.keys()

entry = next(e for e in entry_points(group="gui_scripts") if e.name == "financial-extract-gui")
assert callable(entry.load())

errors = []
root = TkinterDnD.Tk()


def failed(kind, value, tb):
    errors.append(str(value))
    traceback.print_exception(kind, value, tb)


root.report_callback_exception = failed
app = FinancialExtractorApp(root)
root.update()
assert app.root.title() == "Financial Statement Extract"
assert app.pdf_run_button.cget("text") == "Choose filing"
assert app.shell.primary_button.winfo_ismapped()
root.after(150, app._on_close)
root.mainloop()
assert app.closing and not errors, errors
assert not {"pipeline", "pandas", "pdfplumber", "camelot"} & sys.modules.keys()
print("Installed-wheel GUI startup, entry point, and shutdown passed; extraction stack not loaded.")
