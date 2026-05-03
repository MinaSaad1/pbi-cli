# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.11.0] - 2026-05-03

### Added
- **Custom visual authoring** -- vibe-code Power BI custom visuals end-to-end with the new `power-bi-custom-visuals` Claude skill. The skill scaffolds a TypeScript project sibling to your `.pbip` via `npx pbiviz new`, iterates against the Power BI Visuals SDK with `tsc --noEmit` between every change, packages a `.pbiviz`, and embeds it into the report. Auto-installs Node and `pbiviz` (with consent), pins SDK to a known-good version, runs an npm allowlist for common deps. Inner loop is agent-driven on TypeScript errors; visual correctness is checked once with the user at the end.
- `pbi visual import-custom <pbiviz>` -- copy a locally-built `.pbiviz` into `StaticResources/RegisteredResources/` and register it in `report.json`. `--replace` overwrites by GUID for the iteration loop.
- `pbi visual list-custom` -- list embedded and public custom visuals with a `kind` distinguisher.
- `pbi visual remove-custom <guid-or-name>` -- deregister and physically delete the `.pbiviz`.

## [3.10.6] - 2026-04-07

### Fixed
- `visual bind` no longer writes the legacy `Commands` block (SemanticQueryDataShapeCommand) to `visual.json`. PBIR 2.7.0 uses `additionalProperties: false` on the query object, so the `Commands` field is a hard schema violation. Only `queryState` projections are now written.
- `pbi report validate` and the full PBIR validator no longer flag a missing `layoutOptimization` field as an error. The real Microsoft schema does not list it as required; the previous check was against a stale internal schema.
- `pbi report set-background` now always writes `transparency: 0` alongside the color. Power BI Desktop defaults a missing `transparency` property to 100 (fully invisible), making the color silently unrendered. The new `--transparency` flag (0-100, default 0) lets callers override for semi-transparent backgrounds.

### Added
- `--no-sync` flag on `report`, `visual`, `filters`, and `bookmarks` command groups. Suppresses the per-command Desktop auto-sync for scripted multi-step builds. Use `pbi report reload` for a single explicit sync at the end of the script.

## [3.10.5] - 2026-04-06

### Fixed
- ASCII banner: replaced incorrect hand-crafted art with the official design from `assets/banner.svg`. The `I` in PBI is now correctly narrow, and a small `███╗/╚══╝` block serves as the visible `-` separator between PBI and CLI.

## [3.10.4] - 2026-04-06

### Added
- ASCII banner displayed in terminal when `pbi` is invoked with no subcommand. Renders in Power BI yellow on color terminals, plain text fallback on legacy terminals without Unicode support. Skipped when `--json` flag is used.

## [3.10.3] - 2026-04-05

### Changed
- Claude Code integration is now fully opt-in. `pbi connect` no longer writes to `~/.claude/`. Run `pbi-cli skills install` explicitly to register skills with Claude Code. See [SECURITY.md](SECURITY.md) for full details.
- `pbi-cli` is now a dedicated management entry point (`pbi-cli skills install/uninstall/list`). Skills subcommands have been removed from the `pbi` entry point.

### Fixed
- DLL licensing: Microsoft Analysis Services client library DLLs bundled in `src/pbi_cli/dlls/` are now correctly attributed under the Microsoft Software License Terms, not sublicensed under MIT. Full EULA text in `THIRD_PARTY_LICENSES.md`.
- `pyproject.toml` updated to PEP 639 dual SPDX expression (`MIT AND LicenseRef-Microsoft-AS-Client-Libraries`) with `license-files` declaration.
- README.md and README.pypi.md updated to reflect the correct 3-step setup flow: `pipx install` → `pbi-cli skills install` → `pbi connect`.

## [3.10.0] - 2026-04-02

### Added
- Split `power-bi-report` skill into 5 focused skills: `power-bi-report` (overview), `power-bi-visuals`, `power-bi-pages`, `power-bi-themes`, `power-bi-filters` (12 skills total)
- CLAUDE.md snippet now organises skills by layer (Semantic Model vs Report Layer)
- Skill triggering test suite (19 prompts, 12 skills)

### Fixed
- `filter_add_topn` inner subquery now correctly references category table when it differs from order-by table
- `theme_set` resourcePackages structure now matches Desktop format (flat `items` array)
- `visual_bind` type annotation corrected to `list[dict[str, Any]]`
- `tmdl_diff` hierarchy changes reported as `hierarchies_*` instead of falling to `other_*`
- Missing `VisualTypeError` and `ReportNotFoundError` classes added to `errors.py`
- `report`, `visual`, `filters`, `format`, `bookmarks` command groups registered in CLI

### Changed
- README rewritten to cover both semantic model and report layers, 12 skills, 27 command groups, 32 visual types

## [3.9.0] - 2026-04-01

### Added
- `pbi database diff-tmdl` command: compare two TMDL export folders offline, summarise changes (tables, measures, columns, relationships, model properties); lineageTag-only changes are stripped to avoid false positives

### Fixed
- `filter_add_topn` inner subquery now correctly references the category table when it differs from the order-by table (cross-table TopN filters)
- `theme_set` resourcePackages structure now matches Desktop format (flat `items`, not nested `resourcePackage`)
- `visual_bind` type annotation corrected from `list[dict[str, str]]` to `list[dict[str, Any]]`
- `tmdl_diff` hierarchy changes now reported as `hierarchies_*` instead of falling through to `other_*`
- Missing `VisualTypeError` and `ReportNotFoundError` error classes added to `errors.py`
- `report`, `visual`, `filters`, `format`, `bookmarks` command groups registered in CLI (were implemented but inaccessible)

## [3.8.0] - 2026-04-01

### Added
- `azureMap` visual type (Azure Maps) with Category and Size roles
- `pageBinding` field surfaced in `page_get()` for drillthrough pages

### Fixed
- `card` and `multiRowCard` queryState role corrected from `Fields` to `Values` (matches Desktop)
- `kpi` template: added `TrendLine` queryState key (date/axis column for sparkline)
- `gauge` template: added `MaxValue` queryState key (target/max measure)
- `MaxValue` added to `MEASURE_ROLES`
- kpi role aliases: `--trend`, `--trend_line`
- gauge role aliases: `--max`, `--max_value`, `--target`

## [3.7.0] - 2026-04-01

### Added
- `page_type`, `filter_config`, and `visual_interactions` fields in page read operations (`page_get`, `page_list`)

## [3.6.0] - 2026-04-01

### Added
- `image` visual type (static images, no data binding)
- `shape` visual type (decorative shapes)
- `textbox` visual type (rich text)
- `pageNavigator` visual type (page navigation buttons)
- `advancedSlicerVisual` visual type (tile/image slicer)

## [3.5.0] - 2026-04-01

### Added
- `clusteredColumnChart` visual type with aliases `clustered_column`
- `clusteredBarChart` visual type with aliases `clustered_bar`
- `textSlicer` visual type with alias `text_slicer`
- `listSlicer` visual type with alias `list_slicer`

## [3.4.0] - 2026-03-31

### Added
- `cardVisual` (modern card) visual type with `Data` role and aliases `card_visual`, `modern_card`
- `actionButton` visual type with alias `action_button`, `button`
- `pbi report set-background` command to set page background colour
- `pbi report set-visibility` command to hide/show pages
- `pbi visual set-container` command for border, background, and title on visual containers

### Fixed
- Visual container schema URL updated from 1.5.0 to 2.7.0
- `visualGroup` containers tagged as type `group` in `visual_list`
- Colour validation, KeyError guards, visibility surfacing, no-op detection

## [3.0.0] - 2026-03-31

### Added
- **PBIR report layer**: `pbi report` command group (create, info, validate, list-pages, add-page, delete-page, get-page, set-theme, get-theme, diff-theme, preview, reload, convert)
- **Visual CRUD**: `pbi visual` command group (add, get, list, update, delete, bind, where, bulk-bind, bulk-update, bulk-delete, calc-add, calc-list, calc-delete, set-container)
- **Filters**: `pbi filters` command group (list, add-categorical, add-topn, add-relative-date, remove, clear)
- **Formatting**: `pbi format` command group (get, clear, background-gradient, background-conditional, background-measure)
- **Bookmarks**: `pbi bookmarks` command group (list, get, add, delete, set-visibility)
- 20 visual type templates (barChart, lineChart, card, tableEx, pivotTable, slicer, kpi, gauge, donutChart, columnChart, areaChart, ribbonChart, waterfallChart, scatterChart, funnelChart, multiRowCard, treemap, cardNew, stackedBarChart, lineStackedColumnComboChart)
- HTML preview server (`pbi report preview`) with live reload
- Power BI Desktop reload trigger (`pbi report reload`)
- PBIR path auto-detection (walk-up from CWD, `.pbip` sibling detection)
- `power-bi-report` Claude Code skill (8th skill)
- Visual data binding with `Table[Column]` notation and role aliases
- Visual calculations (calc-add, calc-list, calc-delete)
- Bulk operations for mass visual updates across pages

### Changed
- Architecture: pbi-cli now covers both semantic model layer (via .NET TOM) and report layer (via PBIR JSON files)

## [2.2.0] - 2026-03-27

### Added
- Promotional SVG assets and redesigned README

## [2.0.0] - 2026-03-27

### Breaking
- Removed MCP server dependency entirely (no more `powerbi-modeling-mcp` binary)
- Removed `connect-fabric` command (future work)
- Removed per-object TMDL export (`table export-tmdl`, `measure export-tmdl`, etc.) -- use `pbi database export-tmdl`
- Removed `model refresh` command
- Removed `security-role export-tmdl` -- use `pbi database export-tmdl`

### Added
- Direct pythonnet/.NET TOM interop (in-process, sub-second commands)
- Bundled Microsoft Analysis Services DLLs (~20MB, no external download needed)
- 2 new Claude Code skills: Diagnostics and Partitions & Expressions (7 total)
- New commands: `trace start/stop/fetch/export`, `transaction begin/commit/rollback`, `calendar list/mark`, `expression list/get/create/delete`, `partition list/create/delete/refresh`, `advanced culture list/get`
- `connections last` command to show last-used connection
- `pbi connect` now auto-installs skills (no separate `pbi skills install` needed)

### Changed
- `pbi setup` now verifies pythonnet + bundled DLLs (no longer downloads a binary)
- Architecture: Click CLI -> tom_backend/adomd_backend -> pythonnet -> .NET TOM (in-process)
- All 7 skills updated to reflect v2 commands and architecture
- README rewritten for v2 architecture

### Removed
- MCP client/server architecture
- Binary manager and auto-download from VS Code Marketplace
- `$PBI_MCP_BINARY` environment variable
- `~/.pbi-cli/bin/` binary directory

## [1.0.6] - 2026-03-26

### Fixed
- Use server-assigned connection name for subsequent commands (fixes "connection not found" mismatch)

## [1.0.5] - 2026-03-26

### Fixed
- Auto-reconnect to saved connection on each command (each invocation starts a fresh MCP server)

## [1.0.4] - 2026-03-26

### Fixed
- Commands now auto-resolve last-used connection from store (no --connection flag needed)

## [1.0.3] - 2026-03-26

### Added
- Support Microsoft Store version of Power BI Desktop for port auto-discovery

### Fixed
- UTF-16 LE encoding when reading Power BI port file
- Updated all 5 skills, error messages, and docs to reflect new install flow

## [1.0.2] - 2026-03-26

### Fixed
- Separate README for GitHub (Mermaid diagrams) and PyPI (text art)

## [1.0.1] - 2026-03-26

### Fixed
- README SVG header and diagrams now render correctly on PyPI

## [1.0.0] - 2026-03-26

### Added
- Auto-discovery of running Power BI Desktop instances (`pbi connect` without `-d`)
- Auto-setup on first connect: downloads MCP binary and installs Claude Code skills automatically
- 5 Claude Code skills: Modeling, DAX, Deployment, Security, Documentation
- Skill installer (`pbi skills install/list/uninstall`)
- Interactive REPL mode (`pbi repl`) with persistent MCP connection, tab completion, command history
- Error hierarchy (`PbiCliError`, `McpToolError`, `BinaryNotFoundError`, `ConnectionRequiredError`)
- 22 command groups covering all Power BI MCP tool operations
- Binary manager: download Power BI MCP binary from VS Code Marketplace
- Connection management with named connections and persistence
- DAX query execution, validation, and cache clearing
- Full CRUD for measures, tables, columns, relationships
- Model metadata, statistics, and refresh operations
- Database import/export (TMDL and TMSL formats)
- Security role management (row-level security)
- Calculation groups, partitions, perspectives, hierarchies
- Named expressions, calendar tables, diagnostic traces
- Transaction management (begin/commit/rollback)
- Advanced operations: cultures, translations, functions, query groups
- Dual output mode: `--json` for agents, Rich tables for humans
- Named connection support with `--connection` / `-c` flag
- Binary resolution chain: env var, managed binary, VS Code extension fallback
- Cross-platform support: Windows, macOS, Linux (x64 and ARM64)
- CI/CD with GitHub Actions (lint, typecheck, test matrix)
- PyPI publishing via trusted OIDC publisher
