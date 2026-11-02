"""The data folder and its layout (ADR-0002, architecture §9).

Every piece of personal data lives in one folder outside the repository: the platform's application data
folder, or IPLIKCI_HOME when it is set (the tests and the demo workspace use that). The folder is private to
the user (0700) and so are its files (0600).
"""

import os
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

HOME_ENV = "IPLIKCI_HOME"
APP = "iplikci"
FOLDER_MODE = 0o700
FILE_MODE = 0o600


def data_dir(env: Mapping[str, str] | None = None, platform: str | None = None) -> Path:
    """IPLIKCI_HOME when it is set, else the platform's folder for application data (ADR-0002)."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    given = env.get(HOME_ENV, "").strip()
    if given:
        return Path(given).expanduser()
    if platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP
    if platform.startswith("win"):
        return Path(env.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / APP
    return Path(env.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / APP


@dataclass(frozen=True, slots=True)
class Layout:
    """The paths inside a data folder."""

    home: Path

    @classmethod
    def default(cls) -> "Layout":
        return cls(data_dir())

    @property
    def settings(self) -> Path:
        return self.home / "settings.toml"

    @property
    def database(self) -> Path:
        return self.home / "iplikci.db"

    @property
    def vault(self) -> Path:
        return self.home / "vault"

    @property
    def objects(self) -> Path:
        """The originals, by content: objects/ab/cd/<sha256>, read-only (ADR-0003)."""
        return self.vault / "objects"

    @property
    def staging(self) -> Path:
        """Documents being read before they are kept; never permanent."""
        return self.vault / "staging"

    @property
    def derived(self) -> Path:
        """Page images, text and word boxes made from the originals; can be made again at any time."""
        return self.vault / "derived"

    @property
    def rules(self) -> Path:
        return self.home / "rules"

    @property
    def personal_rules(self) -> Path:
        """The user's category rules and decisions; they go above the rules shipped with the app."""
        return self.rules / "personal.yaml"

    @property
    def alert_rules(self) -> Path:
        return self.rules / "alerts.yaml"

    @property
    def rules_history(self) -> Path:
        """Every rule file as it was before a change."""
        return self.rules / "history"

    @property
    def inbox(self) -> Path:
        return self.home / "inbox"

    @property
    def exports(self) -> Path:
        return self.home / "exports"

    @property
    def backups(self) -> Path:
        return self.home / "backups"

    @property
    def logs(self) -> Path:
        return self.home / "logs"

    @property
    def run(self) -> Path:
        """Locks and what a running process tells the others."""
        return self.home / "run"

    @property
    def baseline(self) -> Path:
        """The verification baseline of the documents in this folder (docs/domain/ledger.md)."""
        return self.home / "baseline.json"

    @property
    def extension(self) -> Path:
        """The browser extension's files, loaded unpacked by the browser from here (K20); made when the user asks."""
        return self.home / "extension"

    def ensure(self) -> None:
        """Create the folder and its subfolders, private to the user. The MVP's archive (archive/mvp) is
        never created or touched here."""
        self.home.mkdir(parents=True, exist_ok=True)
        _private(self.home)
        for folder in (
            self.objects,
            self.staging,
            self.derived,
            self.rules_history,
            self.inbox,
            self.exports,
            self.backups,
            self.logs,
            self.run,
        ):
            folder.mkdir(parents=True, exist_ok=True)
            _private(folder)
        for parent in (self.vault, self.rules):
            _private(parent)


def write_private(path: Path, text: str) -> None:
    """Write a text file only the user can read (0600), as every file in the data folder is."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, FILE_MODE)
    if hasattr(os, "fchmod"):  # an older file keeps its mode on open; Windows has no such modes
        os.fchmod(fd, FILE_MODE)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


def replace_private(path: Path, text: str) -> None:
    """Put text in place of the file at path at once (0600): written beside it under a name of its own, then moved
    over it, so a reader sees the old file or the new one, never half of one."""
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".yeni")
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, FILE_MODE)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def _private(folder: Path) -> None:
    if sys.platform != "win32":  # Windows keeps a user's AppData private through its own permissions
        os.chmod(folder, FOLDER_MODE)
