"""PBIR visual CRUD commands."""

from __future__ import annotations

import click

from pbi_cli.commands._helpers import run_command
from pbi_cli.main import PbiContext, pass_context


@click.group()
@click.option(
    "--path",
    "-p",
    default=None,
    help="Path to .Report folder (auto-detected from CWD if omitted).",
)
@click.option(
    "--no-sync",
    is_flag=True,
    default=False,
    help="Skip Desktop auto-sync after write commands. Use for scripted multi-step builds.",
)
@click.pass_context
def visual(ctx: click.Context, path: str | None, no_sync: bool) -> None:
    """Manage visuals in PBIR report pages."""
    ctx.ensure_object(dict)
    ctx.obj["report_path"] = path
    ctx.obj["no_sync"] = no_sync


def _get_report_path(click_ctx: click.Context) -> str | None:
    """Extract report_path from parent context."""
    if click_ctx.parent:
        result: str | None = click_ctx.parent.obj.get("report_path")
        return result
    return None


@visual.command(name="list")
@click.option("--page", required=True, help="Page name/ID.")
@click.pass_context
@pass_context
def visual_list(ctx: PbiContext, click_ctx: click.Context, page: str) -> None:
    """List all visuals on a page."""
    from pbi_cli.core.pbir_path import resolve_report_path
    from pbi_cli.core.visual_backend import visual_list as _visual_list

    definition_path = resolve_report_path(_get_report_path(click_ctx))
    run_command(ctx, _visual_list, definition_path=definition_path, page_name=page)


@visual.command()
@click.argument("name")
@click.option("--page", required=True, help="Page name/ID.")
@click.pass_context
@pass_context
def get(ctx: PbiContext, click_ctx: click.Context, name: str, page: str) -> None:
    """Get detailed information about a visual."""
    from pbi_cli.core.pbir_path import resolve_report_path
    from pbi_cli.core.visual_backend import visual_get

    definition_path = resolve_report_path(_get_report_path(click_ctx))
    run_command(
        ctx,
        visual_get,
        definition_path=definition_path,
        page_name=page,
        visual_name=name,
    )


@visual.command()
@click.option("--page", required=True, help="Page name/ID.")
@click.option(
    "--type",
    "visual_type",
    required=True,
    help="Visual type (bar_chart, line_chart, card, table, matrix).",
)
@click.option("--name", "-n", default=None, help="Visual name (auto-generated if omitted).")
@click.option("--x", type=float, default=None, help="X position on canvas.")
@click.option("--y", type=float, default=None, help="Y position on canvas.")
@click.option("--width", type=float, default=None, help="Visual width in pixels.")
@click.option("--height", type=float, default=None, help="Visual height in pixels.")
@click.pass_context
@pass_context
def add(
    ctx: PbiContext,
    click_ctx: click.Context,
    page: str,
    visual_type: str,
    name: str | None,
    x: float | None,
    y: float | None,
    width: float | None,
    height: float | None,
) -> None:
    """Add a new visual to a page."""
    from pbi_cli.core.pbir_path import resolve_report_path
    from pbi_cli.core.visual_backend import visual_add

    definition_path = resolve_report_path(_get_report_path(click_ctx))
    run_command(
        ctx,
        visual_add,
        definition_path=definition_path,
        page_name=page,
        visual_type=visual_type,
        name=name,
        x=x,
        y=y,
        width=width,
        height=height,
    )


@visual.command()
@click.argument("name")
@click.option("--page", required=True, help="Page name/ID.")
@click.option("--x", type=float, default=None, help="New X position.")
@click.option("--y", type=float, default=None, help="New Y position.")
@click.option("--width", type=float, default=None, help="New width.")
@click.option("--height", type=float, default=None, help="New height.")
@click.option("--hidden/--visible", default=None, help="Toggle visibility.")
@click.pass_context
@pass_context
def update(
    ctx: PbiContext,
    click_ctx: click.Context,
    name: str,
    page: str,
    x: float | None,
    y: float | None,
    width: float | None,
    height: float | None,
    hidden: bool | None,
) -> None:
    """Update visual position, size, or visibility."""
    from pbi_cli.core.pbir_path import resolve_report_path
    from pbi_cli.core.visual_backend import visual_update

    definition_path = resolve_report_path(_get_report_path(click_ctx))
    run_command(
        ctx,
        visual_update,
        definition_path=definition_path,
        page_name=page,
        visual_name=name,
        x=x,
        y=y,
        width=width,
        height=height,
        hidden=hidden,
    )


@visual.command()
@click.argument("name")
@click.option("--page", required=True, help="Page name/ID.")
@click.pass_context
@pass_context
def delete(ctx: PbiContext, click_ctx: click.Context, name: str, page: str) -> None:
    """Delete a visual from a page."""
    from pbi_cli.core.pbir_path import resolve_report_path
    from pbi_cli.core.visual_backend import visual_delete

    definition_path = resolve_report_path(_get_report_path(click_ctx))
    run_command(
        ctx,
        visual_delete,
        definition_path=definition_path,
        page_name=page,
        visual_name=name,
    )


@visual.command()
@click.argument("name")
@click.option("--page", required=True, help="Page name/ID.")
@click.option(
    "--category",
    multiple=True,
    help="Category/axis column: bar, line, donut charts. Table[Column] format.",
)
@click.option(
    "--value",
    multiple=True,
    help="Value/measure: all chart types. Treated as measure. Table[Measure] format.",
)
@click.option(
    "--row",
    multiple=True,
    help="Row grouping column: matrix only. Table[Column] format.",
)
@click.option(
    "--field",
    multiple=True,
    help="Data field: card, slicer. Treated as measure for cards. Table[Field] format.",
)
@click.option(
    "--legend",
    multiple=True,
    help="Legend/series column: bar, line, donut charts. Table[Column] format.",
)
@click.option(
    "--indicator",
    multiple=True,
    help="KPI indicator measure. Table[Measure] format.",
)
@click.option(
    "--goal",
    multiple=True,
    help="KPI goal measure. Table[Measure] format.",
)
@click.pass_context
@pass_context
def bind(
    ctx: PbiContext,
    click_ctx: click.Context,
    name: str,
    page: str,
    category: tuple[str, ...],
    value: tuple[str, ...],
    row: tuple[str, ...],
    field: tuple[str, ...],
    legend: tuple[str, ...],
    indicator: tuple[str, ...],
    goal: tuple[str, ...],
) -> None:
    """Bind semantic model fields to a visual's data roles.

    Examples:

      pbi visual bind mychart --page p1 --category "Geo[Region]" --value "Sales[Amount]"

      pbi visual bind mycard --page p1 --field "Sales[Total Revenue]"

      pbi visual bind mymatrix --page p1 --row "Product[Category]" --value "Sales[Qty]"

      pbi visual bind mykpi --page p1 --indicator "Sales[Revenue]" --goal "Sales[Target]"
    """
    from pbi_cli.core.pbir_path import resolve_report_path
    from pbi_cli.core.visual_backend import visual_bind

    bindings: list[dict[str, str]] = []
    for f in category:
        bindings.append({"role": "category", "field": f})
    for f in value:
        bindings.append({"role": "value", "field": f})
    for f in row:
        bindings.append({"role": "row", "field": f})
    for f in field:
        bindings.append({"role": "field", "field": f})
    for f in legend:
        bindings.append({"role": "legend", "field": f})
    for f in indicator:
        bindings.append({"role": "indicator", "field": f})
    for f in goal:
        bindings.append({"role": "goal", "field": f})

    if not bindings:
        raise click.UsageError(
            "At least one binding required "
            "(--category, --value, --row, --field, --legend, --indicator, or --goal)."
        )

    definition_path = resolve_report_path(_get_report_path(click_ctx))
    run_command(
        ctx,
        visual_bind,
        definition_path=definition_path,
        page_name=page,
        visual_name=name,
        bindings=bindings,
    )


# ---------------------------------------------------------------------------
# v3.1.0 Bulk operations
# ---------------------------------------------------------------------------


@visual.command()
@click.option("--page", required=True, help="Page name/ID.")
@click.option("--type", "visual_type", default=None, help="Filter by PBIR visual type or alias.")
@click.option("--name-pattern", default=None, help="fnmatch glob on visual name (e.g. 'Chart_*').")
@click.option("--x-min", type=float, default=None, help="Minimum x position.")
@click.option("--x-max", type=float, default=None, help="Maximum x position.")
@click.option("--y-min", type=float, default=None, help="Minimum y position.")
@click.option("--y-max", type=float, default=None, help="Maximum y position.")
@click.pass_context
@pass_context
def where(
    ctx: PbiContext,
    click_ctx: click.Context,
    page: str,
    visual_type: str | None,
    name_pattern: str | None,
    x_min: float | None,
    x_max: float | None,
    y_min: float | None,
    y_max: float | None,
) -> None:
    """Filter visuals by type and/or position bounds.

    Examples:

      pbi visual where --page overview --type barChart

      pbi visual where --page overview --x-max 640

      pbi visual where --page overview --type kpi --name-pattern "KPI_*"
    """
    from pbi_cli.core.bulk_backend import visual_where
    from pbi_cli.core.pbir_path import resolve_report_path

    definition_path = resolve_report_path(_get_report_path(click_ctx))
    run_command(
        ctx,
        visual_where,
        definition_path=definition_path,
        page_name=page,
        visual_type=visual_type,
        name_pattern=name_pattern,
        x_min=x_min,
        x_max=x_max,
        y_min=y_min,
        y_max=y_max,
    )


@visual.command(name="bulk-bind")
@click.option("--page", required=True, help="Page name/ID.")
@click.option("--type", "visual_type", required=True, help="Target PBIR visual type or alias.")
@click.option("--name-pattern", default=None, help="Restrict to visuals matching fnmatch pattern.")
@click.option("--category", multiple=True, help="Category/axis. Table[Column].")
@click.option("--value", multiple=True, help="Value/measure: all chart types. Table[Measure].")
@click.option("--row", multiple=True, help="Row grouping: matrix only. Table[Column].")
@click.option("--field", multiple=True, help="Data field: card, slicer. Table[Field].")
@click.option("--legend", multiple=True, help="Legend/series. Table[Column].")
@click.option("--indicator", multiple=True, help="KPI indicator measure. Table[Measure].")
@click.option("--goal", multiple=True, help="KPI goal measure. Table[Measure].")
@click.option("--column", "col_value", multiple=True, help="Combo column Y. Table[Measure].")
@click.option("--line", multiple=True, help="Line Y axis for combo chart. Table[Measure].")
@click.option("--x", "x_field", multiple=True, help="X axis for scatter chart. Table[Measure].")
@click.option("--y", "y_field", multiple=True, help="Y axis for scatter chart. Table[Measure].")
@click.pass_context
@pass_context
def bulk_bind(
    ctx: PbiContext,
    click_ctx: click.Context,
    page: str,
    visual_type: str,
    name_pattern: str | None,
    category: tuple[str, ...],
    value: tuple[str, ...],
    row: tuple[str, ...],
    field: tuple[str, ...],
    legend: tuple[str, ...],
    indicator: tuple[str, ...],
    goal: tuple[str, ...],
    col_value: tuple[str, ...],
    line: tuple[str, ...],
    x_field: tuple[str, ...],
    y_field: tuple[str, ...],
) -> None:
    """Bind fields to ALL visuals of a given type on a page.

    Examples:

      pbi visual bulk-bind --page overview --type barChart \\
          --category "Date[Month]" --value "Sales[Revenue]"

      pbi visual bulk-bind --page overview --type kpi \\
          --indicator "Sales[Revenue]" --goal "Sales[Target]"

      pbi visual bulk-bind --page overview --type lineStackedColumnComboChart \\
          --column "Sales[Revenue]" --line "Sales[Margin]"
    """
    from pbi_cli.core.bulk_backend import visual_bulk_bind
    from pbi_cli.core.pbir_path import resolve_report_path

    bindings: list[dict[str, str]] = []
    for f in category:
        bindings.append({"role": "category", "field": f})
    for f in value:
        bindings.append({"role": "value", "field": f})
    for f in row:
        bindings.append({"role": "row", "field": f})
    for f in field:
        bindings.append({"role": "field", "field": f})
    for f in legend:
        bindings.append({"role": "legend", "field": f})
    for f in indicator:
        bindings.append({"role": "indicator", "field": f})
    for f in goal:
        bindings.append({"role": "goal", "field": f})
    for f in col_value:
        bindings.append({"role": "column", "field": f})
    for f in line:
        bindings.append({"role": "line", "field": f})
    for f in x_field:
        bindings.append({"role": "x", "field": f})
    for f in y_field:
        bindings.append({"role": "y", "field": f})

    if not bindings:
        raise click.UsageError("At least one binding role required.")

    definition_path = resolve_report_path(_get_report_path(click_ctx))
    run_command(
        ctx,
        visual_bulk_bind,
        definition_path=definition_path,
        page_name=page,
        visual_type=visual_type,
        bindings=bindings,
        name_pattern=name_pattern,
    )


@visual.command(name="bulk-update")
@click.option("--page", required=True, help="Page name/ID.")
@click.option("--type", "visual_type", default=None, help="Filter by visual type or alias.")
@click.option("--name-pattern", default=None, help="fnmatch filter on visual name.")
@click.option("--width", type=float, default=None, help="Set width for all matching visuals.")
@click.option("--height", type=float, default=None, help="Set height for all matching visuals.")
@click.option("--x", "set_x", type=float, default=None, help="Set x position.")
@click.option("--y", "set_y", type=float, default=None, help="Set y position.")
@click.option("--hidden/--visible", default=None, help="Show or hide all matching visuals.")
@click.pass_context
@pass_context
def bulk_update(
    ctx: PbiContext,
    click_ctx: click.Context,
    page: str,
    visual_type: str | None,
    name_pattern: str | None,
    width: float | None,
    height: float | None,
    set_x: float | None,
    set_y: float | None,
    hidden: bool | None,
) -> None:
    """Update dimensions or visibility for ALL visuals matching the filter.

    Examples:

      pbi visual bulk-update --page overview --type kpi --height 200 --width 300

      pbi visual bulk-update --page overview --name-pattern "Temp_*" --hidden
    """
    from pbi_cli.core.bulk_backend import visual_bulk_update
    from pbi_cli.core.pbir_path import resolve_report_path

    definition_path = resolve_report_path(_get_report_path(click_ctx))
    run_command(
        ctx,
        visual_bulk_update,
        definition_path=definition_path,
        page_name=page,
        where_type=visual_type,
        where_name_pattern=name_pattern,
        set_hidden=hidden,
        set_width=width,
        set_height=height,
        set_x=set_x,
        set_y=set_y,
    )


@visual.command(name="bulk-delete")
@click.option("--page", required=True, help="Page name/ID.")
@click.option("--type", "visual_type", default=None, help="Filter by visual type or alias.")
@click.option("--name-pattern", default=None, help="fnmatch filter on visual name.")
@click.pass_context
@pass_context
def bulk_delete(
    ctx: PbiContext,
    click_ctx: click.Context,
    page: str,
    visual_type: str | None,
    name_pattern: str | None,
) -> None:
    """Delete ALL visuals matching the filter (requires --type or --name-pattern).

    Examples:

      pbi visual bulk-delete --page overview --type barChart

      pbi visual bulk-delete --page overview --name-pattern "Draft_*"
    """
    from pbi_cli.core.bulk_backend import visual_bulk_delete
    from pbi_cli.core.pbir_path import resolve_report_path

    definition_path = resolve_report_path(_get_report_path(click_ctx))
    run_command(
        ctx,
        visual_bulk_delete,
        definition_path=definition_path,
        page_name=page,
        where_type=visual_type,
        where_name_pattern=name_pattern,
    )


# ---------------------------------------------------------------------------
# v3.2.0 Visual Calculations (Phase 7)
# ---------------------------------------------------------------------------


@visual.command(name="calc-add")
@click.argument("visual_name")
@click.option("--page", required=True, help="Page name/ID.")
@click.option("--name", "calc_name", required=True, help="Display name for the calculation.")
@click.option("--expression", required=True, help="DAX expression for the calculation.")
@click.option("--role", default="Y", show_default=True, help="Target data role (e.g. Y, Values).")
@click.pass_context
@pass_context
def calc_add(
    ctx: PbiContext,
    click_ctx: click.Context,
    visual_name: str,
    page: str,
    calc_name: str,
    expression: str,
    role: str,
) -> None:
    """Add a visual calculation to a data role's projections.

    Examples:

      pbi visual calc-add MyChart --page overview --name "Running sum" \\
          --expression "RUNNINGSUM([Sum of Sales])"

      pbi visual calc-add MyChart --page overview --name "Rank" \\
          --expression "RANK()" --role Y
    """
    from pbi_cli.core.pbir_path import resolve_report_path
    from pbi_cli.core.visual_backend import visual_calc_add

    definition_path = resolve_report_path(_get_report_path(click_ctx))
    run_command(
        ctx,
        visual_calc_add,
        definition_path=definition_path,
        page_name=page,
        visual_name=visual_name,
        calc_name=calc_name,
        expression=expression,
        role=role,
    )


@visual.command(name="calc-list")
@click.argument("visual_name")
@click.option("--page", required=True, help="Page name/ID.")
@click.pass_context
@pass_context
def calc_list(
    ctx: PbiContext,
    click_ctx: click.Context,
    visual_name: str,
    page: str,
) -> None:
    """List all visual calculations on a visual across all roles.

    Examples:

      pbi visual calc-list MyChart --page overview
    """
    from pbi_cli.core.pbir_path import resolve_report_path
    from pbi_cli.core.visual_backend import visual_calc_list

    definition_path = resolve_report_path(_get_report_path(click_ctx))
    run_command(
        ctx,
        visual_calc_list,
        definition_path=definition_path,
        page_name=page,
        visual_name=visual_name,
    )


@visual.command(name="set-container")
@click.argument("name")
@click.option("--page", required=True, help="Page name/ID.")
@click.option(
    "--border-show",
    type=bool,
    default=None,
    help="Show (true) or hide (false) the visual border.",
)
@click.option(
    "--background-show",
    type=bool,
    default=None,
    help="Show (true) or hide (false) the visual background.",
)
@click.option("--title", default=None, help="Set container title text.")
@click.pass_context
@pass_context
def set_container(
    ctx: PbiContext,
    click_ctx: click.Context,
    name: str,
    page: str,
    border_show: bool | None,
    background_show: bool | None,
    title: str | None,
) -> None:
    """Set container-level border, background, or title on a visual."""
    from pbi_cli.core.pbir_path import resolve_report_path
    from pbi_cli.core.visual_backend import visual_set_container

    definition_path = resolve_report_path(_get_report_path(click_ctx))
    run_command(
        ctx,
        visual_set_container,
        definition_path=definition_path,
        page_name=page,
        visual_name=name,
        border_show=border_show,
        background_show=background_show,
        title=title,
    )


@visual.command(name="calc-delete")
@click.argument("visual_name")
@click.option("--page", required=True, help="Page name/ID.")
@click.option("--name", "calc_name", required=True, help="Name of the calculation to delete.")
@click.pass_context
@pass_context
def calc_delete(
    ctx: PbiContext,
    click_ctx: click.Context,
    visual_name: str,
    page: str,
    calc_name: str,
) -> None:
    """Delete a visual calculation by name.

    Examples:

      pbi visual calc-delete MyChart --page overview --name "Running sum"
    """
    from pbi_cli.core.pbir_path import resolve_report_path
    from pbi_cli.core.visual_backend import visual_calc_delete

    definition_path = resolve_report_path(_get_report_path(click_ctx))
    run_command(
        ctx,
        visual_calc_delete,
        definition_path=definition_path,
        page_name=page,
        visual_name=visual_name,
        calc_name=calc_name,
    )


# ---------------------------------------------------------------------------
# Custom visual commands (locally-built .pbiviz embedding)
# ---------------------------------------------------------------------------


@visual.command(name="import-custom")
@click.argument("pbiviz_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--replace",
    is_flag=True,
    default=False,
    help="Overwrite an existing custom visual with the same GUID.",
)
@click.pass_context
@pass_context
def import_custom(
    ctx: PbiContext,
    click_ctx: click.Context,
    pbiviz_file: str,
    replace: bool,
) -> None:
    """Import a locally-built .pbiviz into the report.

    Copies the file to ``StaticResources/RegisteredResources/`` and
    registers it in ``report.json``. Sanity-checks the archive and
    manifest; deep validation is left to ``pbiviz package`` and Power BI
    Desktop's loader.

    The GUID is read from the archive's ``package.json``. Pass
    ``--replace`` to overwrite an existing entry with the same GUID
    (typical during the vibe-coding iteration loop).
    """
    from pathlib import Path

    from pbi_cli.core.custom_visual_backend import custom_visual_import
    from pbi_cli.core.pbir_path import resolve_report_path

    definition_path = resolve_report_path(_get_report_path(click_ctx))
    run_command(
        ctx,
        custom_visual_import,
        definition_path=definition_path,
        pbiviz_path=Path(pbiviz_file),
        replace=replace,
    )


@visual.command(name="list-custom")
@click.pass_context
@pass_context
def list_custom(ctx: PbiContext, click_ctx: click.Context) -> None:
    """List custom visuals registered in the report.

    Shows both embedded (locally-built ``.pbiviz``) and public
    (AppSource / organizational) custom visuals with a ``kind``
    distinguisher.
    """
    from pbi_cli.core.custom_visual_backend import custom_visual_list
    from pbi_cli.core.pbir_path import resolve_report_path

    definition_path = resolve_report_path(_get_report_path(click_ctx))
    run_command(
        ctx,
        custom_visual_list,
        definition_path=definition_path,
    )


@visual.command(name="remove-custom")
@click.argument("identifier")
@click.pass_context
@pass_context
def remove_custom(
    ctx: PbiContext,
    click_ctx: click.Context,
    identifier: str,
) -> None:
    """Remove an embedded custom visual by GUID or name.

    GUID is canonical and unambiguous. Name lookup matches the
    ``<safe-name>`` portion of the registered filename; if the name
    matches multiple visuals, the command errors and asks you to
    disambiguate by GUID. The ``.pbiviz`` resource file is deleted from
    ``StaticResources/RegisteredResources/`` along with its registration.

    Public (AppSource) entries are out of scope; remove those from
    ``report.json`` directly or via Power BI Desktop.
    """
    from pbi_cli.core.custom_visual_backend import custom_visual_remove
    from pbi_cli.core.pbir_path import resolve_report_path

    definition_path = resolve_report_path(_get_report_path(click_ctx))
    run_command(
        ctx,
        custom_visual_remove,
        definition_path=definition_path,
        identifier=identifier,
    )
