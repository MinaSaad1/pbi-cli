"""Tests for pbi_cli.core.pbir_path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pbi_cli.core.errors import AmbiguousReportError, ReportNotFoundError
from pbi_cli.core.pbir_path import (
    get_page_dir,
    get_pages_dir,
    get_visual_dir,
    get_visuals_dir,
    resolve_report_path,
    validate_report_structure,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPORT_JSON = json.dumps(
    {
        "$schema": "https://developer.microsoft.com/json-schemas/"
        "fabric/item/report/definition/report/1.0.0/schema.json"
    }
)
_VERSION_JSON = json.dumps(
    {
        "$schema": "https://developer.microsoft.com/json-schemas/"
        "fabric/item/report/definition/version/1.0.0/schema.json",
        "version": "1.0.0",
    }
)


def scaffold_valid_pbir(root: Path, report_name: str = "MyReport") -> Path:
    """Create a minimal valid PBIR structure under *root*.

    Returns the ``definition/`` path so tests can use it directly.

    Structure created::

        root/
        MyReport.Report/
            definition/
                report.json
                version.json
    """
    definition = root / f"{report_name}.Report" / "definition"
    definition.mkdir(parents=True)
    (definition / "report.json").write_text(_REPORT_JSON)
    (definition / "version.json").write_text(_VERSION_JSON)
    return definition


def add_page(definition: Path, page_name: str, *, with_page_json: bool = True) -> Path:
    """Add a page directory inside *definition*/pages/ and return the page dir."""
    page_dir = definition / "pages" / page_name
    page_dir.mkdir(parents=True, exist_ok=True)
    if with_page_json:
        (page_dir / "page.json").write_text(json.dumps({"name": page_name}))
    return page_dir


def add_visual(
    definition: Path,
    page_name: str,
    visual_name: str,
    *,
    with_visual_json: bool = True,
) -> Path:
    """Add a visual directory and return the visual dir."""
    visual_dir = definition / "pages" / page_name / "visuals" / visual_name
    visual_dir.mkdir(parents=True, exist_ok=True)
    if with_visual_json:
        (visual_dir / "visual.json").write_text(json.dumps({"name": visual_name}))
    return visual_dir


# ---------------------------------------------------------------------------
# resolve_report_path -- explicit path variants
# ---------------------------------------------------------------------------


def test_resolve_explicit_definition_folder(tmp_path: Path) -> None:
    """Pointing directly at the definition/ folder resolves correctly."""
    definition = scaffold_valid_pbir(tmp_path)

    result = resolve_report_path(explicit_path=str(definition))

    assert result == definition.resolve()


def test_resolve_explicit_report_folder(tmp_path: Path) -> None:
    """Pointing at the .Report/ folder resolves to its definition/ child."""
    definition = scaffold_valid_pbir(tmp_path)
    report_folder = definition.parent  # MyReport.Report/

    result = resolve_report_path(explicit_path=str(report_folder))

    assert result == definition.resolve()


def test_resolve_explicit_parent_folder(tmp_path: Path) -> None:
    """Pointing at the folder containing .Report/ resolves correctly."""
    definition = scaffold_valid_pbir(tmp_path)

    # tmp_path contains MyReport.Report/
    result = resolve_report_path(explicit_path=str(tmp_path))

    assert result == definition.resolve()


def test_resolve_explicit_not_found(tmp_path: Path) -> None:
    """An explicit path with no PBIR content raises ReportNotFoundError."""
    empty_dir = tmp_path / "not_a_report"
    empty_dir.mkdir()

    with pytest.raises(ReportNotFoundError):
        resolve_report_path(explicit_path=str(empty_dir))


def test_resolve_explicit_nonexistent_path(tmp_path: Path) -> None:
    """A path that does not exist on disk raises ReportNotFoundError."""
    ghost = tmp_path / "ghost_folder"

    with pytest.raises(ReportNotFoundError):
        resolve_report_path(explicit_path=str(ghost))


# ---------------------------------------------------------------------------
# resolve_report_path -- CWD walk-up detection
# ---------------------------------------------------------------------------


def test_resolve_walkup_from_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Walk-up detection finds .Report/definition when CWD is a child dir."""
    definition = scaffold_valid_pbir(tmp_path)
    nested_cwd = tmp_path / "deep" / "nested"
    nested_cwd.mkdir(parents=True)
    monkeypatch.chdir(nested_cwd)

    result = resolve_report_path()

    assert result == definition.resolve()


def test_resolve_walkup_from_report_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Walk-up detection works when CWD is already the project root."""
    definition = scaffold_valid_pbir(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = resolve_report_path()

    assert result == definition.resolve()


# ---------------------------------------------------------------------------
# resolve_report_path -- .pbip sibling detection
# ---------------------------------------------------------------------------


def test_resolve_pbip_sibling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A sibling .pbip file guides resolution when no .Report is in the walk-up."""
    # Place .pbip in an isolated directory (no .Report parent chain)
    project_dir = tmp_path / "workspace"
    project_dir.mkdir()
    (project_dir / "MyReport.pbip").write_text("{}")
    definition = project_dir / "MyReport.Report" / "definition"
    definition.mkdir(parents=True)
    (definition / "report.json").write_text(_REPORT_JSON)
    (definition / "version.json").write_text(_VERSION_JSON)
    monkeypatch.chdir(project_dir)

    result = resolve_report_path()

    assert result == definition.resolve()


def test_resolve_no_report_anywhere_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When no PBIR structure is discoverable, ReportNotFoundError is raised."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ReportNotFoundError):
        resolve_report_path()


def test_resolve_walkup_ambiguous_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two sibling .Report folders with no --path raises AmbiguousReportError
    instead of silently picking one."""
    scaffold_valid_pbir(tmp_path, report_name="ReportA")
    scaffold_valid_pbir(tmp_path, report_name="ReportB")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(AmbiguousReportError) as exc_info:
        resolve_report_path()

    assert "ReportA.Report" in str(exc_info.value)
    assert "ReportB.Report" in str(exc_info.value)


def test_resolve_walkup_single_report_still_works(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A single .Report folder still resolves normally (no false positive)."""
    definition = scaffold_valid_pbir(tmp_path, report_name="OnlyReport")
    monkeypatch.chdir(tmp_path)

    result = resolve_report_path()

    assert result == definition.resolve()


def test_resolve_explicit_path_bypasses_ambiguity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An explicit --path is unaffected even with multiple sibling .Report folders."""
    definition_a = scaffold_valid_pbir(tmp_path, report_name="ReportA")
    scaffold_valid_pbir(tmp_path, report_name="ReportB")
    monkeypatch.chdir(tmp_path)

    result = resolve_report_path(explicit_path=str(definition_a.parent))

    assert result == definition_a.resolve()


# ---------------------------------------------------------------------------
# get_pages_dir
# ---------------------------------------------------------------------------


def test_get_pages_dir_creates_missing_dir(tmp_path: Path) -> None:
    """get_pages_dir creates the pages/ folder when it does not exist."""
    definition = scaffold_valid_pbir(tmp_path)
    pages = definition / "pages"
    assert not pages.exists()

    result = get_pages_dir(definition)

    assert result == pages
    assert pages.is_dir()


def test_get_pages_dir_idempotent(tmp_path: Path) -> None:
    """get_pages_dir does not raise when pages/ already exists."""
    definition = scaffold_valid_pbir(tmp_path)
    (definition / "pages").mkdir()

    result = get_pages_dir(definition)

    assert result.is_dir()


# ---------------------------------------------------------------------------
# get_page_dir
# ---------------------------------------------------------------------------


def test_get_page_dir_returns_correct_path(tmp_path: Path) -> None:
    """get_page_dir returns the expected path without creating it."""
    definition = scaffold_valid_pbir(tmp_path)

    result = get_page_dir(definition, "SalesOverview")

    assert result == definition / "pages" / "SalesOverview"


def test_get_page_dir_does_not_create_dir(tmp_path: Path) -> None:
    """get_page_dir is a pure path computation -- it must not create the directory."""
    definition = scaffold_valid_pbir(tmp_path)

    result = get_page_dir(definition, "NonExistentPage")

    assert not result.exists()


# ---------------------------------------------------------------------------
# get_visuals_dir
# ---------------------------------------------------------------------------


def test_get_visuals_dir_creates_missing_dirs(tmp_path: Path) -> None:
    """get_visuals_dir creates pages/<page>/visuals/ when missing."""
    definition = scaffold_valid_pbir(tmp_path)
    visuals = definition / "pages" / "Page1" / "visuals"
    assert not visuals.exists()

    result = get_visuals_dir(definition, "Page1")

    assert result == visuals
    assert visuals.is_dir()


def test_get_visuals_dir_idempotent(tmp_path: Path) -> None:
    """get_visuals_dir does not raise when the visuals/ dir already exists."""
    definition = scaffold_valid_pbir(tmp_path)
    visuals = definition / "pages" / "Page1" / "visuals"
    visuals.mkdir(parents=True)

    result = get_visuals_dir(definition, "Page1")

    assert result.is_dir()


# ---------------------------------------------------------------------------
# get_visual_dir
# ---------------------------------------------------------------------------


def test_get_visual_dir_returns_correct_path(tmp_path: Path) -> None:
    """get_visual_dir returns the expected nested path without creating it."""
    definition = scaffold_valid_pbir(tmp_path)

    result = get_visual_dir(definition, "Page1", "BarChart01")

    assert result == definition / "pages" / "Page1" / "visuals" / "BarChart01"


def test_get_visual_dir_does_not_create_dir(tmp_path: Path) -> None:
    """get_visual_dir is a pure path computation -- it must not create the directory."""
    definition = scaffold_valid_pbir(tmp_path)

    result = get_visual_dir(definition, "Page1", "Ghost")

    assert not result.exists()


# ---------------------------------------------------------------------------
# validate_report_structure
# ---------------------------------------------------------------------------


def test_validate_valid_structure_no_pages(tmp_path: Path) -> None:
    """A minimal valid structure with no pages produces no errors."""
    definition = scaffold_valid_pbir(tmp_path)

    errors = validate_report_structure(definition)

    assert errors == []


def test_validate_valid_structure_with_pages_and_visuals(tmp_path: Path) -> None:
    """A fully valid structure with pages and visuals produces no errors."""
    definition = scaffold_valid_pbir(tmp_path)
    add_page(definition, "Page1")
    add_visual(definition, "Page1", "Visual01")

    errors = validate_report_structure(definition)

    assert errors == []


def test_validate_missing_report_json(tmp_path: Path) -> None:
    """Absence of report.json is reported as an error."""
    definition = scaffold_valid_pbir(tmp_path)
    (definition / "report.json").unlink()

    errors = validate_report_structure(definition)

    assert any("report.json" in e for e in errors)


def test_validate_missing_version_json(tmp_path: Path) -> None:
    """Absence of version.json is reported as an error."""
    definition = scaffold_valid_pbir(tmp_path)
    (definition / "version.json").unlink()

    errors = validate_report_structure(definition)

    assert any("version.json" in e for e in errors)


def test_validate_page_missing_page_json(tmp_path: Path) -> None:
    """A page directory that lacks page.json is flagged."""
    definition = scaffold_valid_pbir(tmp_path)
    add_page(definition, "BadPage", with_page_json=False)

    errors = validate_report_structure(definition)

    assert any("BadPage" in e and "page.json" in e for e in errors)


def test_validate_visual_missing_visual_json(tmp_path: Path) -> None:
    """A visual directory that lacks visual.json is flagged."""
    definition = scaffold_valid_pbir(tmp_path)
    add_page(definition, "Page1")
    add_visual(definition, "Page1", "BrokenVisual", with_visual_json=False)

    errors = validate_report_structure(definition)

    assert any("BrokenVisual" in e and "visual.json" in e for e in errors)


def test_validate_nonexistent_dir(tmp_path: Path) -> None:
    """A definition path that does not exist on disk returns an error."""
    ghost = tmp_path / "does_not_exist" / "definition"

    errors = validate_report_structure(ghost)

    assert len(errors) == 1
    assert "does not exist" in errors[0].lower() or str(ghost) in errors[0]


def test_validate_multiple_errors_reported(tmp_path: Path) -> None:
    """Both report.json and version.json missing are returned together."""
    definition = scaffold_valid_pbir(tmp_path)
    (definition / "report.json").unlink()
    (definition / "version.json").unlink()

    errors = validate_report_structure(definition)

    assert len(errors) == 2
    messages = " ".join(errors)
    assert "report.json" in messages
    assert "version.json" in messages


def test_validate_multiple_page_errors(tmp_path: Path) -> None:
    """Each page missing page.json produces a separate error entry."""
    definition = scaffold_valid_pbir(tmp_path)
    add_page(definition, "PageA", with_page_json=False)
    add_page(definition, "PageB", with_page_json=False)

    errors = validate_report_structure(definition)

    page_errors = [e for e in errors if "page.json" in e]
    assert len(page_errors) == 2


def test_validate_multiple_visual_errors(tmp_path: Path) -> None:
    """Each visual missing visual.json produces a separate error entry."""
    definition = scaffold_valid_pbir(tmp_path)
    add_page(definition, "Page1")
    add_visual(definition, "Page1", "Vis1", with_visual_json=False)
    add_visual(definition, "Page1", "Vis2", with_visual_json=False)

    errors = validate_report_structure(definition)

    visual_errors = [e for e in errors if "visual.json" in e]
    assert len(visual_errors) == 2


def test_validate_valid_page_with_no_visuals_dir(tmp_path: Path) -> None:
    """A page with no visuals/ sub-directory is still valid."""
    definition = scaffold_valid_pbir(tmp_path)
    add_page(definition, "Page1")
    # No visuals/ directory created -- that is fine

    errors = validate_report_structure(definition)

    assert errors == []
