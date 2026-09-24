"""Compare an Apple balance-sheet candidate with the reviewed phase-1 reference.

Read-only. Exit 0: no bounded differences; 1: differences; 2: invalid evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.compare_workbook_baseline import has_differences, inspect_workbook


def load_reference(folder, *, required_files=()):
    """Read only hash-verified evidence, including every requested companion."""
    folder = folder.resolve()
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    for name, record in manifest["files"].items():
        path = (folder / name).resolve()
        if not path.is_relative_to(folder):
            raise ValueError(f"Evidence path escapes baseline: {name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Evidence integrity check failed: {name}")
    if not {"source.pdf", "before.xlsx", "expected.json", *required_files} <= manifest["files"].keys():
        raise ValueError("Manifest does not register all required evidence")
    reference = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
    if reference["source_sha256"] != manifest["files"]["source.pdf"]["sha256"]:
        raise ValueError("Reference belongs to a different PDF")
    return reference


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args(argv)
    try:
        reference = load_reference(args.baseline)
        result = inspect_workbook(args.candidate, reference)
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 1 if has_differences(result) else 0
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
