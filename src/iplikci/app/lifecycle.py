"""The service's own life from the interface (ADR-0017, "Her iş arayüzde"): stopping it, restarting it, putting a
backup back and removing it from the computer.

The service ends its own process. A clean exit stays a stop until the next login or until the app is opened again;
the exit code RESTART starts it again: launchd and systemd restart an unsuccessful exit, and on Windows, whose task
does not, a detached helper runs the task again once this process has ended (service/respawn). What must happen with the database closed waits in run/: a backup put back at the
next start, before anything opens the database, and the data folder moved to the Trash once this run has let go of
it. A removal request only this run's stop honours: one an earlier run left behind is dropped."""

import json
import logging
from dataclasses import asdict, dataclass
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
RESTORE_OUTCOME = "geri-yukleme-sonucu.json"  # how the last restore went, for the interface that asked for it
REMOVAL_REQUEST = "kaldir.json"
REMOVED = "service.removed"  # the audit log's action
RESTORE_REQUESTED = "backup.restore_requested"

__all__ = ["RESTART", "STOP", "Actor", "Lifecycle", "LifecycleError", "NotRegistered", "Registration", "RestoreOutcome"]

log = logging.getLogger("iplikci.service")


class Lifecycle(Protocol):
    def end(self, code: int) -> None:
        """End the service once the responses being written are sent; the process exits with code."""
        ...

    def ending(self) -> bool:
        """Whether the service is stopping, asked to here or by the system: an event stream ends rather than hold
        the stop up."""
        ...


class LifecycleError(Exception):
    """The step cannot be taken here; the message says why (Turkish)."""


class NotRegistered(LifecycleError):
    """The computer's service manager does not start this data folder's service: it runs by hand."""


@dataclass(frozen=True, slots=True)
class RestoreOutcome:
    backup: str
    ok: bool
    error: str  # why it could not be done (Turkish); "" when it was
    at: str  # when the start put it back or gave up, ISO 8601


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


def must_be_registered(ws: Workspace, step: str = "ön planda çalışan servis yeniden başlatılamaz") -> None:
    """Restarting and putting a backup back need the service manager, which starts the service again: a service run
    by hand (in the foreground) would only end. Removing needs it too, as the manager knows one registration."""
    if not registration(ws).registered:
        raise NotRegistered(f"Servis bu bilgisayara bu veri klasörü için kayıtlı değil; {step}.")


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
    first, so a backup that fails is never tried again at every start; the failure is logged, the data stays as it
    was (backup.restore puts back what was there when it stops half way) and the outcome waits in run/ for the
    interface that asked."""
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
    except (backup.BackupError, OSError) as exc:  # OSError: the backup before it could not be made, a full disk
        log.error("the backup %s could not be put back: %s", name, exc)
        _say_restored(ws, RestoreOutcome(name, False, str(exc), _now()))
        return None
    log.info("the backup %s was put back; the data before it is in %s", name, restored.safety)
    _say_restored(ws, RestoreOutcome(name, True, "", _now()))
    return restored


def last_restore(ws: Workspace) -> RestoreOutcome | None:
    """How the last restore went, as the start that tried it wrote it; None before any."""
    try:
        found = json.loads((ws.run / RESTORE_OUTCOME).read_text(encoding="utf-8"))
        return RestoreOutcome(str(found["backup"]), bool(found["ok"]), str(found["error"]), str(found["at"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _say_restored(ws: Workspace, outcome: RestoreOutcome) -> None:
    write_private(ws.run / RESTORE_OUTCOME, json.dumps(asdict(outcome), ensure_ascii=False))


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def remove(ws: Workspace, to_trash: bool, actor: Actor) -> bool:
    """Take the service off the computer's service manager (the running process ends after this response) and, when
    asked, have the data folder moved to the Trash once it has ended. Whether a registration was removed.

    Only this data folder's registered service removes itself: the manager knows one registration, and a service run
    by hand on another folder (a demo, a development copy) would take off the one the computer starts."""
    must_be_registered(ws, "kaldırmak, bilgisayarın başlattığı başka bir servisin kaydını silerdi")
    try:
        removed = manager.for_platform().unregister()
    except manager.ManagerError as exc:
        raise LifecycleError(str(exc)) from exc
    with ws.db() as db:
        audit.record(db, actor, REMOVED, ws.home.name, data_to_trash=to_trash)
    if to_trash:
        write_private(ws.run / REMOVAL_REQUEST, json.dumps({"data_to_trash": True}))
    return removed


def drop_stale_removal(ws: Workspace) -> bool:
    """At the start: a removal an earlier run asked for but could not finish (it ended on an error before its stop)
    is dropped, never honoured later. The user has opened the app again since, and a restart would otherwise take the
    data folder to the Trash. Whether one was dropped."""
    request = ws.run / REMOVAL_REQUEST
    if not request.is_file():
        return False
    request.unlink(missing_ok=True)
    log.warning("a removal an earlier run could not finish is dropped; the data folder stays")
    return True


def removal_asked(ws: Workspace, code: int) -> bool:
    """At the end of the run: whether this run's removal asked for the data folder to go to the Trash. Only the stop
    that removal ends the service with honours it; the request goes either way."""
    request = ws.run / REMOVAL_REQUEST
    if not request.is_file():
        return False
    request.unlink(missing_ok=True)
    return code == STOP


def move_data_to_trash(ws: Workspace) -> Path | None:
    """The data folder to the Trash (never deleted, ADR-0003), once the service has let go of it: its lock, its log
    and its output file closed, which Windows needs to move a folder. Where it went, or None when it stayed."""
    moved = move_to_system_trash(ws.home)
    return None if moved == ws.home and ws.home.exists() else moved
