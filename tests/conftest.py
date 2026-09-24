"""One native Tk interpreter for the UI suite on Windows."""

import sys
from pathlib import Path

import pytest
from tkinterdnd2 import TkinterDnD

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def tk_runtime():
    # Unloading/recreating Tk/TkDND between preview and live-view modules can
    # break Tcl file loading on Windows. Each test still owns its Toplevel;
    # share only the interpreter, as the desktop application does.
    root = TkinterDnD.Tk()
    root.withdraw()
    yield root
    root.destroy()
