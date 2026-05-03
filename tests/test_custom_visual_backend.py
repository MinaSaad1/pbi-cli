"""Tests for pbi_cli.core.custom_visual_backend.

Covers import-custom, list-custom, remove-custom on PBIR, plus the
pbiviz.json patch-bump helper used by the power-bi-custom-visuals skill.

Fixture .pbiviz files are built in-memory with ``zipfile`` rather than
shelled out to ``pbiviz package`` so the unit suite stays Node-free.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from pbi_cli.core.custom_visual_backend import (
    custom_visual_import,
    custom_visual_list,
    custom_visual_remove,
    pbiviz_bump_patch,
)
from pbi_cli.core.errors import PbiCliError

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _build_pbiviz(
    path: Path,
    *,
    guid: str = "MyVisual1234ABCD",
    name: str = "MyVisual",
    display_name: str | None = None,
    version: str = "1.0.0",
    api_version: str = "5.11.0",
    omit_package_json: bool = False,
    bad_zip: bool = False,
    bad_json: bool = False,
    missing_visual_block: bool = False,
    missing_guid: bool = False,
) -> Path:
    """Write a synthetic .pbiviz to *path* and return it.

    Knobs let tests exercise validation paths without maintaining
    multiple checked-in binary fixtures.
    """
    if bad_zip:
        path.write_bytes(b"this is not a zip file")
        return path

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if not omit_package_json:
            visual_block: dict[str, Any] = {}
            if not missing_visual_block:
                visual_block = {
                    "name": name,
                    "displayName": display_name or name,
                    "version": version,
                    "apiVersion": api_version,
                }
                if not missing_guid:
                    visual_block["guid"] = guid
            manifest: dict[str, Any] = {} if missing_visual_block else {"visual": visual_block}
            payload = "this is not json" if bad_json else json.dumps(manifest)
            zf.writestr("package.json", payload)
        # Minimal resources file so the zip isn't suspiciously empty.
        zf.writestr("resources/visual.js", "// stub")

    path.write_bytes(buf.getvalue())
    return path


def _make_report(tmp_path: Path) -> Path:
    """Build a tiny PBIR-shaped folder and return the *definition* path."""
    report = tmp_path / "Demo.Report"
    definition = report / "definition"
    definition.mkdir(parents=True)
    (definition / "report.json").write_text(
        json.dumps({"layoutOptimization": "Disabled"}, indent=2),
        encoding="utf-8",
    )
    return definition


def _read_report_json(definition: Path) -> dict[str, Any]:
    return json.loads((definition / "report.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# import-custom
# ---------------------------------------------------------------------------


class TestImport:
    def test_imports_a_valid_pbiviz(self, tmp_path: Path) -> None:
        defn = _make_report(tmp_path)
        pbiviz = _build_pbiviz(tmp_path / "MyVisual.pbiviz")

        result = custom_visual_import(defn, pbiviz, replace=False)

        assert result["status"] == "added"
        assert result["guid"] == "MyVisual1234ABCD"
        assert result["version"] == "1.0.0"
        assert result["replaced"] is False

        # File landed in RegisteredResources/
        resources = defn.parent / "StaticResources" / "RegisteredResources"
        assert resources.is_dir()
        landed = list(resources.glob("*.pbiviz"))
        assert len(landed) == 1
        assert "MyVisual1234ABCD" in landed[0].name

        # report.json registered both the resource and the customVisual
        rj = _read_report_json(defn)
        assert rj["customVisuals"] == [{"name": "MyVisual1234ABCD", "version": "1.0.0"}]
        pkg = next(p for p in rj["resourcePackages"] if p["name"] == "RegisteredResources")
        assert any(i["type"] == 5 and "MyVisual1234ABCD" in i["name"] for i in pkg["items"])

    def test_rejects_duplicate_without_replace(self, tmp_path: Path) -> None:
        defn = _make_report(tmp_path)
        pbiviz = _build_pbiviz(tmp_path / "v1.pbiviz")
        custom_visual_import(defn, pbiviz, replace=False)

        # Second import with same GUID
        pbiviz2 = _build_pbiviz(tmp_path / "v2.pbiviz", version="1.0.1")
        with pytest.raises(PbiCliError, match="already registered"):
            custom_visual_import(defn, pbiviz2, replace=False)

    def test_replace_overwrites_in_place(self, tmp_path: Path) -> None:
        defn = _make_report(tmp_path)
        custom_visual_import(defn, _build_pbiviz(tmp_path / "v1.pbiviz"), replace=False)
        result = custom_visual_import(
            defn,
            _build_pbiviz(tmp_path / "v2.pbiviz", version="1.0.42"),
            replace=True,
        )

        assert result["status"] == "added"
        assert result["replaced"] is True
        assert result["version"] == "1.0.42"

        rj = _read_report_json(defn)
        assert rj["customVisuals"] == [{"name": "MyVisual1234ABCD", "version": "1.0.42"}]
        # No duplicate items in the resource package
        pkg = next(p for p in rj["resourcePackages"] if p["name"] == "RegisteredResources")
        custom_items = [i for i in pkg["items"] if i["type"] == 5]
        assert len(custom_items) == 1

    def test_missing_pbiviz_raises(self, tmp_path: Path) -> None:
        defn = _make_report(tmp_path)
        with pytest.raises(PbiCliError, match="not found"):
            custom_visual_import(defn, tmp_path / "nope.pbiviz", replace=False)

    def test_bad_zip_raises(self, tmp_path: Path) -> None:
        defn = _make_report(tmp_path)
        pbiviz = _build_pbiviz(tmp_path / "bad.pbiviz", bad_zip=True)
        with pytest.raises(PbiCliError, match="not a valid zip"):
            custom_visual_import(defn, pbiviz, replace=False)

    def test_missing_package_json_raises(self, tmp_path: Path) -> None:
        defn = _make_report(tmp_path)
        pbiviz = _build_pbiviz(tmp_path / "no-manifest.pbiviz", omit_package_json=True)
        with pytest.raises(PbiCliError, match="package.json not found"):
            custom_visual_import(defn, pbiviz, replace=False)

    def test_bad_json_raises(self, tmp_path: Path) -> None:
        defn = _make_report(tmp_path)
        pbiviz = _build_pbiviz(tmp_path / "badjson.pbiviz", bad_json=True)
        with pytest.raises(PbiCliError, match="not valid JSON"):
            custom_visual_import(defn, pbiviz, replace=False)

    def test_missing_visual_block_raises(self, tmp_path: Path) -> None:
        defn = _make_report(tmp_path)
        pbiviz = _build_pbiviz(tmp_path / "noblock.pbiviz", missing_visual_block=True)
        with pytest.raises(PbiCliError, match="missing 'visual'"):
            custom_visual_import(defn, pbiviz, replace=False)

    def test_missing_guid_raises(self, tmp_path: Path) -> None:
        defn = _make_report(tmp_path)
        pbiviz = _build_pbiviz(tmp_path / "noguid.pbiviz", missing_guid=True)
        with pytest.raises(PbiCliError, match="visual.guid"):
            custom_visual_import(defn, pbiviz, replace=False)

    def test_no_report_json_raises(self, tmp_path: Path) -> None:
        # Definition folder exists but report.json doesn't
        report = tmp_path / "Demo.Report"
        defn = report / "definition"
        defn.mkdir(parents=True)
        pbiviz = _build_pbiviz(tmp_path / "v.pbiviz")
        with pytest.raises(PbiCliError, match="report.json not found"):
            custom_visual_import(defn, pbiviz, replace=False)


# ---------------------------------------------------------------------------
# list-custom
# ---------------------------------------------------------------------------


class TestList:
    def test_empty_report(self, tmp_path: Path) -> None:
        defn = _make_report(tmp_path)
        result = custom_visual_list(defn)
        assert result == {"embedded": [], "public": [], "total": 0}

    def test_lists_embedded(self, tmp_path: Path) -> None:
        defn = _make_report(tmp_path)
        custom_visual_import(defn, _build_pbiviz(tmp_path / "v.pbiviz"), replace=False)

        result = custom_visual_list(defn)

        assert result["total"] == 1
        assert result["public"] == []
        assert len(result["embedded"]) == 1
        e = result["embedded"][0]
        assert e["kind"] == "embedded"
        assert e["guid"] == "MyVisual1234ABCD"
        assert e["version"] == "1.0.0"
        assert e["file"] is not None and e["file"].endswith(".pbiviz")

    def test_lists_public_visuals(self, tmp_path: Path) -> None:
        defn = _make_report(tmp_path)
        rj_path = defn / "report.json"
        data = json.loads(rj_path.read_text(encoding="utf-8"))
        data["publicCustomVisuals"] = ["PublicGuid1", "PublicGuid2"]
        rj_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        result = custom_visual_list(defn)

        assert result["total"] == 2
        assert result["embedded"] == []
        assert {p["guid"] for p in result["public"]} == {"PublicGuid1", "PublicGuid2"}
        assert all(p["kind"] == "public" for p in result["public"])

    def test_lists_mixed(self, tmp_path: Path) -> None:
        defn = _make_report(tmp_path)
        custom_visual_import(defn, _build_pbiviz(tmp_path / "v.pbiviz"), replace=False)

        rj_path = defn / "report.json"
        data = json.loads(rj_path.read_text(encoding="utf-8"))
        data["publicCustomVisuals"] = ["PublicGuid1"]
        rj_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        result = custom_visual_list(defn)
        assert result["total"] == 2
        assert len(result["embedded"]) == 1
        assert len(result["public"]) == 1


# ---------------------------------------------------------------------------
# remove-custom
# ---------------------------------------------------------------------------


class TestRemove:
    def test_removes_by_guid(self, tmp_path: Path) -> None:
        defn = _make_report(tmp_path)
        custom_visual_import(defn, _build_pbiviz(tmp_path / "v.pbiviz"), replace=False)

        result = custom_visual_remove(defn, "MyVisual1234ABCD")

        assert result["status"] == "removed"
        assert result["guid"] == "MyVisual1234ABCD"
        assert result["file_deleted"] is True

        # File gone, registration gone
        resources = defn.parent / "StaticResources" / "RegisteredResources"
        assert list(resources.glob("*.pbiviz")) == []

        rj = _read_report_json(defn)
        assert rj.get("customVisuals", []) == []

    def test_removes_by_name(self, tmp_path: Path) -> None:
        defn = _make_report(tmp_path)
        custom_visual_import(
            defn,
            _build_pbiviz(tmp_path / "v.pbiviz", name="MyVisual"),
            replace=False,
        )

        result = custom_visual_remove(defn, "MyVisual")

        assert result["status"] == "removed"
        assert result["guid"] == "MyVisual1234ABCD"

    def test_ambiguous_name_raises(self, tmp_path: Path) -> None:
        defn = _make_report(tmp_path)
        custom_visual_import(
            defn,
            _build_pbiviz(tmp_path / "a.pbiviz", guid="GuidA1234567890", name="Same"),
            replace=False,
        )
        custom_visual_import(
            defn,
            _build_pbiviz(tmp_path / "b.pbiviz", guid="GuidB1234567890", name="Same"),
            replace=False,
        )

        with pytest.raises(PbiCliError, match="matches 2 custom visuals"):
            custom_visual_remove(defn, "Same")

    def test_unknown_identifier_raises(self, tmp_path: Path) -> None:
        defn = _make_report(tmp_path)
        with pytest.raises(PbiCliError, match="No embedded custom visual found"):
            custom_visual_remove(defn, "NotARealGuid")

    def test_empty_identifier_raises(self, tmp_path: Path) -> None:
        defn = _make_report(tmp_path)
        with pytest.raises(PbiCliError, match="required"):
            custom_visual_remove(defn, "   ")


# ---------------------------------------------------------------------------
# pbiviz.json patch bump
# ---------------------------------------------------------------------------


class TestPatchBump:
    def _write(self, path: Path, version: str) -> None:
        path.write_text(
            json.dumps({"visual": {"version": version}}, indent=2),
            encoding="utf-8",
        )

    def test_bumps_clean_semver(self, tmp_path: Path) -> None:
        pj = tmp_path / "pbiviz.json"
        self._write(pj, "1.0.5")

        result = pbiviz_bump_patch(pj)

        assert result == {"status": "bumped", "previous": "1.0.5", "version": "1.0.6"}
        data = json.loads(pj.read_text(encoding="utf-8"))
        assert data["visual"]["version"] == "1.0.6"

    def test_bumps_zero_patch(self, tmp_path: Path) -> None:
        pj = tmp_path / "pbiviz.json"
        self._write(pj, "0.1.0")
        assert pbiviz_bump_patch(pj)["version"] == "0.1.1"

    def test_skips_user_override_pattern(self, tmp_path: Path) -> None:
        pj = tmp_path / "pbiviz.json"
        self._write(pj, "1.0.0-rc.1")

        result = pbiviz_bump_patch(pj)

        assert result["status"] == "skipped"
        assert "user override" in result["reason"]
        # File untouched
        data = json.loads(pj.read_text(encoding="utf-8"))
        assert data["visual"]["version"] == "1.0.0-rc.1"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(PbiCliError, match="not found"):
            pbiviz_bump_patch(tmp_path / "missing.json")

    def test_missing_visual_block_raises(self, tmp_path: Path) -> None:
        pj = tmp_path / "pbiviz.json"
        pj.write_text(json.dumps({"other": "stuff"}), encoding="utf-8")
        with pytest.raises(PbiCliError, match="missing 'visual'"):
            pbiviz_bump_patch(pj)

    def test_missing_version_raises(self, tmp_path: Path) -> None:
        pj = tmp_path / "pbiviz.json"
        pj.write_text(json.dumps({"visual": {"name": "x"}}), encoding="utf-8")
        with pytest.raises(PbiCliError, match="visual.version"):
            pbiviz_bump_patch(pj)
