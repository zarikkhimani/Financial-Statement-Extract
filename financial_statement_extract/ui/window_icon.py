"""Application icon setup shared by the live and preview windows."""

from pathlib import Path
import sys
import tkinter as tk


_ASSET_DIR = Path(__file__).resolve().parent.parent / "assets"


def apply_window_icon(root: tk.Misc) -> None:
    """Apply the packaged FinExtract portrait icon to a Tk window."""
    if sys.platform == "win32":
        icon_path = _ASSET_DIR / "app_icon.ico"
        root.iconbitmap(default=str(icon_path))
        root._finextract_icon_path = icon_path
        return

    photo = tk.PhotoImage(master=root, file=str(_ASSET_DIR / "app_icon.png"))
    root.iconphoto(True, photo)
    # Tk must retain the PhotoImage for the lifetime of the window.
    root._finextract_icon_photo = photo
