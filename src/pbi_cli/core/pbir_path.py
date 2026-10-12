"""PBIR report folder resolution and path utilities."""

from __future__ import annotations

from pathlib import Path

from pbi_cli.core.errors import AmbiguousReportError, ReportNotFoundError

# Maximum parent directories to walk up when auto-detecting
_MAX_WALK_UP = 5


def resolve_report_path(explicit_path: str | None = None) -> Path:
    """Resolve the PBIR definition folder path.

    Resolution order:
    1. Explicit ``--path`` provided by user.
    2. Walk up from CWD looking for ``*.Report/definition/report.json``.
    3. Look for a sibling ``.pbip`` file and derive the ``.Report`` folder.
    4. Raise ``ReportNotFoundError``.
    """
    if explicit_path is not None:
        return _resolve_explicit(Path(explicit_path))

    cwd = Path.cwd()

    # Try walk-up detection
    found = _find_definition_walkup(cwd)
    if found is not None:
        return found

    # Try .pbip sibling detection
    found = _find_from_pbip(cwd)
    if found is not None:
        return found

    raise ReportNotFoundError()


def _resolve_explicit(path: Path) -> Path:
    """Normalise an explicit path to the definition folder."""
    path = path.resolve()

    # User pointed directly at the definition folder
    if path.name == "definition" and (path / "report.json").exists():
        return path

    # User pointed at the .Report folder
    defn = path / "definition"
    if defn.is_dir() and (defn / "report.json").exists():
        return defn

    # User pointed at something that contains a .Report child
    for child in path.iterdir() if path.is_dir() else []:
        if child.name.endswith(".Report") and child.is_dir():
            defn = child / "definition"
            if (defn / "report.json").exists():
                return defn

    raise ReportNotFoundError(
        f"No PBIR definition found at '{path}'. "
        "Expected a folder containing definition/report.json."
    )


def _find_definition_walkup(start: Path) -> Path | None:
    """Walk up from *start* looking for a .Report/definition/ folder.

    Raises ``AmbiguousReportError`` if a single directory level contains more
    than one valid ``.Report`` folder -- silently picking one here would let
    a command write into a report the caller never meant to touch.
    """
    current = start.resolve()
    for _ in range(_MAX_WALK_UP):
        matches = []
        for child in sorted(current.iterdir()):
            if child.is_dir() and child.name.endswith(".Report"):
                defn = child / "definition"
                if defn.is_dir() and (defn / "report.json").exists():
                    matches.append(defn)
        if len(matches) > 1:
            raise AmbiguousReportError([str(m.parent) for m in matches])
        if matches:
            return matches[0]
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _find_from_pbip(start: Path) -> Path | None:
    """Look for a .pbip file and derive the .Report folder."""
    if not start.is_dir():
        return None
    try:
        for item in start.iterdir():
            if item.is_file() and item.suffix == ".pbip":
                report_folder = start / f"{item.stem}.Report"
                defn = report_folder / "definition"
                if defn.is_dir() and (defn / "report.json").exists():
                    return defn
    except (OSError, PermissionError):
        return None
    return None


def get_pages_dir(definition_path: Path) -> Path:
    """Return the pages directory, creating it if needed."""
    pages = definition_path / "pages"
    pages.mkdir(exist_ok=True)
    return pages


def get_page_dir(definition_path: Path, page_name: str) -> Path:
    """Return the directory for a specific page."""
    return definition_path / "pages" / page_name


def get_visuals_dir(definition_path: Path, page_name: str) -> Path:
    """Return the visuals directory for a specific page."""
    visuals = definition_path / "pages" / page_name / "visuals"
    visuals.mkdir(parents=True, exist_ok=True)
    return visuals


def get_visual_dir(definition_path: Path, page_name: str, visual_name: str) -> Path:
    """Return the directory for a specific visual."""
    return definition_path / "pages" / page_name / "visuals" / visual_name


def validate_report_structure(definition_path: Path) -> list[str]:
    """Check that the PBIR folder structure is valid.

    Returns a list of error messages (empty if valid).
    """
    errors: list[str] = []

    if not definition_path.is_dir():
        errors.append(f"Definition folder does not exist: {definition_path}")
        return errors

    report_json = definition_path / "report.json"
    if not report_json.exists():
        errors.append("Missing required file: report.json")

    version_json = definition_path / "version.json"
    if not version_json.exists():
        errors.append("Missing required file: version.json")

    pages_dir = definition_path / "pages"
    if pages_dir.is_dir():
        for page_dir in sorted(pages_dir.iterdir()):
            if not page_dir.is_dir():
                continue
            page_json = page_dir / "page.json"
            if not page_json.exists():
                errors.append(f"Page folder '{page_dir.name}' missing page.json")
            visuals_dir = page_dir / "visuals"
            if visuals_dir.is_dir():
                for visual_dir in sorted(visuals_dir.iterdir()):
                    if not visual_dir.is_dir():
                        continue
                    visual_json = visual_dir / "visual.json"
                    if not visual_json.exists():
                        errors.append(
                            f"Visual folder '{page_dir.name}/visuals/{visual_dir.name}' "
                            "missing visual.json"
                        )

    return errors
