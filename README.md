<p align="center">
  <img src="https://raw.githubusercontent.com/MinaSaad1/pbi-cli/master/assets/banner.svg" alt="pbi-cli" width="850"/>
</p>

<p align="center">
  <b>Give Claude Code the Power BI skills it needs.</b><br/>
  Install once, then just ask Claude to work with your semantic models <i>and</i> reports.
</p>

<p align="center">
  <a href="https://pypi.org/project/pbi-cli-tool/"><img src="https://img.shields.io/pypi/pyversions/pbi-cli-tool?style=flat-square&color=3776ab&label=Python" alt="Python"></a>
  <a href="https://github.com/MinaSaad1/pbi-cli/actions"><img src="https://img.shields.io/github/actions/workflow/status/MinaSaad1/pbi-cli/ci.yml?branch=master&style=flat-square&label=CI" alt="CI"></a>
  <a href="https://github.com/MinaSaad1/pbi-cli/blob/master/LICENSE"><img src="https://img.shields.io/github/license/MinaSaad1/pbi-cli?style=flat-square&color=06d6a0" alt="License"></a>
  <a href="https://www.linkedin.com/in/minasaad1/"><img src="https://img.shields.io/badge/LinkedIn-Mina%20Saad-0A66C2?style=flat-square&logo=linkedin&logoColor=white" alt="LinkedIn"></a>
  <a href="https://mina-saad.com"><img src="https://img.shields.io/badge/Website-mina--saad.com-58a6ff?style=flat-square&logo=googlechrome&logoColor=white" alt="Website"></a>
</p>

<p align="center">
  <a href="#why-pbi-cli">Why pbi-cli</a> &bull;
  <a href="#get-started">Get Started</a> &bull;
  <a href="#semantic-model-layer">Modeling</a> &bull;
  <a href="#report-layer">Reporting</a> &bull;
  <a href="#skills">Skills</a> &bull;
  <a href="#all-commands">All Commands</a> &bull;
  <a href="#contributing">Contributing</a>
</p>

---

## Why pbi-cli?

<p align="center">
  <img src="https://raw.githubusercontent.com/MinaSaad1/pbi-cli/master/assets/before-after.svg" alt="Why pbi-cli" width="850"/>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/MinaSaad1/pbi-cli/master/assets/layers.svg" alt="Dual-Layer Architecture" width="850"/>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/MinaSaad1/pbi-cli/master/assets/stats.svg" alt="pbi-cli at a Glance" width="850"/>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/MinaSaad1/pbi-cli/master/assets/downloads-chart.svg" alt="pbi-cli cumulative downloads from PyPI" width="850"/>
</p>

<p align="center">
  <sub>Cumulative downloads, refreshed daily from <a href="https://pypistats.org/packages/pbi-cli-tool">pypistats.org</a> via GitHub Actions.</sub>
</p>

---

## Get Started

```bash
pipx install pbi-cli-tool    # 1. Install (handles PATH automatically)
pbi-cli skills install       # 2. Register Claude Code skills (one-time setup)
pbi connect                  # 3. Connect to Power BI Desktop
```

Open Power BI Desktop with a `.pbix` file, run the three commands above, and start asking Claude.

> **Requires:** Windows with Python 3.10+ and Power BI Desktop running.

<details>
<summary><b>Alternative: give Claude the repo URL</b></summary>

```
Install and set up pbi-cli from https://github.com/MinaSaad1/pbi-cli.git
```

Claude will clone, install, connect, and set up skills automatically.

</details>

<details>
<summary><b>Using pip instead of pipx?</b></summary>

```bash
pip install pbi-cli-tool
```

On Windows, `pip install` often places the `pbi` command in a directory that isn't on your PATH.

**Fix: Add the Scripts directory to PATH**

```bash
python -c "import site; print(site.getusersitepackages().replace('site-packages','Scripts'))"
```

Add the printed path to your system PATH, then restart your terminal. We recommend `pipx` to avoid this entirely.

</details>

---

## Semantic Model Layer

Ask Claude to work with your Power BI semantic model. Requires `pbi connect`.

<p align="center">
  <img src="https://raw.githubusercontent.com/MinaSaad1/pbi-cli/master/assets/chat-demo.svg" alt="Just Ask Claude" width="850"/>
</p>

### Create measures in bulk

<p align="center">
  <img src="https://raw.githubusercontent.com/MinaSaad1/pbi-cli/master/assets/bulk-operations.svg" alt="Bulk operations" width="850"/>
</p>

### Debug broken DAX

<p align="center">
  <img src="https://raw.githubusercontent.com/MinaSaad1/pbi-cli/master/assets/dax-debugging.svg" alt="DAX debugging" width="850"/>
</p>

### Snapshot and restore your model

<p align="center">
  <img src="https://raw.githubusercontent.com/MinaSaad1/pbi-cli/master/assets/backup-restore.svg" alt="Backup and restore" width="850"/>
</p>

### Audit your model for issues

<p align="center">
  <img src="https://raw.githubusercontent.com/MinaSaad1/pbi-cli/master/assets/model-health-check.svg" alt="Model health check" width="850"/>
</p>

### Test row-level security

<p align="center">
  <img src="https://raw.githubusercontent.com/MinaSaad1/pbi-cli/master/assets/rls-testing.svg" alt="RLS testing" width="850"/>
</p>

---

## Report Layer

Ask Claude to build and manage your Power BI reports. No connection needed -- works directly on PBIR files.

<p align="center">
  <img src="https://raw.githubusercontent.com/MinaSaad1/pbi-cli/master/assets/chat-demo-report.svg" alt="Ask Claude to build reports" width="850"/>
</p>

### Build a report in 6 steps

<p align="center">
  <img src="https://raw.githubusercontent.com/MinaSaad1/pbi-cli/master/assets/report-workflow.svg" alt="Report workflow" width="850"/>
</p>

### Visuals, pages, themes, filters

<p align="center">
  <img src="https://raw.githubusercontent.com/MinaSaad1/pbi-cli/master/assets/report-layer.svg" alt="Report layer capabilities" width="850"/>
</p>

### 32 visual types

<p align="center">
  <img src="https://raw.githubusercontent.com/MinaSaad1/pbi-cli/master/assets/visual-types.svg" alt="32 Visual Types" width="850"/>
</p>

---

## Architecture

<p align="center">
  <img src="https://raw.githubusercontent.com/MinaSaad1/pbi-cli/master/assets/architecture-flow.svg" alt="Architecture" width="850"/>
</p>

**Two layers, one CLI:**

- **Semantic Model layer** -- Direct in-process .NET interop from Python to Power BI Desktop via TOM/ADOMD. No MCP server, no external binaries, sub-second execution.
- **Report layer** -- Reads and writes PBIR (Enhanced Report Format) JSON files directly. No connection needed. Works with `.pbip` projects.

### Desktop Auto-Sync

<p align="center">
  <img src="https://raw.githubusercontent.com/MinaSaad1/pbi-cli/master/assets/auto-sync.svg" alt="Desktop Auto-Sync" width="850"/>
</p>

<details>
<summary><b>Configuration details</b></summary>

All config lives in `~/.pbi-cli/`:

```
~/.pbi-cli/
  config.json          # Default connection preference
  connections.json     # Named connections
  repl_history         # REPL command history
```

Bundled DLLs ship inside the Python package (`pbi_cli/dlls/`).

</details>

---

## Skills

After running `pbi-cli skills install`, Claude Code discovers **13 Power BI skills**. Each skill teaches Claude a different area. You don't need to memorize commands.

<p align="center">
  <img src="https://raw.githubusercontent.com/MinaSaad1/pbi-cli/master/assets/skills-hub.svg" alt="12 Skills" width="850"/>
</p>

### Semantic Model Skills (require `pbi connect`)

| Skill | What you say | What Claude does |
|-------|-------------|-----------------|
| **DAX** | *"What are the top 10 products by revenue?"* | Writes and executes DAX queries, validates syntax |
| **Modeling** | *"Create a star schema with Sales and Calendar"* | Creates tables, relationships, measures, hierarchies |
| **Deployment** | *"Save a snapshot before I make changes"* | Exports/imports TMDL, manages transactions, diffs snapshots |
| **Security** | *"Set up RLS for regional managers"* | Creates roles, filters, perspectives |
| **Docs** | *"Document everything in this model"* | Generates data dictionaries, measure inventories |
| **Partitions** | *"Show me the M query for the Sales table"* | Manages partitions, expressions, calendar config |
| **Diagnostics** | *"Why is this query so slow?"* | Traces queries, checks model health, benchmarks |

### Report Layer Skills (no connection needed)

| Skill | What you say | What Claude does |
|-------|-------------|-----------------|
| **Report** | *"Create a new report project for Sales"* | Scaffolds PBIR reports, validates structure, previews layout |
| **Visuals** | *"Add a bar chart showing revenue by region"* | Adds, binds, updates, bulk-manages 32 visual types |
| **Pages** | *"Add an Executive Overview page"* | Manages pages, bookmarks, visibility, drillthrough |
| **Themes** | *"Apply our corporate brand colours"* | Applies themes, conditional formatting, colour scales |
| **Filters** | *"Show only the top 10 products"* | Adds page/visual filters (TopN, date, categorical) |
| **Custom Visuals** | *"Build a radial gauge Power BI doesn't have"* | Scaffolds a TypeScript visual project, iterates on `tsc --noEmit`, packages `.pbiviz`, imports into the report |

---

## Custom Visual Authoring

The **Custom Visuals** skill turns vibe-coding into the Power BI Visuals SDK loop.
Claude scaffolds a sibling TypeScript project with `npx pbiviz new`, iterates against
the Power BI Visuals API with `tsc --noEmit` between every change, packages a
`.pbiviz`, and embeds it into your report:

```bash
# After installing the skill, just describe what you want in Claude Code:
#   "Build me a radial gauge that highlights values above target"
#
# Under the hood, the skill drives:
npx --yes powerbi-visuals-tools@^5.6.0 new mygaugevisual
# (Claude edits src/visual.ts + capabilities.json, runs tsc --noEmit until clean)
npx --yes powerbi-visuals-tools@^5.6.0 package
pbi visual import-custom dist/mygaugevisual.1.0.5.pbiviz --replace
```

The skill auto-installs Node and `pbiviz` on first run (with your consent), pins
the SDK to a known-good version, keeps the TypeScript project as a sibling to your
`.pbip` (no PBIR contamination), and operates under a curated npm allowlist for
common deps (D3, Lodash, date-fns) -- anything off-list requires explicit approval.

Three new pbi-cli commands support the loop:

| Command | What it does |
|---------|-------------|
| `pbi visual import-custom <pbiviz>` | Embed a locally-built `.pbiviz` into the report's `RegisteredResources/` and register it in `report.json`. `--replace` overwrites by GUID. |
| `pbi visual list-custom` | List embedded and public (AppSource) custom visuals, distinguished by `kind`. |
| `pbi visual remove-custom <guid-or-name>` | Deregister and physically delete the `.pbiviz` resource. |

---

## All Commands

27 command groups covering both the semantic model and the report layer.

| Category | Commands |
|----------|----------|
| **Queries** | `dax execute`, `dax validate`, `dax clear-cache` |
| **Model** | `table`, `column`, `measure`, `relationship`, `hierarchy`, `calc-group` |
| **Deploy** | `database export-tmdl`, `database import-tmdl`, `database export-tmsl`, `database diff-tmdl`, `transaction` |
| **Security** | `security-role`, `perspective` |
| **Connect** | `connect`, `disconnect`, `connections list`, `connections last` |
| **Data** | `partition`, `expression`, `calendar`, `advanced culture` |
| **Diagnostics** | `trace start/stop/fetch/export`, `model stats` |
| **Report** | `report create`, `report info`, `report validate`, `report preview`, `report reload` |
| **Pages** | `report add-page`, `report delete-page`, `report get-page`, `report set-background`, `report set-visibility` |
| **Visuals** | `visual add/get/list/update/delete`, `visual bind`, `visual bulk-bind/bulk-update/bulk-delete`, `visual where` |
| **Filters** | `filters list`, `filters add-categorical/add-topn/add-relative-date`, `filters remove/clear` |
| **Formatting** | `format get/clear`, `format background-gradient/background-conditional/background-measure` |
| **Bookmarks** | `bookmarks list/get/add/delete/set-visibility` |
| **Tools** | `setup`, `repl`, `skills install/list/uninstall` |

Use `--json` for machine-readable output (for scripts and AI agents):

```bash
pbi --json measure list
pbi --json dax execute "EVALUATE Sales"
pbi --json visual list --page overview
```

Run `pbi <command> --help` for full options.

---

## REPL Mode

For interactive work, the REPL keeps a persistent connection:

```
$ pbi repl

pbi> connect --data-source localhost:54321
Connected: localhost-54321

pbi(localhost-54321)> measure list
pbi(localhost-54321)> dax execute "EVALUATE TOPN(5, Sales)"
pbi(localhost-54321)> exit
```

Tab completion, command history, and a dynamic prompt showing your active connection.

---

## Development

```bash
git clone https://github.com/MinaSaad1/pbi-cli.git
cd pbi-cli
pip install -e ".[dev]"
```

```bash
ruff check src/ tests/         # Lint
mypy src/                      # Type check
pytest -m "not e2e"            # Run tests (488 tests)
```

---

## Bundled third-party software

`pbi-cli-tool` ships with Microsoft Analysis Services client library
assemblies (`Microsoft.AnalysisServices.*.dll`) under `src/pbi_cli/dlls/`.
These binaries are **not** covered by pbi-cli's MIT license. They are
redistributed unmodified under the Microsoft Software License Terms for
Microsoft Analysis Management Objects (AMO) and Microsoft Analysis
Services - ADOMD.NET. Full terms are in
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) and the companion
[NOTICE](NOTICE) file. By installing `pbi-cli-tool` you agree to those
terms in addition to the MIT License that applies to the rest of the
package.

---

## Contributing

Contributions are welcome! Please open an issue first to discuss what you'd like to change.

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Open a pull request

---

<p align="center">
  <a href="https://github.com/MinaSaad1/pbi-cli"><img src="https://img.shields.io/badge/GitHub-pbi--cli-1a1a2e?style=flat-square&logo=github" alt="GitHub"></a>
  <a href="https://pypi.org/project/pbi-cli-tool/"><img src="https://img.shields.io/badge/PyPI-pbi--cli--tool-f2c811?style=flat-square&logo=pypi&logoColor=white" alt="PyPI"></a>
</p>

<p align="center">
  <sub>MIT License — bundled Microsoft DLLs are licensed separately, see <a href="THIRD_PARTY_LICENSES.md">THIRD_PARTY_LICENSES.md</a></sub>
</p>
