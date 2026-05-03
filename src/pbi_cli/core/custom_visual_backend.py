"""Custom visual operations for PBIR reports.

Embedded ``.pbiviz`` packages are placed in
``<.Report>/StaticResources/RegisteredResources/`` and registered in
``definition/report.json`` so that Power BI Desktop loads them on open.

Public (AppSource / organizational) visuals are referenced by GUID only via
``publicCustomVisuals`` and have no embedded resource.

Scope is locally-built ``.pbiviz`` files (the vibe-coding output path).
AppSource registration is intentionally out of scope; ``list-custom`` reads
``publicCustomVisuals`` for completeness but ``import-custom`` and
``remove-custom`` only operate on embedded resources.
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from pbi_cli.core.errors import PbiCliError

# Resource type code used for custom visuals in PBIR ``resourcePackages`` items.
# Mirrors the legacy PBIX resource enum where 5 == CustomVisual.
_CUSTOM_VISUAL_RESOURCE_TYPE = 5

# Subpath used in the ``path`` field of resource items (logical scope, not
# a real subfolder; physical file lives directly under RegisteredResources).
_CUSTOM_VISUAL_PATH_SCOPE = "CustomVisuals"


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return result


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# .pbiviz package inspection
# ---------------------------------------------------------------------------


def _read_pbiviz_manifest(pbiviz_path: Path) -> dict[str, Any]:
    """Open a .pbiviz archive and return the parsed package.json visual block.

    Sanity checks only: archive opens, package.json present and parseable,
    visual.guid and visual.version are non-empty strings. Deep validation
    (capabilities schema, API compatibility) is left to ``pbiviz package``
    and Power BI Desktop's loader.
    """
    if not pbiviz_path.exists():
        raise PbiCliError(f".pbiviz file not found: {pbiviz_path}")
    if not pbiviz_path.is_file():
        raise PbiCliError(f".pbiviz path is not a file: {pbiviz_path}")

    try:
        with zipfile.ZipFile(pbiviz_path, "r") as zf:
            try:
                manifest_bytes = zf.read("package.json")
            except KeyError as exc:
                raise PbiCliError(
                    f"Invalid .pbiviz: package.json not found inside {pbiviz_path.name}"
                ) from exc
    except zipfile.BadZipFile as exc:
        raise PbiCliError(f"Invalid .pbiviz: not a valid zip archive ({pbiviz_path.name})") from exc

    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PbiCliError(
            f"Invalid .pbiviz: package.json is not valid JSON ({pbiviz_path.name})"
        ) from exc

    visual = manifest.get("visual")
    if not isinstance(visual, dict):
        raise PbiCliError(
            "Invalid .pbiviz: package.json missing 'visual' object "
            "(expected fields: guid, name, version, apiVersion)"
        )

    guid = visual.get("guid")
    version = visual.get("version")
    name = visual.get("name") or visual.get("displayName")

    if not isinstance(guid, str) or not guid.strip():
        raise PbiCliError("Invalid .pbiviz: visual.guid missing or empty")
    if not isinstance(version, str) or not version.strip():
        raise PbiCliError("Invalid .pbiviz: visual.version missing or empty")
    if not isinstance(name, str) or not name.strip():
        raise PbiCliError("Invalid .pbiviz: visual.name (or displayName) missing or empty")

    return {
        "guid": guid.strip(),
        "name": name.strip(),
        "version": version.strip(),
        "display_name": (visual.get("displayName") or name).strip(),
        "api_version": str(visual.get("apiVersion") or "").strip(),
    }


def _resource_filename(manifest: dict[str, Any]) -> str:
    """Build the on-disk filename for a custom visual resource.

    Uses ``<sanitized-name>.<guid>.pbiviz`` to avoid collisions when two
    visuals happen to share a friendly name.
    """
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", manifest["name"]).strip("_") or "visual"
    return f"{safe_name}.{manifest['guid']}.pbiviz"


# ---------------------------------------------------------------------------
# report.json mutation
# ---------------------------------------------------------------------------


def _get_or_create_resource_package(report_data: dict[str, Any]) -> dict[str, Any]:
    """Ensure a RegisteredResources package exists and return it."""
    packages = report_data.setdefault("resourcePackages", [])
    for pkg in packages:
        if pkg.get("name") == "RegisteredResources":
            pkg.setdefault("items", [])
            return pkg  # type: ignore[no-any-return]

    pkg = {
        "name": "RegisteredResources",
        "type": "RegisteredResources",
        "items": [],
    }
    packages.append(pkg)
    return pkg


def _find_embedded_entry(report_data: dict[str, Any], guid: str) -> dict[str, Any] | None:
    """Return the customVisuals entry matching the given GUID, or None."""
    for entry in report_data.get("customVisuals", []) or []:
        if isinstance(entry, dict) and entry.get("name") == guid:
            return entry
    return None


def _remove_embedded_registration(
    report_data: dict[str, Any], guid: str, filename: str | None
) -> bool:
    """Remove a custom visual's entries from report.json.

    Returns True if anything was removed.
    """
    removed = False

    custom_visuals = report_data.get("customVisuals")
    if isinstance(custom_visuals, list):
        new_list = [
            e for e in custom_visuals if not (isinstance(e, dict) and e.get("name") == guid)
        ]
        if len(new_list) != len(custom_visuals):
            report_data["customVisuals"] = new_list
            removed = True

    if filename is not None:
        for pkg in report_data.get("resourcePackages", []) or []:
            if pkg.get("name") != "RegisteredResources":
                continue
            items = pkg.get("items")
            if not isinstance(items, list):
                continue
            new_items = [i for i in items if i.get("name") != filename]
            if len(new_items) != len(items):
                pkg["items"] = new_items
                removed = True

    return removed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def custom_visual_import(
    definition_path: Path,
    pbiviz_path: Path,
    replace: bool = False,
) -> dict[str, Any]:
    """Register a locally-built .pbiviz into a PBIR report.

    Validates the zip + manifest, copies the file to
    ``StaticResources/RegisteredResources/``, and updates ``report.json``
    so Desktop loads it on open.

    Returns ``{status, guid, name, version, file}``. Status is ``"added"``
    on first import or when ``replace=True`` overwrites an existing entry.
    """
    manifest = _read_pbiviz_manifest(pbiviz_path)
    guid = manifest["guid"]

    report_json_path = definition_path / "report.json"
    if not report_json_path.exists():
        raise PbiCliError("report.json not found -- is this a valid PBIR definition folder?")
    report_data = _read_json(report_json_path)

    existing = _find_embedded_entry(report_data, guid)
    if existing is not None and not replace:
        raise PbiCliError(
            f"Custom visual already registered (guid={guid}, version="
            f"{existing.get('version')!r}). Pass --replace to overwrite."
        )

    filename = _resource_filename(manifest)
    report_folder = definition_path.parent
    resources_dir = report_folder / "StaticResources" / "RegisteredResources"
    resources_dir.mkdir(parents=True, exist_ok=True)
    dest = resources_dir / filename

    if existing is not None:
        # Best-effort cleanup of any prior on-disk file with this GUID.
        for old in resources_dir.glob(f"*.{guid}.pbiviz"):
            try:
                old.unlink()
            except OSError:
                pass
        _remove_embedded_registration(report_data, guid, filename=None)

    dest.write_bytes(pbiviz_path.read_bytes())

    pkg = _get_or_create_resource_package(report_data)
    pkg_items: list[dict[str, Any]] = pkg["items"]
    # Drop any stale item with same filename, then append fresh.
    pkg["items"] = [i for i in pkg_items if i.get("name") != filename]
    pkg["items"].append(
        {
            "name": filename,
            "type": _CUSTOM_VISUAL_RESOURCE_TYPE,
            "path": f"{_CUSTOM_VISUAL_PATH_SCOPE}/{filename}",
        }
    )

    custom_visuals = report_data.setdefault("customVisuals", [])
    custom_visuals.append({"name": guid, "version": manifest["version"]})

    _write_json(report_json_path, report_data)

    return {
        "status": "added",
        "guid": guid,
        "name": manifest["name"],
        "version": manifest["version"],
        "file": str(dest),
        "replaced": existing is not None,
    }


def custom_visual_list(definition_path: Path) -> dict[str, Any]:
    """List custom visuals registered in a PBIR report.

    Returns ``{embedded: [...], public: [...]}`` where each item carries
    a ``kind`` field. Embedded entries include the on-disk file path when
    present; public entries are GUID-only AppSource/org references.
    """
    report_json_path = definition_path / "report.json"
    if not report_json_path.exists():
        raise PbiCliError("report.json not found -- is this a valid PBIR definition folder?")
    report_data = _read_json(report_json_path)

    report_folder = definition_path.parent
    resources_dir = report_folder / "StaticResources" / "RegisteredResources"

    # Build a guid -> filename map from the resource package, if any
    guid_to_file: dict[str, str] = {}
    for pkg in report_data.get("resourcePackages", []) or []:
        if pkg.get("name") != "RegisteredResources":
            continue
        for item in pkg.get("items", []) or []:
            if item.get("type") != _CUSTOM_VISUAL_RESOURCE_TYPE:
                continue
            name = item.get("name")
            if not isinstance(name, str):
                continue
            # Filename pattern: <safe>.<guid>.pbiviz
            m = re.match(r"^.+\.([0-9A-Za-z_-]+)\.pbiviz$", name)
            if m:
                guid_to_file[m.group(1)] = name

    embedded: list[dict[str, Any]] = []
    for entry in report_data.get("customVisuals", []) or []:
        if not isinstance(entry, dict):
            continue
        guid = entry.get("name")
        if not isinstance(guid, str):
            continue
        filename = guid_to_file.get(guid)
        file_path = (
            str(resources_dir / filename)
            if filename and (resources_dir / filename).exists()
            else None
        )
        embedded.append(
            {
                "kind": "embedded",
                "guid": guid,
                "version": entry.get("version"),
                "file": file_path,
            }
        )

    public: list[dict[str, Any]] = []
    for guid in report_data.get("publicCustomVisuals", []) or []:
        if isinstance(guid, str):
            public.append({"kind": "public", "guid": guid})

    return {
        "embedded": embedded,
        "public": public,
        "total": len(embedded) + len(public),
    }


def custom_visual_remove(
    definition_path: Path,
    identifier: str,
) -> dict[str, Any]:
    """Remove an embedded custom visual by GUID or friendly name.

    Friendly-name lookup is best-effort against the on-disk filename
    pattern ``<safe-name>.<guid>.pbiviz``. If ambiguous, raises with
    guidance to disambiguate by GUID.

    Public (AppSource) visuals registered via ``publicCustomVisuals`` are
    out of scope here -- a separate ``register-public`` / ``unregister-public``
    surface is intentionally deferred.
    """
    if not identifier or not identifier.strip():
        raise PbiCliError("Identifier (GUID or name) is required.")
    identifier = identifier.strip()

    report_json_path = definition_path / "report.json"
    if not report_json_path.exists():
        raise PbiCliError("report.json not found -- is this a valid PBIR definition folder?")
    report_data = _read_json(report_json_path)

    report_folder = definition_path.parent
    resources_dir = report_folder / "StaticResources" / "RegisteredResources"

    # Build candidate map: guid -> filename
    guid_to_file: dict[str, str] = {}
    for pkg in report_data.get("resourcePackages", []) or []:
        if pkg.get("name") != "RegisteredResources":
            continue
        for item in pkg.get("items", []) or []:
            if item.get("type") != _CUSTOM_VISUAL_RESOURCE_TYPE:
                continue
            name = item.get("name")
            if not isinstance(name, str):
                continue
            m = re.match(r"^(.+)\.([0-9A-Za-z_-]+)\.pbiviz$", name)
            if m:
                guid_to_file[m.group(2)] = name

    target_guid: str | None = None

    # Direct GUID match against customVisuals
    for entry in report_data.get("customVisuals", []) or []:
        if isinstance(entry, dict) and entry.get("name") == identifier:
            target_guid = identifier
            break

    if target_guid is None:
        # Try name-based lookup via the filename pattern
        matches: list[str] = []
        for guid, fname in guid_to_file.items():
            m = re.match(r"^(.+)\.([0-9A-Za-z_-]+)\.pbiviz$", fname)
            if not m:
                continue
            safe_name = m.group(1)
            if safe_name == identifier or safe_name.lower() == identifier.lower():
                matches.append(guid)
        if len(matches) > 1:
            raise PbiCliError(
                f"Name {identifier!r} matches {len(matches)} custom visuals "
                f"({', '.join(matches)}). Disambiguate by passing the GUID."
            )
        if len(matches) == 1:
            target_guid = matches[0]

    if target_guid is None:
        raise PbiCliError(
            f"No embedded custom visual found for identifier {identifier!r}. "
            "Use `pbi visual list-custom` to see what's registered."
        )

    filename: str | None = guid_to_file.get(target_guid)
    removed = _remove_embedded_registration(report_data, target_guid, filename)
    if not removed:
        raise PbiCliError(f"Custom visual {target_guid!r} not found in report.json registration.")

    file_deleted = False
    if filename is not None:
        candidate = resources_dir / filename
        if candidate.exists():
            try:
                candidate.unlink()
                file_deleted = True
            except OSError as exc:
                raise PbiCliError(f"Failed to delete {candidate}: {exc}") from exc

    _write_json(report_json_path, report_data)

    return {
        "status": "removed",
        "guid": target_guid,
        "file_deleted": file_deleted,
        "file": str(resources_dir / filename) if filename else None,
    }


# ---------------------------------------------------------------------------
# pbiviz.json version auto-bump (skill helper)
# ---------------------------------------------------------------------------

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def pbiviz_bump_patch(pbiviz_json_path: Path) -> dict[str, Any]:
    """Increment the patch version in a custom visual project's pbiviz.json.

    Used by the ``power-bi-custom-visuals`` skill between iterations so
    Power BI Desktop's GUID+version cache invalidates and serves fresh
    code on each repackage.

    If the current version doesn't match ``<int>.<int>.<int>``, treat as a
    user-managed override and skip without raising. Returns the chosen
    behavior so the skill can surface it to the user.
    """
    if not pbiviz_json_path.exists():
        raise PbiCliError(f"pbiviz.json not found: {pbiviz_json_path}")

    data = _read_json(pbiviz_json_path)
    visual = data.get("visual")
    if not isinstance(visual, dict):
        raise PbiCliError("pbiviz.json: missing 'visual' block")

    current = visual.get("version")
    if not isinstance(current, str):
        raise PbiCliError("pbiviz.json: visual.version is missing")

    m = _SEMVER_RE.match(current.strip())
    if m is None:
        return {
            "status": "skipped",
            "reason": "version does not match major.minor.patch; treating as user override",
            "version": current,
        }

    major, minor, patch = (int(g) for g in m.groups())
    new_version = f"{major}.{minor}.{patch + 1}"
    visual["version"] = new_version
    _write_json(pbiviz_json_path, data)

    return {
        "status": "bumped",
        "previous": current,
        "version": new_version,
    }
