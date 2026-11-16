"""Portable source snapshots for the seven reviewed table-cutoff cases.

Only external PDF readers are substituted. Candidate scoring, selection,
statement recovery, auditing and workbook writing execute production code.
"""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from financial_statement_extract import extract_filing

FIXTURES = Path(__file__).parent / "fixtures/table_completeness"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))


def load(name):
    path = FIXTURES / name
    entry = next(r for r in MANIFEST["artifacts"] if r["file"] == name)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"], "Fixture changed without source review"
    return json.loads(gzip.decompress(path.read_bytes()))


CASES = [load(f"TC{i:02d}.json.gz") for i in range(1, 8)]
CONTROLS = load("controls.json.gz")


class SnapshotPage:
    def __init__(self, data):
        self.data = deepcopy(data)
        self.width, self.height = data["width"], data["height"]

    def extract_text(self, **kwargs):
        assert not kwargs, "Capture new reader options explicitly before extending the snapshot"
        return self.data["text"]

    def extract_words(self, **kwargs):
        assert kwargs == {"x_tolerance": 1, "y_tolerance": 2}
        return deepcopy(self.data["words"])

    def find_tables(self, **kwargs):
        assert not kwargs
        tables = []
        for item in self.data["tables"]:
            tables.append(SimpleNamespace(bbox=tuple(item["bbox"]), cells=deepcopy(item["cells"]),
                          rows=[SimpleNamespace(cells=deepcopy(row)) for row in item["rows"]],
                          extract=lambda item=item: deepcopy(item["extracted"])))
        return tables


class SnapshotPDF:
    def __init__(self, case):
        # Page zero is accessed only for cover metadata. Other unrecorded pages fail explicitly.
        self.pages = [None] * max(p["number"] for p in case["pages"])
        self.pages[0] = SimpleNamespace(extract_text=lambda: "")
        for page in case["pages"]:
            self.pages[page["number"] - 1] = SnapshotPage(page)
        self.metadata = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def replay(case, monkeypatch, directory):
    import extractors
    import pipeline

    def camelot_read(path, *, pages, flavor, suppress_stdout):
        assert suppress_stdout is True
        page = next(p for p in case["pages"] if p["number"] == int(pages))
        return [SimpleNamespace(df=pd.DataFrame(deepcopy(t["rows"])),
                                parsing_report=deepcopy(t["parsing_report"]),
                                rows=deepcopy(t["row_bounds"]), cols=deepcopy(t["column_bounds"]))
                for t in page["camelot_candidates"] if t["flavor"] == flavor]

    monkeypatch.setattr(extractors.pdfplumber, "open", lambda *args, **kwargs: SnapshotPDF(case))
    monkeypatch.setattr(extractors.camelot, "read_pdf", camelot_read)
    # The separate experimental comparison does not feed selected statement tables.
    monkeypatch.setattr(pipeline, "extract_tables_pdfplumber_experimental", lambda *args: ([], [], []))
    source = directory / (case["id"] + ".pdf")
    source.write_bytes(b"%PDF-1.4\n% external-reader snapshot fixture\n")
    return extract_filing(source, output_dir=directory,
                          pages=",".join(str(p["number"]) for p in case["pages"]), page_policy="exact")
