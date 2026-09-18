"""Pure-function backend for PBIR visual operations.

Mirrors ``report_backend.py`` but focuses on individual visual CRUD.
Every function takes a ``Path`` to the definition folder and returns
plain Python dicts suitable for ``format_result()``.
"""

from __future__ import annotations

import json
import re
import secrets
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pbi_cli.core.errors import PbiCliError, VisualTypeError
from pbi_cli.core.field_resolver import (
    AGGREGATE_FUNCTIONS,
    AGGREGATE_LABELS,
    FieldIndex,
    ResolvedField,
    index_from_report,
    parse_aggregation,
)
from pbi_cli.core.pbir_models import (
    SUPPORTED_VISUAL_TYPES,
    VISUAL_TYPE_ALIASES,
)
from pbi_cli.core.pbir_path import get_visual_dir, get_visuals_dir

# ---------------------------------------------------------------------------
# JSON helpers (same as report_backend)
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return result


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _generate_name() -> str:
    return secrets.token_hex(10)


# ---------------------------------------------------------------------------
# Template loading
# ---------------------------------------------------------------------------

# Data role mappings for each visual type
VISUAL_DATA_ROLES: dict[str, list[str]] = {
    # Original 9
    "barChart": ["Category", "Y", "Legend"],
    "lineChart": ["Category", "Y", "Legend"],
    "card": ["Values"],
    "tableEx": ["Values"],
    "pivotTable": ["Rows", "Values", "Columns"],
    "slicer": ["Values"],
    "kpi": ["Indicator", "Goal", "TrendLine"],
    "gauge": ["Y", "MaxValue"],
    "donutChart": ["Category", "Y", "Legend"],
    # v3.1.0 additions
    "columnChart": ["Category", "Y", "Legend"],
    "areaChart": ["Category", "Y", "Legend"],
    "ribbonChart": ["Category", "Y", "Legend"],
    "waterfallChart": ["Category", "Y", "Breakdown"],
    "scatterChart": ["Details", "X", "Y", "Size", "Legend"],
    "funnelChart": ["Category", "Y"],
    "multiRowCard": ["Values"],
    "treemap": ["Category", "Values"],
    "cardNew": ["Fields"],
    "stackedBarChart": ["Category", "Y", "Legend"],
    "lineStackedColumnComboChart": ["Category", "ColumnY", "LineY", "Legend"],
    # v3.4.0 additions
    "cardVisual": ["Data"],
    "actionButton": [],
    # v3.5.0 additions
    "clusteredColumnChart": ["Category", "Y", "Legend"],
    "clusteredBarChart": ["Category", "Y", "Legend"],
    "textSlicer": ["Values"],
    "listSlicer": ["Values"],
    # v3.6.0 additions
    "image": [],
    "shape": [],
    "textbox": [],
    "pageNavigator": [],
    "advancedSlicerVisual": ["Values"],
    # v3.8.0 additions
    "azureMap": ["Category", "Size"],
}

# Roles that should default to Measure references (not Column)
MEASURE_ROLES: frozenset[str] = frozenset(
    {
        "Y",
        "Values",
        "Fields",  # "Fields" is used by cardNew only
        "Indicator",
        "Goal",
        # v3.1.0 additions
        "ColumnY",
        "LineY",
        "X",
        "Size",
        # v3.4.0 additions
        "Data",
        # v3.8.0 additions
        "MaxValue",
    }
)

# Slicers filter on columns: their "Values" role holds dimension columns.
SLICER_VISUAL_TYPES: frozenset[str] = frozenset(
    {"slicer", "textSlicer", "listSlicer", "advancedSlicerVisual"}
)

_VALID_KINDS = frozenset({"auto", "column", "measure"})

# Visuals whose value roles show a non-summarizable column as-is (a text
# column in a table or card). Everywhere else Desktop falls back to Count.
RAW_COLUMN_VISUAL_TYPES: frozenset[str] = frozenset(
    {"tableEx", "card", "multiRowCard", "cardNew", "cardVisual"}
)


def _default_is_measure(visual_type: str, user_role: str, pbir_role: str) -> bool:
    """Fallback Column/Measure guess when the semantic model can't be consulted."""
    if visual_type in SLICER_VISUAL_TYPES:
        return False
    if visual_type == "tableEx":
        # Table "Values" mixes both; trust the flag the user picked.
        return user_role == "value"
    return pbir_role in MEASURE_ROLES


def _implicit_aggregation(
    visual_type: str,
    pbir_role: str,
    hit: ResolvedField | None,
) -> int | None:
    """Aggregation Desktop would apply to a model column in this role.

    Only value roles aggregate, and slicers never do. Without model metadata
    the column is left as-is.
    """
    if hit is None or visual_type in SLICER_VISUAL_TYPES or pbir_role not in MEASURE_ROLES:
        return None
    function = hit.default_aggregation()
    if function is None and visual_type not in RAW_COLUMN_VISUAL_TYPES:
        return AGGREGATE_FUNCTIONS["count"]
    return function


# User-friendly role aliases to PBIR role names
ROLE_ALIASES: dict[str, dict[str, str]] = {
    # Original 9
    "barChart": {"category": "Category", "value": "Y", "legend": "Legend"},
    "lineChart": {"category": "Category", "value": "Y", "legend": "Legend"},
    "card": {"field": "Values", "value": "Values"},
    "tableEx": {"value": "Values", "column": "Values"},
    "pivotTable": {"row": "Rows", "value": "Values", "column": "Columns"},
    "slicer": {"value": "Values", "field": "Values"},
    "kpi": {
        "indicator": "Indicator",
        "value": "Indicator",
        "goal": "Goal",
        "trend_line": "TrendLine",
        "trend": "TrendLine",
    },
    "gauge": {
        "value": "Y",
        "max": "MaxValue",
        "max_value": "MaxValue",
        "target": "MaxValue",
    },
    "donutChart": {"category": "Category", "value": "Y", "legend": "Legend"},
    # v3.1.0 additions
    "columnChart": {"category": "Category", "value": "Y", "legend": "Legend"},
    "areaChart": {"category": "Category", "value": "Y", "legend": "Legend"},
    "ribbonChart": {"category": "Category", "value": "Y", "legend": "Legend"},
    "waterfallChart": {"category": "Category", "value": "Y", "breakdown": "Breakdown"},
    "scatterChart": {
        "x": "X",
        "y": "Y",
        "detail": "Details",
        "size": "Size",
        "legend": "Legend",
        "value": "Y",
    },
    "funnelChart": {"category": "Category", "value": "Y"},
    "multiRowCard": {"field": "Values", "value": "Values"},
    "treemap": {"category": "Category", "value": "Values"},
    "cardNew": {"field": "Fields", "value": "Fields"},
    "stackedBarChart": {"category": "Category", "value": "Y", "legend": "Legend"},
    "lineStackedColumnComboChart": {
        "category": "Category",
        "column": "ColumnY",
        "line": "LineY",
        "legend": "Legend",
        "value": "ColumnY",
    },
    # v3.4.0 additions
    "cardVisual": {"field": "Data", "value": "Data"},
    "actionButton": {},
    # v3.5.0 additions
    "clusteredColumnChart": {"category": "Category", "value": "Y", "legend": "Legend"},
    "clusteredBarChart": {"category": "Category", "value": "Y", "legend": "Legend"},
    "textSlicer": {"value": "Values", "field": "Values"},
    "listSlicer": {"value": "Values", "field": "Values"},
    # v3.6.0 additions
    "image": {},
    "shape": {},
    "textbox": {},
    "pageNavigator": {},
    "advancedSlicerVisual": {"value": "Values", "field": "Values"},
    # v3.8.0 additions
    "azureMap": {"category": "Category", "value": "Size", "size": "Size"},
}


def _resolve_visual_type(user_type: str) -> str:
    """Resolve a user-provided visual type to a PBIR visualType."""
    if user_type in SUPPORTED_VISUAL_TYPES:
        return user_type
    resolved = VISUAL_TYPE_ALIASES.get(user_type)
    if resolved is not None:
        return resolved
    raise VisualTypeError(user_type)


def _load_template(visual_type: str) -> str:
    """Load a visual template as a raw string (contains placeholders)."""
    import importlib.resources

    templates_pkg = importlib.resources.files("pbi_cli.templates.visuals")
    template_file = templates_pkg / f"{visual_type}.json"
    return template_file.read_text(encoding="utf-8")


def _build_visual_json(
    template_str: str,
    name: str,
    x: float,
    y: float,
    width: float,
    height: float,
    z: int = 0,
    tab_order: int = 0,
) -> dict[str, Any]:
    """Fill placeholders in a template string and return parsed JSON."""
    filled = (
        template_str.replace("__VISUAL_NAME__", name)
        .replace("__X__", str(int(x)))
        .replace("__Y__", str(int(y)))
        .replace("__WIDTH__", str(int(width)))
        .replace("__HEIGHT__", str(int(height)))
        .replace("__Z__", str(z))
        .replace("__TAB_ORDER__", str(tab_order))
    )
    result: dict[str, Any] = json.loads(filled)
    return result


# ---------------------------------------------------------------------------
# Default positions and sizes per visual type
# ---------------------------------------------------------------------------

DEFAULT_SIZES: dict[str, tuple[float, float]] = {
    # Original 9
    "barChart": (400, 300),
    "lineChart": (400, 300),
    "card": (200, 120),
    "tableEx": (500, 350),
    "pivotTable": (500, 350),
    "slicer": (200, 300),
    "kpi": (250, 150),
    "gauge": (300, 250),
    "donutChart": (350, 300),
    # v3.1.0 additions
    "columnChart": (400, 300),
    "areaChart": (400, 300),
    "ribbonChart": (400, 300),
    "waterfallChart": (450, 300),
    "scatterChart": (400, 350),
    "funnelChart": (350, 300),
    "multiRowCard": (300, 200),
    "treemap": (400, 300),
    "cardNew": (200, 120),
    "stackedBarChart": (400, 300),
    "lineStackedColumnComboChart": (500, 300),
    # v3.4.0 additions -- sizes from real Desktop export
    "cardVisual": (217, 87),
    "actionButton": (51, 22),
    # v3.5.0 additions
    "clusteredColumnChart": (400, 300),
    "clusteredBarChart": (400, 300),
    "textSlicer": (200, 50),
    "listSlicer": (200, 300),
    # v3.6.0 additions (from real HR Analysis Desktop export sizing)
    "image": (200, 150),
    "shape": (300, 200),
    "textbox": (300, 100),
    "pageNavigator": (120, 400),
    "advancedSlicerVisual": (280, 280),
    # v3.8.0 additions
    "azureMap": (500, 400),
}


# ---------------------------------------------------------------------------
# Visual CRUD operations
# ---------------------------------------------------------------------------


def visual_list(definition_path: Path, page_name: str) -> list[dict[str, Any]]:
    """List all visuals on a page."""
    visuals_dir = definition_path / "pages" / page_name / "visuals"
    if not visuals_dir.is_dir():
        return []

    results: list[dict[str, Any]] = []
    for vdir in sorted(visuals_dir.iterdir()):
        if not vdir.is_dir():
            continue
        vfile = vdir / "visual.json"
        if not vfile.exists():
            continue
        data = _read_json(vfile)

        # Group container: has "visualGroup" key instead of "visual"
        if "visualGroup" in data and "visual" not in data:
            results.append(
                {
                    "name": data.get("name", vdir.name),
                    "visual_type": "group",
                    "x": 0,
                    "y": 0,
                    "width": 0,
                    "height": 0,
                }
            )
            continue

        pos = data.get("position", {})
        visual_config = data.get("visual", {})
        results.append(
            {
                "name": data.get("name", vdir.name),
                "visual_type": visual_config.get("visualType", "unknown"),
                "x": pos.get("x", 0),
                "y": pos.get("y", 0),
                "width": pos.get("width", 0),
                "height": pos.get("height", 0),
            }
        )

    return results


def visual_get(definition_path: Path, page_name: str, visual_name: str) -> dict[str, Any]:
    """Get detailed information about a visual."""
    visual_dir = get_visual_dir(definition_path, page_name, visual_name)
    vfile = visual_dir / "visual.json"

    if not vfile.exists():
        raise PbiCliError(f"Visual '{visual_name}' not found on page '{page_name}'.")

    data = _read_json(vfile)
    pos = data.get("position", {})
    visual_config = data.get("visual", {})
    query_state = visual_config.get("query", {}).get("queryState", {})

    # Extract bindings summary
    bindings: list[dict[str, Any]] = []
    for role, state in query_state.items():
        projections = state.get("projections", [])
        for proj in projections:
            field = proj.get("field", {})
            query_ref = proj.get("queryRef", "")
            bindings.append(
                {
                    "role": role,
                    "query_ref": query_ref,
                    "field": _summarize_field(field),
                }
            )

    return {
        "name": data.get("name", visual_name),
        "visual_type": visual_config.get("visualType", "unknown"),
        "x": pos.get("x", 0),
        "y": pos.get("y", 0),
        "width": pos.get("width", 0),
        "height": pos.get("height", 0),
        "bindings": bindings,
        "is_hidden": data.get("isHidden", False),
    }


def visual_add(
    definition_path: Path,
    page_name: str,
    visual_type: str,
    name: str | None = None,
    x: float | None = None,
    y: float | None = None,
    width: float | None = None,
    height: float | None = None,
) -> dict[str, Any]:
    """Add a new visual to a page."""
    # Validate page exists
    page_dir = definition_path / "pages" / page_name
    if not page_dir.is_dir():
        raise PbiCliError(f"Page '{page_name}' not found.")

    resolved_type = _resolve_visual_type(visual_type)
    visual_name = name or _generate_name()

    # Defaults
    default_w, default_h = DEFAULT_SIZES.get(resolved_type, (400, 300))
    final_x = x if x is not None else 50
    final_y = y if y is not None else _next_y_position(definition_path, page_name)
    final_w = width if width is not None else default_w
    final_h = height if height is not None else default_h

    # Determine z-order
    z = _next_z_order(definition_path, page_name)

    # Load and fill template
    template_str = _load_template(resolved_type)
    visual_data = _build_visual_json(
        template_str,
        name=visual_name,
        x=final_x,
        y=final_y,
        width=final_w,
        height=final_h,
        z=z,
        tab_order=z,
    )

    # Write to disk
    visual_dir = get_visuals_dir(definition_path, page_name) / visual_name
    visual_dir.mkdir(parents=True, exist_ok=True)
    _write_json(visual_dir / "visual.json", visual_data)

    return {
        "status": "created",
        "name": visual_name,
        "visual_type": resolved_type,
        "page": page_name,
        "x": final_x,
        "y": final_y,
        "width": final_w,
        "height": final_h,
    }


def visual_update(
    definition_path: Path,
    page_name: str,
    visual_name: str,
    x: float | None = None,
    y: float | None = None,
    width: float | None = None,
    height: float | None = None,
    hidden: bool | None = None,
) -> dict[str, Any]:
    """Update visual position, size, or visibility."""
    visual_dir = get_visual_dir(definition_path, page_name, visual_name)
    vfile = visual_dir / "visual.json"

    if not vfile.exists():
        raise PbiCliError(f"Visual '{visual_name}' not found on page '{page_name}'.")

    data = _read_json(vfile)
    pos = data.get("position", {})

    if x is not None:
        pos["x"] = x
    if y is not None:
        pos["y"] = y
    if width is not None:
        pos["width"] = width
    if height is not None:
        pos["height"] = height
    data["position"] = pos

    if hidden is not None:
        data["isHidden"] = hidden

    _write_json(vfile, data)

    return {
        "status": "updated",
        "name": visual_name,
        "page": page_name,
        "position": {
            "x": pos.get("x", 0),
            "y": pos.get("y", 0),
            "width": pos.get("width", 0),
            "height": pos.get("height", 0),
        },
    }


def visual_set_container(
    definition_path: Path,
    page_name: str,
    visual_name: str,
    border_show: bool | None = None,
    background_show: bool | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """Set container-level properties (border, background, title) on a visual.

    Only the keyword arguments that are provided (not None) are updated.
    Other ``visualContainerObjects`` keys are preserved unchanged.

    The ``visualContainerObjects`` key is separate from ``visual.objects`` --
    it controls the container chrome (border, background, header title) rather
    than the visual's own formatting.
    """
    visual_dir = get_visual_dir(definition_path, page_name, visual_name)
    visual_json_path = visual_dir / "visual.json"
    if not visual_json_path.exists():
        raise PbiCliError(f"Visual '{visual_name}' not found on page '{page_name}'.")

    data = _read_json(visual_json_path)
    visual = data.get("visual")
    if visual is None:
        raise PbiCliError(f"Visual '{visual_name}' has invalid JSON -- missing 'visual' key.")

    if border_show is None and background_show is None and title is None:
        return {
            "status": "no-op",
            "visual": visual_name,
            "page": page_name,
            "border_show": None,
            "background_show": None,
            "title": None,
        }

    vco: dict[str, Any] = dict(visual.get("visualContainerObjects", {}))

    def _bool_entry(value: bool) -> list[dict[str, Any]]:
        return [{"properties": {"show": {"expr": {"Literal": {"Value": str(value).lower()}}}}}]

    if border_show is not None:
        vco = {**vco, "border": _bool_entry(border_show)}
    if background_show is not None:
        vco = {**vco, "background": _bool_entry(background_show)}
    if title is not None:
        vco = {
            **vco,
            "title": [{"properties": {"text": {"expr": {"Literal": {"Value": f"'{title}'"}}}}}],
        }

    updated_visual = {**visual, "visualContainerObjects": vco}
    _write_json(visual_json_path, {**data, "visual": updated_visual})

    return {
        "status": "updated",
        "visual": visual_name,
        "page": page_name,
        "border_show": border_show,
        "background_show": background_show,
        "title": title,
    }


def visual_delete(definition_path: Path, page_name: str, visual_name: str) -> dict[str, Any]:
    """Delete a visual from a page."""
    visual_dir = get_visual_dir(definition_path, page_name, visual_name)

    if not visual_dir.exists():
        raise PbiCliError(f"Visual '{visual_name}' not found on page '{page_name}'.")

    _rmtree(visual_dir)

    return {"status": "deleted", "name": visual_name, "page": page_name}


def visual_bind(
    definition_path: Path,
    page_name: str,
    visual_name: str,
    bindings: list[dict[str, Any]],
    field_index: FieldIndex | None = None,
    live_index_loader: Callable[[], FieldIndex | None] | None = None,
) -> dict[str, Any]:
    """Bind semantic model fields to visual data roles.

    Each binding dict should have:
      - ``role``: Data role (e.g. "category", "value", "row")
      - ``field``: Field reference in ``Table[Column]`` notation
      - ``kind``: (optional) ``"column"``, ``"measure"`` or ``"auto"`` (default)
      - ``measure``: (optional, legacy) bool, same as ``kind="measure"``
      - ``aggregation``: (optional) ``sum``, ``average``, ``count``, ``none``...
        for a column; overrides the implicit aggregation

    Roles are resolved through ``ROLE_ALIASES`` to the actual PBIR role name.
    With ``kind="auto"`` the Column/Measure wrapper is decided by, in order:

    1. ``field_index`` (defaults to the TMDL / model.bim the report points to)
    2. ``live_index_loader`` (called lazily, only for fields step 1 missed)
    3. A per-visual default: slicers bind columns, value roles bind measures

    A model column placed in a value role (chart Y, matrix values, table
    values...) is wrapped in the aggregation Desktop would apply: its
    ``summarizeBy``, else Sum for numeric columns. Non-summarizable columns
    fall back to Count, except in tables and cards where they stay as-is.
    """
    visual_dir = get_visual_dir(definition_path, page_name, visual_name)
    vfile = visual_dir / "visual.json"

    if not vfile.exists():
        raise PbiCliError(f"Visual '{visual_name}' not found on page '{page_name}'.")

    data = _read_json(vfile)
    visual_config = data.get("visual", {})
    visual_type = visual_config.get("visualType", "")
    query = visual_config.setdefault("query", {})
    query_state = query.setdefault("queryState", {})

    role_map = ROLE_ALIASES.get(visual_type, {})
    applied: list[dict[str, str]] = []
    warnings: list[str] = []

    if field_index is None:
        field_index = index_from_report(definition_path)
    live_index: FieldIndex | None = None
    live_loaded = False

    for binding in bindings:
        user_role = binding["role"].lower()
        field_ref = binding["field"]
        kind = str(binding.get("kind") or "auto").lower()
        if binding.get("measure"):
            kind = "measure"
        if kind not in _VALID_KINDS:
            raise PbiCliError(f"Invalid field kind '{kind}'. Use column, measure or auto.")

        # Resolve role alias
        pbir_role = role_map.get(user_role, binding["role"])

        # Parse Table[Column]
        table, column = _parse_field_ref(field_ref)

        requested_agg = binding.get("aggregation")
        hit: ResolvedField | None = None
        if kind != "auto":
            is_measure = kind == "measure"
            resolved_by = "explicit"
        else:
            hit = field_index.lookup(table, column) if field_index else None
            source = field_index.source if field_index else ""
            if hit is None and live_index_loader is not None:
                if not live_loaded:
                    live_index = live_index_loader()
                    live_loaded = True
                if live_index is not None:
                    hit = live_index.lookup(table, column)
                    source = live_index.source
            if hit is not None:
                is_measure = hit.kind == "measure"
                table, column = hit.table, hit.name
                resolved_by = source
            else:
                is_measure = _default_is_measure(visual_type, user_role, pbir_role)
                resolved_by = "default"
                if field_index or live_index:
                    warnings.append(
                        f"'{field_ref}' was not found in the semantic model; "
                        f"bound as {'Measure' if is_measure else 'Column'}. "
                        "Check the name or pass --kind to override."
                    )

        # Aggregation for columns in value roles
        function: int | None = None
        if requested_agg:
            if is_measure:
                warnings.append(
                    f"--aggregation ignored for '{field_ref}': measures are already aggregated."
                )
            else:
                try:
                    function = parse_aggregation(str(requested_agg))
                except ValueError as e:
                    raise PbiCliError(str(e)) from e
        elif not is_measure:
            function = _implicit_aggregation(visual_type, pbir_role, hit)

        # Build queryState projection (uses Entity directly, matching Desktop)
        wrapper = "Measure" if is_measure else "Column"
        field_expr: dict[str, Any] = {
            wrapper: {
                "Expression": {"SourceRef": {"Entity": table}},
                "Property": column,
            }
        }
        query_ref = f"{table}.{column}"
        native_ref = column
        if function is not None:
            prefix, label = AGGREGATE_LABELS[function]
            field_expr = {"Aggregation": {"Expression": field_expr, "Function": function}}
            query_ref = f"{prefix}({table}.{column})"
            native_ref = f"{label} {column}"

        projection: dict[str, Any] = {
            "field": field_expr,
            "queryRef": query_ref,
            "nativeQueryRef": native_ref,
        }
        if not is_measure and function is None:
            projection["active"] = True

        # Add to query state
        role_state = query_state.setdefault(pbir_role, {"projections": []})
        role_state["projections"].append(projection)

        entry = {
            "role": pbir_role,
            "field": field_ref,
            "query_ref": query_ref,
            "kind": wrapper,
            "resolved_by": resolved_by,
        }
        if function is not None:
            entry["aggregation"] = AGGREGATE_LABELS[function][0]
        applied.append(entry)

    data["visual"] = visual_config
    _write_json(vfile, data)

    result: dict[str, Any] = {
        "status": "bound",
        "name": visual_name,
        "page": page_name,
        "bindings": applied,
    }
    if warnings:
        result["warnings"] = warnings
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_FIELD_REF_PATTERN = re.compile(r"^(.+)\[(.+)\]$")


def _parse_field_ref(ref: str) -> tuple[str, str]:
    """Parse ``Table[Column]`` or ``[Measure]`` notation.

    Returns (table, column).
    """
    match = _FIELD_REF_PATTERN.match(ref.strip())
    if match:
        table = match.group(1).strip()
        column = match.group(2).strip()
        return table, column

    raise PbiCliError(f"Invalid field reference '{ref}'. Expected 'Table[Column]' format.")


def _summarize_field(field: dict[str, Any]) -> str:
    """Produce a human-readable summary of a query field expression."""
    if "Aggregation" in field:
        agg = field["Aggregation"]
        prefix = AGGREGATE_LABELS.get(agg.get("Function", -1), ("Agg", ""))[0]
        return f"{prefix}({_summarize_field(agg.get('Expression', {}))})"
    for kind in ("Column", "Measure"):
        if kind in field:
            item = field[kind]
            source_ref = item.get("Expression", {}).get("SourceRef", {})
            # queryState uses Entity, Commands uses Source
            source = source_ref.get("Entity", source_ref.get("Source", "?"))
            prop = item.get("Property", "?")
            if kind == "Measure":
                return f"{source}.[{prop}]"
            return f"{source}.{prop}"
    return str(field)


def _next_y_position(definition_path: Path, page_name: str) -> float:
    """Calculate the next y position to avoid overlap with existing visuals."""
    visuals_dir = definition_path / "pages" / page_name / "visuals"
    if not visuals_dir.is_dir():
        return 50

    max_bottom = 50.0
    for vdir in visuals_dir.iterdir():
        if not vdir.is_dir():
            continue
        vfile = vdir / "visual.json"
        if not vfile.exists():
            continue
        try:
            data = _read_json(vfile)
            pos = data.get("position", {})
            bottom = pos.get("y", 0) + pos.get("height", 0)
            if bottom > max_bottom:
                max_bottom = bottom
        except (json.JSONDecodeError, KeyError):
            continue

    return max_bottom + 20


def _next_z_order(definition_path: Path, page_name: str) -> int:
    """Determine the next z-order value for a new visual."""
    visuals_dir = definition_path / "pages" / page_name / "visuals"
    if not visuals_dir.is_dir():
        return 0

    max_z = -1
    for vdir in visuals_dir.iterdir():
        if not vdir.is_dir():
            continue
        vfile = vdir / "visual.json"
        if not vfile.exists():
            continue
        try:
            data = _read_json(vfile)
            z = data.get("position", {}).get("z", 0)
            if z > max_z:
                max_z = z
        except (json.JSONDecodeError, KeyError):
            continue

    return max_z + 1


def _rmtree(path: Path) -> None:
    """Recursively remove a directory tree."""
    if path.is_dir():
        for child in path.iterdir():
            _rmtree(child)
        path.rmdir()
    else:
        path.unlink()


# ---------------------------------------------------------------------------
# Visual Calculations (Phase 7)
# ---------------------------------------------------------------------------


def visual_calc_add(
    definition_path: Path,
    page_name: str,
    visual_name: str,
    calc_name: str,
    expression: str,
    role: str = "Y",
) -> dict[str, Any]:
    """Add a visual calculation to a data role's projections.

    Appends a NativeVisualCalculation projection to queryState[role].projections[].
    If the role does not exist in queryState, creates it with an empty projections list.
    If a calc with the same Name already exists in that role, replaces it (idempotent).

    Returns {"status": "added", "visual": visual_name, "name": calc_name,
             "role": role, "expression": expression}.
    Raises PbiCliError if visual.json not found.
    """
    vfile = get_visual_dir(definition_path, page_name, visual_name) / "visual.json"
    if not vfile.exists():
        raise PbiCliError(f"Visual '{visual_name}' not found on page '{page_name}'.")

    data = _read_json(vfile)
    visual_config = data.setdefault("visual", {})
    query = visual_config.setdefault("query", {})
    query_state = query.setdefault("queryState", {})
    role_state = query_state.setdefault(role, {"projections": []})
    projections: list[dict[str, Any]] = role_state.setdefault("projections", [])

    new_proj: dict[str, Any] = {
        "field": {
            "NativeVisualCalculation": {
                "Language": "dax",
                "Expression": expression,
                "Name": calc_name,
            }
        },
        "queryRef": "select",
        "nativeQueryRef": calc_name,
    }

    # Replace existing calc with same name (idempotent), else append
    updated = False
    new_projections: list[dict[str, Any]] = []
    for proj in projections:
        nvc = proj.get("field", {}).get("NativeVisualCalculation", {})
        if nvc.get("Name") == calc_name:
            new_projections.append(new_proj)
            updated = True
        else:
            new_projections.append(proj)

    if not updated:
        new_projections.append(new_proj)

    role_state["projections"] = new_projections
    _write_json(vfile, data)

    return {
        "status": "added",
        "visual": visual_name,
        "name": calc_name,
        "role": role,
        "expression": expression,
    }


def visual_calc_list(
    definition_path: Path,
    page_name: str,
    visual_name: str,
) -> list[dict[str, Any]]:
    """List all visual calculations across all roles.

    Returns list of {"name": ..., "expression": ..., "role": ..., "query_ref": "select"}.
    Returns [] if no NativeVisualCalculation projections found.
    """
    vfile = get_visual_dir(definition_path, page_name, visual_name) / "visual.json"
    if not vfile.exists():
        raise PbiCliError(f"Visual '{visual_name}' not found on page '{page_name}'.")

    data = _read_json(vfile)
    query_state = data.get("visual", {}).get("query", {}).get("queryState", {})

    results: list[dict[str, Any]] = []
    for role, state in query_state.items():
        for proj in state.get("projections", []):
            nvc = proj.get("field", {}).get("NativeVisualCalculation")
            if nvc is not None:
                results.append(
                    {
                        "name": nvc.get("Name", ""),
                        "expression": nvc.get("Expression", ""),
                        "role": role,
                        "query_ref": proj.get("queryRef", "select"),
                    }
                )

    return results


def visual_calc_delete(
    definition_path: Path,
    page_name: str,
    visual_name: str,
    calc_name: str,
) -> dict[str, Any]:
    """Delete a visual calculation by name.

    Searches all roles' projections for NativeVisualCalculation with Name==calc_name.
    Raises PbiCliError if not found.
    Returns {"status": "deleted", "visual": visual_name, "name": calc_name}.
    """
    vfile = get_visual_dir(definition_path, page_name, visual_name) / "visual.json"
    if not vfile.exists():
        raise PbiCliError(f"Visual '{visual_name}' not found on page '{page_name}'.")

    data = _read_json(vfile)
    query_state = data.get("visual", {}).get("query", {}).get("queryState", {})

    found = False
    for role, state in query_state.items():
        projections: list[dict[str, Any]] = state.get("projections", [])
        new_projections = [
            proj
            for proj in projections
            if proj.get("field", {}).get("NativeVisualCalculation", {}).get("Name") != calc_name
        ]
        if len(new_projections) < len(projections):
            state["projections"] = new_projections
            found = True

    if not found:
        raise PbiCliError(f"Visual calculation '{calc_name}' not found in visual '{visual_name}'.")

    _write_json(vfile, data)
    return {"status": "deleted", "visual": visual_name, "name": calc_name}
