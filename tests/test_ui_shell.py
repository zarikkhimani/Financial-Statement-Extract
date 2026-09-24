"""Native layout and state-retention checks for the Phase 2 preview."""

import subprocess
import sys
import tkinter as tk

import pytest

from financial_statement_extract.ui.preview import PreviewApp, SCENARIOS


@pytest.fixture
def preview(tkinter_root, monkeypatch):
    root = tk.Toplevel(tkinter_root)
    callback_errors = []
    monkeypatch.setattr(tkinter_root, "report_callback_exception", lambda *exc: callback_errors.append(exc))
    app = PreviewApp(root)
    root.update()
    yield app
    app.close()
    assert not callback_errors, callback_errors


@pytest.fixture(scope="module")
def tkinter_root(tk_runtime):
    return tk_runtime


def bounds(widget):
    return (widget.winfo_rootx(), widget.winfo_rooty(),
            widget.winfo_rootx() + widget.winfo_width(), widget.winfo_rooty() + widget.winfo_height())


def assert_inside(child, parent):
    left, top, right, bottom = bounds(child)
    pl, pt, pr, pb = bounds(parent)
    assert child.winfo_ismapped(), str(child)
    assert pl <= left < right <= pr and pt <= top < bottom <= pb, (str(child), bounds(child), bounds(parent))


def test_wide_shell_gives_results_most_width_and_does_not_clip_setup(preview):
    shell = preview.shell
    assert not shell.narrow
    assert shell.surface.winfo_width() > shell.body.winfo_width() * 0.65
    assert_inside(shell.primary_button, preview.root)
    assert_inside(shell.status_label, preview.root)
    assert_inside(shell.pages_help, shell.setup)
    for field in shell.fields:
        assert_inside(field, shell.setup)
        assert field.winfo_width() >= shell.setup.winfo_width() * 0.8


def test_collapse_and_reflow_keep_draft_selection_scroll_and_focus(preview):
    shell = preview.shell
    preview.variables.client_name.set("Edited sample name")
    preview.variables.pages.set("42-43,47")
    preview.table.selection_set("12")
    preview.table.focus("12")
    preview.table.yview_moveto(1.0)
    preview.root.update()
    selection = preview.table.selection()
    old_scroll = preview.table.yview()
    control = shell.setup_entries["client_name"]
    control.focus_force()
    preview.root.update()
    shell.toggle_setup()
    preview.root.update()
    assert preview.root.focus_get() is shell.setup_toggle
    assert not shell.setup.winfo_ismapped()
    assert shell.setup_toggle.cget("text") == "Show setup (modified)"
    shell.toggle_setup()
    preview.root.update()
    assert shell.setup_entries["client_name"] is control
    assert preview.table.selection() == selection
    assert preview.table.yview() == old_scroll

    preview.root.geometry("720x820")
    preview.root.update()
    assert shell.narrow
    assert not shell.setup_visible
    assert preview.table.selection() == selection
    assert preview.state.client_name == "Edited sample name"
    assert preview.state.pages == "42-43,47"
    shell.toggle_setup()
    preview.root.update()
    assert shell.setup_visible
    assert_inside(shell.setup_toggle, preview.root)
    assert_inside(shell.primary_button, preview.root)
    assert_inside(shell.pages_help, shell.setup)
    assert preview.table.winfo_height() >= preview.theme.px(90)
    preview.root.geometry("1120x820")
    preview.root.update()
    assert not shell.narrow and shell.setup_visible
    preview.root.geometry("720x820")
    preview.root.update()
    assert shell.setup_visible  # The narrow-layout choice was retained.


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_scenarios_fit_minimum_window_and_disabled_action_has_reason(preview, scenario):
    preview.root.geometry("640x700")
    preview.scenario.set(scenario)
    preview.root.update()
    shell = preview.shell
    assert_inside(shell.primary_button, preview.root)
    assert_inside(shell.status_label, preview.root)
    assert_inside(shell.setup_toggle, preview.root)
    assert_inside(preview.scenario_select, preview.root)
    assert_inside(preview.size_select, preview.root)
    assert not shell.setup_visible
    if scenario == "Running":
        assert shell.primary_button.instate(["disabled"])
        assert shell.disabled_reason.get()
        assert_inside(shell.reason_label, preview.root)
    else:
        assert shell.primary_button.instate(["!disabled"])


def test_preview_edits_and_simulation_do_not_load_extraction_stack():
    completed = subprocess.run(
        [sys.executable, "-c", (
            "import sys; import tkinter as tk; from financial_statement_extract.ui.preview import PreviewApp; "
            "r=tk.Tk(); r.withdraw(); a=PreviewApp(r, scenario='Ready'); "
            "a.shell.primary_button.invoke(); assert a.scenario.get() == 'Running'; "
            "r.after(2100, r.quit); r.mainloop(); assert a.scenario.get() == 'Completed'; "
            "assert not {'pipeline', 'pandas', 'pdfplumber', 'camelot'} & sys.modules.keys(); a.close()"
        )], capture_output=True, text=True, timeout=15,
    )
    assert completed.returncode == 0, completed.stderr


def test_switching_scenario_cancels_pending_simulation(preview):
    preview.scenario.set("Ready")
    preview.shell.primary_button.invoke()
    timer = preview._simulation_timer
    assert timer in preview.root.tk.call("after", "info")
    preview.scenario.set("Error")
    assert timer not in preview.root.tk.call("after", "info")
    assert preview._simulation_timer is None


def test_larger_text_uses_scaled_rows_and_retains_primary_action(tkinter_root):
    root = tk.Toplevel(tkinter_root)
    app = PreviewApp(root, size="720x820", text_scale=1.25)
    try:
        root.update()
        assert app.shell.narrow
        assert_inside(app.shell.primary_button, root)
        assert_inside(app.shell.setup_toggle, root)
        assert app.theme.fonts["body"].actual("size") > 10
    finally:
        app.close()


def test_text_uses_three_discrete_sizes_as_window_narrows(preview):
    preview.root.geometry("1120x820")
    preview.root.update()
    normal = preview.theme.fonts["body"].actual("size")
    assert preview.shell.text_size_tier == "normal"

    preview.root.geometry("900x820")
    preview.root.update()
    smaller = preview.theme.fonts["body"].actual("size")
    assert preview.shell.text_size_tier == "smaller"

    preview.root.geometry("700x820")
    preview.root.update()
    smallest = preview.theme.fonts["body"].actual("size")
    assert preview.shell.text_size_tier == "smallest"
    assert normal > smaller > smallest

    preview.root.geometry("1120x820")
    preview.root.update()
    assert preview.theme.fonts["body"].actual("size") == normal
    assert preview.shell.text_size_tier == "normal"
