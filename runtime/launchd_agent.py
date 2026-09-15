# macOS LaunchAgent helpers — crash recovery tied to keep_running_in_tray.

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

from config.settings import APP_NAME, PROJECT_ROOT
from runtime.single_instance import is_pid_running

LABEL = "com.taskforge.runtime"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG_DIR = Path.home() / "Library" / "Logs" / APP_NAME


def _launchd_domain() -> str:
    return f"gui/{os.getuid()}"


def _launchd_target() -> str:
    return f"{_launchd_domain()}/{LABEL}"


def resolve_program_arguments() -> list[str] | None:
    """Return argv for the LaunchAgent, or None if this platform cannot install one."""
    if sys.platform != "darwin":
        return None

    if getattr(sys, "frozen", False):
        return [sys.executable, "--background"]

    app_bundle = Path(sys.executable).resolve().parent.parent.parent
    if app_bundle.suffix == ".app":
        binary = app_bundle / "Contents" / "MacOS" / app_bundle.stem
        if binary.is_file():
            return [str(binary), "--background"]

    for candidate in (
        Path("/Applications") / "TaskForge.app",
        Path.home() / "Applications" / "TaskForge.app",
        PROJECT_ROOT / "dist" / "TaskForge.app",
    ):
        binary = candidate / "Contents" / "MacOS" / "TaskForge"
        if binary.is_file():
            return [str(binary), "--background"]

    app_py = PROJECT_ROOT / "app.py"
    if app_py.is_file():
        return [sys.executable, str(app_py), "--background"]

    return None


def is_agent_loaded() -> bool:
    if sys.platform != "darwin":
        return False
    try:
        result = subprocess.run(
            ["launchctl", "print", _launchd_target()],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def agent_pid() -> int | None:
    if not is_agent_loaded():
        return None
    try:
        result = subprocess.run(
            ["launchctl", "print", _launchd_target()],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("pid ="):
            pid_text = stripped.split("=", 1)[1].strip()
            try:
                return int(pid_text)
            except ValueError:
                return None
    return None


def is_supervised_by_launchd() -> bool:
    """True when the current process is the launchd-managed TaskForge job."""
    managed = agent_pid()
    return managed is not None and managed == os.getpid()


def _write_plist(program_args: list[str]) -> None:
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "Label": LABEL,
        "ProgramArguments": program_args,
        "RunAtLoad": True,
        # Restart only after crashes / non-zero exits — not after tray Quit (exit 0).
        "KeepAlive": {"SuccessfulExit": True},
        "StandardOutPath": str(LOG_DIR / "launchd.out.log"),
        "StandardErrorPath": str(LOG_DIR / "launchd.err.log"),
    }
    with PLIST_PATH.open("wb") as handle:
        plistlib.dump(payload, handle)


def _run_launchctl(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["launchctl", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def prepare_crash_recovery() -> tuple[bool, str, bool]:
    """
    Register crash-recovery settings.

    Returns (ok, message, needs_handoff). When needs_handoff is True, the caller
    must release the instance lock and exit so launchd can start the supervised
    process that KeepAlive can restart after crashes.
    """
    if sys.platform != "darwin":
        return True, "Crash recovery is only available on macOS.", False

    program_args = resolve_program_arguments()
    if not program_args:
        return True, "Crash recovery is unavailable for this install.", False

    try:
        _write_plist(program_args)
        if is_supervised_by_launchd():
            return True, "Crash recovery active for this session.", False
        return True, "", True
    except OSError as exc:
        return False, str(exc), False


def handoff_to_launchd_supervision() -> tuple[bool, str]:
    """
    Start (or restart) the launchd-managed TaskForge job.

    Call release() on the instance lock before invoking this.
    """
    if sys.platform != "darwin":
        return False, "Crash recovery is only available on macOS."

    program_args = resolve_program_arguments()
    if not program_args:
        return False, "Could not determine how to launch TaskForge for crash recovery."

    try:
        _write_plist(program_args)

        if is_agent_loaded():
            managed = agent_pid()
            if managed == os.getpid():
                return True, ""
            if managed is not None and is_pid_running(managed):
                bootout = _run_launchctl(["bootout", _launchd_target()])
                if bootout.returncode != 0 and bootout.stderr.strip():
                    return False, bootout.stderr.strip()

            kick = _run_launchctl(["kickstart", _launchd_target()])
            if kick.returncode != 0:
                message = kick.stderr.strip() or "launchctl kickstart failed."
                return False, message
            return True, ""

        bootstrap = _run_launchctl(["bootstrap", _launchd_domain(), str(PLIST_PATH)])
        if bootstrap.returncode != 0:
            message = bootstrap.stderr.strip() or "launchctl bootstrap failed."
            return False, message

        _run_launchctl(["enable", _launchd_target()])
        return True, ""
    except OSError as exc:
        return False, str(exc)


def register_crash_recovery_plist() -> tuple[bool, str]:
    """Write the LaunchAgent plist without starting another TaskForge process."""
    ok, message, _needs_handoff = prepare_crash_recovery()
    if not ok:
        return False, message
    if message:
        return True, message
    return True, (
        "Background mode updated. Restart TaskForge once to enable crash recovery."
    )


def uninstall_crash_recovery_agent() -> tuple[bool, str]:
    if sys.platform != "darwin":
        return True, "Crash recovery disabled."

    try:
        if PLIST_PATH.exists():
            PLIST_PATH.unlink()

        if not is_agent_loaded():
            return True, "Crash recovery disabled."

        if is_supervised_by_launchd():
            # Removing the plist is enough; bootout would kill this running instance.
            return True, "Crash recovery disabled."

        bootout = _run_launchctl(["bootout", _launchd_target()])
        if bootout.returncode != 0 and bootout.stderr.strip():
            return False, bootout.stderr.strip()
        return True, "Crash recovery disabled."
    except OSError as exc:
        return False, str(exc)


def sync_crash_recovery_agent(enabled: bool) -> tuple[bool, str, bool]:
    """Sync crash recovery. Returns (ok, message, needs_handoff)."""
    if enabled:
        return prepare_crash_recovery()
    ok, message = uninstall_crash_recovery_agent()
    return ok, message, False
