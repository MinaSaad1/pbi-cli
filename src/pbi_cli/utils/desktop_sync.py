"""Close and reopen Power BI Desktop to sync PBIR file changes.

Power BI Desktop does not auto-detect PBIR file changes on disk.
When pbi-cli writes to report JSON files while Desktop has the .pbip
open, Desktop's in-memory state overwrites CLI changes on save.

This module uses a safe **save-first-then-rewrite** pattern:

  1. Snapshot recently modified PBIR files (our changes)
  2. Close Desktop WITH save (preserves user's unsaved modeling work)
  3. Re-apply our PBIR snapshots (Desktop's save overwrote them)
  4. Reopen Desktop with the .pbip file

This preserves both the user's in-progress Desktop work (measures,
relationships, etc.) AND our report-layer changes (filters, visuals, etc.).

Requires pywin32.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path, PureWindowsPath
from typing import Any

# How long to wait for the save prompt to appear after WM_CLOSE. Desktop can be
# slow to raise it when busy (e.g. immediately after a table refresh).
DIALOG_TIMEOUT = 60.0
# How long to wait for the process to exit once the prompt has been accepted.
# Saving a large model routinely exceeds a minute.
CLOSE_TIMEOUT = 600.0
POLL_INTERVAL = 0.5


def sync_desktop(
    pbip_hint: str | Path | None = None,
    definition_path: str | Path | None = None,
) -> dict[str, Any]:
    """Close Desktop (with save), re-apply PBIR changes, and reopen.

    *pbip_hint* narrows the search to a specific .pbip file.
    *definition_path* is the PBIR definition folder; recently modified
    files here are snapshotted before Desktop saves and restored after.
    """
    try:
        import win32con  # noqa: F401
        import win32gui  # noqa: F401
    except ImportError:
        return {
            "status": "manual",
            "method": "instructions",
            "message": (
                "pywin32 is not installed. Install with: pip install pywin32\n"
                "Then pbi-cli can auto-sync Desktop after report changes.\n"
                "For now: save in Desktop, close, reopen the .pbip file."
            ),
        }

    info = _find_desktop_process(pbip_hint)
    if info is None:
        return {
            "status": "skipped",
            "method": "pywin32",
            "message": "Power BI Desktop is not running. No sync needed.",
        }

    hwnd = info["hwnd"]
    pbip_path = info["pbip_path"]
    pid = info["pid"]

    # Step 1: Snapshot our PBIR changes (files modified in the last 5 seconds)
    snapshots = _snapshot_recent_changes(definition_path)

    # Step 2: Close Desktop WITH save (Enter = Save button)
    close_err = _close_with_save(hwnd, pid)
    if close_err is not None:
        return close_err

    # Step 3: Re-apply our PBIR changes (Desktop's save overwrote them)
    restored = _restore_snapshots(snapshots)

    # Step 4: Reopen
    reopen_result = _reopen_pbip(pbip_path)
    if restored:
        reopen_result["restored_files"] = restored
    return reopen_result


# ---------------------------------------------------------------------------
# Snapshot / Restore
# ---------------------------------------------------------------------------


def _snapshot_recent_changes(
    definition_path: str | Path | None,
    max_age_seconds: float = 5.0,
) -> dict[Path, bytes]:
    """Read files modified within *max_age_seconds* under *definition_path*."""
    if definition_path is None:
        return {}

    defn = Path(definition_path)
    if not defn.is_dir():
        return {}

    now = time.time()
    snapshots: dict[Path, bytes] = {}

    for fpath in defn.rglob("*.json"):
        try:
            age = now - fpath.stat().st_mtime
            if age <= max_age_seconds:
                snapshots[fpath] = fpath.read_bytes()
        except OSError:
            continue

    return snapshots


def _restore_snapshots(snapshots: dict[Path, bytes]) -> list[str]:
    """Write snapshotted file contents back to disk."""
    restored: list[str] = []
    for fpath, content in snapshots.items():
        try:
            fpath.write_bytes(content)
            restored.append(fpath.name)
        except OSError:
            continue
    return restored


# ---------------------------------------------------------------------------
# Desktop process discovery
# ---------------------------------------------------------------------------


def _hint_tokens(pbip_hint: str | Path) -> set[str]:
    """Lowercased name tokens from a hint path: its stem plus every directory name.

    The hint reaching ``sync_desktop`` from the report layer is a ``.Report`` folder,
    not a ``.pbip``. Its stem is therefore the *report* name, which need not resemble
    the project name at all -- so matching on the stem alone silently discards the
    correct process. Including the ancestor directory names lets the usual layouts
    (``<Project>/<Project>.Report`` and thin-report repos that nest reports under a
    project folder) resolve, while keeping the hint a real filter.

    Paths are parsed with Windows semantics on every platform. This module only
    runs on Windows, and ``PureWindowsPath`` splits on both separators, so a
    backslash literal in a test means on a POSIX CI runner what it means here.

    The drive anchor and single-character names are dropped: they carry no
    project identity and would only widen the match.
    """
    p = PureWindowsPath(str(pbip_hint))
    parts = p.parts[1:] if p.anchor else p.parts
    tokens = {part.lower().strip() for part in parts}
    # A ".Report" folder's stem keeps a trailing space in some exports; normalise.
    tokens.add(p.stem.lower().strip())
    return {t for t in tokens if len(t) > 1}


def _hint_matches(hint_parts: set[str], pbip_path: str) -> bool:
    """True when the open .pbip belongs to the hinted project.

    The comparison is exact. Substring matching in either direction looked
    permissive in a good way, but every ancestor directory is a token, so
    ordinary path components became live matchers: a username directory made
    ``Mina_Test.pbip`` match a hint under ``C:/Users/mina/``, and a project
    named ``Sales`` matched ``Salesforce_Extract.pbip``.

    That is not a wrong answer, it is a wrong *process*. ``_find_desktop_process``
    hands its first match to ``_close_with_save``, which force-closes and saves
    it -- so a loose predicate here restarts somebody else's Desktop session and
    reopens the wrong .pbip. Failing to match is recoverable ("not running");
    matching the wrong instance is not.
    """
    return PureWindowsPath(pbip_path).stem.lower().strip() in hint_parts


def _find_desktop_process(
    pbip_hint: str | Path | None,
) -> dict[str, Any] | None:
    """Find the PBI Desktop window, its PID, and the .pbip file it has open."""
    import win32gui
    import win32process

    hint_parts: set[str] | None = None
    if pbip_hint is not None:
        hint_parts = _hint_tokens(pbip_hint)

    matches: list[dict[str, Any]] = []

    def callback(hwnd: int, _: Any) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return True

        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        cmd_info = _get_process_info(pid)
        if cmd_info is None:
            return True

        exe_path = cmd_info.get("exe", "")
        if "pbidesktop" not in exe_path.lower():
            return True

        pbip_path = cmd_info.get("pbip")
        if pbip_path is None:
            return True

        if hint_parts is not None:
            if not _hint_matches(hint_parts, pbip_path):
                return True

        matches.append(
            {
                "hwnd": hwnd,
                "pid": pid,
                "title": title,
                "exe_path": exe_path,
                "pbip_path": pbip_path,
            }
        )
        return True

    try:
        win32gui.EnumWindows(callback, None)
    except Exception:
        pass

    return matches[0] if matches else None


_PS_PROCESS_QUERY = (
    '$p = Get-CimInstance Win32_Process -Filter "ProcessId=%d"; '
    "if ($p) { [pscustomobject]@{ exe = $p.ExecutablePath; cmd = $p.CommandLine } "
    "| ConvertTo-Json -Compress }"
)


def _get_process_info(pid: int) -> dict[str, str] | None:
    """Get exe path and .pbip file from a process command line.

    Uses PowerShell's ``Get-CimInstance Win32_Process`` rather than ``wmic``.
    WMIC was deprecated in 2021 and is **no longer present** on Windows 11
    24H2 and later, so the previous implementation raised ``FileNotFoundError``
    for every process. Because the failure was swallowed, discovery silently
    returned no matches and ``sync_desktop`` reported "Power BI Desktop is not
    running" while it was plainly running.
    """
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                _PS_PROCESS_QUERY % pid,
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
    except Exception:
        return None

    out = out.strip()
    if not out:
        return None

    try:
        data = json.loads(out)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    exe = data.get("exe")
    if not exe:
        return None

    result: dict[str, str] = {"exe": str(exe)}
    for part in str(data.get("cmd") or "").split('"'):
        part = part.strip()
        if part.lower().endswith(".pbip"):
            result["pbip"] = part
            break

    return result


# ---------------------------------------------------------------------------
# Close with save
# ---------------------------------------------------------------------------


def _close_with_save(hwnd: int, pid: int) -> dict[str, Any] | None:
    """Close Desktop via WM_CLOSE and click Save in the dialog.

    Returns an error dict on failure, or None on success.
    """
    import win32con
    import win32gui

    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)

    # Poll for the save dialog rather than assuming it is up after a fixed wait.
    _accept_save_dialog(pid)

    # Then wait for the process to actually exit. Writing a large model can take
    # minutes -- Desktop shows a "Working on it" dialog throughout -- so this is
    # deliberately generous; the previous 20s deadline expired mid-save.
    deadline = time.monotonic() + CLOSE_TIMEOUT
    while _process_alive(pid):
        if time.monotonic() >= deadline:
            return {
                "status": "error",
                "method": "pywin32",
                "message": (
                    f"Power BI Desktop did not close within {CLOSE_TIMEOUT:.0f} seconds. "
                    "Please save and close manually, then reopen the .pbip file."
                ),
            }
        time.sleep(POLL_INTERVAL)

    return None


def _save_dialog_present() -> bool:
    """True when Desktop's [Save] [Don't Save] [Cancel] prompt is on screen."""
    import win32gui

    found = False

    def callback(hwnd: int, _: Any) -> bool:
        nonlocal found
        if win32gui.IsWindowVisible(hwnd):
            if win32gui.GetWindowText(hwnd) == "Microsoft Power BI Desktop":
                found = True
        return True

    try:
        win32gui.EnumWindows(callback, None)
    except Exception:
        pass

    return found


def _accept_save_dialog(pid: int | None = None, timeout: float = DIALOG_TIMEOUT) -> None:
    """Wait for the save dialog to appear, then accept it (Enter = Save).

    After WM_CLOSE, Power BI Desktop shows a dialog:
      [Save]  [Don't Save]  [Cancel]
    'Save' is the default focused button, so Enter clicks it.

    The dialog is POLLED rather than checked once. Desktop does not raise it
    promptly when it is busy — notably straight after a table refresh — and a
    single check meant the prompt could appear *after* we looked, so no key was
    ever sent and the caller then waited out its timeout on a dialog nobody had
    answered. That failure was silent: the dialog is the only thing that can
    complete the close, so missing it strands the save entirely.

    Polling alone has a third outcome to account for, and it is the common one:
    Desktop with nothing to save closes on WM_CLOSE without ever prompting.
    Without *pid* the loop cannot tell that from a late dialog and burns the
    whole timeout -- 60s where the fixed-sleep version took 2s. Watching the
    process closes that gap.
    """
    deadline = time.monotonic() + timeout
    while not _save_dialog_present():
        if pid is not None and not _process_alive(pid):
            return  # closed cleanly; there was nothing to save
        if time.monotonic() >= deadline:
            return
        time.sleep(POLL_INTERVAL)

    try:
        shell = _get_wscript_shell()
        activated = shell.AppActivate("Microsoft Power BI Desktop")
        if activated:
            time.sleep(0.3)
            # Enter = Save (the default button)
            shell.SendKeys("{ENTER}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Reopen / utilities
# ---------------------------------------------------------------------------


def _reopen_pbip(pbip_path: str) -> dict[str, Any]:
    """Launch the .pbip file with the system default handler."""
    try:
        subprocess.Popen(  # noqa: S603
            ["cmd", "/c", "start", "", pbip_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {
            "status": "success",
            "method": "pywin32",
            "message": f"Desktop synced: {Path(pbip_path).name}",
            "file": pbip_path,
        }
    except Exception as e:
        return {
            "status": "error",
            "method": "pywin32",
            "message": f"Failed to reopen: {e}. Open manually: {pbip_path}",
        }


def _process_alive(pid: int) -> bool:
    """Check if a process is still running."""
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        return str(pid) in out
    except Exception:
        return False


def _get_wscript_shell() -> Any:
    """Get a WScript.Shell COM object for SendKeys."""
    import win32com.client

    return win32com.client.Dispatch("WScript.Shell")
