"""Which computer this is, to tell a data folder copied to another computer (macOS's Migration Assistant, a restore
onto a new disk) from the one that made it. Two computers using one id would both write into one part of the sync
folder; the copy takes a new id instead (ADR-0025). Only a digest of the system's own machine id is kept, never the id."""

import functools
import hashlib
import platform
import re
import subprocess
import sys
import uuid
from pathlib import Path

_IOREG = re.compile(r'"IOPlatformUUID"\s*=\s*"([^"]+)"')


def _mac() -> str:
    try:
        out = subprocess.run(
            ["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    found = _IOREG.search(out)
    return found[1] if found else ""


def _linux() -> str:
    for path in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
        try:
            text = path.read_text(encoding="ascii").strip()
        except OSError:
            continue
        if text:
            return text
    return ""


def _windows() -> str:
    if sys.platform != "win32":
        return ""
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
    except OSError:
        return ""
    return str(value)


@functools.cache
def fingerprint() -> str:
    """A digest of this computer's machine id (the network card's address and the computer's name when the system
    gives none)."""
    if sys.platform == "darwin":
        raw = _mac()
    elif sys.platform == "win32":
        raw = _windows()
    else:
        raw = _linux()
    if not raw:
        raw = f"{uuid.getnode():012x}|{platform.node()}"
    return hashlib.sha256(f"iplikci|{raw}".encode()).hexdigest()[:16]


def computer_name() -> str:
    """The name the computer goes by, for the user to tell their computers apart ("MacBook Pro"); "" if none."""
    if sys.platform == "darwin":
        try:
            out = subprocess.run(
                ["/usr/sbin/scutil", "--get", "ComputerName"], capture_output=True, text=True, timeout=5, check=False
            )
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    name = platform.node().split(".")[0]
    return name.removesuffix("-local")
