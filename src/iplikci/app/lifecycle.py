"""The service's own life from the interface (ADR-0017, "Her iş arayüzde"): stopping it, restarting it, putting a
backup back and removing it from the computer.

The service ends its own process. A clean exit stays a stop until the next login or until the app is opened again;
the exit code RESTART asks the system's service manager to start it again, as launchd, systemd and the Windows task
restart only an unsuccessful exit. What must happen with the database closed waits in run/: a backup put back at the
next start, before anything opens the database, and the data folder moved to the Trash at the end of this run."""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from ..domain.codes import Actor
from ..service import manager
from ..settings.paths import write_private
from ..storage import audit
from ..storage import db as database
from ..vault.trash import move_to_system_trash
from . import backup, setup
from .workspace import Workspace

STOP = 0
RESTART = 75  # EX_TEMPFAIL: an unsuccessful exit, which the service managers answer by starting the service again
RESTORE_REQUEST = "geri-yukle.json"
REMOVAL_REQUEST = "kaldir.json"
REMOVED = "service.removed"  # the audit log's action
RESTORE_REQUESTED = "backup.restore_requested"

__all__ = ["RESTART", "STOP", "Actor", "Lifecycle", "LifecycleError", "Registration"]

log = logging.getLogger("iplikci.service")


class Lifecycle(Protocol):
    def end(self, code: int) -> None:
        """End the service once the responses being written are sent; the process exits with code."""
        ...


class LifecycleError(Exception):
    """The step cannot be taken here; the message says why (Turkish)."""


@dataclass(frozen=True, slots=True)
class Registration:
    registered: bool  # the system's service manager starts this data folder's service
    manager: str  # launchd, systemd, Görev Zamanlayıcı; "" on a system with none this program knows


def registration(ws: Workspace) -> Registration:
    try:
        name = manager.for_platform().name
    except manager.ManagerError:
        return Registration(False, "")
    home = setup.registered_home()
    return Registration(home is not None and home.resolve() == ws.home.resolve(), name)


def must_be_registered(ws: Workspace) -> None:
    """A restart comes from the service manager: a service run by hand (in the foreground) would only end."""
    if not registration(ws).registered:
        raise LifecycleError(
            "Servis bu bilgisayara bu veri klasörü için kayıtlı değil; ön planda çalışan servis yeniden başlatılamaz."
        )


def request_restore(ws: Workspace, name: str, actor: Actor) -> backup.Backup:
    """A backup of the backups folder to put back at the next start, by its name only (never a path a request makes
    up), checked now: a damaged one, or one of a newer version, is refused before the service ends. BackupError says
    why."""
    found = [b for b in backup.every(ws) if b.name == name]
    if not found:
        raise backup.BackupError(f"{name!r} adında bir yedek yok")
    chosen = found[0]
    problems = backup.verify(chosen)
    if problems:
        raise backup.BackupError(f"{chosen.name} yedeği bozuk: {'; '.join(problems[:3])}")
    if chosen.schema > database.schema_version():
        raise backup.BackupError(
            f"{chosen.name} daha yeni bir sürümle ({chosen.app}) alınmış; önce İplikçi Nedim'i güncelleyin"
        )
    write_private(
        ws.run / RESTORE_REQUEST,
        json.dumps({"backup": chosen.name, "requested_at": datetime.now(UTC).isoformat(timespec="seconds")}),
    )
    with ws.db() as db:
        audit.record(db, actor, RESTORE_REQUESTED, chosen.name)
    return chosen


def apply_pending_restore(ws: Workspace) -> backup.Restored | None:
    """Put back the backup a restore asked for, at the start, before anything opens the database. The request goes
    first, so a backup that fails is never tried again at every start; the failure is logged and the data stays as
    it was."""
    request = ws.run / RESTORE_REQUEST
    try:
        name = str(json.loads(request.read_text(encoding="utf-8"))["backup"])
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError):
        log.error("a restore request could not be read; it is dropped")
        request.unlink(missing_ok=True)
        return None
    request.unlink(missing_ok=True)
    try:
        restored = backup.restore(ws, backup.find(ws, name))
    except backup.BackupError as exc:
        log.error("the backup %s could not be put back: %s", name, exc)
        return None
    log.info("the backup %s was put back; the data before it is in %s", name, restored.safety)
    return restored


def remove(ws: Workspace, to_trash: bool, actor: Actor) -> bool:
    """Take the service off the computer's service manager (the running process ends after this response) and, when
    asked, have the data folder moved to the Trash once it has ended. Whether a registration was removed."""
    try:
        removed = manager.for_platform().unregister()
    except manager.ManagerError as exc:
        raise LifecycleError(str(exc)) from exc
    with ws.db() as db:
        audit.record(db, actor, REMOVED, ws.home.name, data_to_trash=to_trash)
    if to_trash:
        write_private(ws.run / REMOVAL_REQUEST, json.dumps({"data_to_trash": True}))
    return removed


def finish_removal(ws: Workspace) -> Path | None:
    """At the very end of the run: the data folder to the Trash, when the removal asked for it (never deleted,
    ADR-0003). Where it went, or None."""
    request = ws.run / REMOVAL_REQUEST
    if not request.is_file():
        return None
    request.unlink(missing_ok=True)
    moved = move_to_system_trash(ws.home)
    log.info("the data folder went to the Trash: %s", moved)
    return moved
