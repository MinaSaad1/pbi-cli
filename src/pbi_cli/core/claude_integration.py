"""CLAUDE.md snippet management for Claude Code integration."""

from __future__ import annotations

from pathlib import Path

import click

CLAUDE_MD_PATH = Path.home() / ".claude" / "CLAUDE.md"

_PBI_CLI_MARKER_START = "<!-- pbi-cli:start -->"
_PBI_CLI_MARKER_END = "<!-- pbi-cli:end -->"

_PBI_CLI_CLAUDE_MD_SNIPPET = (
    "\n"
    "<!-- pbi-cli:start -->\n"
    "# Power BI CLI (pbi-cli)\n"
    "\n"
    "When working with Power BI, DAX, semantic models, or data modeling,\n"
    "invoke the relevant pbi-cli skill before responding:\n"
    "\n"
    "**Semantic Model (requires `pbi connect`):**\n"
    "- **power-bi-dax** -- DAX queries, measures, calculations\n"
    "- **power-bi-modeling** -- tables, columns, measures, relationships\n"
    "- **power-bi-deployment** -- TMDL export/import, transactions, diff\n"
    "- **power-bi-docs** -- model documentation, data dictionary\n"
    "- **power-bi-partitions** -- partitions, M expressions, data sources\n"
    "- **power-bi-security** -- RLS roles, perspectives, access control\n"
    "- **power-bi-diagnostics** -- troubleshooting, tracing, setup\n"
    "\n"
    "**Report Layer (no connection needed):**\n"
    "- **power-bi-report** -- scaffold, validate, preview PBIR reports\n"
    "- **power-bi-visuals** -- add, bind, update, bulk-manage visuals\n"
    "- **power-bi-pages** -- pages, bookmarks, visibility, drillthrough\n"
    "- **power-bi-themes** -- themes, conditional formatting, styling\n"
    "- **power-bi-filters** -- page and visual filters (TopN, date, categorical)\n"
    "- **power-bi-custom-visuals** -- vibe-code .pbiviz custom visuals "
    "(TS scaffold, tsc loop, package, import)\n"
    "\n"
    "Critical: Multi-line DAX (VAR/RETURN) cannot be passed via `-e`.\n"
    "Use `--file` or stdin piping instead. See power-bi-dax skill.\n"
    "<!-- pbi-cli:end -->\n"
)


def ensure_claude_md_snippet() -> None:
    """Append pbi-cli section to ~/.claude/CLAUDE.md if not already present."""
    if CLAUDE_MD_PATH.exists():
        existing = CLAUDE_MD_PATH.read_text(encoding="utf-8")
        if _PBI_CLI_MARKER_START in existing:
            return  # Already present
    else:
        CLAUDE_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing = ""

    new_content = existing.rstrip() + _PBI_CLI_CLAUDE_MD_SNIPPET
    CLAUDE_MD_PATH.write_text(new_content, encoding="utf-8")
    click.echo("  Added pbi-cli section to ~/.claude/CLAUDE.md", err=True)


def remove_claude_md_snippet() -> None:
    """Remove pbi-cli section from ~/.claude/CLAUDE.md if present."""
    if not CLAUDE_MD_PATH.exists():
        return

    content = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    if _PBI_CLI_MARKER_START not in content:
        return

    start_idx = content.index(_PBI_CLI_MARKER_START)
    end_idx = content.index(_PBI_CLI_MARKER_END) + len(_PBI_CLI_MARKER_END)

    before = content[:start_idx].rstrip()
    after = content[end_idx:].lstrip("\n")

    cleaned = before
    if after:
        cleaned = before + "\n\n" + after
    cleaned = cleaned.rstrip() + "\n" if cleaned.strip() else ""

    CLAUDE_MD_PATH.write_text(cleaned, encoding="utf-8")
    click.echo("  Removed pbi-cli section from ~/.claude/CLAUDE.md", err=True)
