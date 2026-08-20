<img src="https://raw.githubusercontent.com/MinaSaad1/pbi-cli/master/assets/header.svg" alt="pbi-cli" width="800"/>

**Give Claude Code the Power BI skills it needs.**
Install once, then just ask Claude to work with your semantic models *and* reports.

<a href="https://pypi.org/project/pbi-cli-tool/"><img src="https://img.shields.io/pypi/pyversions/pbi-cli-tool?style=flat-square&color=3776ab&label=Python" alt="Python"></a>
<a href="https://github.com/MinaSaad1/pbi-cli/actions"><img src="https://img.shields.io/github/actions/workflow/status/MinaSaad1/pbi-cli/ci.yml?branch=master&style=flat-square&label=CI" alt="CI"></a>
<a href="https://github.com/MinaSaad1/pbi-cli/blob/master/LICENSE"><img src="https://img.shields.io/github/license/MinaSaad1/pbi-cli?style=flat-square&color=06d6a0" alt="License"></a>

[Get Started](#get-started) &bull; [Skills](#skills) &bull; [All Commands](#all-commands) &bull; [REPL Mode](#repl-mode) &bull; [Contributing](#contributing)

---

## What is this?

pbi-cli gives **Claude Code** (and other AI agents) the ability to manage Power BI semantic models **and reports**. It ships with 12 skills that Claude discovers automatically. You ask in plain English, Claude uses the right `pbi` commands.

```
You                        Claude Code              pbi-cli              Power BI
 "Add a YTD measure   --->  Uses Power BI    --->   CLI commands   --->  Desktop
  to the Sales table"       skills (12)
```

**Two layers, one CLI:**
- **Semantic Model** -- Direct .NET interop to Power BI Desktop (measures, tables, DAX, security)
- **Report Layer** -- Reads/writes PBIR JSON files directly (visuals, pages, themes, filters)

---

## Get Started

**Fastest way:** Just give Claude the repo URL and let it handle everything:

```
Install and set up pbi-cli from https://github.com/MinaSaad1/pbi-cli.git
```

**Or install manually (two commands):**

```bash
pipx install pbi-cli-tool    # 1. Install (handles PATH automatically)
pbi-cli skills install       # 2. Register Claude Code skills (one-time setup)
pbi connect                  # 3. Connect to Power BI Desktop
```

Open Power BI Desktop with a `.pbix` file, run the three commands above, and start asking Claude.

> **Requires:** Windows with Python 3.10+ and Power BI Desktop running.

<details>
<summary><b>Using pip instead of pipx?</b></summary>

```bash
pip install pbi-cli-tool
```

On Windows, `pip install` often places the `pbi` command in a directory that isn't on your PATH.

**Fix: Add the Scripts directory to PATH**

Find the directory:
```bash
python -c "import site; print(site.getusersitepackages().replace('site-packages','Scripts'))"
```

Add the printed path to your system PATH, then restart your terminal. We recommend `pipx` to avoid this entirely.

</details>

---

## Skills

After running `pbi-cli skills install`, Claude Code discovers **12 Power BI skills**. Each skill teaches Claude a different area. You don't need to memorize commands.

### Semantic Model (require `pbi connect`)

| Skill | What you say | What Claude does |
|-------|-------------|-----------------|
| **DAX** | *"Top 10 products by revenue?"* | Writes and executes DAX queries |
| **Modeling** | *"Create a star schema"* | Creates tables, relationships, measures |
| **Deployment** | *"Save a snapshot"* | Exports/imports TMDL, diffs snapshots |
| **Security** | *"Set up RLS"* | Creates roles, filters, perspectives |
| **Docs** | *"Document this model"* | Generates data dictionaries |
| **Partitions** | *"Show the M query"* | Manages partitions, expressions |
| **Diagnostics** | *"Why is this slow?"* | Traces queries, benchmarks |

### Report Layer (no connection needed)

| Skill | What you say | What Claude does |
|-------|-------------|-----------------|
| **Report** | *"Create a new report"* | Scaffolds PBIR reports, validates, previews |
| **Visuals** | *"Add a bar chart"* | Adds, binds, bulk-manages 32 visual types |
| **Pages** | *"Add a new page"* | Manages pages, bookmarks, drillthrough |
| **Themes** | *"Apply brand colours"* | Themes, conditional formatting |
| **Filters** | *"Show top 10 only"* | TopN, date, categorical filters |

---

## All Commands

27 command groups covering both the semantic model and the report layer.

| Category | Commands |
|----------|----------|
| **Queries** | `dax execute`, `dax validate`, `dax clear-cache` |
| **Model** | `table`, `column`, `measure`, `relationship`, `hierarchy`, `calc-group` |
| **Deploy** | `database export-tmdl/import-tmdl/export-tmsl/diff-tmdl`, `transaction` |
| **Security** | `security-role`, `perspective` |
| **Connect** | `connect`, `disconnect`, `connections list/last` |
| **Data** | `partition`, `expression`, `calendar`, `advanced culture` |
| **Diagnostics** | `trace start/stop/fetch/export`, `model stats` |
| **Report** | `report create/info/validate/preview/reload`, `report add-page/delete-page/get-page` |
| **Visuals** | `visual add/get/list/update/delete/bind`, `visual bulk-bind/bulk-update/bulk-delete` |
| **Filters** | `filters list/add-categorical/add-topn/add-relative-date/remove/clear` |
| **Formatting** | `format get/clear/background-gradient/background-conditional/background-measure` |
| **Bookmarks** | `bookmarks list/get/add/delete/set-visibility` |
| **Tools** | `setup`, `repl` |
| **Setup** | `pbi-cli skills install/list/uninstall` (on the `pbi-cli` command, not `pbi`) |

Use `--json` for machine-readable output:

```bash
pbi --json measure list
pbi --json visual list --page overview
```

---

## 32 Supported Visual Types

**Charts:** bar, line, column, area, ribbon, waterfall, stacked bar, clustered bar, clustered column, scatter, funnel, combo, donut/pie, treemap

**Cards/KPIs:** card, cardVisual (modern), cardNew, multi-row card, KPI, gauge

**Tables:** table, matrix &bull; **Slicers:** slicer, text, list, advanced &bull; **Maps:** Azure Map

**Decorative:** action button, image, shape, textbox, page navigator

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

Tab completion, command history, and a dynamic prompt.

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
assemblies (`Microsoft.AnalysisServices.*.dll`) inside the PyPI wheel
under `src/pbi_cli/dlls/`. These binaries are **not** covered by
pbi-cli's MIT license. They are redistributed unmodified under the
Microsoft Software License Terms for Microsoft Analysis Management
Objects (AMO) and Microsoft Analysis Services - ADOMD.NET. Full terms
are in [THIRD_PARTY_LICENSES.md](https://github.com/MinaSaad1/pbi-cli/blob/master/THIRD_PARTY_LICENSES.md)
and the companion [NOTICE](https://github.com/MinaSaad1/pbi-cli/blob/master/NOTICE)
file. By installing `pbi-cli-tool` you agree to those terms in addition
to the MIT License that applies to the rest of the package.

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
  <sub>MIT License — bundled Microsoft DLLs are licensed separately, see <a href="https://github.com/MinaSaad1/pbi-cli/blob/master/THIRD_PARTY_LICENSES.md">THIRD_PARTY_LICENSES.md</a></sub>
</p>
