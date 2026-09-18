"""Tests for Column vs Measure resolution in visual bindings (issue #19)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from pbi_cli.core.bulk_backend import visual_bulk_bind
from pbi_cli.core.errors import PbiCliError
from pbi_cli.core.field_resolver import (
    FieldIndex,
    find_semantic_model_dir,
    index_from_bim,
    index_from_report,
    index_from_tmdl_dir,
    index_from_tom,
)
from pbi_cli.core.report_backend import page_add, report_create
from pbi_cli.core.visual_backend import visual_add, visual_bind
from pbi_cli.main import cli

SALES_TMDL = """table Sales
\tlineageTag: 1111

\tmeasure 'Total Revenue' = SUM(Sales[Amount])
\t\tformatString: #,0
\t\tlineageTag: 2222

\tmeasure Margin = ```
\t\t\tVAR x = 1
\t\t\tcolumn Fake = 1
\t\t\tRETURN x
\t\t\t```
\t\tlineageTag: 3333

\tcolumn Region
\t\tdataType: string
\t\tsourceColumn: Region

\tcolumn 'Order Date'
\t\tdataType: dateTime

\tcolumn 'It''s Quoted'
\t\tdataType: string

\tcolumn Amount
\t\tdataType: double

\tpartition Sales = m
\t\tmode: import
\t\tsource =
\t\t\t\tlet
\t\t\t\t    column = 1
\t\t\t\tin column
"""

MEASURES_TMDL = """table _Measures
\tmeasure 'Order Count' = COUNTROWS(Sales)
"""


def _projection(definition: Path, page: str, visual: str, role: str) -> list[dict[str, Any]]:
    vfile = definition / "pages" / page / "visuals" / visual / "visual.json"
    data = json.loads(vfile.read_text(encoding="utf-8"))
    projections: list[dict[str, Any]] = data["visual"]["query"]["queryState"][role]["projections"]
    return projections


def _kind(projection: dict[str, Any]) -> str:
    return next(iter(projection["field"]))


def _lookup_kind(index: FieldIndex, table: str, name: str) -> str:
    hit = index.lookup(table, name)
    assert hit is not None, f"{table}[{name}] not indexed"
    return hit.kind


@pytest.fixture
def pbip(tmp_path: Path) -> Path:
    """A PBIP project with a TMDL model; returns the report ``definition/`` path."""
    report_create(tmp_path, "Test")
    tables = tmp_path / "Test.SemanticModel" / "definition" / "tables"
    tables.mkdir()
    (tables / "Sales.tmdl").write_text(SALES_TMDL, encoding="utf-8")
    (tables / "_Measures.tmdl").write_text(MEASURES_TMDL, encoding="utf-8")
    definition = tmp_path / "Test.Report" / "definition"
    page_add(definition, "Page1", name="page1")
    return definition


@pytest.fixture
def blank_pbip(tmp_path: Path) -> Path:
    """A PBIP project whose semantic model has no tables (fresh scaffold)."""
    report_create(tmp_path, "Blank")
    definition = tmp_path / "Blank.Report" / "definition"
    page_add(definition, "Page1", name="page1")
    return definition


# ---------------------------------------------------------------------------
# Index builders
# ---------------------------------------------------------------------------


def test_tmdl_index_classifies_columns_and_measures(pbip: Path) -> None:
    index = index_from_tmdl_dir(pbip.parent.parent / "Test.SemanticModel" / "definition")
    assert _lookup_kind(index, "Sales", "Region") == "column"
    assert _lookup_kind(index, "Sales", "Order Date") == "column"
    assert _lookup_kind(index, "Sales", "It's Quoted") == "column"
    assert _lookup_kind(index, "Sales", "Total Revenue") == "measure"
    assert _lookup_kind(index, "Sales", "Margin") == "measure"


def test_tmdl_index_ignores_text_inside_expressions(pbip: Path) -> None:
    index = index_from_tmdl_dir(pbip.parent.parent / "Test.SemanticModel" / "definition")
    assert index.lookup("Sales", "Fake") is None
    assert index.lookup("Sales", "column") is None
    assert len(index) == 7  # 5 columns + 2 measures in Sales, 1 measure in _Measures


def test_lookup_is_case_insensitive_and_returns_canonical_names(pbip: Path) -> None:
    index = index_from_report(pbip)
    assert index is not None
    hit = index.lookup("sales", "region")
    assert hit is not None
    assert (hit.table, hit.name) == ("Sales", "Region")


def test_measure_on_wrong_table_resolves_to_home_table(pbip: Path) -> None:
    index = index_from_report(pbip)
    assert index is not None
    hit = index.lookup("Sales", "Order Count")
    assert hit is not None
    assert (hit.kind, hit.table) == ("measure", "_Measures")


def test_index_from_bim(tmp_path: Path) -> None:
    bim = tmp_path / "model.bim"
    bim.write_text(
        json.dumps(
            {
                "model": {
                    "tables": [
                        {
                            "name": "Geo",
                            "columns": [
                                {"name": "RowNumber-1", "type": "rowNumber"},
                                {"name": "City"},
                            ],
                            "measures": [{"name": "Cities"}],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    index = index_from_bim(bim)
    assert _lookup_kind(index, "Geo", "City") == "column"
    assert _lookup_kind(index, "Geo", "Cities") == "measure"
    assert index.lookup("Geo", "RowNumber-1") is None


def test_index_from_tom(mock_session: Any) -> None:
    index = index_from_tom(mock_session.model)
    assert _lookup_kind(index, "Sales", "Amount") == "column"
    assert _lookup_kind(index, "Sales", "Total Sales") == "measure"


def test_find_semantic_model_dir(pbip: Path, tmp_path: Path) -> None:
    assert find_semantic_model_dir(pbip) == (tmp_path / "Test.SemanticModel").resolve()


def test_index_from_report_none_for_blank_model(blank_pbip: Path) -> None:
    assert index_from_report(blank_pbip) is None


def test_index_from_report_none_for_live_connected_report(tmp_path: Path) -> None:
    definition = tmp_path / "Live.Report" / "definition"
    definition.mkdir(parents=True)
    (definition.parent / "definition.pbir").write_text(
        json.dumps({"datasetReference": {"byConnection": {"connectionString": "x"}}}),
        encoding="utf-8",
    )
    assert index_from_report(definition) is None


# ---------------------------------------------------------------------------
# visual_bind resolution
# ---------------------------------------------------------------------------


def test_slicer_bound_to_column_emits_column(pbip: Path) -> None:
    """The exact repro from issue #19."""
    visual_add(pbip, "page1", "slicer", name="slicer_region")
    result = visual_bind(
        pbip, "page1", "slicer_region", [{"role": "field", "field": "Sales[Region]"}]
    )
    proj = _projection(pbip, "page1", "slicer_region", "Values")[0]
    assert _kind(proj) == "Column"
    assert proj["active"] is True
    assert result["bindings"][0]["kind"] == "Column"
    assert result["bindings"][0]["resolved_by"] == "tmdl"
    assert "warnings" not in result


@pytest.mark.parametrize("vtype", ["slicer", "textSlicer", "listSlicer", "advancedSlicerVisual"])
def test_slicers_default_to_column_without_model(blank_pbip: Path, vtype: str) -> None:
    visual_add(blank_pbip, "page1", vtype, name="s")
    result = visual_bind(blank_pbip, "page1", "s", [{"role": "field", "field": "Geo[City]"}])
    assert _kind(_projection(blank_pbip, "page1", "s", "Values")[0]) == "Column"
    assert result["bindings"][0]["resolved_by"] == "default"
    # No model to check against, so no "not found" warning.
    assert "warnings" not in result


def test_card_bound_to_measure_emits_measure(pbip: Path) -> None:
    visual_add(pbip, "page1", "card", name="c")
    visual_bind(pbip, "page1", "c", [{"role": "field", "field": "Sales[Total Revenue]"}])
    proj = _projection(pbip, "page1", "c", "Values")[0]
    assert _kind(proj) == "Measure"
    assert "active" not in proj


def test_card_bound_to_column_emits_column(pbip: Path) -> None:
    visual_add(pbip, "page1", "card", name="c")
    visual_bind(pbip, "page1", "c", [{"role": "field", "field": "Sales[Region]"}])
    assert _kind(_projection(pbip, "page1", "c", "Values")[0]) == "Column"


def test_table_mixes_columns_and_measures(pbip: Path) -> None:
    visual_add(pbip, "page1", "table", name="t")
    visual_bind(
        pbip,
        "page1",
        "t",
        [
            {"role": "value", "field": "Sales[Region]"},
            {"role": "value", "field": "Sales[Order Date]"},
            {"role": "value", "field": "Sales[Total Revenue]"},
        ],
    )
    kinds = [_kind(p) for p in _projection(pbip, "page1", "t", "Values")]
    assert kinds == ["Column", "Column", "Measure"]


def test_table_role_defaults_without_model(blank_pbip: Path) -> None:
    visual_add(blank_pbip, "page1", "table", name="t")
    visual_bind(
        blank_pbip,
        "page1",
        "t",
        [
            {"role": "column", "field": "Geo[City]"},
            {"role": "value", "field": "Sales[Revenue]"},
        ],
    )
    kinds = [_kind(p) for p in _projection(blank_pbip, "page1", "t", "Values")]
    assert kinds == ["Column", "Measure"]


def test_measure_on_wrong_table_is_rewritten_to_home_table(pbip: Path) -> None:
    visual_add(pbip, "page1", "card", name="c")
    result = visual_bind(pbip, "page1", "c", [{"role": "field", "field": "Sales[Order Count]"}])
    proj = _projection(pbip, "page1", "c", "Values")[0]
    assert proj["field"]["Measure"]["Expression"]["SourceRef"]["Entity"] == "_Measures"
    assert proj["queryRef"] == "_Measures.Order Count"
    assert result["bindings"][0]["field"] == "Sales[Order Count]"


def test_names_are_canonicalised_from_model(pbip: Path) -> None:
    visual_add(pbip, "page1", "slicer", name="s")
    visual_bind(pbip, "page1", "s", [{"role": "field", "field": "sales[region]"}])
    proj = _projection(pbip, "page1", "s", "Values")[0]
    assert proj["queryRef"] == "Sales.Region"


def test_unknown_field_warns_and_falls_back(pbip: Path) -> None:
    visual_add(pbip, "page1", "card", name="c")
    result = visual_bind(pbip, "page1", "c", [{"role": "field", "field": "Sales[Typo]"}])
    assert _kind(_projection(pbip, "page1", "c", "Values")[0]) == "Measure"
    assert result["bindings"][0]["resolved_by"] == "default"
    assert "Sales[Typo]" in result["warnings"][0]


def test_explicit_kind_overrides_model(pbip: Path) -> None:
    visual_add(pbip, "page1", "slicer", name="s")
    result = visual_bind(
        pbip, "page1", "s", [{"role": "field", "field": "Sales[Region]", "kind": "measure"}]
    )
    assert _kind(_projection(pbip, "page1", "s", "Values")[0]) == "Measure"
    assert result["bindings"][0]["resolved_by"] == "explicit"


def test_legacy_measure_flag_still_forces_measure(blank_pbip: Path) -> None:
    visual_add(blank_pbip, "page1", "bar", name="b")
    visual_bind(
        blank_pbip, "page1", "b", [{"role": "category", "field": "Geo[City]", "measure": True}]
    )
    assert _kind(_projection(blank_pbip, "page1", "b", "Category")[0]) == "Measure"


def test_invalid_kind_raises(blank_pbip: Path) -> None:
    visual_add(blank_pbip, "page1", "card", name="c")
    with pytest.raises(PbiCliError, match="Invalid field kind"):
        visual_bind(blank_pbip, "page1", "c", [{"role": "field", "field": "A[B]", "kind": "x"}])


def test_live_index_used_only_for_fields_missing_on_disk(pbip: Path) -> None:
    calls: list[int] = []
    live = FieldIndex(source="live model")
    live.add("column", "NewTable", "NewCol")

    def loader() -> FieldIndex:
        calls.append(1)
        return live

    visual_add(pbip, "page1", "card", name="c")
    visual_bind(
        pbip,
        "page1",
        "c",
        [{"role": "field", "field": "Sales[Total Revenue]"}],
        live_index_loader=loader,
    )
    assert calls == []  # on-disk model answered, no connection opened

    result = visual_bind(
        pbip,
        "page1",
        "c",
        [
            {"role": "field", "field": "NewTable[NewCol]"},
            {"role": "field", "field": "NewTable[Other]"},
        ],
        live_index_loader=loader,
    )
    assert calls == [1]  # loaded once, reused for the second miss
    assert result["bindings"][0]["resolved_by"] == "live model"
    assert result["bindings"][0]["kind"] == "Column"


def test_live_loader_failure_falls_back_to_default(blank_pbip: Path) -> None:
    visual_add(blank_pbip, "page1", "slicer", name="s")
    result = visual_bind(
        blank_pbip,
        "page1",
        "s",
        [{"role": "field", "field": "Geo[City]"}],
        live_index_loader=lambda: None,
    )
    assert result["bindings"][0]["resolved_by"] == "default"
    assert _kind(_projection(blank_pbip, "page1", "s", "Values")[0]) == "Column"


def test_bulk_bind_resolves_per_field(pbip: Path) -> None:
    visual_add(pbip, "page1", "slicer", name="s1")
    visual_add(pbip, "page1", "slicer", name="s2")
    result = visual_bulk_bind(
        pbip, "page1", "slicer", [{"role": "field", "field": "Sales[Region]"}]
    )
    assert result["bound"] == 2
    for name in ("s1", "s2"):
        assert _kind(_projection(pbip, "page1", name, "Values")[0]) == "Column"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _invoke(runner: CliRunner, definition: Path, *args: str) -> Any:
    report = str(definition.parent)
    return runner.invoke(cli, ["--json", "visual", "--path", report, "--no-sync", *args])


def test_cli_bind_slicer_column(cli_runner: CliRunner, pbip: Path, tmp_connections: Path) -> None:
    _invoke(cli_runner, pbip, "add", "--page", "page1", "--type", "slicer", "--name", "s")
    result = _invoke(cli_runner, pbip, "bind", "s", "--page", "page1", "--field", "Sales[Region]")
    assert result.exit_code == 0, result.output
    assert _kind(_projection(pbip, "page1", "s", "Values")[0]) == "Column"


def test_cli_bind_kind_override(cli_runner: CliRunner, pbip: Path, tmp_connections: Path) -> None:
    _invoke(cli_runner, pbip, "add", "--page", "page1", "--type", "card", "--name", "c")
    result = _invoke(
        cli_runner,
        pbip,
        "bind",
        "c",
        "--page",
        "page1",
        "--field",
        "Sales[Total Revenue]",
        "--kind",
        "column",
    )
    assert result.exit_code == 0, result.output
    assert _kind(_projection(pbip, "page1", "c", "Values")[0]) == "Column"


def test_cli_bind_table_column_option(
    cli_runner: CliRunner, blank_pbip: Path, tmp_connections: Path
) -> None:
    _invoke(cli_runner, blank_pbip, "add", "--page", "page1", "--type", "table", "--name", "t")
    result = _invoke(
        cli_runner,
        blank_pbip,
        "bind",
        "t",
        "--page",
        "page1",
        "--column",
        "Geo[City]",
        "--value",
        "Sales[Revenue]",
    )
    assert result.exit_code == 0, result.output
    kinds = {p["queryRef"]: _kind(p) for p in _projection(blank_pbip, "page1", "t", "Values")}
    assert kinds == {"Geo.City": "Column", "Sales.Revenue": "Measure"}


def test_cli_bind_uses_live_model_when_disk_model_is_blank(
    cli_runner: CliRunner,
    blank_pbip: Path,
    patch_session: Any,
    tmp_connections: Path,
) -> None:
    """Issue #19 flow: tables made via `pbi connect`, report scaffolded blank."""
    _invoke(cli_runner, blank_pbip, "add", "--page", "page1", "--type", "card", "--name", "c")
    result = _invoke(
        cli_runner,
        blank_pbip,
        "bind",
        "c",
        "--page",
        "page1",
        "--field",
        "Sales[Amount]",
        "--field",
        "Sales[Total Sales]",
    )
    assert result.exit_code == 0, result.output
    kinds = [_kind(p) for p in _projection(blank_pbip, "page1", "c", "Values")]
    assert kinds == ["Column", "Measure"]


def test_cli_bulk_bind_kind(cli_runner: CliRunner, blank_pbip: Path, tmp_connections: Path) -> None:
    _invoke(cli_runner, blank_pbip, "add", "--page", "page1", "--type", "card", "--name", "c1")
    result = _invoke(
        cli_runner,
        blank_pbip,
        "bulk-bind",
        "--page",
        "page1",
        "--type",
        "card",
        "--field",
        "Geo[City]",
        "--kind",
        "column",
    )
    assert result.exit_code == 0, result.output
    assert _kind(_projection(blank_pbip, "page1", "c1", "Values")[0]) == "Column"
