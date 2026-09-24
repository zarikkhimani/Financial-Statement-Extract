"""Visible-desktop startup policy, without moving or switching desktops."""

import ctypes
import sys
from ctypes import wintypes
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from financial_statement_extract.ui import desktop, workspace


@pytest.mark.skipif(sys.platform != "win32", reason="Windows desktop APIs")
@pytest.mark.parametrize("visible", [False, True])
def test_desktop_check_rejects_only_inactive_desktop(monkeypatch, visible):
    def information(handle, index, value, size, needed):
        assert handle == 123
        assert index == 6
        assert size == ctypes.sizeof(wintypes.BOOL)
        ctypes.cast(value, ctypes.POINTER(wintypes.BOOL))[0] = visible
        return True

    user32 = SimpleNamespace(GetThreadDesktop=Mock(return_value=123),
                             GetUserObjectInformationW=Mock(side_effect=information))
    kernel32 = SimpleNamespace(GetCurrentThreadId=Mock(return_value=456))
    monkeypatch.setattr(desktop.ctypes, "WinDLL", lambda name, **kw: user32 if name == "user32" else kernel32)
    if visible:
        desktop.require_interactive_desktop()
    else:
        with pytest.raises(RuntimeError, match="hidden or locked desktop"):
            desktop.require_interactive_desktop()
    user32.GetThreadDesktop.assert_called_once_with(456)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows desktop APIs")
@pytest.mark.parametrize("failed_api", ["GetThreadDesktop", "GetUserObjectInformationW"])
def test_desktop_api_failure_does_not_allow_hidden_startup(monkeypatch, failed_api):
    user32 = SimpleNamespace(GetThreadDesktop=Mock(return_value=123),
                             GetUserObjectInformationW=Mock(return_value=True))
    getattr(user32, failed_api).return_value = 0
    kernel32 = SimpleNamespace(GetCurrentThreadId=Mock(return_value=456))
    monkeypatch.setattr(desktop.ctypes, "WinDLL", lambda name, **kw: user32 if name == "user32" else kernel32)
    with pytest.raises(OSError):
        desktop.require_interactive_desktop()


def test_rejected_launch_creates_no_window_or_worker(monkeypatch):
    guard = Mock(side_effect=RuntimeError("hidden desktop"))
    create_root = Mock()
    create_app = Mock()
    monkeypatch.setattr(workspace, "require_interactive_desktop", guard)
    monkeypatch.setattr(workspace.TkinterDnD, "Tk", create_root)
    monkeypatch.setattr(workspace, "FinancialExtractorApp", create_app)
    with pytest.raises(RuntimeError, match="hidden desktop"):
        workspace.main()
    create_root.assert_not_called()
    create_app.assert_not_called()


@pytest.mark.parametrize("failure", ["initialization", "display", "event_loop", None])
def test_entrypoint_always_cleans_up_window(monkeypatch, failure):
    root = Mock()
    root.winfo_viewable.return_value = failure != "display"
    app = SimpleNamespace(closing=False)
    create_app = Mock(return_value=app)
    if failure == "initialization":
        create_app.side_effect = RuntimeError("setup failed")
    if failure == "event_loop":
        root.mainloop.side_effect = RuntimeError("event loop failed")
    monkeypatch.setattr(workspace, "require_interactive_desktop", lambda: None)
    monkeypatch.setattr(workspace.TkinterDnD, "Tk", lambda: root)
    monkeypatch.setattr(workspace, "FinancialExtractorApp", create_app)
    showerror = Mock()
    monkeypatch.setattr(workspace.messagebox, "showerror", showerror)
    if failure:
        with pytest.raises(RuntimeError):
            workspace.main()
        showerror.assert_called_once()
    else:
        workspace.main()
        assert app.closing
        showerror.assert_not_called()
    root.destroy.assert_called_once()
    if failure in {"initialization", "display"}:
        root.mainloop.assert_not_called()
