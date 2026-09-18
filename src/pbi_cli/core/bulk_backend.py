"""Bulk visual operations for PBIR reports.

Orchestration layer over visual_backend.py -- applies filtering
(by type, name pattern, position bounds) and fans out to the
individual visual_* pure functions.

Every function follows the same signature contract as the rest of the
report layer: takes a ``definition_path: Path`` and returns a plain dict.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pbi_cli.core.field_resolver import FieldIndex, index_from_report
from pbi_cli.core.visual_backend import (
    VISUAL_DATA_ROLES,
    _resolve_visual_type,
    visual_bind,
    visual_delete,
    visual_list,
    visual_update,
)


def visual_where(
    definition_path: Path,
    page_name: str,
    visual_type: str | None = None,
    name_pattern: str | None = None,
    x_min: float | None = None,
    x_max: float | None = None,
    y_min: float | None = None,
    y_max: float | None = None,
) -> list[dict[str, Any]]:
    """Filter visuals on a page by type and/or position bounds.

    Returns the subset of ``visual_list()`` matching ALL provided criteria.
    All filter arguments are optional -- omitting all returns every visual.

    Args:
        definition_path: Path to the ``definition/`` folder.
        page_name: Name of the page to search.
        visual_type: Resolved PBIR visualType or user alias (e.g. ``"bar"``).
        name_pattern: fnmatch pattern matched against visual names (e.g. ``"Chart_*"``).
        x_min: Minimum x position (inclusive).
        x_max: Maximum x position (inclusive).
        y_min: Minimum y position (inclusive).
        y_max: Maximum y position (inclusive).
    """
    resolved_type: str | None = None
    if visual_type is not None:
        resolved_type = _resolve_visual_type(visual_type)

    all_visuals = visual_list(definition_path, page_name)
    result: list[dict[str, Any]] = []

    for v in all_visuals:
        if resolved_type is not None and v.get("visual_type") != resolved_type:
            continue
        if name_pattern is not None and not fnmatch.fnmatch(v.get("name", ""), name_pattern):
            continue
        x = v.get("x", 0.0)
        y = v.get("y", 0.0)
        if x_min is not None and x < x_min:
            continue
        if x_max is not None and x > x_max:
            continue
        if y_min is not None and y < y_min:
            continue
        if y_max is not None and y > y_max:
            continue
        result.append(v)

    return result


def visual_bulk_bind(
    definition_path: Path,
    page_name: str,
    visual_type: str,
    bindings: list[dict[str, str]],
    name_pattern: str | None = None,
    live_index_loader: Callable[[], FieldIndex | None] | None = None,
) -> dict[str, Any]:
    """Bind fields to every visual of a given type on a page.

    Applies the same ``bindings`` list to each matching visual by calling
    ``visual_bind()`` in sequence.  Stops and raises on the first error.

    Args:
        definition_path: Path to the ``definition/`` folder.
        page_name: Name of the page.
        visual_type: PBIR visualType or user alias -- required (unlike ``visual_where``).
        bindings: List of ``{"role": ..., "field": ...}`` dicts, same format as
            ``visual_bind()``.
        name_pattern: Optional fnmatch filter on visual name.
        live_index_loader: Optional lazy loader for the live model's field
            index, forwarded to ``visual_bind()``.

    Returns:
        ``{"bound": N, "page": page_name, "type": resolved_type, "visuals": [names],
          "bindings": bindings}``
    """
    matching = visual_where(
        definition_path,
        page_name,
        visual_type=visual_type,
        name_pattern=name_pattern,
    )
    field_index = index_from_report(definition_path)
    live_cache: list[FieldIndex | None] = []

    def cached_live() -> FieldIndex | None:
        if live_index_loader is None:
            return None
        if not live_cache:
            live_cache.append(live_index_loader())
        return live_cache[0]

    bound_names: list[str] = []
    for v in matching:
        visual_bind(
            definition_path,
            page_name,
            v["name"],
            bindings,
            field_index=field_index,
            live_index_loader=cached_live,
        )
        bound_names.append(v["name"])

    resolved_type = _resolve_visual_type(visual_type)
    return {
        "bound": len(bound_names),
        "page": page_name,
        "type": resolved_type,
        "visuals": bound_names,
        "bindings": bindings,
    }


def visual_bulk_update(
    definition_path: Path,
    page_name: str,
    where_type: str | None = None,
    where_name_pattern: str | None = None,
    set_hidden: bool | None = None,
    set_width: float | None = None,
    set_height: float | None = None,
    set_x: float | None = None,
    set_y: float | None = None,
) -> dict[str, Any]:
    """Apply position/visibility updates to all visuals matching the filter.

    Delegates to ``visual_update()`` for each match.  At least one ``set_*``
    argument must be provided.

    Returns:
        ``{"updated": N, "page": page_name, "visuals": [names]}``
    """
    if all(v is None for v in (set_hidden, set_width, set_height, set_x, set_y)):
        raise ValueError("At least one set_* argument must be provided to bulk-update")

    matching = visual_where(
        definition_path,
        page_name,
        visual_type=where_type,
        name_pattern=where_name_pattern,
    )
    updated_names: list[str] = []
    for v in matching:
        visual_update(
            definition_path,
            page_name,
            v["name"],
            x=set_x,
            y=set_y,
            width=set_width,
            height=set_height,
            hidden=set_hidden,
        )
        updated_names.append(v["name"])

    return {
        "updated": len(updated_names),
        "page": page_name,
        "visuals": updated_names,
    }


def visual_bulk_delete(
    definition_path: Path,
    page_name: str,
    where_type: str | None = None,
    where_name_pattern: str | None = None,
) -> dict[str, Any]:
    """Delete all visuals on a page matching the filter criteria.

    Delegates to ``visual_delete()`` for each match.

    Returns:
        ``{"deleted": N, "page": page_name, "visuals": [names]}``
    """
    if where_type is None and where_name_pattern is None:
        raise ValueError(
            "Provide at least --type or --name-pattern to prevent accidental bulk deletion"
        )

    matching = visual_where(
        definition_path,
        page_name,
        visual_type=where_type,
        name_pattern=where_name_pattern,
    )
    deleted_names: list[str] = []
    for v in matching:
        visual_delete(definition_path, page_name, v["name"])
        deleted_names.append(v["name"])

    return {
        "deleted": len(deleted_names),
        "page": page_name,
        "visuals": deleted_names,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _supported_roles_for_type(visual_type: str) -> list[str]:
    """Return the data role names for a visual type (for help text generation)."""
    resolved = _resolve_visual_type(visual_type)
    return VISUAL_DATA_ROLES.get(resolved, [])
