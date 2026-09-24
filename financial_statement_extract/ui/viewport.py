"""Overflow for enlarged native controls without destroying their state."""

import tkinter as tk
from tkinter import ttk


class WorkspaceViewport(ttk.Frame):
    def __init__(self, parent, theme):
        super().__init__(parent, style="Surface.TFrame")
        self.theme = theme
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, width=1, height=1, highlightthickness=0, borderwidth=0,
                                background=theme.colors["surface"], takefocus=False)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.content = ttk.Frame(self.canvas, style="Surface.TFrame")
        self.window = self.canvas.create_window(0, 0, anchor="nw", window=self.content)
        self.minimum_height = lambda: 0
        self._geometry = None
        self._pending_sync = None
        self.canvas.bind("<Configure>", self.sync)
        self.content.bind("<Configure>", self.sync)
        parent.winfo_toplevel().bind("<FocusIn>", self._focus_into_view, add="+")
        parent.winfo_toplevel().bind("<MouseWheel>", self._wheel, add="+")
        parent.winfo_toplevel().bind("<<WorkspaceContentChanged>>", self.sync, add="+")
        parent.winfo_toplevel().bind("<Configure>", self._content_resized, add="+")

    def _content_resized(self, event):
        if str(event.widget).startswith(str(self.content)):
            self.sync()

    def _wheel(self, event):
        if (str(event.widget).startswith(str(self.canvas))
                and event.widget.winfo_class() in {"Canvas", "Frame", "TFrame", "TLabel"} and event.delta):
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
            return "break"

    def sync(self, _event=None):
        if self._pending_sync is None:
            # The top-level owns timer commands, matching its shutdown/cancel
            # boundary; registering them on children leaves stale Tcl commands.
            self._pending_sync = self.winfo_toplevel().after_idle(self._sync)

    def _sync(self):
        self._pending_sync = None
        height = max(1, self.canvas.winfo_height())
        total = max(height, self.minimum_height())
        if total > height:
            self.scrollbar.grid(row=0, column=1, sticky="ns")
        else:
            self.scrollbar.grid_remove()
        geometry = (max(1, self.canvas.winfo_width()), total)
        if geometry != self._geometry:
            self._geometry = geometry
            self.canvas.itemconfigure(self.window, width=geometry[0], height=total)
            self.canvas.configure(scrollregion=(0, 0, geometry[0], total))
        if total == height:
            self.canvas.yview_moveto(0)

    def _focus_into_view(self, event):
        widget = event.widget
        if str(widget).startswith(str(self.content) + "."):
            self.reveal(widget)

    def reveal(self, widget):
        """Scroll the outer workspace only; keep inner table/text scroll intact."""
        self.update_idletasks()
        height = self.canvas.winfo_height()
        total = max(height, self.content.winfo_height())
        top = widget.winfo_rooty() - self.content.winfo_rooty()
        visible_top = self.canvas.canvasy(0)
        bottom = top + min(widget.winfo_height(), height)
        if top < visible_top:
            self.canvas.yview_moveto(top / total)
        elif bottom > visible_top + height:
            self.canvas.yview_moveto((bottom - height) / total)
        self.update_idletasks()
