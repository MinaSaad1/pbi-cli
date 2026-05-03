# AGENTS.md — Custom Visual Project Guide

This file is for AI agents iterating on this Power BI custom visual.
The `power-bi-custom-visuals` skill (from pbi-cli) drops it in on
scaffold. Keep it. Update it as the project evolves.

## Editable vs locked files

✅ **Editable freely:**

- `src/visual.ts` — the `IVisual` implementation. Render logic lives here.
- `src/settings.ts` — formatting model definitions (right-pane controls).
- `capabilities.json` — data roles, dataViewMappings, objects (formatting
  property declarations).
- `style/visual.less` — visual-scoped CSS.
- `assets/icon.png` — visual icon (replace, don't rename).

🔒 **Don't touch without surfacing to the user first:**

- `tsconfig.json` — TypeScript compiler config.
- `pbiviz.json` — visual metadata (the skill auto-bumps `version` here;
  don't edit `version` manually unless you mean to override the
  auto-bump pattern).
- `package.json` — dependencies are governed by the skill's allowlist.
  See the npm dependency policy in the skill.
- `webpack.config.js` (if present) — bundler config.
- `.eslintrc*`, `.prettierrc*` — toolchain configs.

If you think you need to change a locked file, **stop and ask the user**
with a one-paragraph explanation of why and what changes you want to
make.

## SDK pattern crib (~30 lines)

### IVisual lifecycle

```ts
import powerbi from "powerbi-visuals-api";
import IVisual = powerbi.extensibility.visual.IVisual;
import VisualConstructorOptions = powerbi.extensibility.visual.VisualConstructorOptions;
import VisualUpdateOptions = powerbi.extensibility.visual.VisualUpdateOptions;

export class Visual implements IVisual {
    private host: powerbi.extensibility.visual.IVisualHost;
    private root: HTMLElement;

    constructor(options: VisualConstructorOptions) {
        this.host = options.host;
        this.root = options.element;
    }

    public update(options: VisualUpdateOptions) {
        const dv = options.dataViews?.[0];
        if (!dv) return;            // no data yet
        // render off dv.categorical or dv.matrix or dv.table
    }
}
```

### Reading categorical data

```ts
const cat = dv.categorical;
if (!cat?.categories || !cat.values) return;
const categoryValues = cat.categories[0].values; // x-axis labels
const measureValues = cat.values[0].values;      // y-axis numbers
```

### Declaring data roles in `capabilities.json`

```json
{
  "dataRoles": [
    { "displayName": "Category", "name": "category", "kind": "Grouping" },
    { "displayName": "Measure",  "name": "measure",  "kind": "Measure"  }
  ],
  "dataViewMappings": [{
    "categorical": {
      "categories": { "for": { "in": "category" } },
      "values":     { "select": [{ "for": { "in": "measure" } }] }
    }
  }]
}
```

`kind` matters: `Grouping` for axis/category fields, `Measure` for
numeric values, `GroupingOrMeasure` only when truly ambiguous.

### Formatting properties (modern formatting model)

In `capabilities.json`:

```json
"objects": {
  "barColor": {
    "properties": {
      "fill": { "type": { "fill": { "solid": { "color": true } } } }
    }
  }
}
```

In `src/visual.ts` use the `formattingModel` API
(`powerbi-visuals-utils-formattingmodel`) rather than the legacy
`enumerateObjectInstances` — the legacy path is deprecated and will
emit warnings on package.

### Selection and tooltips

Use `host.createSelectionIdBuilder()` per data point and
`host.tooltipService` for tooltips. Don't roll your own DOM tooltips
unless you have a strong reason; tooltips need to interact with the
Power BI report context (drill-through, etc.).

## Common gotchas

- **`powerbi-visuals-api` major version mismatch** between the version
  in `package.json` and the type imports → cryptic "type X is not
  assignable to type Y" errors. Fix: align the `package.json` version
  to the API your code targets.
- **`enumerateObjectInstances` removed in v5+** → use the formatting
  model API.
- **Empty dataView on first `update()` call** → guard with
  `if (!options.dataViews?.[0]) return;`. Power BI calls `update()`
  before any data is bound.
- **Numbers vs PrimitiveValue** → `cat.values[0].values` are
  `PrimitiveValue[]` (string|number|boolean|Date|null). Cast or
  narrow before doing math: `Number(v) || 0`.
- **`update()` called on resize** → check `options.type` or just
  re-render every time; visuals should be cheap to re-render.
