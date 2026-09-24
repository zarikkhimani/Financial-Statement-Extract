from app import FinancialExtractorApp
from financial_statement_extract.ui.controller import ExtractionController
from financial_statement_extract.ui.lifecycle import JobLifecycle
from financial_statement_extract.ui.state import WorkspaceState
import pytest
import subprocess
import sys
import textwrap
from pathlib import Path


class FakeRoot:
    def __init__(self):
        self.quit_calls = 0
        self.destroy_calls = 0
        self.after_calls = 0

    def quit(self):
        self.quit_calls += 1

    def destroy(self):
        self.destroy_calls += 1

    def after(self, *_args):
        self.after_calls += 1


class FakeProgress:
    def __init__(self):
        self.stop_calls = 0

    def stop(self):
        self.stop_calls += 1


class ActiveWorker:
    @staticmethod
    def is_alive():
        return True


@pytest.mark.parametrize("confirmed", [False, True])
def test_exit_warns_with_active_worker_and_defaults_to_staying_open(monkeypatch, confirmed):
    app = FinancialExtractorApp.__new__(FinancialExtractorApp)
    app.root = FakeRoot()
    app.progress = FakeProgress()
    app.controller = ExtractionController()
    app.controller.worker = ActiveWorker()
    app.closing = False
    app._confirming_close = False
    calls = []

    def confirm(*args, **kwargs):
        calls.append((args, kwargs))
        app._on_close()  # A nested close event must not open a second prompt.
        return confirmed

    monkeypatch.setattr("app.messagebox.askyesno", confirm)

    app._on_close()
    assert app.closing is confirmed
    assert app.progress.stop_calls == int(confirmed)
    assert app.root.quit_calls == int(confirmed)
    assert app.root.destroy_calls == int(confirmed)
    assert calls[0][1]["default"] == "no"
    assert "incomplete workbook" in calls[0][0][1]
    assert len(calls) == 1
    if confirmed:
        app._on_close()
        assert len(calls) == 1


def test_queue_poller_does_not_reschedule_while_closing():
    app = FinancialExtractorApp.__new__(FinancialExtractorApp)
    app.root = FakeRoot()
    app.controller = ExtractionController()
    app.closing = True
    app.controller.work_queue.put(("pdf_error", "Queued after shutdown"))

    app._poll_queue()

    assert app.root.after_calls == 0
    assert not app.controller.work_queue.empty()


def test_exit_warns_until_queued_outcome_is_consumed(monkeypatch):
    app = FinancialExtractorApp.__new__(FinancialExtractorApp)
    app.root = FakeRoot()
    app.progress = FakeProgress()
    app.controller = ExtractionController()
    app.lifecycle = JobLifecycle()
    draft = WorkspaceState(input_path="synthetic.pdf")
    app.lifecycle.begin(draft.to_request(), draft.draft_key())
    app.closing = app._confirming_close = False
    calls = []
    monkeypatch.setattr("app.messagebox.askyesno", lambda *args, **kw: calls.append(args) or False)
    app._on_close()
    assert len(calls) == 1
    assert not app.closing
    app.lifecycle.succeed()
    app._on_close()
    assert len(calls) == 1  # Idle/completed closing is not unnecessarily blocked.
    assert app.closing


@pytest.mark.parametrize("busy", [False, True])
@pytest.mark.parametrize("close_action", ["window", "button", "menu"])
def test_actual_gui_process_exits_when_closed(tmp_path, busy, close_action):
    # Exercise the actual entrypoint/Tk window and an indefinitely blocked
    # extraction worker. A process timeout catches invisible background work.
    marker = tmp_path / "window-closed.txt"
    script = textwrap.dedent('''
        import sys
        import threading
        import tkinter as tk
        import traceback
        from pathlib import Path
        from financial_statement_extract.ui import workspace
        from financial_statement_extract.ui.state import WorkspaceState

        marker = Path(sys.argv[1])
        busy = sys.argv[2] == "True"
        close_action = sys.argv[3]
        original_app = workspace.FinancialExtractorApp
        entered = threading.Event()

        def runner(*args):
            entered.set()
            threading.Event().wait()  # Only process exit can stop this job.

        def create_app(root):
            app = original_app(root, runner=runner)
            def callback_error(*exc):
                traceback.print_exception(*exc)
                root.quit()
            root.report_callback_exception = callback_error
            def close():
                assert root.state() == "normal"
                assert root.winfo_viewable()
                if busy:
                    app.controller.start(WorkspaceState(input_path="synthetic.pdf").to_request())
                    assert entered.wait(5)
                    assert app.controller.is_running
                if close_action == "window":
                    root.tk.call(root.protocol("WM_DELETE_WINDOW"))
                elif close_action == "button":
                    app.exit_button.invoke()
                else:
                    file_menu = root.nametowidget(app.accessibility.menu.entrycget("File", "menu"))
                    file_menu.invoke("Exit")
                assert app.closing
                try:
                    assert not root.winfo_exists()
                except tk.TclError:
                    pass  # Tk interpreter has also gone away.
                marker.write_text("closed", encoding="utf-8")
            root.after(100, close)
            return app

        # The test runner may intentionally use an isolated Windows desktop.
        # Only bypass that startup policy; run the real window/close lifecycle.
        workspace.require_interactive_desktop = lambda: None
        workspace.FinancialExtractorApp = create_app
        workspace.messagebox.askyesno = lambda *args, **kwargs: True
        workspace.main()
    ''')
    completed = subprocess.run(
        [sys.executable, "-c", script, str(marker), str(busy), close_action],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    assert marker.is_file(), completed.stderr
    assert marker.read_text(encoding="utf-8") == "closed"
