"""A message in the system's own window, for the app opened without a terminal (ADR-0017): AppleScript's dialog on
macOS, the message box on Windows, zenity or kdialog on Linux. The text goes as an argument, never into a script, so
nothing in it can run. Where no window can be shown it goes to stderr."""

import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence

TITLE = "İplikçi Nedim"
_SCRIPT = (
    "on run argv",
    'display dialog (item 1 of argv) with title (item 2 of argv) buttons {"Tamam"} default button 1',
    "end run",
)

type Run = Callable[[Sequence[str]], int]


def _run(args: Sequence[str]) -> int:
    return subprocess.run(list(args), capture_output=True, check=False).returncode


def command(text: str, platform: str, which: Callable[[str], str | None] = shutil.which) -> list[str] | None:
    """The program that shows text in a window on this system; None where there is none."""
    if platform == "darwin":
        return ["osascript", *(part for line in _SCRIPT for part in ("-e", line)), text, TITLE]
    if platform.startswith("linux"):
        if which("zenity"):
            return ["zenity", "--info", f"--title={TITLE}", f"--text={text}", "--no-markup"]
        if which("kdialog"):
            return ["kdialog", "--title", TITLE, "--msgbox", text]
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
