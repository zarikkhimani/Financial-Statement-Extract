"""Explicit local Windows open actions; never interpolate paths into commands."""

import os

from path_policy import normalize_path


def open_result_path(path, *, folder=False):
    local = normalize_path(path)
    if folder:
        if not local.is_dir():
            raise FileNotFoundError(f"Output folder is no longer available: {local}")
    else:
        if local.suffix.lower() != ".xlsx":
            raise ValueError("Only the generated .xlsx workbook can be opened here.")
        if not local.is_file():
            raise FileNotFoundError(f"Workbook is no longer available: {local}")
    os.startfile(str(local), "open")
