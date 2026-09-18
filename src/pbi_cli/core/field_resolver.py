"""Resolve whether a ``Table[Field]`` reference is a column or a measure.

Visual bindings must wrap each field as either a ``Column`` or a ``Measure``
expression in PBIR. Guessing from the data role alone is wrong for slicers
and tables (their ``Values`` role almost always holds columns), so the
binder asks the semantic model first. Three sources are supported:

- TMDL (``<Name>.SemanticModel/definition/tables/*.tmdl``)
- TMSL (``<Name>.SemanticModel/model.bim``)
- A live TOM model from ``pbi connect``

The report folder locates its semantic model via
``definition.pbir -> datasetReference.byPath.path``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

FieldKind = Literal["column", "measure"]


@dataclass(frozen=True)
class ResolvedField:
    """A field found in the semantic model, with canonical casing."""

    kind: FieldKind
    table: str
    name: str


@dataclass
class FieldIndex:
    """Case-insensitive lookup of columns and measures by table."""

    source: str = ""
    _fields: dict[tuple[str, str], ResolvedField] = field(default_factory=dict)
    _measures_by_name: dict[str, list[ResolvedField]] = field(default_factory=dict)

    def add(self, kind: FieldKind, table: str, name: str) -> None:
        resolved = ResolvedField(kind=kind, table=table, name=name)
        self._fields[(table.lower(), name.lower())] = resolved
        if kind == "measure":
            self._measures_by_name.setdefault(name.lower(), []).append(resolved)

    def __len__(self) -> int:
        return len(self._fields)

    def lookup(self, table: str, name: str) -> ResolvedField | None:
        """Find ``table[name]``.

        Measure names are unique across a model, so a measure referenced
        under the wrong table (e.g. ``Sales[Total]`` when it lives on
        ``_Measures``) is still found and returned with its home table.
        """
        hit = self._fields.get((table.lower(), name.lower()))
        if hit is not None:
            return hit
        measures = self._measures_by_name.get(name.lower(), [])
        if len(measures) == 1:
            return measures[0]
        return None


# ---------------------------------------------------------------------------
# TMDL
# ---------------------------------------------------------------------------

_DECL_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<kw>table|column|measure)[ \t]+(?P<rest>.+)$")


def _parse_tmdl_name(rest: str) -> str:
    """Parse the object name that follows a TMDL keyword.

    Handles ``'Quoted Name'`` (with ``''`` escapes) and bare identifiers
    terminated by whitespace or ``=``.
    """
    rest = rest.strip()
    if rest.startswith("'"):
        out: list[str] = []
        i = 1
        while i < len(rest):
            ch = rest[i]
            if ch == "'":
                if i + 1 < len(rest) and rest[i + 1] == "'":
                    out.append("'")
                    i += 2
                    continue
                break
            out.append(ch)
            i += 1
        return "".join(out)
    match = re.match(r"[^\s=]+", rest)
    return match.group(0) if match else rest


def _index_tmdl_text(text: str, index: FieldIndex) -> None:
    table: str | None = None
    child_indent: str | None = None
    in_fence = False

    for raw in text.splitlines():
        line = raw.rstrip("\r\n")
        stripped = line.strip()
        if in_fence:
            if stripped.startswith("```"):
                in_fence = False
            continue
        if not stripped:
            continue
        # A ``` fence opens a verbatim block, either on its own line or
        # trailing the declaration (``measure X = ```\``).
        if stripped.endswith("```"):
            in_fence = True

        match = _DECL_RE.match(line)
        if match is None:
            if table is not None and child_indent is None and line[:1] in (" ", "\t"):
                child_indent = line[: len(line) - len(line.lstrip())]
            continue

        indent = match.group("indent")
        kw = match.group("kw")
        if kw == "table" and indent == "":
            table = _parse_tmdl_name(match.group("rest"))
            child_indent = None
            continue
        if table is None:
            continue
        if child_indent is None:
            child_indent = indent
        if indent != child_indent:
            continue
        index.add(kw, table, _parse_tmdl_name(match.group("rest")))  # type: ignore[arg-type]


def index_from_tmdl_dir(definition_dir: Path) -> FieldIndex:
    """Index every ``tables/*.tmdl`` file under a TMDL ``definition`` folder."""
    index = FieldIndex(source="tmdl")
    tables_dir = definition_dir / "tables"
    if not tables_dir.is_dir():
        return index
    for tmdl in sorted(tables_dir.glob("*.tmdl")):
        try:
            _index_tmdl_text(tmdl.read_text(encoding="utf-8-sig"), index)
        except (OSError, UnicodeDecodeError):
            continue
    return index


# ---------------------------------------------------------------------------
# TMSL (model.bim)
# ---------------------------------------------------------------------------


def index_from_bim(bim_path: Path) -> FieldIndex:
    index = FieldIndex(source="model.bim")
    data = json.loads(bim_path.read_text(encoding="utf-8-sig"))
    for table in data.get("model", {}).get("tables", []):
        tname = table.get("name", "")
        for col in table.get("columns", []):
            if col.get("type") == "rowNumber":
                continue
            index.add("column", tname, col.get("name", ""))
        for meas in table.get("measures", []):
            index.add("measure", tname, meas.get("name", ""))
    return index


# ---------------------------------------------------------------------------
# Live TOM model
# ---------------------------------------------------------------------------


def index_from_tom(model: Any) -> FieldIndex:
    """Index a ``Microsoft.AnalysisServices.Tabular.Model``."""
    index = FieldIndex(source="live model")
    for table in model.Tables:
        tname = str(table.Name)
        for col in table.Columns:
            if str(col.Type) == "RowNumber":
                continue
            index.add("column", tname, str(col.Name))
        for meas in table.Measures:
            index.add("measure", tname, str(meas.Name))
    return index


# ---------------------------------------------------------------------------
# Report -> semantic model
# ---------------------------------------------------------------------------


def find_semantic_model_dir(definition_path: Path) -> Path | None:
    """Locate the semantic model folder referenced by a PBIR report.

    ``definition_path`` is the report's ``definition/`` folder. Returns
    ``None`` for live-connected reports (``byConnection``) or when the
    referenced folder is missing.
    """
    pbir = definition_path.parent / "definition.pbir"
    if not pbir.exists():
        return None
    try:
        data = json.loads(pbir.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    rel = data.get("datasetReference", {}).get("byPath", {}).get("path")
    if not rel:
        return None
    model_dir = (pbir.parent / rel).resolve()
    return model_dir if model_dir.is_dir() else None


def index_from_report(definition_path: Path) -> FieldIndex | None:
    """Build a field index from the semantic model a report points to."""
    model_dir = find_semantic_model_dir(definition_path)
    if model_dir is None:
        return None
    try:
        tmdl_dir = model_dir / "definition"
        if tmdl_dir.is_dir():
            index = index_from_tmdl_dir(tmdl_dir)
            if len(index):
                return index
        bim = model_dir / "model.bim"
        if bim.exists():
            return index_from_bim(bim)
    except (OSError, json.JSONDecodeError):
        return None
    return None
