"""Pure-function backend for PBIR report and page operations.

Mirrors ``tom_backend.py`` but operates on JSON files instead of .NET TOM.
Every function takes a ``Path`` to the definition folder and returns a plain
Python dict suitable for ``format_result()``.
"""

from __future__ import annotations

import json
import re
import secrets
from pathlib import Path
from typing import Any

from pbi_cli.core.errors import PbiCliError
from pbi_cli.core.pbir_models import (
    DEFAULT_BASE_THEME,
    SCHEMA_PAGE,
    SCHEMA_PAGES_METADATA,
    SCHEMA_REPORT,
    SCHEMA_VERSION,
)
from pbi_cli.core.pbir_path import (
    get_page_dir,
    get_pages_dir,
    validate_report_structure,
)

# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict[str, Any]:
    """Read and parse a JSON file."""
    result: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return result


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON with consistent formatting."""
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _generate_name() -> str:
    """Generate a 20-character hex identifier matching PBIR convention."""
    return secrets.token_hex(10)


# ---------------------------------------------------------------------------
# Report operations
# ---------------------------------------------------------------------------


def report_info(definition_path: Path) -> dict[str, Any]:
    """Return report metadata summary."""
    report_data = _read_json(definition_path / "report.json")
    pages_dir = definition_path / "pages"

    pages: list[dict[str, Any]] = []
    if pages_dir.is_dir():
        for page_dir in sorted(pages_dir.iterdir()):
            if not page_dir.is_dir():
                continue
            page_json = page_dir / "page.json"
            if page_json.exists():
                page_data = _read_json(page_json)
                visual_count = 0
                visuals_dir = page_dir / "visuals"
                if visuals_dir.is_dir():
                    visual_count = sum(
                        1
                        for v in visuals_dir.iterdir()
                        if v.is_dir() and (v / "visual.json").exists()
                    )
                pages.append(
                    {
                        "name": page_data.get("name", page_dir.name),
                        "display_name": page_data.get("displayName", ""),
                        "ordinal": page_data.get("ordinal", 0),
                        "visual_count": visual_count,
                    }
                )

    theme = report_data.get("themeCollection", {}).get("baseTheme", {})

    return {
        "page_count": len(pages),
        "theme": theme.get("name", "Default"),
        "pages": pages,
        "total_visuals": sum(p["visual_count"] for p in pages),
        "path": str(definition_path),
    }


def report_create(
    target_path: Path,
    name: str,
    dataset_path: str | None = None,
) -> dict[str, Any]:
    """Scaffold a new PBIR report project structure.

    Creates:
      <target_path>/<name>.Report/definition/report.json
      <target_path>/<name>.Report/definition/version.json
      <target_path>/<name>.Report/definition/pages/ (empty)
      <target_path>/<name>.Report/definition.pbir
      <target_path>/<name>.pbip (optional project file)
    """
    target_path = target_path.resolve()
    report_folder = target_path / f"{name}.Report"
    definition_dir = report_folder / "definition"
    pages_dir = definition_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    # version.json
    _write_json(
        definition_dir / "version.json",
        {
            "$schema": SCHEMA_VERSION,
            "version": "2.0.0",
        },
    )

    # report.json (matches Desktop defaults)
    _write_json(
        definition_dir / "report.json",
        {
            "$schema": SCHEMA_REPORT,
            "themeCollection": {
                "baseTheme": dict(DEFAULT_BASE_THEME),
            },
            "layoutOptimization": "None",
            "settings": {
                "useStylableVisualContainerHeader": True,
                "defaultDrillFilterOtherVisuals": True,
                "allowChangeFilterTypes": True,
                "useEnhancedTooltips": True,
                "useDefaultAggregateDisplayName": True,
            },
            "slowDataSourceSettings": {
                "isCrossHighlightingDisabled": False,
                "isSlicerSelectionsButtonEnabled": False,
                "isFilterSelectionsButtonEnabled": False,
                "isFieldWellButtonEnabled": False,
                "isApplyAllButtonEnabled": False,
            },
        },
    )

    # pages.json (empty page order)
    _write_json(
        definition_dir / "pages" / "pages.json",
        {
            "$schema": SCHEMA_PAGES_METADATA,
            "pageOrder": [],
        },
    )

    # Scaffold a blank semantic model if no dataset path provided
    if not dataset_path:
        dataset_path = f"../{name}.SemanticModel"
        _scaffold_blank_semantic_model(target_path, name)

    # definition.pbir (datasetReference is REQUIRED by Desktop)
    _write_json(
        report_folder / "definition.pbir",
        {
            "version": "4.0",
            "datasetReference": {
                "byPath": {"path": dataset_path},
            },
        },
    )

    # .platform file for the report
    _write_json(
        report_folder / ".platform",
        {
            "$schema": (
                "https://developer.microsoft.com/json-schemas/"
                "fabric/gitIntegration/platformProperties/2.0.0/schema.json"
            ),
            "metadata": {
                "type": "Report",
                "displayName": name,
            },
            "config": {
                "version": "2.0",
                "logicalId": "00000000-0000-0000-0000-000000000000",
            },
        },
    )

    # .pbip project file
    _write_json(
        target_path / f"{name}.pbip",
        {
            "version": "1.0",
            "artifacts": [
                {
                    "report": {"path": f"{name}.Report"},
                }
            ],
        },
    )

    return {
        "status": "created",
        "name": name,
        "path": str(report_folder),
        "definition_path": str(definition_dir),
    }


def report_validate(definition_path: Path) -> dict[str, Any]:
    """Validate the PBIR report structure and JSON files.

    Returns a dict with ``valid`` bool and ``errors`` list.
    """
    errors = validate_report_structure(definition_path)

    # Validate JSON syntax of all files
    if definition_path.is_dir():
        for json_file in definition_path.rglob("*.json"):
            try:
                _read_json(json_file)
            except json.JSONDecodeError as e:
                rel = json_file.relative_to(definition_path)
                errors.append(f"Invalid JSON in {rel}: {e}")

    # Validate required schema fields
    report_json = definition_path / "report.json"
    if report_json.exists():
        try:
            data = _read_json(report_json)
            if "themeCollection" not in data:
                errors.append("report.json missing required 'themeCollection'")
        except json.JSONDecodeError:
            pass  # Already caught above

    # Validate pages
    pages_dir = definition_path / "pages"
    if pages_dir.is_dir():
        for page_dir in sorted(pages_dir.iterdir()):
            if not page_dir.is_dir():
                continue
            page_json = page_dir / "page.json"
            if page_json.exists():
                try:
                    pdata = _read_json(page_json)
                    for req in ("name", "displayName", "displayOption"):
                        if req not in pdata:
                            errors.append(f"Page '{page_dir.name}' missing required '{req}'")
                except json.JSONDecodeError:
                    pass

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "files_checked": sum(1 for _ in definition_path.rglob("*.json"))
        if definition_path.is_dir()
        else 0,
    }


# ---------------------------------------------------------------------------
# Page operations
# ---------------------------------------------------------------------------


def page_list(definition_path: Path) -> list[dict[str, Any]]:
    """List all pages in the report."""
    pages_dir = definition_path / "pages"
    if not pages_dir.is_dir():
        return []

    # Read page order if available
    pages_meta = pages_dir / "pages.json"
    page_order: list[str] = []
    if pages_meta.exists():
        meta = _read_json(pages_meta)
        page_order = meta.get("pageOrder", [])

    results: list[dict[str, Any]] = []
    for page_dir in sorted(pages_dir.iterdir()):
        if not page_dir.is_dir():
            continue
        page_json = page_dir / "page.json"
        if not page_json.exists():
            continue
        data = _read_json(page_json)
        visual_count = 0
        visuals_dir = page_dir / "visuals"
        if visuals_dir.is_dir():
            visual_count = sum(
                1 for v in visuals_dir.iterdir() if v.is_dir() and (v / "visual.json").exists()
            )
        results.append(
            {
                "name": data.get("name", page_dir.name),
                "display_name": data.get("displayName", ""),
                "ordinal": data.get("ordinal", 0),
                "width": data.get("width", 1280),
                "height": data.get("height", 720),
                "display_option": data.get("displayOption", "FitToPage"),
                "visual_count": visual_count,
                "is_hidden": data.get("visibility") == "HiddenInViewMode",
                "page_type": data.get("type", "Default"),
            }
        )

    # Sort by page order if available, then by ordinal
    if page_order:
        order_map = {name: i for i, name in enumerate(page_order)}
        results.sort(key=lambda p: order_map.get(p["name"], 9999))
    else:
        results.sort(key=lambda p: p["ordinal"])

    return results


def page_add(
    definition_path: Path,
    display_name: str,
    name: str | None = None,
    width: int = 1280,
    height: int = 720,
    display_option: str = "FitToPage",
) -> dict[str, Any]:
    """Add a new page to the report."""
    page_name = name or _generate_name()
    pages_dir = get_pages_dir(definition_path)
    page_dir = pages_dir / page_name

    if page_dir.exists():
        raise PbiCliError(f"Page '{page_name}' already exists.")

    page_dir.mkdir(parents=True)
    (page_dir / "visuals").mkdir()

    # Write page.json (no ordinal - Desktop uses pages.json pageOrder instead)
    _write_json(
        page_dir / "page.json",
        {
            "$schema": SCHEMA_PAGE,
            "name": page_name,
            "displayName": display_name,
            "displayOption": display_option,
            "height": height,
            "width": width,
        },
    )

    # Update pages.json
    _update_page_order(definition_path, page_name, action="add")

    return {
        "status": "created",
        "name": page_name,
        "display_name": display_name,
    }


def page_delete(definition_path: Path, page_name: str) -> dict[str, Any]:
    """Delete a page and all its visuals."""
    page_dir = get_page_dir(definition_path, page_name)

    if not page_dir.exists():
        raise PbiCliError(f"Page '{page_name}' not found.")

    # Recursively remove
    _rmtree(page_dir)

    # Update pages.json
    _update_page_order(definition_path, page_name, action="remove")

    return {"status": "deleted", "name": page_name}


def page_get(definition_path: Path, page_name: str) -> dict[str, Any]:
    """Get details of a specific page."""
    page_dir = get_page_dir(definition_path, page_name)
    page_json = page_dir / "page.json"

    if not page_json.exists():
        raise PbiCliError(f"Page '{page_name}' not found.")

    data = _read_json(page_json)
    visual_count = 0
    visuals_dir = page_dir / "visuals"
    if visuals_dir.is_dir():
        visual_count = sum(
            1 for v in visuals_dir.iterdir() if v.is_dir() and (v / "visual.json").exists()
        )

    return {
        "name": data.get("name", page_name),
        "display_name": data.get("displayName", ""),
        "ordinal": data.get("ordinal", 0),
        "width": data.get("width", 1280),
        "height": data.get("height", 720),
        "display_option": data.get("displayOption", "FitToPage"),
        "visual_count": visual_count,
        "is_hidden": data.get("visibility") == "HiddenInViewMode",
        "page_type": data.get("type", "Default"),
        "filter_config": data.get("filterConfig"),
        "visual_interactions": data.get("visualInteractions"),
        "page_binding": data.get("pageBinding"),
    }


def page_set_background(
    definition_path: Path,
    page_name: str,
    color: str,
    transparency: int = 0,
) -> dict[str, Any]:
    """Set the background color of a page.

    Updates the ``objects.background`` property in ``page.json``.
    The color must be a hex string, e.g. ``'#F8F9FA'``.

    ``transparency`` is 0 (fully opaque) to 100 (fully transparent). Desktop
    defaults missing transparency to 100 (invisible), so this function always
    writes it explicitly. Pass a value to override.
    """
    if not re.fullmatch(r"#[0-9A-Fa-f]{3,8}", color):
        raise PbiCliError(f"Invalid color '{color}' -- expected hex format like '#F8F9FA'.")
    if not 0 <= transparency <= 100:
        raise PbiCliError(f"Invalid transparency '{transparency}' -- must be 0-100.")

    page_dir = get_page_dir(definition_path, page_name)
    page_json_path = page_dir / "page.json"
    if not page_json_path.exists():
        raise PbiCliError(f"Page '{page_name}' not found.")

    page_data = _read_json(page_json_path)
    background_entry = {
        "properties": {
            "color": {"solid": {"color": {"expr": {"Literal": {"Value": f"'{color}'"}}}}},
            "transparency": {"expr": {"Literal": {"Value": f"{transparency}D"}}},
        }
    }
    objects = {**page_data.get("objects", {}), "background": [background_entry]}
    _write_json(page_json_path, {**page_data, "objects": objects})
    return {
        "status": "updated",
        "page": page_name,
        "background_color": color,
        "transparency": transparency,
    }


def page_set_visibility(
    definition_path: Path,
    page_name: str,
    hidden: bool,
) -> dict[str, Any]:
    """Show or hide a page in the report navigation.

    Setting ``hidden=True`` writes ``"visibility": "HiddenInViewMode"`` to
    ``page.json``.  Setting ``hidden=False`` removes the key if present.
    """
    page_dir = get_page_dir(definition_path, page_name)
    page_json_path = page_dir / "page.json"
    if not page_json_path.exists():
        raise PbiCliError(f"Page '{page_name}' not found.")

    page_data = _read_json(page_json_path)
    if hidden:
        updated = {**page_data, "visibility": "HiddenInViewMode"}
    else:
        updated = {k: v for k, v in page_data.items() if k != "visibility"}
    _write_json(page_json_path, updated)
    return {"status": "updated", "page": page_name, "hidden": hidden}


# ---------------------------------------------------------------------------
# Theme operations
# ---------------------------------------------------------------------------


def theme_set(definition_path: Path, theme_path: Path) -> dict[str, Any]:
    """Apply a custom theme JSON to the report."""
    if not theme_path.exists():
        raise PbiCliError(f"Theme file not found: {theme_path}")

    theme_data = _read_json(theme_path)
    theme_name = theme_data.get("name", theme_path.stem)
    report_json_path = definition_path / "report.json"
    report_data = _read_json(report_json_path)

    # Set custom theme
    theme_collection = report_data.get("themeCollection", {})
    theme_collection["customTheme"] = {
        "name": theme_name,
        "reportVersionAtImport": "5.55",
        "type": "RegisteredResources",
    }
    report_data["themeCollection"] = theme_collection

    # Copy theme file to RegisteredResources if needed
    report_folder = definition_path.parent
    resources_dir = report_folder / "StaticResources" / "RegisteredResources"
    resources_dir.mkdir(parents=True, exist_ok=True)
    theme_dest = resources_dir / theme_path.name
    theme_dest.write_text(theme_path.read_text(encoding="utf-8"), encoding="utf-8")

    # name/path are the theme's display name, no folder, no extension --
    # matches Desktop's own save output, not the source filename.
    resource_packages = report_data.get("resourcePackages", [])
    found = False
    for pkg in resource_packages:
        if pkg.get("name") == "RegisteredResources":
            found = True
            items = pkg.get("items", [])
            theme_item = {
                "name": theme_name,
                "type": "CustomTheme",
                "path": theme_name,
            }
            existing_names = {i["name"] for i in items}
            if theme_name not in existing_names:
                items.append(theme_item)
            pkg["items"] = items
            break

    if not found:
        resource_packages.append(
            {
                "name": "RegisteredResources",
                "type": "RegisteredResources",
                "items": [
                    {
                        "name": theme_name,
                        "type": "CustomTheme",
                        "path": theme_name,
                    }
                ],
            }
        )
    report_data["resourcePackages"] = resource_packages

    _write_json(report_json_path, report_data)

    return {
        "status": "applied",
        "theme": theme_data.get("name", theme_path.stem),
        "file": str(theme_dest),
    }


def theme_get(definition_path: Path) -> dict[str, Any]:
    """Return current theme information for the report.

    Reads ``report.json`` to determine the base and custom theme names.
    If a custom theme is set and the theme file exists in
    ``StaticResources/RegisteredResources/``, the full theme JSON is also
    returned.

    Returns:
        ``{"base_theme": str, "custom_theme": str | None,
           "theme_data": dict | None}``
    """
    report_json_path = definition_path / "report.json"
    if not report_json_path.exists():
        raise PbiCliError("report.json not found -- is this a valid PBIR definition folder?")

    report_data = _read_json(report_json_path)
    theme_collection = report_data.get("themeCollection", {})

    base_theme = theme_collection.get("baseTheme", {}).get("name", "")
    custom_theme_info = theme_collection.get("customTheme")
    custom_theme_name: str | None = None
    theme_data: dict[str, Any] | None = None

    if custom_theme_info:
        custom_theme_name = custom_theme_info.get("name")
        # Try to load from RegisteredResources
        report_folder = definition_path.parent
        resources_dir = report_folder / "StaticResources" / "RegisteredResources"
        if resources_dir.is_dir():
            for candidate in resources_dir.glob("*.json"):
                try:
                    parsed = _read_json(candidate)
                    if parsed.get("name") == custom_theme_name:
                        theme_data = parsed
                        break
                except Exception:
                    continue

    return {
        "base_theme": base_theme,
        "custom_theme": custom_theme_name,
        "theme_data": theme_data,
    }


def theme_diff(definition_path: Path, theme_path: Path) -> dict[str, Any]:
    """Compare a proposed theme JSON file against the currently applied theme.

    If no custom theme is set, the diff compares against an empty dict
    (i.e. everything in the proposed file is an addition).

    Returns:
        ``{"current": str, "proposed": str,
           "added": list[str], "removed": list[str], "changed": list[str]}``
    """
    if not theme_path.exists():
        raise PbiCliError(f"Proposed theme file not found: {theme_path}")

    current_info = theme_get(definition_path)
    current_data: dict[str, Any] = current_info.get("theme_data") or {}
    proposed_data = _read_json(theme_path)

    current_name = current_info.get("custom_theme") or current_info.get("base_theme") or "(none)"
    proposed_name = proposed_data.get("name", theme_path.stem)

    added, removed, changed = _dict_diff(current_data, proposed_data)

    return {
        "current": current_name,
        "proposed": proposed_name,
        "added": added,
        "removed": removed,
        "changed": changed,
    }


def _dict_diff(
    current: dict[str, Any],
    proposed: dict[str, Any],
    prefix: str = "",
) -> tuple[list[str], list[str], list[str]]:
    """Recursively diff two dicts and return (added, removed, changed) key paths."""
    added: list[str] = []
    removed: list[str] = []
    changed: list[str] = []

    all_keys = set(current) | set(proposed)
    for key in sorted(all_keys):
        path = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if key not in current:
            added.append(path)
        elif key not in proposed:
            removed.append(path)
        elif isinstance(current[key], dict) and isinstance(proposed[key], dict):
            sub_added, sub_removed, sub_changed = _dict_diff(
                current[key], proposed[key], prefix=path
            )
            added.extend(sub_added)
            removed.extend(sub_removed)
            changed.extend(sub_changed)
        elif current[key] != proposed[key]:
            changed.append(path)

    return added, removed, changed


# ---------------------------------------------------------------------------
# Convert operations
# ---------------------------------------------------------------------------


def report_convert(
    source_path: Path,
    output_path: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Convert a PBIR report project to a distributable .pbip package.

    This scaffolds the proper .pbip project structure from an existing
    .Report folder. It does NOT convert .pbix to .pbip (that requires
    Power BI Desktop's "Save as .pbip" feature).
    """
    source_path = source_path.resolve()

    # Find the .Report folder
    report_folder: Path | None = None
    if source_path.name.endswith(".Report") and source_path.is_dir():
        report_folder = source_path
    else:
        for child in source_path.iterdir():
            if child.is_dir() and child.name.endswith(".Report"):
                report_folder = child
                break

    if report_folder is None:
        raise PbiCliError(
            f"No .Report folder found in '{source_path}'. Expected a folder ending in .Report."
        )

    name = report_folder.name.replace(".Report", "")
    target = output_path.resolve() if output_path else source_path

    # Create .pbip file
    pbip_path = target / f"{name}.pbip"
    if pbip_path.exists() and not force:
        raise PbiCliError(f".pbip file already exists at '{pbip_path}'. Use --force to overwrite.")
    _write_json(
        pbip_path,
        {
            "version": "1.0",
            "artifacts": [
                {"report": {"path": f"{name}.Report"}},
            ],
        },
    )

    # Create .gitignore if not present
    gitignore = target / ".gitignore"
    gitignore_created = not gitignore.exists()
    if gitignore_created:
        gitignore_content = "# Power BI local settings\n.pbi/\n*.pbix\n*.bak\n"
        gitignore.write_text(gitignore_content, encoding="utf-8")

    # Validate the definition.pbir exists
    defn_pbir = report_folder / "definition.pbir"

    return {
        "status": "converted",
        "name": name,
        "pbip_path": str(pbip_path),
        "report_folder": str(report_folder),
        "has_definition_pbir": defn_pbir.exists(),
        "gitignore_created": gitignore_created,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _scaffold_blank_semantic_model(target_path: Path, name: str) -> None:
    """Create a minimal TMDL semantic model so Desktop can open the report."""
    model_dir = target_path / f"{name}.SemanticModel"
    defn_dir = model_dir / "definition"
    defn_dir.mkdir(parents=True, exist_ok=True)

    # model.tmdl (minimal valid TMDL)
    (defn_dir / "model.tmdl").write_text(
        "model Model\n  culture: en-US\n  defaultPowerBIDataSourceVersion: powerBI_V3\n",
        encoding="utf-8",
    )

    # .platform file (required by Desktop)
    _write_json(
        model_dir / ".platform",
        {
            "$schema": (
                "https://developer.microsoft.com/json-schemas/"
                "fabric/gitIntegration/platformProperties/2.0.0/schema.json"
            ),
            "metadata": {
                "type": "SemanticModel",
                "displayName": name,
            },
            "config": {
                "version": "2.0",
                "logicalId": "00000000-0000-0000-0000-000000000000",
            },
        },
    )

    # definition.pbism (matches Desktop format)
    _write_json(
        model_dir / "definition.pbism",
        {
            "version": "4.1",
            "settings": {},
        },
    )


def _update_page_order(definition_path: Path, page_name: str, action: str) -> None:
    """Update pages.json with page add/remove."""
    pages_meta_path = definition_path / "pages" / "pages.json"

    if pages_meta_path.exists():
        meta = _read_json(pages_meta_path)
    else:
        meta = {"$schema": SCHEMA_PAGES_METADATA}

    order = meta.get("pageOrder", [])

    if action == "add" and page_name not in order:
        order.append(page_name)
    elif action == "remove" and page_name in order:
        order = [p for p in order if p != page_name]

    meta["pageOrder"] = order

    # Always set activePageName to the first page (Desktop requires this)
    if order:
        meta["activePageName"] = meta.get("activePageName", order[0])
        # If active page was removed, reset to first
        if meta["activePageName"] not in order:
            meta["activePageName"] = order[0]

    _write_json(pages_meta_path, meta)


def _rmtree(path: Path) -> None:
    """Recursively remove a directory tree (stdlib-only)."""
    if path.is_dir():
        for child in path.iterdir():
            _rmtree(child)
        path.rmdir()
    else:
        path.unlink()
