from pathlib import Path
import sys
import tkinter as tk

from financial_statement_extract.ui.window_icon import apply_window_icon


def test_packaged_portrait_icon_applies_to_window(tk_runtime):
    root = tk.Toplevel(tk_runtime)
    root.withdraw()
    try:
        apply_window_icon(root)
        if sys.platform == "win32":
            assert root._finextract_icon_path.name == "app_icon.ico"
        else:
            assert root._finextract_icon_photo.width() == 512
            assert root._finextract_icon_photo.height() == 512
    finally:
        root.destroy()


def test_portrait_icon_assets_are_packaged_with_the_application():
    asset_dir = Path(__file__).resolve().parents[1] / "financial_statement_extract" / "assets"
    assert (asset_dir / "app_icon.png").is_file()
    assert (asset_dir / "app_icon.ico").is_file()
