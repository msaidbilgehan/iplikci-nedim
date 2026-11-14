"""What opening the app does (ADR-0017): the copy the installer put on the computer registers the background service
for the data folder, starts it when it is not running, restarts it when it runs an older version, and gives a
one-time login link for the browser; on the first run the interface opens the setup wizard by itself. Nothing here
needs a terminal: a problem is said in the system's own window (dialog.py)."""

import os
import shutil
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

from .. import __version__
from ..app.workspace import Workspace
from ..settings import locks
from ..storage import db as database
from ..update.install import Kind, detect
from ..versions import newer, version_key
from . import client, desktop, instance
from .manager import Program, ServiceManager, installed_program

WAIT_SECONDS = 45.0  # how long the service may take to answer after it was started: its first start makes the folder
LOCK_NAME = "uygulama.kilit"  # in run/: one opening of the app at a time for a data folder
LOCK_MARGIN = 15.0  # an opening waits for the one before it as long as that may take, and this much longer
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
    and not the random place macOS runs a downloaded app from until it is moved (App Translocation). An Applications
    folder on another disk lasts as /Applications does. The app's own executable tells the same with the same
    patterns before its Python runs (packaging/build.py)."""
    text = executable.as_posix()
    if platform != "darwin":
        return None
    on_a_volume = fnmatchcase(text, "/Volumes/*") and not fnmatchcase(text, "/Volumes/*/Applications/*")
    if on_a_volume or fnmatchcase(text, "*/AppTranslocation/*"):
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
    serving: Callable[[Path], instance.Holder | None] = instance.current,
    login: Callable[[Workspace], str] | None = None,
    wait: float = WAIT_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> Opened:
    """Make sure the service of this data folder runs this copy, then a login link. LaunchError, ManagerError (the
    service manager refused) and DevelopmentCopy say why it could not. An older copy never takes over from a newer
    one, and a second opening waits until the first one is done. Once this copy's service answers, the copies of
    older versions an AppImage left behind go, and the Linux app's menu entry opens this copy (in_menu)."""
    why = misplaced(executable, platform)
    if why is not None:
        raise LaunchError(why)
    program = installed_program(ws.home)  # DevelopmentCopy from a development folder: it never registers
    with _one_opening(ws.run, wait + LOCK_MARGIN):
        before = serving(ws.run)
        _refuse_older(ws, before)
        registered = not _same_copy(service.registered(), program)
        restarted = False
        if registered:
            service.install(program)  # replaces an older registration and starts the service
            restarted = True
        elif before is None or (before.version and before.version != __version__):
            service.restart()  # not running (stopped, or not started at this login), or an older version still runs
            restarted = True
        deadline = time.monotonic() + wait
        while not (healthy(ws.port) and (not restarted or _replaced(serving(ws.run), before))):
            if time.monotonic() > deadline:
                raise LaunchError(
                    "Arka plan servisi başlatıldı ama yanıt vermedi. Birkaç saniye sonra uygulamayı yeniden açın; "
                    f"sorun sürerse günlüğe bakın: {ws.layout.logs}"
                )
            sleep(_PAUSE)
        for older in older_copies(executable, platform):
            shutil.rmtree(older, ignore_errors=True)  # a Python this program copied for an older version, no document
        in_menu(executable, platform, registered=registered)
        return Opened((login or _login_link)(ws), registered, restarted)


def in_menu(executable: Path, platform: str, *, registered: bool) -> bool:
    """The Linux app's entry in the desktop's menu (desktop), for the copy AppRun runs: written as the app registers
    the service (its first opening, a new version's AppImage), or when there is none yet (a copy from before the
    entry). An entry already there is left as the user may have changed it in a menu editor. Whether it was
    written."""
    if detect(executable, platform).kind is not Kind.LINUX_COPY:
        return False
    if not registered and desktop.present():
        return False
    return desktop.add(executable)


@contextmanager
def _one_opening(run: Path, seconds: float) -> Generator[None]:
    """One opening of the app at a time for a data folder: a second one, started while the first registers or starts
    the service (a double click, two clicks on a menu item), waits for it and then finds the service ready."""
    try:
        with locks.held(run / LOCK_NAME, seconds):
            yield
    except locks.LockTimeout:
        raise LaunchError("İplikçi Nedim zaten açılıyor; açılınca tarayıcıda görünecek.") from None


def _refuse_older(ws: Workspace, running: instance.Holder | None) -> None:
    """An older copy never registers itself over a newer one: its service could not read what the newer one wrote,
    and the service manager would start it again and again."""
    if running is not None and newer(running.version, __version__):
        raise LaunchError(
            f"Bu bilgisayarda İplikçi Nedim'in daha yeni bir sürümü ({running.version}) çalışıyor; açtığınız kopya "
            f"daha eski ({__version__}). Yeni sürümü açın."
        )
    if database.written_by_newer(ws.layout.database) is not None:
        raise LaunchError("Bu veri klasörünü İplikçi Nedim'in daha yeni bir sürümü açmış; yeni sürümü açın.")


def _replaced(now: instance.Holder | None, before: instance.Holder | None) -> bool:
    """After a start or a restart: a service holds the data folder, has said who it is, and is not the one before
    it. The one before may still answer for a moment as it ends, and a login link it gave would end with it."""
    return now is not None and now.pid != 0 and (before is None or now.pid != before.pid)


def older_copies(executable: Path, platform: str) -> list[Path]:
    """The Pythons of versions older than this one an AppImage left (Linux: AppRun copies the Python once per version
    to ~/.local/lib/iplikci/<version>, as the AppImage is mounted somewhere new at every start); none elsewhere. A
    newer version's copy stays, and so do the copies of this version AppRun may be making (<version>.yeni…).

    An earlier AppRun kept the copies inside the data folder (iplikci/app/<version>), where removing the data took
    the program along: those go too, and their folder with them when nothing else is in it."""
    if not platform.startswith("linux"):
        return []
    root = executable.parent.parent  # ~/.local/lib/iplikci/<version>/bin/python3
    folder = root.parent
    this = version_key(root.name)
    if (folder.name, folder.parent.name) != ("iplikci", "lib") or this is None:
        return []
    gone = [path for key, path in _copies(folder) if key < this]
    earlier = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "iplikci" / "app"
    there = [path for key, path in _copies(earlier) if key <= this]
    if there and len(there) == len(list(earlier.iterdir())):
        return [*gone, earlier]
    return [*gone, *there]


def _copies(folder: Path) -> list[tuple[tuple[int, ...], Path]]:
    """The copies of the program in folder with their versions; one AppRun is making (<version>.yeni.<pid>) counts as
    its version."""
    if not folder.is_dir():
        return []
    found: list[tuple[tuple[int, ...], Path]] = []
    for path in sorted(folder.iterdir()):
        key = version_key(path.name)
        if key is not None and path.is_dir() and not path.is_symlink():
            found.append((key, path))
    return found


def _login_link(ws: Workspace) -> str:
    try:
        return str(client.call(ws, "POST", "/api/login-links")["url"])
    except client.ServiceError as exc:
        raise LaunchError(f"Arayüz için giriş bağlantısı alınamadı: {exc}.") from exc
