"""Tests for pbi_cli.utils.desktop_sync process discovery."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

from pbi_cli.utils.desktop_sync import (
    _accept_save_dialog,
    _get_process_info,
    _hint_matches,
    _hint_tokens,
)

EXE = r"C:\Program Files\WindowsApps\Microsoft.MicrosoftPowerBIDesktop\bin\pbidesktop.exe"
PBIP = r"C:\repo\models\THSAchievement\THSAchievement.pbip"


def _out(exe: str | None, cmd: str | None) -> str:
    return json.dumps({"exe": exe, "cmd": cmd})


def test_returns_exe_and_pbip_from_quoted_command_line() -> None:
    """The .pbip is extracted from a quoted command line."""
    with patch.object(subprocess, "check_output", return_value=_out(EXE, f'"{EXE}" "{PBIP}"')):
        assert _get_process_info(1234) == {"exe": EXE, "pbip": PBIP}


def test_returns_exe_and_pbip_from_unquoted_command_line() -> None:
    """A space-free .pbip path is still found when the command line is unquoted."""
    unquoted = r"C:\repo\THS.pbip"
    with patch.object(subprocess, "check_output", return_value=_out(EXE, unquoted)):
        assert _get_process_info(1234) == {"exe": EXE, "pbip": unquoted}


def test_omits_pbip_when_command_line_has_none() -> None:
    """A Desktop launched without a file yields an exe but no pbip key."""
    with patch.object(subprocess, "check_output", return_value=_out(EXE, f'"{EXE}"')):
        assert _get_process_info(1234) == {"exe": EXE}


def test_returns_none_when_process_absent() -> None:
    """PowerShell prints nothing when the pid does not exist."""
    with patch.object(subprocess, "check_output", return_value="   \n"):
        assert _get_process_info(4321) is None


def test_returns_none_without_executable_path() -> None:
    """A process we cannot read the exe path for is unusable."""
    with patch.object(subprocess, "check_output", return_value=_out(None, "whatever")):
        assert _get_process_info(1234) is None


def test_returns_none_on_malformed_output() -> None:
    """Non-JSON output must not raise."""
    with patch.object(subprocess, "check_output", return_value="not json at all"):
        assert _get_process_info(1234) is None


def test_returns_none_when_helper_missing() -> None:
    """A missing interpreter is reported as no info, not an exception.

    This is the failure mode the wmic implementation hit on Windows 11 24H2+,
    where wmic no longer exists.
    """
    with patch.object(subprocess, "check_output", side_effect=FileNotFoundError):
        assert _get_process_info(1234) is None


def test_does_not_invoke_wmic() -> None:
    """Guard against regressing to wmic, which is absent on current Windows."""
    with patch.object(subprocess, "check_output", return_value=_out(EXE, "")) as mock:
        _get_process_info(1234)
    argv = mock.call_args.args[0]
    assert argv[0] == "powershell"
    assert "wmic" not in " ".join(argv).lower()


# --- hint matching ---------------------------------------------------------

THIN_REPORT = r"semantic-models/THSAchievement/reports/ACA_THS/ACA_THS .Report"
SIDE_BY_SIDE = r"C:\work\MyModel\MyModel.Report"


def test_hint_matches_project_via_ancestor_directory() -> None:
    """A .Report folder named unlike the .pbip still resolves via its project folder.

    The report layer passes a .Report path, whose stem is the REPORT name. Matching
    on that stem alone discarded the correct process.
    """
    assert _hint_matches(_hint_tokens(THIN_REPORT), r"C:\x\THSAchievement.pbip")


def test_hint_matches_side_by_side_layout() -> None:
    """The conventional <Project>/<Project>.Report layout still matches."""
    assert _hint_matches(_hint_tokens(SIDE_BY_SIDE), r"C:\work\MyModel\MyModel.pbip")


def test_hint_matches_direct_pbip_hint() -> None:
    """A genuine .pbip hint keeps working."""
    assert _hint_matches(_hint_tokens(r"C:\x\THSAchievement.pbip"), r"C:\x\THSAchievement.pbip")


def test_hint_rejects_unrelated_project() -> None:
    """The hint is still a filter - an unrelated project must not match."""
    assert not _hint_matches(_hint_tokens(THIN_REPORT), r"C:\x\BMAT_Bromcom_Data_Model.pbip")


# --- save-dialog race ------------------------------------------------------


def test_accept_save_dialog_waits_for_a_late_dialog() -> None:
    """The prompt is polled, not checked once.

    Desktop does not raise the dialog promptly when busy (e.g. straight after a
    table refresh). A single check meant the prompt could appear after we looked,
    so no key was ever sent and the close stranded silently.
    """
    calls = {"n": 0}

    def present() -> bool:
        calls["n"] += 1
        return calls["n"] >= 3  # appears only on the third look

    shell = MagicMock()
    shell.AppActivate.return_value = True
    with (
        patch("pbi_cli.utils.desktop_sync._save_dialog_present", side_effect=present),
        patch("pbi_cli.utils.desktop_sync._get_wscript_shell", return_value=shell),
        patch("pbi_cli.utils.desktop_sync.time.sleep"),
    ):
        _accept_save_dialog(timeout=10)

    shell.SendKeys.assert_called_once_with("{ENTER}")


def test_accept_save_dialog_gives_up_at_the_deadline() -> None:
    """A dialog that never appears must not hang forever, and must send nothing."""
    shell = MagicMock()
    with (
        patch("pbi_cli.utils.desktop_sync._save_dialog_present", return_value=False),
        patch("pbi_cli.utils.desktop_sync._get_wscript_shell", return_value=shell),
        patch("pbi_cli.utils.desktop_sync.time.sleep"),
    ):
        _accept_save_dialog(timeout=0)

    shell.SendKeys.assert_not_called()
