"""Tests for pbi_cli.core.report_backend.

Covers all public functions: report_info, report_create, report_validate,
page_list, page_add, page_delete, page_get, and theme_set.

A ``sample_report`` fixture builds a minimal valid PBIR folder in tmp_path
so every test starts from a consistent, known-good state.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pbi_cli.core.errors import PbiCliError
from pbi_cli.core.report_backend import (
    page_add,
    page_delete,
    page_get,
    page_list,
    page_set_background,
    page_set_visibility,
    report_create,
    report_info,
    report_validate,
    theme_diff,
    theme_get,
    theme_set,
)

# ---------------------------------------------------------------------------
# Schema constants (mirrors pbir_models.py -- used only for fixture JSON)
# ---------------------------------------------------------------------------

_SCHEMA_REPORT = (
    "https://developer.microsoft.com/json-schemas/"
    "fabric/item/report/definition/report/1.0.0/schema.json"
)
_SCHEMA_PAGE = (
    "https://developer.microsoft.com/json-schemas/"
    "fabric/item/report/definition/page/1.0.0/schema.json"
)
_SCHEMA_PAGES_METADATA = (
    "https://developer.microsoft.com/json-schemas/"
    "fabric/item/report/definition/pagesMetadata/1.0.0/schema.json"
)
_SCHEMA_VERSION = (
    "https://developer.microsoft.com/json-schemas/"
    "fabric/item/report/definition/versionMetadata/1.0.0/schema.json"
)
_SCHEMA_VISUAL_CONTAINER = (
    "https://developer.microsoft.com/json-schemas/"
    "fabric/item/report/definition/visualContainer/2.7.0/schema.json"
)
_SCHEMA_VISUAL_CONFIG = (
    "https://developer.microsoft.com/json-schemas/"
    "fabric/item/report/definition/visualConfiguration/2.3.0/schema.json"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, data: dict[str, Any]) -> None:
    """Write a dict as formatted JSON."""
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _read(path: Path) -> dict[str, Any]:
    """Read and parse a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[return-value]


def _make_page(
    pages_dir: Path,
    page_name: str,
    display_name: str,
    ordinal: int = 0,
    with_visual: bool = True,
) -> None:
    """Create a minimal page folder inside *pages_dir*."""
    page_dir = pages_dir / page_name
    page_dir.mkdir(parents=True, exist_ok=True)

    _write(
        page_dir / "page.json",
        {
            "$schema": _SCHEMA_PAGE,
            "name": page_name,
            "displayName": display_name,
            "displayOption": "FitToPage",
            "width": 1280,
            "height": 720,
            "ordinal": ordinal,
        },
    )

    visuals_dir = page_dir / "visuals"
    visuals_dir.mkdir(exist_ok=True)

    if with_visual:
        visual_dir = visuals_dir / "visual_def456"
        visual_dir.mkdir()
        _write(
            visual_dir / "visual.json",
            {
                "$schema": _SCHEMA_VISUAL_CONTAINER,
                "name": "vis1",
                "position": {"x": 50, "y": 50, "width": 400, "height": 300, "z": 0, "tabOrder": 0},
                "visual": {
                    "$schema": _SCHEMA_VISUAL_CONFIG,
                    "visualType": "barChart",
                    "query": {
                        "queryState": {
                            "Category": {"projections": []},
                            "Y": {"projections": []},
                        },
                    },
                    "objects": {},
                },
            },
        )


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_report(tmp_path: Path) -> Path:
    """Build a minimal valid PBIR folder and return the *definition* path.

    Layout::

        MyReport.Report/
            definition.pbir
            definition/
                version.json
                report.json
                pages/
                    pages.json
                    page_abc123/
                        page.json
                        visuals/
                            visual_def456/
                                visual.json
    """
    report_folder = tmp_path / "MyReport.Report"
    definition_dir = report_folder / "definition"
    pages_dir = definition_dir / "pages"
    pages_dir.mkdir(parents=True)

    # version.json
    _write(
        definition_dir / "version.json",
        {
            "$schema": _SCHEMA_VERSION,
            "version": "1.0.0",
        },
    )

    # report.json
    _write(
        definition_dir / "report.json",
        {
            "$schema": _SCHEMA_REPORT,
            "themeCollection": {
                "baseTheme": {
                    "name": "CY24SU06",
                    "reportVersionAtImport": "5.55",
                    "type": "SharedResources",
                },
            },
            "layoutOptimization": "Disabled",
        },
    )

    # pages.json
    _write(
        pages_dir / "pages.json",
        {
            "$schema": _SCHEMA_PAGES_METADATA,
            "pageOrder": ["page1"],
        },
    )

    # definition.pbir
    _write(
        report_folder / "definition.pbir",
        {
            "$schema": (
                "https://developer.microsoft.com/json-schemas/"
                "fabric/item/report/definitionProperties/2.0.0/schema.json"
            ),
            "version": "4.0",
        },
    )

    # Page with one visual
    _make_page(pages_dir, "page1", "Page One", ordinal=0, with_visual=True)

    return definition_dir


# ---------------------------------------------------------------------------
# report_info
# ---------------------------------------------------------------------------


class TestReportInfo:
    def test_report_info_returns_page_count(self, sample_report: Path) -> None:
        result = report_info(sample_report)
        assert result["page_count"] == 1

    def test_report_info_returns_theme(self, sample_report: Path) -> None:
        result = report_info(sample_report)
        assert result["theme"] == "CY24SU06"

    def test_report_info_counts_visuals(self, sample_report: Path) -> None:
        result = report_info(sample_report)
        assert result["total_visuals"] == 1

    def test_report_info_pages_structure(self, sample_report: Path) -> None:
        result = report_info(sample_report)
        pages = result["pages"]
        assert len(pages) == 1
        page = pages[0]
        assert page["name"] == "page1"
        assert page["display_name"] == "Page One"
        assert page["ordinal"] == 0
        assert page["visual_count"] == 1

    def test_report_info_includes_path(self, sample_report: Path) -> None:
        result = report_info(sample_report)
        assert "path" in result
        assert str(sample_report) in result["path"]

    def test_report_info_empty_report(self, tmp_path: Path) -> None:
        """A report with no pages directory returns zero counts."""
        definition_dir = tmp_path / "Empty.Report" / "definition"
        definition_dir.mkdir(parents=True)
        _write(
            definition_dir / "report.json",
            {
                "$schema": _SCHEMA_REPORT,
                "themeCollection": {
                    "baseTheme": {
                        "name": "CY24SU06",
                        "reportVersionAtImport": "5.55",
                        "type": "SharedResources",
                    },
                },
                "layoutOptimization": "Disabled",
            },
        )

        result = report_info(definition_dir)
        assert result["page_count"] == 0
        assert result["total_visuals"] == 0
        assert result["pages"] == []

    def test_report_info_multiple_pages(self, sample_report: Path) -> None:
        """Adding a second page updates page_count and total_visuals."""
        pages_dir = sample_report / "pages"
        # Second page with no visual
        _make_page(pages_dir, "page2", "Page Two", ordinal=1, with_visual=False)
        pages_meta = pages_dir / "pages.json"
        meta = _read(pages_meta)
        meta["pageOrder"] = ["page1", "page2"]
        _write(pages_meta, meta)

        result = report_info(sample_report)
        assert result["page_count"] == 2
        # page1 has 1 visual, page2 has 0
        assert result["total_visuals"] == 1

    def test_report_info_default_theme_when_missing(self, tmp_path: Path) -> None:
        """Returns 'Default' when themeCollection is absent from report.json."""
        definition_dir = tmp_path / "Bare.Report" / "definition"
        definition_dir.mkdir(parents=True)
        _write(
            definition_dir / "report.json",
            {
                "$schema": _SCHEMA_REPORT,
                "layoutOptimization": "Disabled",
            },
        )

        result = report_info(definition_dir)
        assert result["theme"] == "Default"


# ---------------------------------------------------------------------------
# report_create
# ---------------------------------------------------------------------------


class TestReportCreate:
    def test_report_create_returns_created_status(self, tmp_path: Path) -> None:
        result = report_create(tmp_path, "SalesReport")
        assert result["status"] == "created"
        assert result["name"] == "SalesReport"

    def test_report_create_report_folder_exists(self, tmp_path: Path) -> None:
        report_create(tmp_path, "SalesReport")
        assert (tmp_path / "SalesReport.Report").is_dir()

    def test_report_create_version_json_exists(self, tmp_path: Path) -> None:
        report_create(tmp_path, "SalesReport")
        version_file = tmp_path / "SalesReport.Report" / "definition" / "version.json"
        assert version_file.exists()
        data = _read(version_file)
        assert data["version"] == "2.0.0"

    def test_report_create_report_json_exists(self, tmp_path: Path) -> None:
        report_create(tmp_path, "SalesReport")
        report_json = tmp_path / "SalesReport.Report" / "definition" / "report.json"
        assert report_json.exists()
        data = _read(report_json)
        assert "themeCollection" in data
        assert "layoutOptimization" in data

    def test_report_create_pages_json_exists(self, tmp_path: Path) -> None:
        report_create(tmp_path, "SalesReport")
        pages_json = tmp_path / "SalesReport.Report" / "definition" / "pages" / "pages.json"
        assert pages_json.exists()
        data = _read(pages_json)
        assert data["pageOrder"] == []

    def test_report_create_definition_pbir_exists(self, tmp_path: Path) -> None:
        report_create(tmp_path, "SalesReport")
        pbir_file = tmp_path / "SalesReport.Report" / "definition.pbir"
        assert pbir_file.exists()

    def test_report_create_pbip_file_exists(self, tmp_path: Path) -> None:
        report_create(tmp_path, "SalesReport")
        pbip_file = tmp_path / "SalesReport.pbip"
        assert pbip_file.exists()
        data = _read(pbip_file)
        assert data["version"] == "1.0"
        assert any(
            a.get("report", {}).get("path") == "SalesReport.Report" for a in data["artifacts"]
        )

    def test_report_create_returns_definition_path(self, tmp_path: Path) -> None:
        result = report_create(tmp_path, "SalesReport")
        expected = str(tmp_path / "SalesReport.Report" / "definition")
        assert result["definition_path"] == expected

    def test_report_create_with_dataset(self, tmp_path: Path) -> None:
        """definition.pbir must include a datasetReference when dataset_path given."""
        result = report_create(tmp_path, "SalesReport", dataset_path="../SalesModel.Dataset")
        assert result["status"] == "created"
        pbir_file = tmp_path / "SalesReport.Report" / "definition.pbir"
        data = _read(pbir_file)
        assert "datasetReference" in data
        assert data["datasetReference"]["byPath"]["path"] == "../SalesModel.Dataset"

    def test_report_create_without_dataset_scaffolds_semantic_model(self, tmp_path: Path) -> None:
        """When no dataset path given, a blank semantic model is scaffolded."""
        report_create(tmp_path, "EmptyReport")
        pbir_file = tmp_path / "EmptyReport.Report" / "definition.pbir"
        data = _read(pbir_file)
        assert "datasetReference" in data
        assert data["datasetReference"]["byPath"]["path"] == "../EmptyReport.SemanticModel"
        # Semantic model files exist
        assert (tmp_path / "EmptyReport.SemanticModel" / "definition" / "model.tmdl").exists()
        assert (tmp_path / "EmptyReport.SemanticModel" / ".platform").exists()
        assert (tmp_path / "EmptyReport.SemanticModel" / "definition.pbism").exists()


# ---------------------------------------------------------------------------
# report_validate
# ---------------------------------------------------------------------------


class TestReportValidate:
    def test_report_validate_valid_report(self, sample_report: Path) -> None:
        result = report_validate(sample_report)
        assert result["valid"] is True
        assert result["errors"] == []

    def test_report_validate_counts_files_checked(self, sample_report: Path) -> None:
        result = report_validate(sample_report)
        # At minimum: version.json, report.json, pages/pages.json,
        # page1/page.json, page1/visuals/visual_def456/visual.json
        assert result["files_checked"] >= 5

    def test_report_validate_missing_report_json(self, tmp_path: Path) -> None:
        """Validation fails when report.json is absent."""
        definition_dir = tmp_path / "Bad.Report" / "definition"
        definition_dir.mkdir(parents=True)
        # Write version.json but no report.json
        _write(definition_dir / "version.json", {"$schema": _SCHEMA_VERSION, "version": "1.0.0"})

        result = report_validate(definition_dir)
        assert result["valid"] is False
        assert any("report.json" in e for e in result["errors"])

    def test_report_validate_missing_version_json(self, tmp_path: Path) -> None:
        """Validation fails when version.json is absent."""
        definition_dir = tmp_path / "NoVer.Report" / "definition"
        definition_dir.mkdir(parents=True)
        _write(
            definition_dir / "report.json",
            {
                "$schema": _SCHEMA_REPORT,
                "themeCollection": {"baseTheme": {}},
                "layoutOptimization": "Disabled",
            },
        )

        result = report_validate(definition_dir)
        assert result["valid"] is False
        assert any("version.json" in e for e in result["errors"])

    def test_report_validate_invalid_json(self, sample_report: Path) -> None:
        """Validation reports an error when a JSON file is malformed."""
        (sample_report / "report.json").write_text("{not valid json", encoding="utf-8")

        result = report_validate(sample_report)
        assert result["valid"] is False
        assert any("report.json" in e for e in result["errors"])

    def test_report_validate_missing_theme_collection(self, sample_report: Path) -> None:
        """report.json without 'themeCollection' is invalid."""
        _write(
            sample_report / "report.json",
            {
                "$schema": _SCHEMA_REPORT,
                "layoutOptimization": "Disabled",
            },
        )

        result = report_validate(sample_report)
        assert result["valid"] is False
        assert any("themeCollection" in e for e in result["errors"])

    def test_report_validate_page_missing_page_json(self, sample_report: Path) -> None:
        """A page folder without page.json is flagged as invalid."""
        orphan_page = sample_report / "pages" / "orphan_page"
        orphan_page.mkdir()
        (orphan_page / "visuals").mkdir()

        result = report_validate(sample_report)
        assert result["valid"] is False
        assert any("orphan_page" in e for e in result["errors"])

    def test_report_validate_nonexistent_folder(self, tmp_path: Path) -> None:
        """Validation of a path that does not exist reports an error."""
        missing = tmp_path / "does_not_exist" / "definition"
        result = report_validate(missing)
        assert result["valid"] is False
        assert result["files_checked"] == 0


# ---------------------------------------------------------------------------
# page_list
# ---------------------------------------------------------------------------


class TestPageList:
    def test_page_list_returns_list(self, sample_report: Path) -> None:
        result = page_list(sample_report)
        assert isinstance(result, list)

    def test_page_list_correct_count(self, sample_report: Path) -> None:
        result = page_list(sample_report)
        assert len(result) == 1

    def test_page_list_page_fields(self, sample_report: Path) -> None:
        page = page_list(sample_report)[0]
        assert page["name"] == "page1"
        assert page["display_name"] == "Page One"
        assert page["ordinal"] == 0
        assert page["width"] == 1280
        assert page["height"] == 720
        assert page["display_option"] == "FitToPage"
        assert page["visual_count"] == 1

    def test_page_list_empty_when_no_pages_dir(self, tmp_path: Path) -> None:
        """Returns empty list when the pages directory does not exist."""
        definition_dir = tmp_path / "NoPages.Report" / "definition"
        definition_dir.mkdir(parents=True)
        _write(
            definition_dir / "report.json",
            {
                "$schema": _SCHEMA_REPORT,
                "themeCollection": {"baseTheme": {}},
                "layoutOptimization": "Disabled",
            },
        )

        result = page_list(definition_dir)
        assert result == []

    def test_page_list_empty_pages_dir(self, tmp_path: Path) -> None:
        """Returns empty list when pages directory exists but has no page folders."""
        definition_dir = tmp_path / "Empty.Report" / "definition"
        pages_dir = definition_dir / "pages"
        pages_dir.mkdir(parents=True)
        _write(pages_dir / "pages.json", {"$schema": _SCHEMA_PAGES_METADATA, "pageOrder": []})

        result = page_list(definition_dir)
        assert result == []

    def test_page_list_respects_page_order(self, sample_report: Path) -> None:
        """Pages are sorted by the order declared in pages.json."""
        pages_dir = sample_report / "pages"
        _make_page(pages_dir, "page2", "Page Two", ordinal=1, with_visual=False)
        # Set page2 first in the explicit order
        _write(
            pages_dir / "pages.json",
            {
                "$schema": _SCHEMA_PAGES_METADATA,
                "pageOrder": ["page2", "page1"],
            },
        )

        result = page_list(sample_report)
        assert result[0]["name"] == "page2"
        assert result[1]["name"] == "page1"

    def test_page_list_falls_back_to_ordinal_sort(self, sample_report: Path) -> None:
        """Without an explicit pageOrder, pages sort by their ordinal field."""
        pages_dir = sample_report / "pages"
        _make_page(pages_dir, "page2", "Page Two", ordinal=1, with_visual=False)
        # Remove pageOrder
        _write(pages_dir / "pages.json", {"$schema": _SCHEMA_PAGES_METADATA, "pageOrder": []})

        result = page_list(sample_report)
        ordinals = [p["ordinal"] for p in result]
        assert ordinals == sorted(ordinals)

    def test_page_list_counts_visuals_correctly(self, sample_report: Path) -> None:
        """Visual count reflects only folders that contain visual.json."""
        pages_dir = sample_report / "pages"
        _make_page(pages_dir, "page2", "Two Visuals", ordinal=1, with_visual=True)
        # Add a second visual to page2
        second_visual = pages_dir / "page2" / "visuals" / "visual_second"
        second_visual.mkdir()
        _write(
            second_visual / "visual.json",
            {
                "$schema": _SCHEMA_VISUAL_CONTAINER,
                "name": "vis2",
                "position": {"x": 0, "y": 0, "width": 200, "height": 200, "z": 1, "tabOrder": 1},
                "visual": {"$schema": _SCHEMA_VISUAL_CONFIG, "visualType": "card", "objects": {}},
            },
        )

        result = page_list(sample_report)
        page2 = next(p for p in result if p["name"] == "page2")
        assert page2["visual_count"] == 2

    def test_page_list_regular_page_type_is_default(self, sample_report: Path) -> None:
        """Regular pages (no type field) surface as page_type='Default'."""
        pages = page_list(sample_report)
        assert pages[0]["page_type"] == "Default"

    def test_page_list_tooltip_page_type(self, sample_report: Path) -> None:
        """Tooltip pages surface as page_type='Tooltip'."""
        page_json = sample_report / "pages" / "page1" / "page.json"
        data = _read(page_json)
        _write(page_json, {**data, "type": "Tooltip"})
        pages = page_list(sample_report)
        assert pages[0]["page_type"] == "Tooltip"


# ---------------------------------------------------------------------------
# page_add
# ---------------------------------------------------------------------------


class TestPageAdd:
    def test_page_add_returns_created_status(self, sample_report: Path) -> None:
        result = page_add(sample_report, "New Page", name="new_page")
        assert result["status"] == "created"

    def test_page_add_creates_page_directory(self, sample_report: Path) -> None:
        page_add(sample_report, "New Page", name="new_page")
        assert (sample_report / "pages" / "new_page").is_dir()

    def test_page_add_creates_page_json(self, sample_report: Path) -> None:
        page_add(sample_report, "New Page", name="new_page")
        page_json = sample_report / "pages" / "new_page" / "page.json"
        assert page_json.exists()
        data = _read(page_json)
        assert data["name"] == "new_page"
        assert data["displayName"] == "New Page"

    def test_page_add_creates_visuals_directory(self, sample_report: Path) -> None:
        page_add(sample_report, "New Page", name="new_page")
        assert (sample_report / "pages" / "new_page" / "visuals").is_dir()

    def test_page_add_respects_custom_dimensions(self, sample_report: Path) -> None:
        page_add(sample_report, "Wide Page", name="wide_page", width=1920, height=1080)
        data = _read(sample_report / "pages" / "wide_page" / "page.json")
        assert data["width"] == 1920
        assert data["height"] == 1080

    def test_page_add_respects_display_option(self, sample_report: Path) -> None:
        page_add(sample_report, "Actual Size", name="actual_page", display_option="ActualSize")
        data = _read(sample_report / "pages" / "actual_page" / "page.json")
        assert data["displayOption"] == "ActualSize"

    def test_page_add_auto_name_is_generated(self, sample_report: Path) -> None:
        """Omitting name generates a non-empty hex identifier."""
        result = page_add(sample_report, "Auto Named")
        assert result["name"]
        assert len(result["name"]) == 20
        # The folder must also exist
        assert (sample_report / "pages" / result["name"]).is_dir()

    def test_page_add_auto_name_is_unique(self, sample_report: Path) -> None:
        """Two sequential auto-named pages receive different names."""
        r1 = page_add(sample_report, "Page A")
        r2 = page_add(sample_report, "Page B")
        assert r1["name"] != r2["name"]

    def test_page_add_updates_pages_json(self, sample_report: Path) -> None:
        """The new page name is appended to pageOrder in pages.json."""
        page_add(sample_report, "New Page", name="new_page")
        meta = _read(sample_report / "pages" / "pages.json")
        assert "new_page" in meta["pageOrder"]

    def test_page_add_appends_to_existing_page_order(self, sample_report: Path) -> None:
        """New page is appended after existing entries, not prepended."""
        page_add(sample_report, "New Page", name="new_page")
        meta = _read(sample_report / "pages" / "pages.json")
        assert meta["pageOrder"].index("page1") < meta["pageOrder"].index("new_page")

    def test_page_add_raises_on_duplicate_name(self, sample_report: Path) -> None:
        """Adding a page whose name already exists raises PbiCliError."""
        with pytest.raises(PbiCliError, match="page1"):
            page_add(sample_report, "Duplicate", name="page1")

    def test_page_add_is_appended_to_page_order(self, sample_report: Path) -> None:
        """New page is appended to pages.json pageOrder."""
        result = page_add(sample_report, "Second", name="second")
        assert result["status"] == "created"
        assert result["name"] == "second"


# ---------------------------------------------------------------------------
# page_delete
# ---------------------------------------------------------------------------


class TestPageDelete:
    def test_page_delete_returns_deleted_status(self, sample_report: Path) -> None:
        result = page_delete(sample_report, "page1")
        assert result["status"] == "deleted"
        assert result["name"] == "page1"

    def test_page_delete_removes_directory(self, sample_report: Path) -> None:
        page_delete(sample_report, "page1")
        assert not (sample_report / "pages" / "page1").exists()

    def test_page_delete_removes_from_page_order(self, sample_report: Path) -> None:
        page_delete(sample_report, "page1")
        meta = _read(sample_report / "pages" / "pages.json")
        assert "page1" not in meta["pageOrder"]

    def test_page_delete_removes_visuals_recursively(self, sample_report: Path) -> None:
        """All nested visual folders are removed along with the page."""
        visual_path = sample_report / "pages" / "page1" / "visuals" / "visual_def456"
        assert visual_path.exists()
        page_delete(sample_report, "page1")
        assert not visual_path.exists()

    def test_page_delete_not_found_raises(self, sample_report: Path) -> None:
        with pytest.raises(PbiCliError, match="ghost_page"):
            page_delete(sample_report, "ghost_page")

    def test_page_delete_only_removes_named_page(self, sample_report: Path) -> None:
        """Deleting one page leaves other pages intact."""
        pages_dir = sample_report / "pages"
        _make_page(pages_dir, "page2", "Page Two", ordinal=1, with_visual=False)

        page_delete(sample_report, "page1")

        assert not (pages_dir / "page1").exists()
        assert (pages_dir / "page2").exists()


# ---------------------------------------------------------------------------
# page_get
# ---------------------------------------------------------------------------


class TestPageGet:
    def test_page_get_returns_correct_name(self, sample_report: Path) -> None:
        result = page_get(sample_report, "page1")
        assert result["name"] == "page1"

    def test_page_get_returns_display_name(self, sample_report: Path) -> None:
        result = page_get(sample_report, "page1")
        assert result["display_name"] == "Page One"

    def test_page_get_returns_dimensions(self, sample_report: Path) -> None:
        result = page_get(sample_report, "page1")
        assert result["width"] == 1280
        assert result["height"] == 720

    def test_page_get_returns_display_option(self, sample_report: Path) -> None:
        result = page_get(sample_report, "page1")
        assert result["display_option"] == "FitToPage"

    def test_page_get_returns_ordinal(self, sample_report: Path) -> None:
        result = page_get(sample_report, "page1")
        assert result["ordinal"] == 0

    def test_page_get_counts_visuals(self, sample_report: Path) -> None:
        result = page_get(sample_report, "page1")
        assert result["visual_count"] == 1

    def test_page_get_not_found_raises(self, sample_report: Path) -> None:
        with pytest.raises(PbiCliError, match="missing_page"):
            page_get(sample_report, "missing_page")

    def test_page_get_zero_visuals_when_folder_empty(self, sample_report: Path) -> None:
        """A page whose visuals folder has no subdirectories returns 0."""
        pages_dir = sample_report / "pages"
        _make_page(pages_dir, "bare_page", "Bare", ordinal=1, with_visual=False)

        result = page_get(sample_report, "bare_page")
        assert result["visual_count"] == 0

    def test_page_get_default_page_type(self, sample_report: Path) -> None:
        """Regular pages surface page_type='Default'; filter_config and visual_interactions None."""
        result = page_get(sample_report, "page1")
        assert result["page_type"] == "Default"
        assert result["filter_config"] is None
        assert result["visual_interactions"] is None

    def test_page_get_tooltip_page_type(self, sample_report: Path) -> None:
        """Tooltip pages surface page_type='Tooltip'."""
        page_json = sample_report / "pages" / "page1" / "page.json"
        data = _read(page_json)
        _write(page_json, {**data, "type": "Tooltip"})
        result = page_get(sample_report, "page1")
        assert result["page_type"] == "Tooltip"

    def test_page_get_surfaces_filter_config(self, sample_report: Path) -> None:
        """page_get returns filterConfig as-is when present."""
        filter_config = {"filters": [{"name": "Filter1", "type": "Categorical"}]}
        page_json = sample_report / "pages" / "page1" / "page.json"
        data = _read(page_json)
        _write(page_json, {**data, "filterConfig": filter_config})
        result = page_get(sample_report, "page1")
        assert result["filter_config"] == filter_config
        assert result["filter_config"]["filters"][0]["name"] == "Filter1"

    def test_page_get_surfaces_visual_interactions(self, sample_report: Path) -> None:
        """page_get returns visualInteractions as-is when present."""
        interactions = [{"source": "visual_abc", "target": "visual_def", "type": "NoFilter"}]
        page_json = sample_report / "pages" / "page1" / "page.json"
        data = _read(page_json)
        _write(page_json, {**data, "visualInteractions": interactions})
        result = page_get(sample_report, "page1")
        assert result["visual_interactions"] == interactions
        assert result["visual_interactions"][0]["type"] == "NoFilter"

    def test_page_get_page_binding_none_for_regular_page(self, sample_report: Path) -> None:
        """Regular pages have no pageBinding -- returns None."""
        result = page_get(sample_report, "page1")
        assert result["page_binding"] is None

    def test_page_get_surfaces_page_binding(self, sample_report: Path) -> None:
        """Drillthrough pageBinding is returned as-is when present."""
        binding = {
            "name": "Pod",
            "type": "Drillthrough",
            "parameters": [
                {
                    "name": "Param_Filter1",
                    "boundFilter": "Filter1",
                }
            ],
        }
        page_json = sample_report / "pages" / "page1" / "page.json"
        data = _read(page_json)
        _write(page_json, {**data, "pageBinding": binding})
        result = page_get(sample_report, "page1")
        assert result["page_binding"] == binding
        assert result["page_binding"]["type"] == "Drillthrough"


# ---------------------------------------------------------------------------
# theme_set
# ---------------------------------------------------------------------------


class TestThemeSet:
    def _make_theme_file(self, tmp_path: Path, name: str = "MyTheme") -> Path:
        """Create a minimal theme JSON file and return its path."""
        theme_file = tmp_path / f"{name}.json"
        _write(
            theme_file,
            {
                "name": name,
                "dataColors": ["#118DFF", "#12239E"],
                "background": "#FFFFFF",
            },
        )
        return theme_file

    def test_theme_set_returns_applied_status(self, sample_report: Path, tmp_path: Path) -> None:
        theme_file = self._make_theme_file(tmp_path)
        result = theme_set(sample_report, theme_file)
        assert result["status"] == "applied"

    def test_theme_set_returns_theme_name(self, sample_report: Path, tmp_path: Path) -> None:
        theme_file = self._make_theme_file(tmp_path, name="CorporateBlue")
        result = theme_set(sample_report, theme_file)
        assert result["theme"] == "CorporateBlue"

    def test_theme_set_copies_file_to_registered_resources(
        self, sample_report: Path, tmp_path: Path
    ) -> None:
        theme_file = self._make_theme_file(tmp_path)
        result = theme_set(sample_report, theme_file)
        dest = Path(result["file"])
        assert dest.exists()

    def test_theme_set_dest_contains_theme_content(
        self, sample_report: Path, tmp_path: Path
    ) -> None:
        theme_file = self._make_theme_file(tmp_path, name="BrightTheme")
        result = theme_set(sample_report, theme_file)
        dest_data = _read(Path(result["file"]))
        assert dest_data["name"] == "BrightTheme"

    def test_theme_set_updates_report_json(self, sample_report: Path, tmp_path: Path) -> None:
        """report.json must have a 'customTheme' entry after theme_set."""
        theme_file = self._make_theme_file(tmp_path, name="Teal")
        theme_set(sample_report, theme_file)
        report_data = _read(sample_report / "report.json")
        custom = report_data["themeCollection"].get("customTheme")
        assert custom is not None
        assert custom["name"] == "Teal"

    def test_theme_set_adds_resource_package_entry(
        self, sample_report: Path, tmp_path: Path
    ) -> None:
        """resourcePackages list is created and includes the theme file."""
        theme_file = self._make_theme_file(tmp_path, name="Ocean")
        theme_set(sample_report, theme_file)
        report_data = _read(sample_report / "report.json")
        packages: list[dict[str, Any]] = report_data.get("resourcePackages", [])
        reg = next(
            (p for p in packages if p.get("name") == "RegisteredResources"),
            None,
        )
        assert reg is not None
        items = reg.get("items", [])
        assert any(i["name"] == "Ocean" for i in items)

    def test_theme_set_resource_package_path_is_bare_theme_name(
        self, sample_report: Path, tmp_path: Path
    ) -> None:
        """name/path match Desktop's own save output: the theme's display
        name, no folder prefix, no extension -- not the source filename."""
        theme_file = self._make_theme_file(tmp_path, name="Ocean")
        theme_set(sample_report, theme_file)
        report_data = _read(sample_report / "report.json")
        packages: list[dict[str, Any]] = report_data.get("resourcePackages", [])
        reg = next(p for p in packages if p.get("name") == "RegisteredResources")
        item = next(i for i in reg["items"] if i["name"] == "Ocean")
        assert item["path"] == "Ocean"

    def test_theme_set_resource_package_type_is_custom_theme_string(
        self, sample_report: Path, tmp_path: Path
    ) -> None:
        """type is the schema's ResourcePackageItemType string enum
        ("CustomTheme"), not a numeric code."""
        theme_file = self._make_theme_file(tmp_path, name="Ocean")
        theme_set(sample_report, theme_file)
        report_data = _read(sample_report / "report.json")
        packages: list[dict[str, Any]] = report_data.get("resourcePackages", [])
        reg = next(p for p in packages if p.get("name") == "RegisteredResources")
        item = next(i for i in reg["items"] if i["name"] == "Ocean")
        assert item["type"] == "CustomTheme"

    def test_theme_set_idempotent_for_same_theme(self, sample_report: Path, tmp_path: Path) -> None:
        """Applying the same theme twice does not duplicate resource entries."""
        theme_file = self._make_theme_file(tmp_path, name="Stable")
        theme_set(sample_report, theme_file)
        theme_set(sample_report, theme_file)
        report_data = _read(sample_report / "report.json")
        packages: list[dict[str, Any]] = report_data.get("resourcePackages", [])
        reg = next(p for p in packages if p.get("name") == "RegisteredResources")
        items = reg.get("items", [])
        names = [i["name"] for i in items]
        # No duplicate entries for the same theme
        assert names.count("Stable") == 1

    def test_theme_set_missing_theme_file_raises(self, sample_report: Path, tmp_path: Path) -> None:
        """Referencing a theme file that does not exist raises PbiCliError."""
        missing = tmp_path / "ghost_theme.json"
        with pytest.raises(PbiCliError, match="ghost_theme.json"):
            theme_set(sample_report, missing)

    def test_theme_set_dest_path_under_report_folder(
        self, sample_report: Path, tmp_path: Path
    ) -> None:
        """The copied theme file is placed inside the .Report folder hierarchy."""
        theme_file = self._make_theme_file(tmp_path, name="DarkMode")
        result = theme_set(sample_report, theme_file)
        dest = Path(result["file"])
        # definition_path is .Report/definition; dest should be under .Report/
        report_folder = sample_report.parent
        assert dest.is_relative_to(report_folder)


# ---------------------------------------------------------------------------
# theme_get
# ---------------------------------------------------------------------------


class TestThemeGet:
    def test_theme_get_base_only(self, sample_report: Path) -> None:
        """Reports with no custom theme return base_theme name and Nones."""
        result = theme_get(sample_report)
        assert result["base_theme"] == "CY24SU06"
        assert result["custom_theme"] is None
        assert result["theme_data"] is None

    def test_theme_get_with_custom(self, sample_report: Path, tmp_path: Path) -> None:
        """After applying a custom theme, theme_get returns its name and data."""
        theme_file = tmp_path / "Corporate.json"
        _write(theme_file, {"name": "Corporate", "dataColors": ["#FF0000"]})
        theme_set(sample_report, theme_file)

        result = theme_get(sample_report)
        assert result["custom_theme"] == "Corporate"
        assert result["theme_data"] is not None
        assert result["theme_data"]["name"] == "Corporate"

    def test_theme_get_missing_report_json_raises(self, tmp_path: Path) -> None:
        """theme_get raises PbiCliError when report.json is absent."""
        definition_dir = tmp_path / "Bad.Report" / "definition"
        definition_dir.mkdir(parents=True)
        with pytest.raises(PbiCliError):
            theme_get(definition_dir)

    def test_theme_get_no_base_theme_returns_empty_string(self, tmp_path: Path) -> None:
        """If themeCollection has no baseTheme, base_theme is an empty string."""
        definition_dir = tmp_path / "NoBase.Report" / "definition"
        definition_dir.mkdir(parents=True)
        _write(
            definition_dir / "report.json",
            {
                "$schema": _SCHEMA_REPORT,
                "themeCollection": {},
                "layoutOptimization": "Disabled",
            },
        )
        result = theme_get(definition_dir)
        assert result["base_theme"] == ""
        assert result["custom_theme"] is None


# ---------------------------------------------------------------------------
# theme_diff
# ---------------------------------------------------------------------------


class TestThemeDiff:
    def test_theme_diff_shows_changes(self, sample_report: Path, tmp_path: Path) -> None:
        """Diff between current and proposed theme reveals added/changed keys."""
        # Apply a base custom theme
        current_file = tmp_path / "Base.json"
        _write(current_file, {"name": "Base", "background": "#FFFFFF", "foreground": "#000000"})
        theme_set(sample_report, current_file)

        # Proposed: changed background, removed foreground, added accent
        proposed_file = tmp_path / "Proposed.json"
        _write(proposed_file, {"name": "Proposed", "background": "#111111", "accent": "#FF0000"})

        result = theme_diff(sample_report, proposed_file)
        assert result["proposed"] == "Proposed"
        assert "background" in result["changed"]
        assert "foreground" in result["removed"]
        assert "accent" in result["added"]

    def test_theme_diff_identical_returns_empty(self, sample_report: Path, tmp_path: Path) -> None:
        """Diffing an identical theme file returns empty added/removed/changed."""
        theme_file = tmp_path / "Same.json"
        _write(theme_file, {"name": "Same", "dataColors": ["#118DFF"]})
        theme_set(sample_report, theme_file)

        result = theme_diff(sample_report, theme_file)
        assert result["added"] == []
        assert result["removed"] == []
        assert result["changed"] == []

    def test_theme_diff_no_custom_all_keys_added(self, sample_report: Path, tmp_path: Path) -> None:
        """With no custom theme applied, every key in proposed appears in 'added'."""
        proposed_file = tmp_path / "New.json"
        _write(proposed_file, {"name": "New", "background": "#AABBCC", "accent": "#112233"})

        result = theme_diff(sample_report, proposed_file)
        assert result["added"] != []
        assert result["removed"] == []
        assert result["changed"] == []

    def test_theme_diff_current_label_uses_base_when_no_custom(
        self, sample_report: Path, tmp_path: Path
    ) -> None:
        """'current' label falls back to base theme name when no custom theme is set."""
        proposed_file = tmp_path / "Any.json"
        _write(proposed_file, {"name": "Any"})

        result = theme_diff(sample_report, proposed_file)
        assert result["current"] == "CY24SU06"


# ---------------------------------------------------------------------------
# Task 2 -- page_set_background
# ---------------------------------------------------------------------------


def test_page_set_background_writes_color(sample_report: Path) -> None:
    result = page_set_background(sample_report, "page1", "#F8F9FA")
    assert result["status"] == "updated"
    assert result["background_color"] == "#F8F9FA"
    assert result["transparency"] == 0
    page_data = _read(sample_report / "pages" / "page1" / "page.json")
    props = page_data["objects"]["background"][0]["properties"]
    assert props["color"]["solid"]["color"]["expr"]["Literal"]["Value"] == "'#F8F9FA'"
    # transparency must always be written so Desktop renders the color as opaque
    assert props["transparency"]["expr"]["Literal"]["Value"] == "0D"


def test_page_set_background_custom_transparency(sample_report: Path) -> None:
    result = page_set_background(sample_report, "page1", "#0E1117", transparency=50)
    assert result["transparency"] == 50
    page_data = _read(sample_report / "pages" / "page1" / "page.json")
    props = page_data["objects"]["background"][0]["properties"]
    assert props["transparency"]["expr"]["Literal"]["Value"] == "50D"


def test_page_set_background_rejects_invalid_transparency(sample_report: Path) -> None:
    with pytest.raises(PbiCliError, match="Invalid transparency"):
        page_set_background(sample_report, "page1", "#000000", transparency=101)


def test_page_set_background_preserves_other_objects(sample_report: Path) -> None:
    page_json = sample_report / "pages" / "page1" / "page.json"
    data = _read(page_json)
    data["objects"] = {"outspace": [{"properties": {"color": {}}}]}
    page_json.write_text(json.dumps(data, indent=2), encoding="utf-8")

    page_set_background(sample_report, "page1", "#FFFFFF")

    updated = _read(page_json)
    assert "outspace" in updated["objects"]
    assert "background" in updated["objects"]


def test_page_set_background_overrides_existing_background(sample_report: Path) -> None:
    page_set_background(sample_report, "page1", "#111111")
    page_set_background(sample_report, "page1", "#AABBCC")
    data = _read(sample_report / "pages" / "page1" / "page.json")
    bg = data["objects"]["background"][0]["properties"]["color"]
    assert bg["solid"]["color"]["expr"]["Literal"]["Value"] == "'#AABBCC'"


def test_page_set_background_raises_for_missing_page(sample_report: Path) -> None:
    with pytest.raises(PbiCliError, match="not found"):
        page_set_background(sample_report, "no_such_page", "#000000")


# ---------------------------------------------------------------------------
# Task 3 -- page_set_visibility
# ---------------------------------------------------------------------------


def test_page_set_visibility_hidden(sample_report: Path) -> None:
    result = page_set_visibility(sample_report, "page1", hidden=True)
    assert result["status"] == "updated"
    assert result["hidden"] is True
    data = _read(sample_report / "pages" / "page1" / "page.json")
    assert data.get("visibility") == "HiddenInViewMode"


def test_page_set_visibility_visible(sample_report: Path) -> None:
    # First hide, then show
    page_json = sample_report / "pages" / "page1" / "page.json"
    data = _read(page_json)
    page_json.write_text(
        json.dumps({**data, "visibility": "HiddenInViewMode"}, indent=2),
        encoding="utf-8",
    )

    result = page_set_visibility(sample_report, "page1", hidden=False)
    assert result["hidden"] is False
    updated = _read(page_json)
    assert "visibility" not in updated


def test_page_set_visibility_idempotent_visible(sample_report: Path) -> None:
    # Calling visible on an already-visible page should not add visibility key
    page_set_visibility(sample_report, "page1", hidden=False)
    data = _read(sample_report / "pages" / "page1" / "page.json")
    assert "visibility" not in data


def test_page_set_visibility_raises_for_missing_page(sample_report: Path) -> None:
    with pytest.raises(PbiCliError, match="not found"):
        page_set_visibility(sample_report, "ghost_page", hidden=True)


# ---------------------------------------------------------------------------
# Fix 4: hex color validation in page_set_background
# ---------------------------------------------------------------------------


def test_page_set_background_rejects_invalid_color(sample_report: Path) -> None:
    with pytest.raises(PbiCliError, match="Invalid color"):
        page_set_background(sample_report, "page1", "F8F9FA")  # missing #


def test_page_set_background_rejects_invalid_color_wrong_chars(sample_report: Path) -> None:
    with pytest.raises(PbiCliError, match="Invalid color"):
        page_set_background(sample_report, "page1", "#GGHHII")  # non-hex chars


def test_page_set_background_accepts_valid_color(sample_report: Path) -> None:
    result = page_set_background(sample_report, "page1", "#F8F9FA")
    assert result["status"] == "updated"
    assert result["background_color"] == "#F8F9FA"
    assert result["transparency"] == 0


# ---------------------------------------------------------------------------
# Fix 3: is_hidden surfaced in page_list and page_get
# ---------------------------------------------------------------------------


def test_page_list_shows_hidden_status(sample_report: Path) -> None:
    pages = page_list(sample_report)
    assert all("is_hidden" in p for p in pages)
    # Initially the page is visible
    assert pages[0]["is_hidden"] is False

    # Hide the first page and verify is_hidden flips
    first_page = pages[0]["name"]
    page_set_visibility(sample_report, first_page, hidden=True)
    updated = page_list(sample_report)
    hidden_page = next(p for p in updated if p["name"] == first_page)
    assert hidden_page["is_hidden"] is True


def test_page_get_shows_hidden_status(sample_report: Path) -> None:
    result = page_get(sample_report, "page1")
    assert "is_hidden" in result
    assert result["is_hidden"] is False

    page_set_visibility(sample_report, "page1", hidden=True)
    result = page_get(sample_report, "page1")
    assert result["is_hidden"] is True
