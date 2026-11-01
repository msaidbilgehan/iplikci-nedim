"""What the commands share: the data folder they work on, progress on the terminal, and how they write times,
sizes and days."""

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

from ..app.workspace import Workspace
from ..settings.config import SettingsError


def open_workspace(parser: argparse.ArgumentParser, home: Path | None = None) -> Workspace:
    try:
        return Workspace.load(home)
    except (OSError, SettingsError) as exc:
        parser.error(str(exc))


def show_progress(i: int, n: int, name: str) -> None:
    if sys.stderr.isatty():
        print(f"\r  belgeler okunuyor {i}/{n}", end="", file=sys.stderr, flush=True)


def clear_progress() -> None:
    if sys.stderr.isatty():
        print("\r" + " " * 60 + "\r", end="", file=sys.stderr)


def local_time(iso: str) -> str:
    """An ISO time in the computer's time zone, as Turkish readers write it."""
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return iso


def human_size(n: int) -> str:
    """A byte count in the largest unit under 1024 of it, with a decimal comma."""
    value, unit = float(n), "B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            break
        value /= 1024
    return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}".replace(".", ",")


def day_arg(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"tarih YYYY-AA-GG biçiminde olmalı: {text!r}") from None
