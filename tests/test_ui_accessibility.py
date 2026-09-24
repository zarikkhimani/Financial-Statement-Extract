"""Native keyboard, enlarged-text overflow, and session preference regressions."""

from tkinter import ttk

import pytest

from models import ExtractionResult
from test_ui_workspace import make_workspace as _workspace_fixture, unexpected_runner

make_workspace = _workspace_fixture


def inside(child, parent):
    assert child.winfo_ismapped(), str(child)
    assert parent.winfo_rootx() <= child.winfo_rootx()
    assert parent.winfo_rooty() <= child.winfo_rooty()
    assert child.winfo_rootx() + child.winfo_width() <= parent.winfo_rootx() + parent.winfo_width(), str(child)
    assert child.winfo_rooty() + child.winfo_height() <= parent.winfo_rooty() + parent.winfo_height(), str(child)


@pytest.mark.parametrize("scale", [1.0, 1.25, 1.5, 1.75, 2.0])
@pytest.mark.parametrize("size", ["640x700", "720x820", "1120x820"])
def test_text_sizes_keep_actions_and_expanded_setup_reachable(make_workspace, scale, size):
    app, _dialogs = make_workspace(unexpected_runner, text_scale=scale)
    app.pdf_path.set(r"C:\Example\Long filing name for keyboard review.pdf")
    app.client_name.set("Long company name " * 8)
    app.root.geometry(size)
    app.root.deiconify()
    app.root.update()
    app.shell.set_setup_visible(True)
    app.shell.setup_panel.set_details_visible(True)
    app.root.update()
    for widget in (app.shell.primary_button, app.shell.setup_toggle, app.shell.status_label,
                   app.shell.source_entry, app.shell.output_entry):
        inside(widget, app.root)
    assert app.shell.source_entry.winfo_width() >= 60
    assert app.shell.viewport.winfo_height() >= 80
    for widget in app.shell.setup_panel.entries.values():
        app.shell.viewport.reveal(widget)
        inside(widget, app.shell.viewport.canvas)
    app.results.focus_content()
    app.root.update()
    app.shell.viewport.reveal(app.results.note)
    inside(app.results.note, app.shell.viewport.canvas)
    assert app.results.note.winfo_height() >= 50
    assert app.state.client_name == "Long company name " * 8
    assert app.controller.worker is None


@pytest.mark.parametrize("scale", [1.0, 1.5, 2.0])
def test_long_results_and_recovery_at_large_text(make_workspace, scale):
    app, _dialogs = make_workspace(unexpected_runner, text_scale=scale)
    app.root.geometry("640x700")
    app.root.deiconify()
    result = ExtractionResult({}, [], [], [], [], {}, [], [], [])
    result.financial_audit_rows = [dict(Status="WARN", Check=f"Long check {i}", Scope="Document",
                                      Detail="Long detail " * 80) for i in range(60)]
    app.results.show_result(result, r"C:\Long output folder\Long workbook.xlsx")
    app.folder_button.pack(side="left")
    app.root.update()
    tree = app.results.tables["Checks"]
    tree.selection_set("40")
    tree.focus("40")
    tree.see("40")
    app.root.update()
    assert tree.winfo_height() >= 70
    app.shell.viewport.reveal(tree)
    assert tree.winfo_width() > 200
    assert "Long check 40" in app.results.details["Checks"].get("1.0", "end")
    for widget in (app.results.toggle, app.folder_button):
        app.shell.viewport.reveal(widget)
        inside(widget, app.shell.viewport.canvas)
    app.results.show_note("Extraction failed", "Check output access. Your settings are retained. Retry when ready. " * 12)
    app.results.focus_content()
    app.root.update()
    assert app.results.note.winfo_height() >= 50
    inside(app.shell.primary_button, app.root)


def test_keyboard_shortcuts_and_readonly_text_do_not_trap_focus(make_workspace, monkeypatch):
    app, dialogs = make_workspace(unexpected_runner)
    app.root.deiconify()
    app.root.update()
    note = app.results.note
    note.focus_force()
    app.root.update()
    assert app.root.focus_get() is note
    expected = note.tk_focusNext()
    note.event_generate("<Tab>")
    app.root.update()
    assert app.root.focus_get() is expected
    note.focus_set()
    expected = note.tk_focusPrev()
    note.event_generate("<Shift-Tab>")
    app.root.update()
    assert app.root.focus_get() is expected
    note.focus_set()
    note.event_generate("<Control-a>")
    app.root.update()
    assert note.tag_ranges("sel")
    original = note.get("1.0", "end")
    note.event_generate("<KeyPress>", keysym="x")
    assert note.get("1.0", "end") == original
    app.root.event_generate("<F1>")
    app.root.event_generate("<F8>")
    assert [dialog[1] for dialog in dialogs] == ["Keyboard shortcuts", "Current status and summary"]
    app.root.event_generate("<Alt-g>")
    assert app.results.diagnostics_visible
    app.root.event_generate("<F6>")
    app.root.update()
    assert app.root.focus_get() is app.results.diagnostics
    calls = []
    app.shell.set_primary_action("Disabled", lambda: calls.append(True), enabled=False, reason="Test unavailable")
    app.root.event_generate("<Control-Return>")
    assert not calls
    app.shell.set_primary_action("Enabled", lambda: calls.append(True))
    app.root.event_generate("<Control-Return>")
    assert calls == [True]


def test_live_scale_and_palette_changes_keep_widgets_draft_and_result(make_workspace):
    app, _dialogs = make_workspace(unexpected_runner)
    app.root.deiconify()
    app.root.update()
    app.client_name.set("Keep this draft")
    app.shell.setup_panel.set_details_visible(True)
    app.results.diagnostics.insert("end", "\n".join(f"line {i}" for i in range(100)))
    app.results.toggle_diagnostics()
    app.results.diagnostics.yview_moveto(0.4)
    app.results.diagnostics.focus_force()
    app.root.update()
    fonts = {role: str(value) for role, value in app.theme.fonts.items()}
    controls = dict(app.shell.setup_panel.entries)
    for scale in (2.0, 1.5, 1.0):
        app.accessibility.set_scale(scale)
        app.root.update()
        assert {role: str(value) for role, value in app.theme.fonts.items()} == fonts
        assert app.shell.setup_panel.entries == controls
        assert app.state.client_name == "Keep this draft"
        assert app.results.diagnostics_visible
        assert app.shell.setup_panel.details_visible
        assert app.results.diagnostics.yview()[0] == pytest.approx(0.4, abs=0.015)
        assert app.root.focus_get() is app.results.diagnostics
    if app.root.tk.call("tk", "windowingsystem") == "win32":
        app.accessibility.system_colors.set(True)
        app.accessibility.refresh()
        app.root.update()
        assert app.results.note.cget("foreground") == "SystemWindowText"
        assert app.results.note.cget("selectbackground") == "SystemHighlight"
        style = ttk.Style(app.root)
        assert style.lookup("Error.TLabel", "foreground") == "SystemWindowText"
        assert style.layout("Accent.TButton") == style.layout("TButton")
        assert style.lookup("Accent.TButton", "foreground") == "SystemButtonText"
        app.accessibility.system_colors.set(False)
        app.accessibility.refresh()
        assert app.results.note.cget("foreground") == app.theme.colors["text-primary"]
    assert app.controller.worker is None


def test_result_keyboard_tabs_and_scale_keep_selection(make_workspace):
    app, _dialogs = make_workspace(unexpected_runner)
    result = ExtractionResult({}, [], [], [], [], {}, [], [], [])
    result.financial_audit_rows = [dict(Status="WARN", Check=str(i), Detail="Review " * 80) for i in range(60)]
    app.results.show_result(result, "output.xlsx")
    app.root.deiconify()
    app.root.update()
    tree = app.results.tables["Checks"]
    tree.selection_set("40")
    tree.focus("40")
    tree.yview_moveto(0.5)
    app.root.update()
    first = tree.yview()[0]
    detail = app.results.details["Checks"]
    detail.focus_force()
    app.root.update()
    detail.event_generate("<Control-Tab>")
    app.root.update()
    assert app.results.notebook.index(app.results.notebook.select()) == 0
    app.results.tables["Statements"].event_generate("<Control-Shift-Tab>")
    app.root.update()
    assert app.results.notebook.index(app.results.notebook.select()) == 1
    for scale in (2.0, 1.0):
        app.accessibility.set_scale(scale)
        app.root.update()
        assert tree.selection() == ("40",)
        assert tree.yview()[0] == pytest.approx(first, abs=0.02)
    assert app.controller.worker is None


def test_tab_order_reaches_offscreen_controls_at_200_percent(make_workspace):
    app, _dialogs = make_workspace(unexpected_runner, text_scale=2.0)
    app.pdf_path.set(r"C:\Example\filing.pdf")
    app.root.geometry("640x700")
    app.root.deiconify()
    app.root.update()
    app.shell.set_setup_visible(True)
    app.shell.setup_panel.set_details_visible(True)
    app.root.update()
    app.shell.setup_toggle.focus_force()
    app.root.update()
    seen = set()
    entries = set(app.shell.setup_panel.entries.values())
    for _ in range(40):
        focused = app.root.focus_get()
        assert focused is not None and focused is not app.root
        seen.add(focused)
        if focused in entries:
            inside(focused, app.shell.viewport.canvas)
        focused.event_generate("<Tab>")
        app.root.update()
    assert entries <= seen
    assert app.shell.primary_button in seen
    assert app.shell.source_entry in seen
    assert app.shell.output_entry in seen


@pytest.mark.parametrize("phase", ["running", "error", "success"])
def test_large_text_lifecycle_actions_fit_minimum_window(make_workspace, tmp_path, phase):
    app, _dialogs = make_workspace(unexpected_runner, text_scale=2.0)
    app.pdf_path.set(str(tmp_path / "filing.pdf"))
    app.lifecycle.begin(app.state.to_request(), app.state)
    if phase == "error":
        app._job_failed("Synthetic permission problem", "PermissionError")
    elif phase == "success":
        app.lifecycle.succeed()
        app._has_result = True
        app._result_output = tmp_path / "workbook.xlsx"
    app._refresh_setup()
    app.root.geometry("640x700")
    app.root.deiconify()
    app.root.update()
    inside(app.shell.primary_button, app.root)
    inside(app.exit_button, app.root)
    inside(app.shell.status_label, app.root)
    assert app.shell.viewport.winfo_height() >= 100
    if phase == "running":
        inside(app.shell.reason_label, app.root)
        assert app.shell.disabled_reason.get()
    if phase == "success":
        inside(app.result_action, app.root)
