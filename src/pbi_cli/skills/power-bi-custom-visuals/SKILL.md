---
name: Power BI Custom Visuals
description: >
  Vibe-code Power BI custom visuals end-to-end: scaffold a TypeScript project,
  iterate on src/visual.ts and capabilities.json, validate with the Power BI
  Visuals SDK toolchain, package to .pbiviz, and import into a PBIR report.
  Invoke this skill whenever the user mentions "custom visual", "pbiviz",
  "powerbi-visuals-tools", "IVisual", "build a chart Power BI doesn't have",
  "developer visual", or wants a custom-built visual that the built-in
  Power BI library can't render. NOT for: changing colors / themes
  (use Power BI Themes), adding built-in visuals like bar/line/card/table
  (use Power BI Visuals), or modifying the data model.
tools: pbi-cli, Bash
---

# Power BI Custom Visuals Skill

Build new Power BI custom visuals from natural language using the
`powerbi-visuals-tools` SDK. Iteration is agent-driven on TypeScript
compile errors; visual correctness is checked once at the end with the
user.

This skill produces a `.pbiviz` package and embeds it into a PBIR report
via `pbi visual import-custom`. The TypeScript project lives **next to**
the `.pbip` folder, never inside it.

## Prerequisites

The skill needs **Node.js** on PATH and the `powerbi-visuals-tools` npm
package. Both are installed on first run with the user's consent; never
silently.

Pinned versions (override via env vars if needed):

- `powerbi-visuals-tools@^5.6.0` (env: `PBIVIZ_VERSION`)
- `powerbi-visuals-api@^5.11.0` (pinned in scaffolded `package.json`)

The skill's edit patterns and AGENTS.md crib were written against these
versions. Bump deliberately.

### First-run prerequisite check

```bash
# 1. Probe Node
node --version || true
```

If `node` is missing, **ask the user**:

> Node.js isn't installed. Custom visual development needs it. Install
> now? (yes/no)
>
> - Windows: `winget install OpenJS.NodeJS.LTS`
> - macOS: `brew install node`
> - Linux: use your package manager or nvm

If user says yes, run the install command appropriate for their OS and
re-probe. If user says no, stop the skill with a clear message.

`pbiviz` itself runs through `npx --yes powerbi-visuals-tools@^5.6.0`,
so there's no global install of the CLI itself. The first `npx`
invocation will fetch and cache it locally.

## Discovery: existing project vs fresh scaffold

The skill's first action is always **discover**, not scaffold.

1. Locate the user's PBIR project (the `.pbip` folder or its `.Report`
   sibling).
2. Look for sibling directories matching `*-visual/` containing a
   `pbiviz.json`.
3. Branch:
   - **None found** → fresh scaffold flow (see "Plan-then-code" below).
   - **One found** → load it; jump to edit-validate-package-import loop.
   - **Multiple found** → ask the user which one; do not guess.

This means re-invoking the skill on day 2 picks up where day 1 left off.

## Plan-then-code (fresh scaffolds only)

For fresh scaffolds, before touching any code:

1. Read the user's natural-language spec.
2. Output a **5-line plan** stating:
   - Data roles needed (and which is `Grouping` vs `Measure`).
   - Primary render approach (DOM, SVG, D3, canvas, charting lib).
   - Formatting properties to expose in the right pane.
   - npm dependencies beyond the scaffold defaults (justify each one;
     see "npm dependency policy" below).
3. **Wait for explicit user OK** before generating code.

The plan exists to foreclose the most expensive failure mode: getting
the data role declarations wrong in `capabilities.json` and discovering
it 15 turns later. Skipping the plan is **not** an optimization.

For sustained-authoring edits to an **existing** project, skip the
plan step and iterate directly.

## Scaffold

Working directory: parent of the user's PBIR project (sibling, never
inside `.Report` or `.pbip`).

**Naming constraint:** `pbiviz new` rejects names containing anything
other than letters and digits. No hyphens, no underscores, no dots.
If the user's spec name has those (e.g. "my-gauge-visual"), strip them
before scaffolding (e.g. `mygaugevisual`). The friendly displayName in
`pbiviz.json` can still carry spaces and punctuation.

```bash
# Inside <project-parent>/
npx --yes powerbi-visuals-tools@^5.6.0 new <visualname>
cd <visualname>
```

### Auto-strip the circle-card demo

`pbiviz new` produces a working "circle card" demo. Strip it before
handing off to iteration:

1. Open `src/visual.ts`. The constructor and `update()` method contain
   demo-specific code (creates an `<svg>` with a `<circle>` and `<text>`
   that displays a number).
2. Replace the `update()` body with a **single comment** like
   `// TODO: build per spec` and remove the SVG/circle helpers.
3. Open `capabilities.json`. Replace the demo's `dataRoles` (typically
   `category` and `measure` for the circle demo) with the data roles
   you planned. Empty the `objects` block; add formatting properties
   per plan.
4. Open `style/visual.less`. Empty it.
5. Bump `apiVersion` in `pbiviz.json` and `powerbi-visuals-api` in
   `package.json` to the pinned version above (only if the scaffold
   doesn't already match).

### Drop in AGENTS.md

Write `AGENTS.md` at the project root using the template at
`./AGENTS-template.md` (bundled alongside this `SKILL.md`). It tells
future-Claude what's editable, what's locked, and gives 30 lines of
SDK pattern crib. **Always drop this file.** It's the biggest single
lever on first-iteration success.

## Inner loop: agent-driven validation

For each user-requested change:

1. Edit the relevant files (see AGENTS.md for editable vs locked).
2. Run **fast** type check:

   ```bash
   npx tsc --noEmit -p tsconfig.json
   ```

3. If errors:
   - Read every error verbatim.
   - Fix them.
   - Re-run `tsc --noEmit`.
   - Repeat **with progress discipline** (see "Failure cap" below).
4. If clean: stop. Don't package every loop. Package only when the user
   asks "show me" or you're at a natural completion point.

Do **not** run `pbiviz start` in v1. The dev server's only purpose is
sub-second hot-reload while a human watches Desktop, which is not how
this loop works.

### Failure cap (self-policed)

To prevent infinite loops on cryptic SDK errors:

- **5-turn no-progress cap.** "Progress" = error count strictly decreased
  OR the qualitative root cause changed. After 5 turns with no progress,
  **stop**.
- **Oscillation detection.** If the same error appears, gets fixed, and
  reappears within 3 turns, **stop**.
- **On stop**: dump the current `tsc` output **verbatim** to the user
  and offer two concrete hypotheses for the root cause. Ask the user to
  guide. Do not silently keep trying.

## Package and import

When the inner loop is clean and you (or the user) are ready to see it:

```bash
# Bump patch version so Power BI Desktop's GUID+version cache invalidates
pbi-cli internal pbiviz-bump  # see note below

# Package
npx --yes powerbi-visuals-tools@^5.6.0 package
# .pbiviz lands in dist/<visualname>.<version>.pbiviz

# Import into the user's report
pbi visual import-custom dist/<visualname>.<version>.pbiviz --replace
```

**Version auto-bump.** Use the helper exposed via the skill (or call
`pbiviz_bump_patch()` from `pbi_cli.core.custom_visual_backend`
programmatically). It increments the patch number in `pbiviz.json`. If
the user has set a non-`<int>.<int>.<int>` version manually, the bump
is skipped and the manual value is respected.

**Why the bump matters.** Power BI Desktop caches custom visuals by
GUID + version. Repackaging without bumping risks Desktop serving stale
code on next open. The bump is cheap insurance.

If `pbiviz package` itself fails (capabilities schema invalid,
unsupported API features, etc.), feed the error to Claude the same way
as `tsc` errors. Subject to the same failure cap.

## Eyeball handoff

After a successful import, hand off to the user **once**:

> Imported. Open the report in Power BI Desktop, place the visual on a
> page, bind data, and tell me what looks wrong. I'll iterate from
> there.

If the user reports issues, repeat the inner loop (skip Plan since the
project exists). If the user reports it looks right, you're done.

## npm dependency policy

Custom visuals routinely need libraries (D3, Lodash, charting libs).
Installing arbitrary packages from npm is a real supply-chain concern
under the user's identity, so this skill operates under an **allowlist**.

### Allowlist (install without asking)

Any package in this list, at or above the version floor, may be
installed via `npm install <pkg>` (or `--save-dev`) without prior
user confirmation:

| Package                              | Floor       |
|--------------------------------------|-------------|
| `d3`                                 | `^7.0.0`    |
| `d3-array`                           | `^3.0.0`    |
| `d3-axis`                            | `^3.0.0`    |
| `d3-color`                           | `^3.0.0`    |
| `d3-format`                          | `^3.0.0`    |
| `d3-interpolate`                     | `^3.0.0`    |
| `d3-scale`                           | `^4.0.0`    |
| `d3-selection`                       | `^3.0.0`    |
| `d3-shape`                           | `^3.0.0`    |
| `d3-time-format`                     | `^4.0.0`    |
| `lodash`                             | `^4.17.0`   |
| `date-fns`                           | `^3.0.0`    |
| `powerbi-visuals-utils-formattingmodel` | `^6.0.0` |
| `powerbi-visuals-utils-tooltiputils` | `^6.0.0`    |
| `powerbi-visuals-utils-chartutils`   | `^6.0.0`    |
| `powerbi-visuals-utils-dataviewutils`| `^6.0.0`    |
| `@types/d3`                          | `^7.0.0`    |
| `@types/lodash`                      | `^4.14.0`   |

Type-only packages follow the same allowlist; there is no separate
`devDependencies` rule.

### Off-allowlist installs

Any package **not** on the allowlist (including any version below a
floor) requires **explicit user confirmation** before running
`npm install`. State all four:

1. **Package name** and exact version range.
2. **Why** it's needed for the user's spec (specific feature, not
   "it might be useful").
3. **Bundle size impact estimate** (k or kk gzipped; check
   bundlephobia.com if uncertain).
4. **Alternative** considered (an allowlisted package or hand-rolled
   code) and why it's worse.

Then wait for explicit "yes" / "go ahead". Don't proceed on silence.

This blocks the worst failure mode: hallucinating a typo'd package
name (e.g. `d3-scaling`) and installing typosquat malware. Typos won't
match the allowlist; the confirm step exposes them.

## Concrete CLI surface used by this skill

Provided by pbi-cli:

- `pbi visual import-custom <pbiviz-file> [--replace] [--no-sync]`
- `pbi visual list-custom`
- `pbi visual remove-custom <guid-or-name> [--no-sync]`

Provided by `npx --yes powerbi-visuals-tools@^5.6.0`:

- `new <name>` — scaffold project
- `package` — produce `.pbiviz` zip
- `--create-cert` — generate dev cert (only needed on first
  `package` invocation per machine; pbiviz prompts automatically)

That's the entire toolchain. No other commands needed in v1.

## What's deliberately out of scope (v1)

- `pbiviz start` live preview server.
- AppSource (public) custom visual registration via GUID-only
  (separate `register-public` command, deferred).
- Publishing to AppSource / Partner Center.
- Multi-visual workspaces, monorepo patterns.
- Custom visual themes / sharing across reports.

If the user asks for any of the above, surface that it's outside v1
scope and offer to file a follow-up.
