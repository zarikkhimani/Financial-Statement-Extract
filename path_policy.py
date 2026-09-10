from __future__ import annotations

import re
from os import PathLike
from pathlib import Path
from urllib.parse import unquote, urlparse


_LOCAL_WINDOWS_DRIVE_URL = re.compile(r"^/[A-Za-z]:[/\\]")
_DEVICE_PREFIXES = (
    "\\??\\",
    "\\device\\",
    "\\globalroot\\",
    "\\global??\\",
)
_RESERVED_DEVICE_NAMES = {
    "aux",
    "clock$",
    "con",
    "conin$",
    "conout$",
    "nul",
    "prn",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


def _is_nonlocal_windows_path(value: str) -> bool:
    """Return True for UNC, extended, and Windows device namespace paths."""
    candidate = unquote(value).replace("/", "\\")
    lowered = candidate.casefold()
    if candidate.startswith("\\\\") or lowered.startswith(_DEVICE_PREFIXES):
        return True

    for component in candidate.split("\\"):
        cleaned = component.rstrip(" .")
        device_name = cleaned.split(".", 1)[0].split(":", 1)[0].casefold()
        if device_name in _RESERVED_DEVICE_NAMES:
            return True
    return False


def normalize_path(
    value: str | PathLike[str],
    *,
    allow_nonlocal_paths: bool = False,
) -> Path:
    """Normalize a path without touching the filesystem.

    Network shares and Windows device namespaces are rejected by default so a
    caller cannot accidentally trigger network or device access while merely
    checking whether an input exists. Library callers may opt in explicitly.
    """
    text = str(value).strip()
    if not text:
        raise ValueError("A path is required.")

    if text.casefold().startswith("file:"):
        parsed = urlparse(text)
        if parsed.scheme.casefold() != "file":
            raise ValueError("Only local file URLs are supported.")
        if parsed.netloc and not allow_nonlocal_paths:
            raise ValueError("Network file URLs are disabled by default.")
        decoded = unquote(parsed.path)
        if parsed.netloc:
            decoded = f"//{parsed.netloc}{decoded}"
        elif _LOCAL_WINDOWS_DRIVE_URL.match(decoded):
            decoded = decoded[1:]
        text = decoded

    if _is_nonlocal_windows_path(text) and not allow_nonlocal_paths:
        raise ValueError("UNC, network, and Windows device paths are disabled by default.")

    return Path(text)
