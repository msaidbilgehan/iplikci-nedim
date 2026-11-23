"""The program's own updates (ADR-0022, F21): whether a newer version is released, and putting it in place.

Every three hours the service fetches the latest release's manifest from GitHub through egress and believes it only
once its signature checks with a key the program carries; until v1.0.11 it looked once a day, from 05:00, and a version
released in the morning waited for the next day. A newer version is installed by itself when the settings say "auto"
and an installer put this copy here; "ask" waits for the user, whom every screen asks (the interface's update banner),
and "off" never asks GitHub unless the user does. One install is under way at a time: a second request while one is
queued or running adds none, and the screens show it as installing from the moment it is queued. Installing downloads this system's file, checks its size and SHA-256 against the manifest, takes a
backup, puts the new version in place (update.install) and has the service start again with it. The new version says
at its start how it went and removes what the old one left. An install of a version that did not come up is not tried
again by itself after TRIES attempts; the user may still ask for it.

What the user is told is kept in run/guncelleme.json, which only the service's worker writes."""

import io
import json
import logging
import shutil
import sys
import tempfile
import time as clock
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from .. import __version__, egress
from ..domain.codes import Actor, BackupReason
from ..service import desktop, launcher, manager
from ..settings import config
from ..settings.paths import replace_private
from ..storage import audit, jobs
from ..update import install, source
from ..update.install import Installation, InstallError, Kind
from ..update.manifest import Entry, Manifest, ManifestError, platform_key, verify
from ..versions import newer
from . import backup
from .kinds import UPDATE_CHECK, UPDATE_INSTALL
from .workspace import Busy, Workspace

CHECK_JOB = UPDATE_CHECK
INSTALL_JOB = UPDATE_INSTALL
CHECK_EVERY = 180  # minutes between the checks, counted from midnight (jobs.schedule.every)
STATE = "guncelleme.json"  # in run/
MANIFEST_LIMIT = 256 << 10
SIGNATURE_LIMIT = 4 << 10
TRIES = 2  # installs of one version that did not come up, after which only the user starts another
SETUP_LOG = "guncelleme-kurulum.log"  # in logs/: what the Windows setup program did
TEMP_PREFIX = "iplikci-guncelleme-"  # a download's folder in the system's temporary folder
INSTALLED = "update.installed"  # the audit log's actions
FAILED = "update.failed"
REQUESTED = "update.requested"
SETTINGS_CHANGED = "settings.changed"

log = logging.getLogger("iplikci.update")

type Restart = Callable[[], None]
type Apply = Callable[[Workspace, Installation, Path, str], None]


class UpdateError(Exception):
    """A check or an install could not be done; the message says why and what to do, for the user (Turkish)."""


@dataclass(frozen=True, slots=True)
class Available:
    version: str
    tag: str
    date: str
    notes: str  # the changelog's section, Markdown
    size: int  # this system's update file in bytes; 0 when the release has none for it
    page: str  # the release's page, where its installers are


@dataclass(frozen=True, slots=True)
class Outcome:
    from_version: str
    to_version: str
    at: str  # ISO 8601
    ok: bool
    error: str  # why it failed (Turkish); "" when it worked
    tries: int  # installs of to_version tried by themselves so far


@dataclass(frozen=True, slots=True)
class UpdateState:
    version: str  # the running one
    mode: str  # [updates] mode: auto, ask or off
    installation: str  # install.Kind: who put this copy here
    automatic: bool  # this copy installs a new version of itself
    platform: str  # this system as a release names it; "" for one the program is not built for
    checked_at: str  # the last check, ISO 8601; "" before any
    check_error: str  # why the last check failed (Turkish); "" when it worked
    available: Available | None  # a released version newer than the running one
    installing: str  # the version being put in place now; ""
    last: Outcome | None  # the last install, as the version that started after it said
    page: str  # where the releases are, for a copy installed by hand


def installation() -> Installation:
    """Which installer put the running program here (update.install.detect)."""
    return install.detect(Path(sys.executable), sys.platform, manager.development_folder() is not None)


def state(ws: Workspace, here: Installation | None = None) -> UpdateState:
    found = installation() if here is None else here
    record = _load(ws)
    available = _available(record.get("available"))
    if available is not None and not newer(available.version, __version__):
        available = None
    going = record.get("installing")
    installing = str(cast(dict[str, Any], going).get("to", "")) if isinstance(going, dict) else ""
    if not installing and available is not None and _queued_install(ws):
        installing = available.version  # queued by the check or the user: under way from now on
    return UpdateState(
        version=__version__,
        mode=ws.fresh_settings().updates.mode,
        installation=found.kind.value,
        automatic=found.automatic,
        platform=platform_key() or "",
        checked_at=str(record.get("checked_at", "")),
        check_error=str(record.get("check_error", "")),
        available=available,
        installing=installing,
        last=_outcome(record.get("last")),
        page=source.page(available.tag) if available is not None else source.page(),
    )


def set_mode(ws: Workspace, mode: str, actor: Actor) -> UpdateState:
    """Whether the program installs, only tells, or never asks; UpdateError for a mode it does not know."""
    if mode not in config.UPDATE_MODES:
        raise UpdateError(f"Güncelleme ayarı şunlardan biri olmalı: {', '.join(config.UPDATE_MODES)}")
    config.update(ws.layout.settings, "updates", {"mode": mode})
    with ws.db() as db:
        audit.record(db, actor, SETTINGS_CHANGED, "updates", mode=mode)
    return state(ws)


def request_check(ws: Workspace) -> None:
    """Ask the service to check now, whatever the mode says: the user asked."""
    with ws.db() as db:
        jobs.add(db, CHECK_JOB, {"forced": True})


def request_install(ws: Workspace, actor: Actor, here: Installation | None = None) -> str:
    """Ask the service to install the newer version the last check found; the version. UpdateError when this copy
    cannot install itself or there is nothing newer."""
    current = state(ws, here)
    if not current.automatic:
        raise UpdateError(
            f"Bu kopya elle kuruldu; kendini güncelleyemez. Yeni sürümü buradan indirip kurun: {current.page}"
        )
    if current.available is None:
        raise UpdateError("Kurulacak yeni bir sürüm yok. Önce yeni sürümü denetleyin.")
    if current.available.size == 0:
        raise UpdateError(f"Bu sürümde bu sistem için güncelleme dosyası yok; kurulum paketini indirin: {current.page}")
    if current.installing:
        return current.installing  # already queued (by the check in "auto") or under way: one install at a time
    with ws.db() as db:
        jobs.add(db, INSTALL_JOB, {"version": current.available.version, "asked": True})
        audit.record(db, actor, REQUESTED, current.available.version)
    return current.available.version


# --- the worker's jobs ----------------------------------------------------------------------------------------------


def check(ws: Workspace, *, forced: bool = False, here: Installation | None = None) -> UpdateState:
    """Fetch and verify the latest release's manifest and keep what it says; queue its install when the mode is
    "auto" and this copy installs itself. With the mode "off" GitHub is asked only when forced. A failure is kept for
    the user, never raised: the next day's check tries again."""
    settings = ws.fresh_settings()
    if settings.updates.mode == "off" and not forced:
        return state(ws, here)
    found = installation() if here is None else here
    record = _load(ws)
    record["checked_at"] = _now()
    try:
        release = latest(settings)
    except UpdateError as exc:
        record["check_error"] = str(exc)
        _save(ws, record)
        log.warning("the update check failed: %s", exc)
        return state(ws, found)
    record["check_error"] = ""
    record["available"] = asdict(_as_available(release)) if newer(release.version, __version__) else None
    _save(ws, record)
    if record["available"] is not None:
        log.info("version %s is released; this is %s", release.version, __version__)
        if settings.updates.mode == "auto" and found.automatic and _tries(record, release.version) < TRIES:
            with ws.db() as db:
                if jobs.waiting(db, INSTALL_JOB) is None:
                    jobs.add(db, INSTALL_JOB, {"version": release.version})
    return state(ws, found)


def install_update(
    ws: Workspace,
    restart: Restart,
    *,
    asked: bool = False,
    here: Installation | None = None,
    apply: Apply | None = None,
) -> UpdateState:
    """Download, check and put in place the latest release, then have the service start again with it (Windows: the
    setup program ends the service itself). The release is fetched and verified again: what the check saw may be
    older. A failure is kept for the user, never raised."""
    found = installation() if here is None else here
    settings = ws.fresh_settings()
    record = _load(ws)
    folder: Path | None = None
    target = ""
    try:
        _must_install_here(ws, found)
        release = latest(settings)
        if not newer(release.version, __version__):
            return state(ws, found)  # already this version or newer: an earlier install came up
        target = release.version
        tries = _tries(record, target)
        if not asked and tries >= TRIES:
            return state(ws, found)
        key = platform_key()
        entry = release.updates.get(key) if key else None
        if entry is None:
            raise UpdateError(
                f"{target} sürümünde bu sistem için güncelleme dosyası yok; kurulum paketini indirin: "
                f"{source.page(release.tag)}"
            )
        folder = Path(tempfile.mkdtemp(prefix=TEMP_PREFIX))
        file = folder / entry.name
        _download(release, entry, file, settings)
        made = backup.take(ws, BackupReason.BEFORE_UPDATE)
        log.info("backup %s made before the update to %s", made.name, target)
        record["installing"] = {"from": __version__, "to": target, "at": _now(), "tries": tries + 1}
        _save(ws, record)
        (apply or _apply)(ws, found, file, target)
    except (UpdateError, InstallError, manager.ManagerError, backup.BackupError, Busy, OSError) as exc:
        if target:
            _failed(ws, record, target, str(exc))
        else:
            record["check_error"] = str(exc)
            _save(ws, record)
        log.warning("the update could not be installed: %s", exc)
        if folder is not None:
            shutil.rmtree(folder, ignore_errors=True)
        return state(ws, found)
    if found.kind is not Kind.WINDOWS_SETUP:
        shutil.rmtree(folder, ignore_errors=True)  # the setup program runs from its folder; the others are done
        log.info("version %s is in place; the service starts again with it", target)
        restart()
    return state(ws, found)


def finish(ws: Workspace, here: Installation | None = None) -> Outcome | None:
    """At the service's start: how the install that ended the last run went, kept for the user, and what the old
    version left removed (its program files, a download). After an update that came up on Linux the app's menu entry
    opens this copy, also where a version from before the entry installed it. None when no install was under way."""
    record = _load(ws)
    going = record.get("installing")
    outcome: Outcome | None = None
    if isinstance(going, dict):
        started = cast(dict[str, Any], going)
        to, tries = str(started.get("to", "")), int(started.get("tries", 1))
        ok = to == __version__
        error = "" if ok else f"{to} kuruldu ama açılan sürüm {__version__}; yeni sürüm başlayamadı."
        outcome = Outcome(str(started.get("from", "")), to, _now(), ok, error, tries)
        record["installing"] = None
        record["last"] = asdict(outcome)
        _save(ws, record)
        with ws.db() as db:
            audit.record(db, Actor.SYSTEM, INSTALLED if ok else FAILED, to, previous=outcome.from_version)
        log.info("the update to %s %s", to, "worked" if ok else "did not come up")
    found = installation() if here is None else here
    if outcome is not None and outcome.ok and found.kind is Kind.LINUX_COPY:
        desktop.add(Path(sys.executable))
    _clean(found)
    return outcome


def latest(settings: config.Settings) -> Manifest:
    """The latest release's manifest, verified (update.manifest.verify); UpdateError says why it is not."""
    data = _fetch(source.latest(source.MANIFEST), MANIFEST_LIMIT, settings)
    seal = _fetch(source.latest(source.SIGNATURE), SIGNATURE_LIMIT, settings)
    try:
        return verify(data, seal)
    except ManifestError as exc:
        raise UpdateError(f"Yeni sürümün bildirgesine güvenilmedi: {exc}") from None


# --- helpers --------------------------------------------------------------------------------------------------------


def _queued_install(ws: Workspace) -> bool:
    """Whether an install job is queued or running."""
    with ws.db() as db:
        return jobs.waiting(db, INSTALL_JOB) is not None


def _must_install_here(ws: Workspace, found: Installation) -> None:
    from . import lifecycle  # here, not above: lifecycle's setup imports background, which imports this module

    if not found.automatic or found.root is None:
        raise UpdateError(f"Bu kopya elle kuruldu; kendini güncelleyemez. Yeni sürümü indirip kurun: {source.page()}")
    if found.kind is not Kind.WINDOWS_SETUP and not lifecycle.registration(ws).registered:
        raise UpdateError(
            "Servis bu bilgisayara bu veri klasörü için kayıtlı değil (elle çalıştırılıyor); güncelleme yapılmadı."
        )


def _fetch(path: str, limit: int, settings: config.Settings) -> bytes:
    into = io.BytesIO()
    try:
        done = egress.https_download(
            egress.GITHUB, path, settings, into, follow=egress.GITHUB_FILES, limit=limit, timeout=30.0
        )
    except (egress.Unreachable, egress.Refused, egress.TooLarge) as exc:
        raise UpdateError(f"Güncelleme kaynağına ulaşılamadı: {exc}") from None
    if done.status == 404:
        raise UpdateError(
            "Güncelleme kaynağında yayımlanmış bir sürüm bulunamadı: sürümler henüz herkese açık bir yerde değil."
        )
    if done.status != 200:
        raise UpdateError(f"Güncelleme kaynağı beklenmeyen bir yanıt verdi ({done.status}).")
    return into.getvalue()


def _download(release: Manifest, entry: Entry, file: Path, settings: config.Settings) -> None:
    """This system's update file into file, its size and SHA-256 the manifest's; UpdateError otherwise."""
    started = clock.monotonic()
    with file.open("wb") as into:
        try:
            done = egress.https_download(
                egress.GITHUB,
                source.tagged(release.tag, entry.name),
                settings,
                into,
                follow=egress.GITHUB_FILES,
                limit=entry.size,
                timeout=120.0,
            )
        except (egress.Unreachable, egress.Refused, egress.TooLarge) as exc:
            raise UpdateError(f"Yeni sürüm indirilemedi: {exc}") from None
    if done.status != 200:
        raise UpdateError(f"Yeni sürüm indirilemedi: sunucu {done.status} yanıtını verdi.")
    if done.size != entry.size or done.sha256 != entry.sha256:
        raise UpdateError("İndirilen dosya bildirgedekiyle aynı değil; kurulmadı.")
    log.info("%s downloaded in %.0f s", entry.name, clock.monotonic() - started)


def _apply(ws: Workspace, found: Installation, file: Path, version: str) -> None:
    root = found.root
    if root is None:  # _must_install_here refused it
        raise UpdateError("Bu kopya kendini güncelleyemez.")
    if found.kind is Kind.MACOS_APP:
        install.apply_macos(root, file, version)
    elif found.kind is Kind.LINUX_COPY:
        python = install.apply_linux(root, file, version)
        service = manager.for_platform()
        if not isinstance(service, manager.Systemd):
            raise UpdateError("Servis yöneticisi systemd değil; güncelleme yapılmadı.")
        service.retarget(manager.Program(python, ws.home.resolve()))
        desktop.add(python, service.menu)  # the menu opens the new copy, as the service does
    elif found.kind is Kind.WINDOWS_SETUP:
        ws.logs.mkdir(parents=True, exist_ok=True)
        manager.spawn_detached(install.windows_command(file, ws.logs / SETUP_LOG))


def _failed(ws: Workspace, record: dict[str, Any], version: str, error: str) -> None:
    tries = _tries(record, version) + 1
    record["installing"] = None
    record["last"] = asdict(Outcome(__version__, version, _now(), False, error, tries))
    _save(ws, record)
    with ws.db() as db:
        audit.record(db, Actor.SYSTEM, FAILED, version, previous=__version__)


def _tries(record: dict[str, Any], version: str) -> int:
    """How many times installing this version failed by itself."""
    last = _outcome(record.get("last"))
    return last.tries if last is not None and not last.ok and last.to_version == version else 0


def _clean(found: Installation) -> None:
    """The program files an update left: the old Contents inside the app (macOS), the copies of older versions
    (Linux), the downloads in the temporary folder. Never a document."""
    gone = [*install.leftovers(found)]
    if found.kind is Kind.LINUX_COPY:
        gone += launcher.older_copies(Path(sys.executable), sys.platform)
    gone += [p for p in Path(tempfile.gettempdir()).glob(f"{TEMP_PREFIX}*") if p.is_dir() and not p.is_symlink()]
    for path in gone:
        shutil.rmtree(path, ignore_errors=True)


def _as_available(release: Manifest) -> Available:
    key = platform_key()
    entry = release.updates.get(key) if key else None
    return Available(
        version=release.version,
        tag=release.tag,
        date=release.date,
        notes=release.notes,
        size=entry.size if entry is not None else 0,
        page=source.page(release.tag),
    )


def _available(value: object) -> Available | None:
    if not isinstance(value, dict):
        return None
    found = cast(dict[str, Any], value)
    try:
        return Available(
            version=str(found["version"]),
            tag=str(found["tag"]),
            date=str(found["date"]),
            notes=str(found["notes"]),
            size=int(found["size"]),
            page=str(found["page"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _outcome(value: object) -> Outcome | None:
    if not isinstance(value, dict):
        return None
    found = cast(dict[str, Any], value)
    try:
        return Outcome(
            from_version=str(found["from_version"]),
            to_version=str(found["to_version"]),
            at=str(found["at"]),
            ok=bool(found["ok"]),
            error=str(found["error"]),
            tries=int(found["tries"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _load(ws: Workspace) -> dict[str, Any]:
    try:
        found: object = json.loads((ws.run / STATE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return cast(dict[str, Any], found) if isinstance(found, dict) else {}


def _save(ws: Workspace, record: dict[str, Any]) -> None:
    ws.run.mkdir(parents=True, exist_ok=True)
    replace_private(ws.run / STATE, json.dumps(record, ensure_ascii=False, sort_keys=True))


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
