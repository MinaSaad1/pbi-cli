---
name: Power BI Visuals
description: >
  Add, configure, bind data to, and bulk-manage visuals on Power BI PBIR report
  pages using pbi-cli. Invoke this skill whenever the user mentions "add a chart",
  "bar chart", "line chart", "card", "KPI", "gauge", "scatter", "table visual",
  "matrix", "slicer", "combo chart", "bind data", "visual type", "visual layout",
  "resize visuals", "bulk update visuals", "bulk delete", "visual calculations",
  or wants to place, move, bind, or remove any visual on a report page. Also invoke
  when the user asks what visual types are supported or how to connect a visual to
  their data model.
tools: pbi-cli
---

# Power BI Visuals Skill

Create and manage visuals on PBIR report pages. No Power BI Desktop connection
is needed -- these commands operate directly on JSON files.

## Adding Visuals

```bash
# Add by alias (pbi-cli resolves to the PBIR type)
pbi visual add --page page_abc123 --type bar
pbi visual add --page page_abc123 --type card --name "Revenue Card"

# Custom position and size (pixels)
pbi visual add --page page_abc123 --type scatter \
    --x 50 --y 400 --width 600 --height 350

# Named visual for easy reference
pbi visual add --page page_abc123 --type combo --name sales_combo
```

Each visual is created as a folder with a `visual.json` file inside the page's
`visuals/` directory. The template includes the correct schema URL and queryState
roles for the chosen type.

## Prerequisite: Measures Must Exist in the Semantic Model

`visual bind` writes field references into the visual JSON. It does **not**
create measures — it only records that a measure should exist. If the measure
is missing from the TMDL, every visual bound to it will show an error in Desktop.

**Before binding any visual to a measure, verify the measure exists:**

```bash
# Option A: create it via pbi-cli (requires pbi connect)
pbi connect
pbi measure create "Total Revenue" -e "SUM(Fact_Sales[Total_Revenue])" -t Fact_Sales

# Option B: check existing measures in the TMDL file directly
# Look for `measure '...' =` lines in SemanticModel/definition/tables/*.tmdl
```

**After adding measures directly to a TMDL file** (without `pbi connect`):
close and reopen the `.pbip` file in Power BI Desktop. Desktop only reads TMDL
on file open — it does not hot-reload TMDL changes made on disk.

**Checklist before opening Desktop:**
- Every `--field`, `--value`, `--indicator` reference points to a real measure or column in the TMDL
- Table names match exactly (case-sensitive in PBIR): `"Fact_Sales"` ≠ `"fact_sales"`
- Measure names match exactly: `"Total Revenue"` ≠ `"Total_Revenue"`

## Binding Data

Visuals start empty. Use `visual bind` with `Table[Column]` notation to connect
them to your semantic model. The bind options vary by visual type -- see the
type table below.

```bash
# Bar chart: category axis + value
pbi visual bind mybar --page p1 \
    --category "Geography[Region]" --value "Sales[Revenue]"

# Card: single field
pbi visual bind mycard --page p1 --field "Sales[Total Revenue]"

# Matrix: rows + values + optional column
pbi visual bind mymatrix --page p1 \
    --row "Product[Category]" --value "Sales[Amount]" --value "Sales[Quantity]"

# Scatter: X, Y, detail, optional size and legend
pbi visual bind myscatter --page p1 \
    --x "Sales[Quantity]" --y "Sales[Revenue]" --detail "Product[Name]"

# Combo chart: category + column series + line series
pbi visual bind mycombo --page p1 \
    --category "Calendar[Month]" --column "Sales[Revenue]" --line "Sales[Margin]"

# KPI: indicator + goal + trend axis
pbi visual bind mykpi --page p1 \
    --indicator "Sales[Revenue]" --goal "Sales[Target]" --trend "Calendar[Date]"

# Gauge: value + max/target
pbi visual bind mygauge --page p1 \
    --value "Sales[Revenue]" --max "Sales[Target]"
```

Binding uses ROLE_ALIASES to translate friendly names like `--value` into the PBIR
role name (e.g. `Y`, `Values`, `Data`). Each field is written as a Column or a Measure
reference based on what it actually is in the semantic model, checked in this order:

1. The report's own semantic model on disk (`definition.pbir` -> `byPath` ->
   `tables/*.tmdl` or `model.bim`)
2. The live model from `pbi connect`, only for fields not found on disk
3. A role default: slicers and table `--column` bind Columns; value, indicator and
   goal roles bind Measures; category, row and legend bind Columns

The JSON output reports `kind` and `resolved_by` per field, plus a `warnings` entry when
a field is missing from the model (usually a typo). Force the wrapper for every field
in one call with `--kind column` or `--kind measure`.

```bash
# Slicer on a dimension column (written as Column)
pbi visual bind myslicer --page p1 --field "Geography[Region]"

# Table mixing columns and measures (each resolved from the model)
pbi visual bind mytable --page p1     --column "Geography[Region]" --column "Product[Name]" --value "Sales[Revenue]"
```

## Inspecting and Updating

```bash
# List all visuals on a page
pbi visual list --page page_abc123

# Get full details of one visual
pbi visual get visual_def456 --page page_abc123

# Move, resize, or toggle visibility
pbi visual update vis1 --page p1 --width 600 --height 400
pbi visual update vis1 --page p1 --x 100 --y 200
pbi visual update vis1 --page p1 --hidden
pbi visual update vis1 --page p1 --visible

# Delete a visual
pbi visual delete visual_def456 --page page_abc123
```

## Container Properties

Set border, background, or title on the visual container itself:

```bash
pbi visual set-container vis1 --page p1 --background "#F0F0F0"
pbi visual set-container vis1 --page p1 --border-color "#CCCCCC" --border-width 2
pbi visual set-container vis1 --page p1 --title "Sales by Region"
```

## Visual Calculations

Add DAX calculations that run inside the visual scope:

```bash
pbi visual calc-add vis1 --page p1 --role Values \
    --name "RunningTotal" --expression "RUNNINGSUM([Revenue])"

pbi visual calc-list vis1 --page p1
pbi visual calc-delete vis1 --page p1 --name "RunningTotal"
```

## Bulk Operations

Operate on many visuals at once by filtering with `--type` or `--name-pattern`:

```bash
# Find visuals matching criteria
pbi visual where --page overview --type barChart
pbi visual where --page overview --type kpi --y-min 300

# Bind the same field to ALL bar charts on a page
pbi visual bulk-bind --page overview --type barChart \
    --category "Date[Month]" --value "Sales[Revenue]"

# Resize all KPI cards
pbi visual bulk-update --page overview --type kpi --width 250 --height 120

# Hide all visuals matching a pattern
pbi visual bulk-update --page overview --name-pattern "Temp_*" --hidden

# Delete all placeholders
pbi visual bulk-delete --page overview --name-pattern "Placeholder_*"
```

Filter options for `where`, `bulk-bind`, `bulk-update`, `bulk-delete`:
- `--type` -- PBIR visual type or alias (e.g. `barChart`, `bar`)
- `--name-pattern` -- fnmatch glob on visual name (e.g. `Chart_*`)
- `--x-min`, `--x-max`, `--y-min`, `--y-max` -- position bounds (pixels)

All bulk commands require at least `--type` or `--name-pattern` to prevent
accidental mass operations.

## Supported Visual Types (32)

### Charts

| Alias              | PBIR Type                    | Bind Options                                  |
|--------------------|------------------------------|-----------------------------------------------|
| bar                | barChart                     | --category, --value, --legend                 |
| line               | lineChart                    | --category, --value, --legend                 |
| column             | columnChart                  | --category, --value, --legend                 |
| area               | areaChart                    | --category, --value, --legend                 |
| ribbon             | ribbonChart                  | --category, --value, --legend                 |
| waterfall          | waterfallChart               | --category, --value, --breakdown              |
| stacked_bar        | stackedBarChart              | --category, --value, --legend                 |
| clustered_bar      | clusteredBarChart            | --category, --value, --legend                 |
| clustered_column   | clusteredColumnChart         | --category, --value, --legend                 |
| scatter            | scatterChart                 | --x, --y, --detail, --size, --legend          |
| funnel             | funnelChart                  | --category, --value                           |
| combo              | lineStackedColumnComboChart  | --category, --column, --line, --legend        |
| donut / pie        | donutChart                   | --category, --value, --legend                 |
| treemap            | treemap                      | --category, --value                           |

### Cards and KPIs

| Alias              | PBIR Type                    | Bind Options                                  |
|--------------------|------------------------------|-----------------------------------------------|
| card               | card                         | --field                                       |
| card_visual        | cardVisual                   | --field (modern card)                         |
| card_new           | cardNew                      | --field                                       |
| multi_row_card     | multiRowCard                 | --field                                       |
| kpi                | kpi                          | --indicator, --goal, --trend                  |
| gauge              | gauge                        | --value, --max / --target                     |

### Tables

| Alias              | PBIR Type                    | Bind Options                                  |
|--------------------|------------------------------|-----------------------------------------------|
| table              | tableEx                      | --value                                       |
| matrix             | pivotTable                   | --row, --value, --column                      |

### Slicers

| Alias              | PBIR Type                    | Bind Options                                  |
|--------------------|------------------------------|-----------------------------------------------|
| slicer             | slicer                       | --field                                       |
| text_slicer        | textSlicer                   | --field                                       |
| list_slicer        | listSlicer                   | --field                                       |
| advanced_slicer    | advancedSlicerVisual         | --field (tile/image slicer)                   |

### Maps

| Alias              | PBIR Type                    | Bind Options                                  |
|--------------------|------------------------------|-----------------------------------------------|
| azure_map / map    | azureMap                     | --category, --size                            |

### Decorative and Navigation

| Alias              | PBIR Type                    | Bind Options                                  |
|--------------------|------------------------------|-----------------------------------------------|
| action_button      | actionButton                 | (no data binding)                             |
| image              | image                        | (no data binding)                             |
| shape              | shape                        | (no data binding)                             |
| textbox            | textbox                      | (no data binding)                             |
| page_navigator     | pageNavigator                | (no data binding)                             |

## Suppressing Auto-Sync (--no-sync)

By default, every write command automatically syncs Power BI Desktop. When
adding or binding many visuals in sequence, Desktop reloads after each one.

Use `--no-sync` on the `visual` command group to batch all changes, then call
`pbi report reload` once at the end:

```bash
# Suppress sync while building visuals
pbi visual --no-sync add --page overview --type card --name rev_card
pbi visual --no-sync bind rev_card --page overview --field "Sales[Total Revenue]"
pbi visual --no-sync add --page overview --type bar --name sales_bar
pbi visual --no-sync bind sales_bar --page overview --category "Product[Category]" --value "Sales[Revenue]"

# Single reload when all visuals are done
pbi report reload
```

## JSON Output

All commands support `--json` for agent consumption:

```bash
pbi --json visual list --page overview
pbi --json visual get vis1 --page overview
pbi --json visual where --page overview --type barChart
```
