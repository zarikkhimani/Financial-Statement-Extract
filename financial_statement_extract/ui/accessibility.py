"""Session-only display preferences and discoverable native keyboard commands."""

import tkinter as tk
from tkinter import messagebox

from .theme import apply_workspace_theme


TEXT_SCALES = (1.0, 1.25, 1.5, 1.75, 2.0)
SHORTCUTS = (
    "Tab / Shift+Tab: next / previous control\n"
    "Ctrl+O: browse filing\nCtrl+Shift+O: browse output folder\n"
    "Ctrl+Enter: current primary action (when enabled)\n"
    "Alt+S: show / hide setup\nAlt+D: show / hide details\n"
    "Alt+G: show / hide diagnostics\nF6: focus results or recovery text\n"
    "Ctrl+Tab / Ctrl+Shift+Tab: switch result tabs\n"
    "Arrow keys: select a table row; Tab: read its full details\n"
    "Ctrl+A / Ctrl+C: select all / copy in read-only text\n"
    "Ctrl+Plus / Ctrl+Minus: text size; Ctrl+0: reset to 100%\n"
    "F8: read current status and result summary\nF1: this help\n\n"
    "Display preferences last for this session. At larger sizes, use the work-area "
    "scrollbar; tabbing to a control also brings it into view."
)


class WorkspaceAccessibility:
    def __init__(self, app):
        self.app = app
        root = app.root
        self.text_scale = tk.DoubleVar(master=root, value=app.theme.text_scale)
        self.system_colors = tk.BooleanVar(master=root, value=app.theme.system_colors)
        menu = tk.Menu(root)
        root.configure(menu=menu)
        self.menu = menu
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Browse filing…", accelerator="Ctrl+O", command=app._choose_pdf)
        file_menu.add_command(label="Browse output folder…", accelerator="Ctrl+Shift+O", command=app._choose_output_dir)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=app._on_close)
        menu.add_cascade(label="File", underline=0, menu=file_menu)
        view = tk.Menu(menu, tearoff=False)
        for label, shortcut, command in (
            ("Toggle setup", "Alt+S", app.shell.toggle_setup),
            ("Toggle details", "Alt+D", self.toggle_details),
            ("Toggle diagnostics", "Alt+G", app.results.toggle_diagnostics),
            ("Focus results", "F6", app.results.focus_content),
        ):
            view.add_command(label=label, accelerator=shortcut, command=command)
        sizes = tk.Menu(view, tearoff=False)
        for scale in TEXT_SCALES:
            sizes.add_radiobutton(label=f"{scale:.0%}", variable=self.text_scale, value=scale, command=self.refresh)
        view.add_cascade(label="Text size", menu=sizes)
        view.add_checkbutton(label="Use Windows system colors", variable=self.system_colors, command=self.refresh,
                             state="normal" if root.tk.call("tk", "windowingsystem") == "win32" else "disabled")
        menu.add_cascade(label="View", underline=0, menu=view)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="Keyboard shortcuts", accelerator="F1", command=self.help)
        help_menu.add_command(label="Current status and summary", accelerator="F8", command=self.read_status)
        menu.add_cascade(label="Help", underline=0, menu=help_menu)
        for sequence, command in (
            ("<Control-o>", app._choose_pdf), ("<Control-O>", app._choose_output_dir),
            ("<Control-Return>", app.shell.primary_button.invoke),
            ("<Alt-s>", app.shell.toggle_setup), ("<Alt-d>", self.toggle_details),
            ("<Alt-g>", app.results.toggle_diagnostics), ("<F6>", app.results.focus_content),
            ("<F1>", self.help), ("<F8>", self.read_status),
            ("<Control-plus>", lambda: self.resize(1)), ("<Control-equal>", lambda: self.resize(1)),
            ("<Control-KP_Add>", lambda: self.resize(1)), ("<Control-minus>", lambda: self.resize(-1)),
            ("<Control-KP_Subtract>", lambda: self.resize(-1)), ("<Control-0>", lambda: self.set_scale(1.0)),
        ):
            root.bind(sequence, lambda _event, callback=command: self._invoke(callback))

    @staticmethod
    def _invoke(command):
        command()
        return "break"

    def toggle_details(self):
        self.app.shell.set_setup_visible(True)
        self.app.shell.setup_panel.toggle_details()

    def resize(self, direction):
        index = min(range(len(TEXT_SCALES)), key=lambda i: abs(TEXT_SCALES[i] - self.text_scale.get()))
        self.set_scale(TEXT_SCALES[max(0, min(len(TEXT_SCALES) - 1, index + direction))])

    def set_scale(self, scale):
        if scale not in TEXT_SCALES:
            raise ValueError("Choose a supported text size from 100% to 200%.")
        self.text_scale.set(scale)
        self.refresh()

    def refresh(self):
        app = self.app
        scroll = [(widget, widget.yview()[0]) for widget in (
            *app.results.tables.values(), *app.results.details.values(), app.results.note, app.results.diagnostics)]
        apply_workspace_theme(app.root, text_scale=self.text_scale.get(),
                              system_colors=self.system_colors.get(), theme=app.theme)
        app.shell.refresh_theme()
        app.results.refresh_theme()
        app.results.reflow_footer()
        app.root.update_idletasks()
        for widget, fraction in scroll:
            widget.yview_moveto(fraction)
        focused = app.root.focus_get()
        if focused is not None and str(focused).startswith(str(app.shell.body) + "."):
            app.shell.viewport.reveal(focused)

    def help(self):
        messagebox.showinfo("Keyboard shortcuts", SHORTCUTS, parent=self.app.root)

    def read_status(self):
        app = self.app
        text = f"{app.results.headline.get()}\n{app.shell.status_text.get()}\n{app.shell.disabled_reason.get()}"
        if app.results.summary:
            text += f"\n{app.results.summary.overview}\nWorkbook: {app.results.output.get()}\nPages: {app.results.pages.get()}"
        else:
            text += "\n" + app.results.note.get("1.0", "end-1c")
        messagebox.showinfo("Current status and summary", text.strip(), parent=app.root)
