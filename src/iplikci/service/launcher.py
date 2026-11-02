"""What opening the app does (ADR-0017): the copy the installer put on the computer registers the background service
for the data folder, starts it when it is not running, restarts it when it runs an older version, and gives a
one-time login link for the browser; on the first run the interface opens the setup wizard by itself. Nothing here
needs a terminal: a problem is said in the system's own window (dialog.py)."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .. import __version__
from ..app.workspace import Workspace
from . import client, instance
from .manager import Program, ServiceManager, installed_program

WAIT_SECONDS = 45.0  # how long the service may take to answer after it was started: its first start makes the folder
_PAUSE = 0.25


class LaunchError(Exception):
    """The app could not be opened; the message says why and what to do, for the user (Turkish)."""


@dataclass(frozen=True, slots=True)
class Opened:
    url: str  # the one-time login link
    registered: bool  # the service was registered now (a first run, a new place or another data folder before)
    restarted: bool  # the service was started now, or restarted for this version


def misplaced(executable: Path, platform: str) -> str | None:
    """Why this copy may not register the service from where it runs, for the user; None when its place lasts. The
    service starts the Python it was registered with at every login, so that path must stay: not a disk image's,
    and not the random place macOS runs a downloaded app from until it is moved (App Translocation)."""
    text = executable.as_posix()
    if platform == "darwin" and (text.startswith("/Volumes/") or "/AppTranslocation/" in text):
        return (
            "İplikçi Nedim'i önce Uygulamalar klasörüne taşıyın, sonra oradan açın. Disk görüntüsünden ya da "
            "indirildiği yerden açılan uygulama her açılışta başka bir yerde çalışır; arka plan servisi onu bulamaz."
        )
    return None


def _same_copy(registered: Program | None, program: Program) -> bool:
    """The registration runs this copy for this data folder (Windows registers pythonw beside the python)."""
    if registered is None:
        return False
    return registered.python.parent == program.python.parent and registered.home == program.home


def open_app(
    ws: Workspace,
    service: ServiceManager,
    platform: str,
    executable: Path,
    *,
    healthy: Callable[[int], bool] = client.healthy,
    login: Callable[[Workspace], str] | None = None,
    wait: float = WAIT_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> Opened:
    """Make sure the service of this data folder runs this copy, then a login link. LaunchError, ManagerError (the
    service manager refused) and DevelopmentCopy say why it could not."""
    why = misplaced(executable, platform)
    if why is not None:
        raise LaunchError(why)
    program = installed_program(ws.home)  # DevelopmentCopy from a development folder: it never registers
    registered = not _same_copy(service.registered(), program)
    holder = instance.current(ws.run)
    restarted = False
    if registered:
        service.install(program)  # replaces an older registration and starts the service
        restarted = True
    elif holder is None or (holder.version and holder.version != __version__):
        service.restart()  # not running (stopped, or not started at this login), or an older version still runs
        restarted = True
    deadline = time.monotonic() + wait
    while not healthy(ws.port):
        if time.monotonic() > deadline:
            raise LaunchError(
                "Arka plan servisi başlatıldı ama yanıt vermedi. Birkaç saniye sonra uygulamayı yeniden açın; "
                f"sorun sürerse günlüğe bakın: {ws.layout.logs}"
            )
        sleep(_PAUSE)
    return Opened((login or _login_link)(ws), registered, restarted)


def _login_link(ws: Workspace) -> str:
    try:
        return str(client.call(ws, "POST", "/api/login-links")["url"])
    except client.ServiceError as exc:
        raise LaunchError(f"Arayüz için giriş bağlantısı alınamadı: {exc}.") from exc
