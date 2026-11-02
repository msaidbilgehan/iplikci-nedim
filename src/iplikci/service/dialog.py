"""The system's own windows, for what is done without a terminal (ADR-0017): a message in AppleScript's dialog on
macOS, the message box on Windows, zenity or kdialog on Linux (a notification where a desktop has neither), and a
folder in the system's file manager. The text goes as an argument, never into a script, so nothing in it can run.
Where nothing can be shown a message goes to stderr."""

import html
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from .manager import creation_flags

TITLE = "İplikçi Nedim"
_SCRIPT = (
    "on run argv",
    'display dialog (item 1 of argv) with title (item 2 of argv) buttons {"Tamam"} default button 1',
    "end run",
)

type Run = Callable[[Sequence[str]], int]


def _run(args: Sequence[str]) -> int:
    return subprocess.run(list(args), capture_output=True, check=False, creationflags=creation_flags()).returncode


def command(text: str, platform: str, which: Callable[[str], str | None] = shutil.which) -> list[str] | None:
    """The program that shows text in a window on this system; None where there is none."""
    if platform == "darwin":
        return ["osascript", *(part for line in _SCRIPT for part in ("-e", line)), text, TITLE]
    if platform.startswith("linux"):
        if which("zenity"):
            return ["zenity", "--info", f"--title={TITLE}", f"--text={text}", "--no-markup"]
        if which("kdialog"):
            return ["kdialog", "--title", TITLE, "--msgbox", text]
        if which("notify-send"):  # neither: a notification that stays until it is closed, its body read as markup
            return ["notify-send", "--urgency=critical", TITLE, html.escape(text, quote=False)]
    return None


if sys.platform == "win32":
    import ctypes

    def _message_box(text: str) -> None:
        ctypes.windll.user32.MessageBoxW(None, text, TITLE, 0x40)  # an information icon and an OK button

else:

    def _message_box(text: str) -> None:
        print(text, file=sys.stderr)


def say(text: str, platform: str = sys.platform, run: Run = _run) -> None:
    """Show text to the user and wait for them to close it."""
    if platform == "win32":
        _message_box(text)
        return
    found = command(text, platform)
    if found is None or run(found) != 0:
        print(text, file=sys.stderr)


def folder_command(path: Path, platform: str, which: Callable[[str], str | None] = shutil.which) -> list[str] | None:
    """The program that shows a folder in the system's file manager; None where there is none."""
    if platform == "darwin":
        return ["open", str(path)]
    if platform == "win32":
        return ["explorer", str(path)]
    if platform.startswith("linux") and which("xdg-open"):
        return ["xdg-open", str(path)]
    return None


def _start(args: Sequence[str]) -> int:
    """Start the file manager; some openers stay until its window closes, so a wait that runs out counts as shown."""
    try:
        done = subprocess.run(list(args), capture_output=True, check=False, timeout=10, creationflags=creation_flags())
        return done.returncode
    except subprocess.TimeoutExpired:
        return 0
    except OSError:
        return 1


def show_folder(path: Path, platform: str = sys.platform, run: Run | None = None) -> bool:
    """Open path in the system's file manager; whether it could be shown. A service without a desktop session (a
    Linux user unit started before the desktop) cannot show it, and the interface gives the path to type instead."""
    found = folder_command(path, platform)
    if found is None:
        return False
    code = (run or _start)(found)
    return platform == "win32" or code == 0  # Explorer answers 1 even when the folder opened
