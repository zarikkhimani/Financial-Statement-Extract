"""Reject Windows GUI launches that would create an inaccessible window."""

import ctypes
import sys
from ctypes import wintypes


def require_interactive_desktop():
    """Check once at startup; locking an already-open desktop must not end a job."""
    if sys.platform != "win32":
        return

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentThreadId.argtypes = []
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    user32.GetThreadDesktop.argtypes = [wintypes.DWORD]
    user32.GetThreadDesktop.restype = wintypes.HANDLE
    user32.GetUserObjectInformationW.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID,
        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetUserObjectInformationW.restype = wintypes.BOOL

    # GetThreadDesktop returns a borrowed handle; it must not be closed.
    desktop = user32.GetThreadDesktop(kernel32.GetCurrentThreadId())
    if not desktop:
        raise ctypes.WinError(ctypes.get_last_error())
    receives_input = wintypes.BOOL()
    needed = wintypes.DWORD()
    # UOI_IO reports whether this desktop receives the user's input.
    if not user32.GetUserObjectInformationW(
        desktop, 6, ctypes.byref(receives_input), ctypes.sizeof(receives_input), ctypes.byref(needed),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    if not receives_input.value:
        raise RuntimeError(
            "Financial Statement Extract cannot open on a hidden or locked desktop. "
            "Unlock your desktop and launch run.bat there. The application has not started."
        )
