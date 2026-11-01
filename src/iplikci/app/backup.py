"""Backups and their restore (architecture §19, F20).

A backup is a folder under backups/ (or the folder the settings name) holding a consistent copy of the database made
through SQLite's online backup API, the primary data dumped from that copy as JSON (what nothing else knows: names and
arrivals, the user's corrections, the audit and event logs), the settings and the rule files, and a manifest with the
sha256 of each. The originals never change, so each is copied once into the backups' own object store
(backups/vault/objects) and every manifest lists the ones it needs. A backup is made in a hidden folder and renamed
when complete: a folder with a manifest is a whole backup.

The service makes one a day. Backups are kept for keep_days days (14) and the newest is always kept. An expired backup
is deleted outright, and so is an object no kept backup needs: they are copies this program made, never the only copy
of a document (the vault keeps the originals; a removed document went to the system Trash).

A restore puts a backup's database, settings and rules back and copies back the originals the archive lacks; in
place, it first backs up what is there, so it can be undone. Once a month the newest backup is restored into a
temporary folder and checked the way `iplikci dogrula --arsiv` and `--yeniden-kur` check the data folder.
"""

import hashlib
import json
import logging
import os
import shutil
import stat
import sys
import tempfile
from collections.abc import Callable, Iterable
from contextlib import closing
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from .. import __version__
from ..domain.codes import Actor, BackupReason
from ..settings import config
from ..settings.paths import Layout, write_private
from ..storage import audit, documents
from ..storage import db as database
from ..vault.store import Vault, VaultError
from . import checks, rebuild
from .workspace import Workspace, file_lock

FORMAT = "iplikci-yedek"
VERSION = 1
PREFIX = "yedek "
MANIFEST = "manifest.json"
DATABASE = "iplikci.db"
PRIMARY = "birincil.json"
SETTINGS = "settings.toml"
RULES = "rules"
LAST_REHEARSAL = "son-prova.json"
FAILED = "backup.failed"  # the system event (architecture §13): told once a day, or once a month for a rehearsal
DAILY_AT = time(3, 30)  # local time; a sleeping computer makes the day's backup when it wakes
_LOCK = ".yedek-kilit"
_WORK = ".yedek-"
_CHUNK = 1 << 20

log = logging.getLogger("iplikci.backup")


class BackupError(Exception):
    """A backup cannot be made, read or restored; the message says why (Turkish)."""


@dataclass(frozen=True, slots=True)
class Backup:
    name: str
    path: Path
    created_at: str  # UTC, ISO 8601
    reason: BackupReason
    app: str  # the version that made it
    schema: int  # the database's newest migration
    documents: int
    annotations: int
    files: dict[str, tuple[str, int]]  # path inside the backup -> (sha256, size)
    objects: tuple[str, ...]  # the originals it needs from the store
    damaged: tuple[str, ...] = ()  # originals left out because their bytes no longer matched their names

    @property
    def size(self) -> int:
        """Bytes of its own files; the originals live in the shared store."""
        return sum(size for _, size in self.files.values())


@dataclass(frozen=True, slots=True)
class Restored:
    backup: str
    home: Path
    objects: int  # originals copied back into the archive
    safety: str  # the backup of what was there before, when restored in place; "" otherwise
    unknown: int  # originals in the archive that the restored database does not know (kept after the backup)


@dataclass(frozen=True, slots=True)
class Rehearsal:
    backup: str
    at: str
    problems: list[str] = field(default_factory=list[str])  # what the archive check found in the restored copy
    differences: list[str] = field(default_factory=list[str])  # what the rebuild check found

    @property
    def ok(self) -> bool:
        return not (self.problems or self.differences)


@dataclass(frozen=True, slots=True)
class Health:
    """The backups as the System screen shows them (F18)."""

    last: str  # when the newest was made; "" if none yet
    next: str  # when the next daily one is due
    count: int
    size: int  # bytes all of them take, the store included
    rehearsal: str  # when the last rehearsal ran; "" if never
    rehearsal_ok: bool | None


def folder(ws: Workspace) -> Path:
    """Where the backups go: the settings' folder, else backups/ in the data folder. The settings as the file says
    now."""
    configured = config.load(ws.layout.settings).backup.folder
    return Path(configured).expanduser() if configured else ws.layout.backups


def _store(root: Path) -> Vault:
    """The backups' own object store, laid out as the vault: root/vault/objects/ab/cd/<sha256>."""
    return Vault(Layout(root))


# --- making one ------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Contents:
    schema: int
    documents: int
    annotations: int
    objects: tuple[str, ...]
    damaged: tuple[str, ...]


def take(ws: Workspace, reason: BackupReason = BackupReason.DAILY, now: datetime | None = None) -> Backup:
    """Back up the data folder now; the backup made. One backup is made at a time."""
    at = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    root = folder(ws)
    root.mkdir(parents=True, exist_ok=True)
    with file_lock(ws.run, _LOCK, timeout=600.0, busy="başka bir yedek alınıyor; biraz sonra yeniden deneyin"):
        final = _free_name(root, f"{PREFIX}{at.astimezone():%Y-%m-%d %H.%M.%S}")
        work = Path(tempfile.mkdtemp(prefix=_WORK, dir=root))
        try:
            contents = _fill(ws, work, _store(root))
            backup = Backup(
                name=final.name,
                path=final,
                created_at=at.isoformat(),
                reason=reason,
                app=__version__,
                schema=contents.schema,
                documents=contents.documents,
                annotations=contents.annotations,
                files={_relative(path, work): (_sha256(path), path.stat().st_size) for path in _files(work)},
                objects=contents.objects,
                damaged=contents.damaged,
            )
            write_private(work / MANIFEST, _manifest(backup))  # last: a folder with a manifest is a whole backup
            os.rename(work, final)
        finally:
            if work.exists():
                _delete(work)  # our own half-made copy
    log.info("backup made: %d documents, %d originals", backup.documents, len(backup.objects))
    return backup


def _free_name(root: Path, name: str) -> Path:
    """name, or name (2), (3)… when a backup made in the same second has it (the one before a restore)."""
    path, n = root / name, 1
    while path.exists():
        n += 1
        path = root / f"{name} ({n})"
    return path


def _fill(ws: Workspace, work: Path, store: Vault) -> _Contents:
    """The database copy, its primary data, the settings and the rules into work, and the originals into store."""
    with ws.db() as live:
        database.backup(live, work / DATABASE)
    with closing(database.open_copy(work / DATABASE)) as copy:
        primary = rebuild.export(copy)  # from the copy: the dump and the database tell the same moment
        schema = max(database.applied(copy))
    write_private(work / PRIMARY, rebuild.dump(primary))
    if ws.layout.settings.is_file():
        _copy_file(ws.layout.settings, work / SETTINGS)
    for source in _files(ws.layout.rules):
        _copy_file(source, work / RULES / source.relative_to(ws.layout.rules))
    objects, damaged = _keep_originals(ws.vault, store)
    return _Contents(schema, len(primary.documents), len(primary.annotations), objects, damaged)


def _keep_originals(vault: Vault, store: Vault) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Copy into the store the originals it lacks; (all the archive holds, those too damaged to copy)."""
    kept: list[str] = []
    damaged: list[str] = []
    for sha256 in vault.objects():
        try:
            store.adopt(vault.path(sha256), sha256)
        except VaultError:
            log.error("an original no longer matches its name; it was left out of the backup")
            damaged.append(sha256)
            continue
        kept.append(sha256)
    return tuple(kept), tuple(damaged)


# --- reading them --------------------------------------------------------------------------------------


def every(ws: Workspace) -> list[Backup]:
    """The whole backups, newest first; a folder whose manifest cannot be read is left out."""
    root = folder(ws)
    if not root.is_dir():
        return []
    found: list[Backup] = []
    for path in root.iterdir():
        if not (path.is_dir() and path.name.startswith(PREFIX)):
            continue
        try:
            found.append(_read(path))
        except BackupError:
            log.warning("a backup's manifest could not be read")
    return sorted(found, key=lambda b: b.created_at, reverse=True)


def find(ws: Workspace, given: str) -> Backup:
    """A backup by its name, or by the path of its folder."""
    path = Path(given).expanduser()
    if not path.is_dir():
        path = folder(ws) / given
    if not path.is_dir():
        names = ", ".join(b.name for b in every(ws)[:3]) or "henüz yedek yok"
        raise BackupError(f"{given!r} adında bir yedek yok (son yedekler: {names})")
    return _read(path)


def _read(path: Path) -> Backup:
    try:
        value: dict[str, Any] = json.loads((path / MANIFEST).read_text(encoding="utf-8"))
        if value.get("format") != FORMAT or value.get("version") != VERSION:
            raise BackupError(f"{path.name} bir {FORMAT} sürüm {VERSION} yedeği değil")
        return Backup(
            name=path.name,
            path=path,
            created_at=str(value["created_at"]),
            reason=BackupReason(value["reason"]),
            app=str(value["app"]),
            schema=int(value["schema"]),
            documents=int(value["documents"]),
            annotations=int(value["annotations"]),
            files={str(name): (str(sha), int(size)) for name, (sha, size) in value["files"].items()},
            objects=tuple(str(sha) for sha in value["objects"]),
            damaged=tuple(str(sha) for sha in value.get("damaged", [])),
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise BackupError(f"{path.name} yedeğinin listesi okunamadı: {exc}") from exc


def _manifest(backup: Backup) -> str:
    value = asdict(backup)
    for key in ("name", "path"):
        value.pop(key)  # the folder says them
    value["files"] = {name: list(entry) for name, entry in backup.files.items()}
    return json.dumps({"format": FORMAT, "version": VERSION} | value, ensure_ascii=False, indent=1, sort_keys=True)


def verify(backup: Backup) -> list[str]:
    """What is wrong with a backup: a file changed or missing, an original missing from the store beside it (the
    originals' bytes are checked as they are copied back)."""
    problems: list[str] = []
    for name, (sha256, size) in backup.files.items():
        path = backup.path / name
        if not path.is_file():
            problems.append(f"{name} yok")
        elif path.stat().st_size != size or _sha256(path) != sha256:
            problems.append(f"{name} değişmiş")
    store = _store(backup.path.parent)
    missing = [sha for sha in backup.objects if not store.has(sha)]
    if missing:
        problems.append(f"{len(missing)} belgenin aslı yedek deposunda yok")
    return problems


def health(ws: Workspace, now: datetime | None = None) -> Health:
    now = now or datetime.now(UTC)
    backups = every(ws)
    last = backups[0].created_at if backups else ""
    root = folder(ws)
    size = sum(path.stat().st_size for path in _files(root)) if root.is_dir() else 0
    rehearsal = _last_rehearsal(root)
    return Health(
        last=last,
        next=next_due(datetime.fromisoformat(last) if last else None, now).isoformat(),
        count=len(backups),
        size=size,
        rehearsal=rehearsal.at if rehearsal else "",
        rehearsal_ok=rehearsal.ok if rehearsal else None,
    )


def next_due(last: datetime | None, now: datetime) -> datetime:
    """When the next daily backup is due: at once when none was made since the last DAILY_AT, else at the next."""
    local = now.astimezone()
    start = datetime.combine(local.date(), DAILY_AT, local.tzinfo)
    if local < start:
        start -= timedelta(days=1)
    if last is None or last < start:
        return now.astimezone(UTC).replace(microsecond=0)
    return (start + timedelta(days=1)).astimezone(UTC)


# --- keeping 14 days ------------------------------------------------------------------------------------


def prune(ws: Workspace, now: datetime | None = None) -> list[str]:
    """Delete the backups older than keep_days days (the newest always stays), the originals no kept backup needs,
    and half-made backups a stop left behind; the names of the backups deleted."""
    now = now or datetime.now(UTC)
    root = folder(ws)
    keep_days = config.load(ws.layout.settings).backup.keep_days
    cutoff = (now - timedelta(days=keep_days)).astimezone(UTC).isoformat()
    with file_lock(ws.run, _LOCK, timeout=600.0, busy="başka bir yedek alınıyor; biraz sonra yeniden deneyin"):
        backups = every(ws)
        expired = [b for b in backups[1:] if b.created_at < cutoff]
        for b in expired:
            _delete(b.path)
        gone = {b.name for b in expired}
        needed = {sha for b in backups if b.name not in gone for sha in b.objects}
        store = _store(root)
        for sha256 in list(store.objects()):
            if sha256 not in needed:
                _delete(store.path(sha256))
        for half in root.glob(f"{_WORK}*") if root.is_dir() else ():
            if half.stat().st_mtime < now.timestamp() - 24 * 3600:
                _delete(half)
    if expired:
        log.info("%d expired backups deleted", len(expired))
    return [b.name for b in expired]


# --- restoring --------------------------------------------------------------------------------------------


def restore(ws: Workspace, backup: Backup, target: Path | None = None, actor: Actor = Actor.USER) -> Restored:
    """Put a backup back: in place (target None), after backing up what is there, or into target, a new or empty
    folder. In place, nothing else may have the database open: the service is stopped first."""
    problems = verify(backup)
    if problems:
        raise BackupError(f"{backup.name} yedeği bozuk: {'; '.join(problems[:3])}")
    if backup.schema > database.schema_version():
        raise BackupError(
            f"{backup.name} daha yeni bir sürümle ({backup.app}) alınmış; önce İplikçi Nedim'i güncelleyin"
        )
    store = _store(backup.path.parent)  # a backup copied elsewhere brings its store along
    if target is None:
        layout, safety = ws.layout, take(ws, BackupReason.BEFORE_RESTORE).name
        with ws.lock():
            _put_back(backup, layout)
            copied = _originals_back(store, backup, Vault(layout))
    else:
        if target.exists() and any(target.iterdir()):
            raise BackupError(f"{target} boş değil; yedek boş ya da yeni bir klasöre geri yüklenir")
        layout, safety = Layout(target.resolve()), ""
        layout.ensure()
        _put_back(backup, layout)
        copied = _originals_back(store, backup, Vault(layout))
    # Opened once through the migrations: a backup of an older version comes up to date here.
    with closing(database.connect(layout.database, layout.backups)) as restored:
        audit.record(restored, actor, "backup.restored", backup.name, safety=safety)
        known = {d.sha256 for d in documents.every(restored)}
    unknown = sum(1 for sha in Vault(layout).objects() if sha not in known)
    log.info("backup restored: %d originals copied back, %d not in its database", copied, unknown)
    return Restored(backup.name, layout.home, copied, safety, unknown)


def _put_back(backup: Backup, layout: Layout) -> None:
    """The database, the settings and the rule files of a backup into a data folder, each replaced whole. The
    database's -wal and -shm files belong to the database replaced: they go with it."""
    for side in ("-wal", "-shm"):
        layout.database.with_name(layout.database.name + side).unlink(missing_ok=True)
    _replace(backup.path / DATABASE, layout.database)
    if (backup.path / SETTINGS).is_file():
        _replace(backup.path / SETTINGS, layout.settings)
    for source in _files(backup.path / RULES):
        _replace(source, layout.rules / source.relative_to(backup.path / RULES))


def _originals_back(store: Vault, backup: Backup, vault: Vault) -> int:
    return sum(vault.adopt(store.path(sha), sha) for sha in backup.objects)


# --- the monthly rehearsal --------------------------------------------------------------------------------


def rehearse(ws: Workspace, backup: Backup | None = None, today: date | None = None) -> Rehearsal:
    """Restore a backup (the newest by default) into a temporary folder and check it as `dogrula --arsiv` and
    `--yeniden-kur` check the data folder; the result is kept for the System screen."""
    chosen = backup or next(iter(every(ws)), None)
    if chosen is None:
        raise BackupError("henüz yedek yok")
    at = datetime.now(UTC).replace(microsecond=0).isoformat()
    with tempfile.TemporaryDirectory(prefix=".prova-", dir=ws.run) as scratch:
        try:
            restored = restore(ws, chosen, Path(scratch) / "veri", Actor.SYSTEM)
        except (BackupError, VaultError) as exc:  # the backup cannot be restored: what the rehearsal is for
            result = Rehearsal(chosen.name, at, [str(exc)])
        else:
            # Built as is, not loaded: loading would make the copy's company names the running service's.
            copy = Workspace(Layout(restored.home), config.load(Layout(restored.home).settings))
            archive = checks.archive(copy)
            problems = [f"bozulmuş belge: {sha}" for sha in archive.integrity.corrupt]
            problems += [f"arşivde olmayan belge: {sha}" for sha in archive.missing]
            problems += [f"veritabanı: {text}" for text in archive.database]
            result = Rehearsal(chosen.name, at, problems, rebuild.check(copy, today=today).differences)
    write_private(folder(ws) / LAST_REHEARSAL, json.dumps(asdict(result), ensure_ascii=False, indent=1))
    return result


def _last_rehearsal(root: Path) -> Rehearsal | None:
    try:
        value: dict[str, Any] = json.loads((root / LAST_REHEARSAL).read_text(encoding="utf-8"))
        return Rehearsal(
            str(value["backup"]),
            str(value["at"]),
            [str(p) for p in value["problems"]],
            [str(d) for d in value["differences"]],
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


# --- files ------------------------------------------------------------------------------------------------


def _files(root: Path) -> Iterable[Path]:
    """Every file under root, in name order; none when root is missing."""
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if sys.platform != "win32":
        os.chmod(target, 0o600)


def _replace(source: Path, target: Path) -> None:
    """Copy source over target in one step: a reader sees the old file or the new one, never half of it."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.geri-yukleniyor")
    _copy_file(source, temporary)
    os.replace(temporary, target)


def _delete(path: Path) -> None:
    """Delete a backup's own file or folder outright; read-only originals included (Windows refuses those)."""

    def writable_again(function: Callable[..., Any], failed: str, _exc: BaseException) -> None:
        os.chmod(failed, stat.S_IWRITE)
        function(failed)

    if path.is_dir():
        shutil.rmtree(path, onexc=writable_again)
    elif path.exists():
        if sys.platform == "win32":
            os.chmod(path, stat.S_IWRITE)
        path.unlink()
