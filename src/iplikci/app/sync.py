"""The sync folder (ADR-0025, F22): turning it on in a folder Google Drive (or another sync service) mirrors, the
rounds the service runs every minute, which computer sends the notifications that leave the computer, and what the
Settings screen shows.

A round:

1. reads the state files the other computers wrote (only those that changed; a file that could not be read is read
   again in the next round) and this computer's own (after a restore the database may be behind what it wrote);
2. brings into the archive the originals of documents that came from the others, each checked against its name;
3. stamps what changed here since the last round, merges the others' pieces (the later change wins; a document's
   removal is never undone) and puts the winners in place, each only if this computer's own value has not changed
   meanwhile, each on its own (a piece that cannot be put in place holds up no other);
4. sends the bytes of documents removed meanwhile to the Trash, once the round's changes are kept;
5. hands over who sends Telegram and e-mail notifications when the computer that did has gone silent;
6. puts this computer's new originals into its part of the folder, writes its state file when a piece changed and its
   cihaz.json every five minutes.

A computer joining a set of data merges nothing until it has read another computer's state file: until then it could
not tell its own old data from the others' newer one. While the folder cannot be reached, or the sync is off, the
rounds still stamp what changes here, so the change keeps the time it was made at.

The database never goes into the folder: each computer reads the documents itself and makes its own analysis and
feed from the same documents, annotations, rules and settings. Telegram's and e-mail's notifications go from one
computer, so they come once, and only that computer reads the bot's messages; the interface's box and the desktop
notifications are every computer's own.
"""

import json
import logging
import os
import platform as platform_module
import sqlite3
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from .. import __version__
from ..domain.codes import Actor, Channel, DocumentStatus
from ..notify import timing
from ..settings import config
from ..storage import audit, documents, events
from ..storage import sync as stored
from ..storage.db import Database
from ..sync import library, machine
from ..sync import places as known_places
from ..sync.clock import Clock, Stamp, StampError
from ..sync.library import Device, LibraryError
from ..sync.state import (
    Entry,
    Kind,
    Newer,
    Published,
    StateError,
    canonical,
    digest,
    entries_digest,
    merge,
    removed_document,
    wins,
)
from ..sync.state import decode as decode_state
from ..sync.state import encode as encode_state
from ..vault.store import VaultError
from . import shared
from .workspace import Busy, Workspace

log = logging.getLogger("iplikci.sync")

SELF = "self"  # sync_state: this computer's id, its machine, the set of data it joined
CLOCK = "clock"  # sync_state: the last stamp the clock gave or saw
LAST = "last"  # sync_state: how the last round went
PUBLISHED = "published"  # sync_state: the digest of the pieces the state file was last written with
CATCH_UP = "catch_up"  # sync_state: channel → since when the notifications this computer took over are to be made
FAILED = "sync.failed"  # the system event: the sync has not worked for FAILED_AFTER; told once a day

HEARTBEAT_EVERY = timedelta(minutes=5)  # how often cihaz.json says this computer is there
TAKEOVER_AFTER = timedelta(minutes=30)  # silence after which another computer sends a channel's notifications
CLAIM_GRACE = timedelta(minutes=10)  # a channel just taken is not let go on an old word that it cannot send
FREE_CATCH_UP = timedelta(minutes=10)  # a channel nobody sent: the notifications made since then are sent
FAILED_AFTER = timedelta(hours=6)  # how long a problem lasts before it is told as an event
OBJECTS_PER_ROUND = 300  # originals copied in or out in one round; the next follows after a short pause
BYTES_PER_ROUND = 200 << 20
LISTING_KEPT = 30 * 60.0  # seconds a listing of the folder's originals is trusted
LEFTOVER_AGE = 3600.0  # seconds after which a half-written file in this computer's part of the folder is removed
EXTERNAL = (Channel.TELEGRAM, Channel.EMAIL)  # the channels whose notifications one computer sends
ON, OFF, RENAMED, SENDER_SET = "sync.on", "sync.off", "sync.renamed", "sync.sender"  # the audit log's actions
APPLIED = "sync.applied"
RECEIVED = "document.received"  # the feed's event, as a document taken in here records it
ARRIVALS_TOLD = 50  # more documents than this coming in one round are one event that counts them
WAITING = "öteki bilgisayarların verileri bu bilgisayara henüz inmedi; katılmak için bekleniyor"


class SyncError(Exception):
    """The sync cannot be turned on or changed as asked; the message says why (Turkish)."""


@dataclass(frozen=True, slots=True)
class Me:
    """This computer in the sync: its id, the machine it was given on, the set of data it is in."""

    device: str
    machine: str
    library: str
    since: str  # when it began syncing (UTC)
    joining: bool = False  # it joined a set of data begun elsewhere and has not merged yet


# --- waking the service's rounds --------------------------------------------------------------------------

_wakers: list[Callable[[], None]] = []
_wakers_lock = threading.Lock()
_channels_changed = threading.Event()


def register(waker: Callable[[], None]) -> Callable[[], None]:
    """The service's round thread asks to be woken; returns what takes it off again."""
    with _wakers_lock:
        _wakers.append(waker)

    def unregister() -> None:
        with _wakers_lock:
            if waker in _wakers:
                _wakers.remove(waker)

    return unregister


def wake() -> None:
    """Ask for a round now (nothing happens outside the service)."""
    with _wakers_lock:
        found = list(_wakers)
    for waker in found:
        waker()


def channels_changed() -> None:
    """A channel was set up, turned on or off, or stopped: the next round asks again which ones this computer can
    send on, and comes at once."""
    _channels_changed.set()
    wake()


def take_channels_changed() -> bool:
    """Whether the channels changed since the last time this was asked."""
    if _channels_changed.is_set():
        _channels_changed.clear()
        return True
    return False


def _forget_files(ws: Workspace) -> None:
    """What the rounds keep of a folder, forgotten: the sync turned on elsewhere, or off."""
    _peers.pop(ws.home, None)
    _beats.pop(ws.home, None)


# --- this computer --------------------------------------------------------------------------------------


def _me(db: Database) -> Me | None:
    found = stored.load(db, SELF)
    if not isinstance(found, dict):
        return None
    value = cast(dict[str, Any], found)
    try:
        return Me(
            str(value["device"]),
            str(value["machine"]),
            str(value["library"]),
            str(value.get("since", "")),
            bool(value.get("joining", False)),
        )
    except KeyError:
        return None


def _save_me(db: Database, me: Me) -> None:
    stored.save(
        db,
        SELF,
        {"device": me.device, "machine": me.machine, "library": me.library, "since": me.since, "joining": me.joining},
    )


def _iso(at: datetime) -> str:
    return at.astimezone(UTC).replace(microsecond=0).isoformat()


def _parse_time(text: str) -> datetime | None:
    try:
        found = datetime.fromisoformat(text)
    except ValueError:
        return None
    return found if found.tzinfo else found.replace(tzinfo=UTC)


def _system() -> str:
    system = platform_module.system()
    return {"Darwin": "macOS"}.get(system, system)


def device_name(settings: config.Settings) -> str:
    return settings.sync.name or machine.computer_name() or "Bilgisayar"


def _clock(db: Database, device: str) -> Clock:
    text = stored.load(db, CLOCK)
    try:
        last = Stamp.parse(text) if isinstance(text, str) else None
    except StampError:
        last = None
    return Clock(device, last)


# --- who sends the notifications that leave the computer ------------------------------------------------


def sends(db: Database, settings: config.Settings, channel: Channel) -> bool:
    """Whether this computer sends the channel's notifications (and, for Telegram, reads the bot's messages): always
    without the sync, and for the interface's box and the desktop; with it, only when this computer holds the channel.
    A channel nobody holds yet is taken by the next round of a computer that can send on it, which then sends what was
    made meanwhile; a copied data folder holds nothing of the computer it was copied from."""
    if channel not in EXTERNAL or not settings.sync.folder:
        return True
    me = _me(db)
    if me is None:
        return True
    if me.machine != machine.fingerprint():
        return False
    row = stored.get(db, Kind.SENDER, channel.value)
    return row is not None and _holder(row.value) == me.device


def _holder(value: str | None) -> str | None:
    found = _sender(value)
    return found[0] if found else None


def _sender(value: str | None) -> tuple[str, datetime | None] | None:
    """(the computer, since when) a channel's sender piece names; None for none."""
    if value is None:
        return None
    try:
        found: Any = json.loads(value)
        return str(found["device"]), _parse_time(str(found.get("since", "")))
    except (ValueError, KeyError, TypeError, AttributeError):
        return None


def catch_ups(db: Database) -> dict[str, str]:
    """The channels this computer took over whose notifications since a time are still to be made: channel → UTC."""
    found = stored.load(db, CATCH_UP)
    return {str(k): str(v) for k, v in cast(dict[str, Any], found).items()} if isinstance(found, dict) else {}


def caught_up(db: Database, channel: str) -> None:
    left = catch_ups(db)
    if left.pop(channel, None) is not None:
        stored.save(db, CATCH_UP, left)


# --- turning it on and off --------------------------------------------------------------------------------


def _folder(text: str) -> Path:
    path = Path(text).expanduser()
    if not path.is_absolute():
        raise SyncError("klasörün tam yolu verilmeli")
    return path


def turn_on(
    ws: Workspace, folder: str, name: str = "", actor: Actor = Actor.USER, channels: Sequence[str] = ()
) -> "Status":
    """Share this computer's data through folder: begin a set of data there, or join the one another computer began.
    Joining, the others' data wins wherever both have a value; this computer's own stays where they have none.
    channels: the external channels this computer can send on now."""
    path = _folder(folder)
    try:
        found = library.marker(path)
        begins = found is None
        library_id = library.create(path) if found is None else found
    except LibraryError as exc:
        raise SyncError(str(exc)) from exc
    except OSError as exc:
        raise SyncError(f"klasöre yazılamadı: {exc.strerror or exc}") from exc
    at = _iso(datetime.now(UTC))
    with ws.db() as db:
        before = _me(db)
        fingerprint = machine.fingerprint()
        device = before.device if before and before.machine == fingerprint else library.new_device_id()
        same = before is not None and before.library == library_id
        if before is not None and not same:
            forgotten = stored.forget(db)  # another set of data: what this computer knew of the last one goes
            log.info("the sync moved to another set of data; %d pieces of the last one forgotten", forgotten)
        joining = before.joining if same and before is not None else not begins
        me = Me(device, fingerprint, library_id, before.since if same and before else at, joining)
        _save_me(db, me)
        audit.record(db, actor, ON, device, began=begins)
    config.update(ws.layout.settings, "sync", {"folder": str(path), "name": name.strip() or None})
    _forget_files(ws)
    settings = ws.fresh_settings()
    try:
        _heartbeat(path, me, settings, tuple(channels), left=False)
    except OSError as exc:
        raise SyncError(f"klasöre yazılamadı: {exc.strerror or exc}") from exc
    channels_changed()
    return status(ws)


def turn_off(ws: Workspace, actor: Actor = Actor.USER) -> "Status":
    """Stop sharing: this computer's part of the folder stays (the others may still need its originals); the channels
    it sent go to the others; its data stays as it is. A data folder copied from another computer says nothing for
    that computer."""
    settings = ws.fresh_settings()
    if not settings.sync.folder:
        return status(ws)
    path = Path(settings.sync.folder)
    with ws.db() as db:
        me = _me(db)
        if me is not None and me.machine == machine.fingerprint() and not me.joining:
            clock = _clock(db, me.device)
            with db.transaction():
                for channel in EXTERNAL:
                    row = stored.get(db, Kind.SENDER, channel.value)
                    if row is not None and _holder(row.value) == me.device:
                        stored.put(db, stored.Row(Kind.SENDER, channel.value, clock.now().text, None, "", True))
                stored.save(db, CLOCK, clock.last.text)
            try:
                if library.marker(path) == me.library:
                    _publish_state(ws, db, path, me, force=True)
                    _heartbeat(path, me, settings, (), left=True)
            except (OSError, LibraryError):
                log.warning("the sync folder could not be told that this computer left")
        audit.record(db, actor, OFF, me.device if me else "")
    config.update(ws.layout.settings, "sync", {"folder": None})
    _forget_files(ws)
    return status(ws)


def rename(ws: Workspace, name: str, actor: Actor = Actor.USER) -> "Status":
    config.update(ws.layout.settings, "sync", {"name": name.strip() or None})
    with ws.db() as db:
        audit.record(db, actor, RENAMED, "")
    wake()
    return status(ws)


def claim(ws: Workspace, channels: Iterable[str], actor: Actor = Actor.USER) -> "Status":
    """This computer sends the given channels' notifications from now on (the Settings screen's button). What the
    quiet hours kept back for the digest on the computer that sent them is made again here."""
    settings = ws.fresh_settings()
    if not settings.sync.folder:
        raise SyncError("eşitleme kapalı: bildirimleri zaten bu bilgisayar gönderiyor")
    wanted = [c for c in EXTERNAL if c.value in set(channels)]
    if not wanted:
        raise SyncError("bu bilgisayarda gönderilebilecek bir kanal yok: önce Telegram'ı ya da e-postayı kurun")
    now = datetime.now(UTC)
    with ws.db() as db:
        me = _me(db)
        if me is None or me.joining:
            raise SyncError("eşitleme henüz başlamadı; biraz sonra yeniden deneyin")
        clock = _clock(db, me.device)
        with db.transaction():
            for channel in wanted:
                row = stored.get(db, Kind.SENDER, channel.value)
                if row is None or _holder(row.value) != me.device:
                    _give(db, clock, channel, me.device, now, _quiet_since(settings, now))
            stored.save(db, CLOCK, clock.last.text)
        audit.record(db, actor, SENDER_SET, me.device, channels=[c.value for c in wanted])
    channels_changed()
    return status(ws)


def _give(
    db: Database, clock: Clock, channel: Channel, device: str, at: datetime, catch_up: datetime | None = None
) -> None:
    """The channel to this computer; catch_up: the notifications made here since then are made on it too."""
    value = canonical({"device": device, "since": _iso(at)})
    stored.put(db, stored.Row(Kind.SENDER, channel.value, clock.now().text, value, "", True))
    if catch_up is not None and catch_up < at:
        stored.save(db, CATCH_UP, catch_ups(db) | {channel.value: _iso(catch_up)})


def _quiet_since(settings: config.Settings, at: datetime) -> datetime:
    """When the quiet hours holding at began (at itself outside them): what they kept back is in the next digest."""
    local = at.astimezone()
    return timing.quiet_since(settings.notify.quiet_hours, local).astimezone(UTC)


# --- a round ---------------------------------------------------------------------------------------------


@dataclass
class Round:
    """What a round did."""

    ran: bool = False  # the sync is on and the folder was there
    more: bool = False  # originals still wait to be copied: another round follows at once
    refresh: bool = False  # the documents, annotations, rules or settings changed: the analysis is made again
    applied: dict[str, int] = field(default_factory=dict[str, int])
    fetched: int = 0  # originals brought into the archive
    published: int = 0  # originals put into this computer's part of the folder
    problem: str = ""  # why it could not do its work (Turkish); "" when it could


@dataclass
class _Peers:
    """What the other computers wrote, as the last rounds read it: a file is read again only when it changed (one that
    could not be read, always), and the folder's originals are listed again only when one is looked for that the last
    listing did not have."""

    states: dict[str, tuple[tuple[int, int] | None, Published]] = field(
        default_factory=dict[str, tuple[tuple[int, int] | None, Published]]
    )
    devices: dict[str, Device] = field(default_factory=dict[str, Device])
    in_folder: dict[str, Path] = field(default_factory=dict[str, Path])  # the originals the last listing found
    listed_at: float = -LISTING_KEPT  # time.monotonic() of the last listing
    removed: int = -1  # documents removed here the last round knew: this computer's copies of new ones leave

    def listing(self, path: Path, fresh: bool = False) -> dict[str, Path]:
        """The folder's originals; listed again when asked, or when the last listing is older than LISTING_KEPT
        (an original that left the folder, a computer's part the user deleted, is put back by the next round)."""
        if fresh or time.monotonic() - self.listed_at > LISTING_KEPT:
            self.in_folder = _listing(path)
            self.listed_at = time.monotonic()
        return self.in_folder


_peers: dict[Path, _Peers] = {}  # by data folder: the service's rounds keep it between rounds


def run_round(ws: Workspace, channels: Callable[[], Sequence[str]] = lambda: (), now: datetime | None = None) -> Round:
    """One round (see the module's description). channels: the external channels this computer can send on now.
    Whatever goes wrong is the round's problem, shown on the Settings screen; the next round tries again."""
    at = now or datetime.now(UTC)
    try:
        return _round(ws, channels, at)
    except Exception as exc:  # the round's boundary: the error is shown, never left to stop the rounds unseen
        log.exception("a sync round failed")
        return _failed(ws, at, f"beklenmeyen bir hata ({type(exc).__name__}); bir sonraki turda yeniden denenecek")


def _round(ws: Workspace, channels: Callable[[], Sequence[str]], at: datetime) -> Round:
    settings = config.load(ws.layout.settings)
    with ws.db() as db:
        me = _me(db)
    if not settings.sync.folder:
        _peers.pop(ws.home, None)
        if me is not None and not me.joining:
            _stamp_only(ws, me)  # a change made while the sync is off keeps the time it was made at
        return Round()
    path = Path(settings.sync.folder)
    try:
        found = library.marker(path)
    except LibraryError as exc:
        return _stamped_failure(ws, me, at, str(exc))
    if found is None:
        problem = "eşitleme klasörü bulunamadı; Google Drive (ya da eşitleme uygulamanız) çalışıyor mu?"
        return _stamped_failure(ws, me, at, problem)
    if me is None:
        me = _register(ws, found)  # the settings name a folder this database never joined (a restored one)
    if found != me.library:
        return _stamped_failure(ws, me, at, "eşitleme klasörü başka bir veri kümesine ait; Ayarlar'dan yeniden seçin")
    me = _same_machine(ws, me)
    _clean_leftovers(path, me)
    peers = _peers.setdefault(ws.home, _Peers())
    remote, read, problems = _read_peers(path, me, peers)
    result = Round(ran=True)
    ready = tuple(channels())
    if me.joining and not read:
        # Nothing of the others is here yet: merging now would take this computer's old data for the newest.
        _heartbeat_if_due(ws, path, me, settings, ready, at)
        result.problem = "; ".join([WAITING, *problems])
        _record(ws, at, result)
        return result
    try:
        _bring_originals(ws, path, peers, remote, result)
        with ws.lock(timeout=5.0):
            applied = _merge(ws, me, remote)
        if me.joining:
            me = replace(me, joining=False)
            with ws.db() as db:
                _save_me(db, me)
    except (Busy, sqlite3.OperationalError):
        applied = None  # a long reading holds the documents, or the database stayed busy: the next round merges
    except OSError as exc:
        return _failed(ws, at, f"eşitleme klasörü okunamadı: {exc.strerror or exc}")
    if applied is not None:
        result.applied = dict(applied.counts)
        result.refresh = applied.changes_numbers
        if applied.settings:
            ws.fresh_settings()  # the readers' company names, as the settings say now
    _sweep_removed(ws)
    try:
        with ws.db() as db:
            _hand_over(db, me, peers.devices, ready, settings, at)
            _put_originals(ws, path, me, peers, result)
            _publish_state(ws, db, path, me)
        _heartbeat_if_due(ws, path, me, settings, ready, at)
    except OSError as exc:
        return _failed(ws, at, f"eşitleme klasörüne yazılamadı: {exc.strerror or exc}")
    result.problem = "; ".join(problems)
    _record(ws, at, result)
    return result


def _register(ws: Workspace, library_id: str) -> Me:
    """A database whose settings name a sync folder it never joined: it joins it now, its data older than all."""
    me = Me(library.new_device_id(), machine.fingerprint(), library_id, _iso(datetime.now(UTC)), joining=True)
    with ws.db() as db:
        _save_me(db, me)
        audit.record(db, Actor.SYSTEM, ON, me.device, began=False)
    return me


def _same_machine(ws: Workspace, me: Me) -> Me:
    """A data folder copied to another computer takes a new id there: two computers never write one part."""
    fingerprint = machine.fingerprint()
    if me.machine == fingerprint:
        return me
    moved = replace(me, device=library.new_device_id(), machine=fingerprint)
    with ws.db() as db:
        _save_me(db, moved)
        audit.record(db, Actor.SYSTEM, ON, moved.device, began=False, moved=True)
    log.info("the data folder was copied from another computer; this one takes a new id in the sync")
    return moved


def _clean_leftovers(path: Path, me: Me) -> None:
    """Half-written files a stop left in this computer's part of the folder: removed once they are an hour old (a
    write in progress is never that old)."""
    cutoff = time.time() - LEFTOVER_AGE
    for leftover in library.leftovers(path, me.device):
        try:
            if leftover.stat().st_mtime < cutoff:
                library.remove_leftover(leftover)
        except OSError:
            continue


def _read_peers(path: Path, me: Me, peers: _Peers) -> tuple[list[Entry], int, list[str]]:
    """The pieces in every computer's state file, this computer's own included; how many files were read; what kept
    a file from being read, or left pieces of it out."""
    entries: list[Entry] = []
    problems: list[str] = []
    read = 0
    for device in library.devices(path):
        folder = library.device_dir(path, device)
        described = library.read_device(path, device)
        if described is not None:
            peers.devices[device] = described
        name = described.name if described else device
        key = library.stat_key(folder / library.STATE_FILE)
        known = peers.states.get(device)
        if known is not None and known[0] == key:
            published = known[1]
        else:
            published, problem = _read_state(folder / library.STATE_FILE, me)
            if problem:
                problems.append(f"{name}: {problem}")
            if published is None:
                peers.states.pop(device, None)  # read again in the next round
                continue
            peers.states[device] = (key, published)
        if published.dropped:
            problems.append(f"{name}: durum dosyasında okunamayan {published.dropped} kayıt atlandı")
        entries.extend(published.entries)
        read += 1
    return entries, read, problems


def _read_state(path: Path, me: Me) -> tuple[Published | None, str]:
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None, ""
    except OSError as exc:
        return None, f"durum dosyası okunamadı ({exc.strerror or exc})"
    try:
        published = decode_state(data, shared.valid)
    except Newer as exc:
        return None, f"{exc}; bu bilgisayardaki İplikçi Nedim'i güncelleyin"
    except StateError:
        return None, ""  # being brought by the sync service: the next round reads it again
    if published.library != me.library:
        return None, "başka bir veri kümesinin dosyası"
    return published, ""


# --- the originals ----------------------------------------------------------------------------------------


def _winners(db: Database, remote: Iterable[Entry], kinds: Iterable[str]) -> dict[tuple[str, str], Entry]:
    wanted = set(kinds)
    here = [Entry(r.kind, r.key, Stamp.parse(r.stamp), r.value) for r in stored.every(db, wanted).values()]
    return merge([*here, *(e for e in remote if e.kind in wanted)])


def _listing(path: Path) -> dict[str, Path]:
    """Every original in the folder, wherever a computer put it; a copy is checked against its name when used."""
    found: dict[str, Path] = {}
    for device in library.devices(path):
        for sha256, where in library.objects(path, device).items():
            found.setdefault(sha256, where)
    return found


def _bring_originals(ws: Workspace, path: Path, peers: _Peers, remote: list[Entry], result: Round) -> None:
    """The bytes of the documents the others kept that this computer lacks, into its archive."""
    with ws.db() as db:
        winners = _winners(db, remote, [Kind.DOCUMENT])
    needed = [e.key for e in winners.values() if not removed_document(e.value) and not ws.vault.has(e.key)]
    if not needed:
        return
    listing = peers.listing(path, fresh=any(sha not in peers.in_folder for sha in needed))
    budget = BYTES_PER_ROUND
    for sha256 in needed:
        source = listing.get(sha256)
        if source is None:
            continue  # not in the folder yet: its computer puts it there, or the sync service is bringing it
        if result.fetched >= OBJECTS_PER_ROUND or budget <= 0:
            result.more = True
            return
        try:
            size = source.stat().st_size
            ws.vault.adopt(source, sha256)
        except VaultError:
            log.warning("an original in the sync folder does not match its name; it was left there")
            continue
        except OSError:
            continue  # not brought down yet (offline, the sync service busy): the next round tries again
        result.fetched += 1
        budget -= size


def _sweep_removed(ws: Workspace) -> None:
    """The bytes of documents removed here that are still in the archive, to the Trash (ADR-0003): a removal another
    computer made is kept in the database first and its bytes move after, so the database never waits on a move; bytes
    brought in before their removal came go the same way."""
    with ws.db() as db:
        left = [d.sha256 for d in documents.every(db, [DocumentStatus.REMOVED]) if ws.vault.has(d.sha256)]
    for sha256 in left:
        try:
            where = ws.vault.remove(sha256)
        except (VaultError, OSError):
            log.warning("a removed document's bytes could not go to the Trash; the next round tries again")
            continue
        ws.vault.drop_derived(sha256)
        with ws.db() as db:
            audit.record(db, Actor.SYNC, shared.REMOVED_BY_SYNC, sha256, trash=where.parent.name)


def _put_originals(ws: Workspace, path: Path, me: Me, peers: _Peers, result: Round) -> None:
    """This computer's originals of kept documents that are nowhere in the folder, into its part of it; its copies of
    documents removed here out of it (to the Trash). A removal is followed only once it is in place here."""
    with ws.db() as db:
        winners = {key: e for (_, key), e in _winners(db, [], [Kind.DOCUMENT]).items()}
        removed_here = {d.sha256 for d in documents.every(db, [DocumentStatus.REMOVED])}
    removed = {key for key, e in winners.items() if removed_document(e.value)} & removed_here
    if len(removed) != peers.removed:
        for sha256, where in library.objects(path, me.device).items():
            if sha256 in removed:
                library.withdraw(where, ws.home)
                peers.in_folder.pop(sha256, None)
        peers.removed = len(removed)
    local = [sha for sha in ws.vault.objects() if sha in winners and sha not in removed_here]
    missing = [sha for sha in local if sha not in peers.listing(path)]
    if not missing:
        return
    listing = peers.listing(path, fresh=True)
    budget = BYTES_PER_ROUND
    for sha256 in missing:
        if sha256 in listing:
            continue
        if result.published >= OBJECTS_PER_ROUND or budget <= 0:
            result.more = True
            return
        try:
            budget -= library.publish(path, me.device, sha256, ws.vault.path(sha256))
        except ValueError:
            log.error("an original no longer matches its name; it was not put into the sync folder")
            continue
        listing[sha256] = library.object_path(path, me.device, sha256)
        result.published += 1


# --- merging -------------------------------------------------------------------------------------------------


def _stamped_failure(ws: Workspace, me: Me | None, at: datetime, problem: str) -> Round:
    """A round that cannot reach the folder still stamps what changed here."""
    if me is not None and not me.joining:
        _stamp_only(ws, me)
    return _failed(ws, at, problem)


def _stamp_only(ws: Workspace, me: Me) -> None:
    """Stamp what changed here, without the folder: once it is back, the change keeps the time it was made at, and a
    later change on another computer wins over it. Only for a computer that has shared its data before."""
    try:
        with ws.lock(timeout=5.0), ws.db() as db:
            files = shared.file_kind_values(ws)
            clock = _clock(db, me.device)
            with db.transaction():
                rows = stored.every(db)
                if rows:
                    _stamp_changes(db, rows, shared.db_values(db) | files, clock, zero=False)
                    stored.save(db, CLOCK, clock.last.text)
    except (Busy, sqlite3.OperationalError):
        return  # the next round stamps it


def _merge(ws: Workspace, me: Me, remote: list[Entry]) -> shared.Applied:
    """Stamp this computer's changes, merge the others' and put the winners in place."""
    applied = shared.Applied()
    files = shared.file_kind_values(ws)
    with ws.db() as db:
        clock = _clock(db, me.device)
        with db.transaction():
            own = shared.db_values(db) | files
            # A computer joining another computer's data (or a database restored from before the sync) stamps its
            # own data older than all: what was decided in the folder wins wherever both have a value.
            _stamp_changes(db, stored.every(db), own, clock, zero=me.joining)
            _take_remote(db, stored.every(db), remote, clock)
            stored.save(db, CLOCK, clock.last.text)
        _apply_db(ws, db, applied)
        _apply_files(ws, db, applied)
        if applied.any:
            audit.record(db, Actor.SYNC, APPLIED, "", files=applied.files, **applied.counts)
        _tell_arrivals(db, applied.added)
    return applied


def _tell_arrivals(db: Database, added: Sequence[str]) -> None:
    """The documents that came from another computer, into the feed as they came in on it: one event each, or one that
    counts them when many came at once (a computer joining, or back after a long time)."""
    if len(added) > ARRIVALS_TOLD:
        events.append(db, RECEIVED, "", count=len(added))
        return
    for sha256 in added:
        first = next(iter(documents.sources(db, sha256)), None)
        events.record(db, RECEIVED, sha256, **({"source": first.kind.value} if first else {}))


def _stamp_changes(
    db: Database,
    rows: dict[tuple[str, str], stored.Row],
    own: dict[tuple[str, str], str],
    clock: Clock,
    zero: bool,
) -> None:
    """This computer's values that changed since they were last compared: stamped now (zero: a value never stamped
    before is older than all)."""
    for (kind, key), value in own.items():
        row = rows.get((kind, key))
        mine = digest(value)
        if row is None:
            stamp = Stamp.zero(clock.device) if zero else clock.now()
            stored.put(db, stored.Row(kind, key, stamp.text, value, mine, True))
        elif mine != row.local:
            if mine == digest(row.value):
                stored.settle(db, kind, key, mine)  # the winner put in place by a round a stop cut short
                continue
            change = Entry(kind, key, clock.now(), value)
            if wins(Entry(kind, key, Stamp.parse(row.stamp), row.value), change):
                stored.put(db, stored.Row(kind, key, change.stamp.text, value, mine, True))
            else:  # a document's change here never undoes its removal: the removal is put in place again
                stored.put(db, replace(row, local=mine, applied=False))
    for (kind, key), row in rows.items():
        if (kind, key) in own or kind in shared.SYNC_KINDS or row.local == "":
            continue
        if kind in shared.KEPT_KINDS:
            # Missing here though this computer had it: a restored older database. The winner comes back.
            stored.put(db, replace(row, local="", applied=False))
        else:
            stored.put(db, stored.Row(kind, key, clock.now().text, None, "", True))  # taken away here


def _take_remote(db: Database, rows: dict[tuple[str, str], stored.Row], remote: Iterable[Entry], clock: Clock) -> None:
    for entry in remote:
        clock.observe(entry.stamp)
        row = rows.get(entry.id)
        current = None if row is None else Entry(row.kind, row.key, Stamp.parse(row.stamp), row.value)
        if not wins(current, entry):
            continue
        local = row.local if row else ""
        settled = entry.kind in shared.SYNC_KINDS or digest(entry.value) == local
        new = stored.Row(entry.kind, entry.key, entry.stamp.text, entry.value, local, settled)
        stored.put(db, new)
        rows[entry.id] = new


_ORDER: dict[str, int] = {Kind.DOCUMENT.value: 0, Kind.SOURCE.value: 1}  # a document's row before its arrivals


def _apply_db(ws: Workspace, db: Database, applied: shared.Applied) -> None:
    """Put the waiting winners of the database's kinds in place, each on its own: one that cannot be put in place
    (its bytes still to come, a value this version does not read) is rolled back alone and holds up no other."""
    waiting = sorted(
        (r for r in stored.waiting(db) if r.kind in shared.DB_KINDS), key=lambda r: (_ORDER.get(r.kind, 2), r.key)
    )
    if not waiting:
        return
    with db.transaction():
        for row in waiting:
            piece = shared.Applied()
            db.execute("SAVEPOINT piece")
            try:
                if digest(shared.own_value(ws, db, row.kind, row.key)) == row.local:
                    shared.put_db(ws, db, row.kind, row.key, row.value, piece)
                    stored.settle(db, row.kind, row.key, digest(shared.own_value(ws, db, row.kind, row.key)))
                # else: changed here meanwhile; the next round stamps that change, and it wins
            except shared.Waits:
                db.execute("ROLLBACK TO piece")
            except Exception:  # a piece's boundary: it waits, logged, while the others go on
                db.execute("ROLLBACK TO piece")
                log.warning("a piece of another computer's data could not be put in place; it waits", exc_info=True)
            else:
                applied.take(piece)
            db.execute("RELEASE piece")


def _apply_files(ws: Workspace, db: Database, applied: shared.Applied) -> None:
    for row in stored.waiting(db):
        if row.kind not in shared.FILE_KINDS:
            continue
        try:
            written = shared.put_file(ws, row.kind, row.key, row.value, row.local)
        except shared.Waits as exc:
            log.info("a shared %s waits: %s", row.kind, exc)
            continue
        except Exception:  # a piece's boundary, as for the database's kinds
            log.warning("a piece of another computer's data could not be put in place; it waits", exc_info=True)
            continue
        stored.settle(db, row.kind, row.key, written)
        applied.note(row.kind)
        applied.files.append(row.key)
        if row.kind == Kind.SETTING:
            applied.settings = True


# --- the senders -------------------------------------------------------------------------------------------


def _hand_over(
    db: Database, me: Me, devices: dict[str, Device], ready: Sequence[str], settings: config.Settings, at: datetime
) -> None:
    """Give this computer a channel nobody sends, or one whose computer has gone silent, can no longer send on it or
    left, with the notifications it may have missed; let a channel go that this computer can no longer send on."""
    clock = _clock(db, me.device)
    changed = False
    with db.transaction():
        for channel in EXTERNAL:
            row = stored.get(db, Kind.SENDER, channel.value)
            found = _sender(row.value) if row else None
            holder, since = found if found else (None, None)
            can = channel.value in ready
            if holder == me.device:
                if not can and (since is None or at - since > CLAIM_GRACE):
                    stored.put(db, stored.Row(Kind.SENDER, channel.value, clock.now().text, None, "", True))
                    changed = True
                continue
            if not can:
                continue
            if holder is None:
                _give(db, clock, channel, me.device, at, at - FREE_CATCH_UP)
                changed = True
                continue
            d = devices.get(holder)
            if _gone(d, channel, me, at):
                seen = _parse_time(d.seen_at) if d else None
                missed = (seen or at - TAKEOVER_AFTER) - HEARTBEAT_EVERY
                _give(db, clock, channel, me.device, at, min(missed, _quiet_since(settings, missed)))
                changed = True
        if changed:
            stored.save(db, CLOCK, clock.last.text)


def _gone(d: Device | None, channel: Channel, me: Me, at: datetime) -> bool:
    if d is None:
        began = _parse_time(me.since)
        return began is not None and at - began > TAKEOVER_AFTER  # its cihaz.json may still be on its way
    seen = _parse_time(d.seen_at)
    return d.left or channel.value not in d.channels or seen is None or at - seen > TAKEOVER_AFTER


# --- writing -----------------------------------------------------------------------------------------------


def _publish_state(ws: Workspace, db: Database, path: Path, me: Me, force: bool = False) -> bool:
    """This computer's state file, written when a piece changed since the last time; whether it was written."""
    entries = [Entry(r.kind, r.key, Stamp.parse(r.stamp), r.value) for r in stored.every(db).values()]
    target = library.device_dir(path, me.device) / library.STATE_FILE
    fingerprint = entries_digest(entries)
    if not force and stored.load(db, PUBLISHED) == fingerprint and target.exists():
        return False
    data = encode_state(Published(me.library, me.device, __version__, _iso(datetime.now(UTC)), tuple(entries)))
    library.write_file(target, data)
    stored.save(db, PUBLISHED, fingerprint)
    return True


_beats: dict[Path, tuple[datetime, tuple[object, ...]]] = {}


def _heartbeat(
    path: Path, me: Me, settings: config.Settings, channels: tuple[str, ...], left: bool, at: datetime | None = None
) -> None:
    seen = _iso(at or datetime.now(UTC))
    library.write_device(path, Device(me.device, device_name(settings), __version__, _system(), seen, channels, left))


def _heartbeat_if_due(
    ws: Workspace, path: Path, me: Me, settings: config.Settings, channels: tuple[str, ...], at: datetime
) -> None:
    said = (me.device, device_name(settings), channels)
    last = _beats.get(ws.home)
    target = library.device_dir(path, me.device) / library.DEVICE_FILE
    if last is not None and last[1] == said and at - last[0] < HEARTBEAT_EVERY and target.exists():
        return
    _heartbeat(path, me, settings, channels, left=False, at=at)
    _beats[ws.home] = (at, said)


# --- how it went ----------------------------------------------------------------------------------------------


def _failed(ws: Workspace, at: datetime, problem: str) -> Round:
    result = Round(problem=problem)
    _record(ws, at, result)
    return result


def _record(ws: Workspace, at: datetime, result: Round) -> None:
    """The round's outcome for the Settings screen; a problem that lasts FAILED_AFTER is told once a day."""
    with ws.db() as db:
        last = stored.load(db, LAST)
        before = cast(dict[str, Any], last) if isinstance(last, dict) else {}
        since = str(before.get("since") or _iso(at)) if result.problem else ""
        value = {
            "at": _iso(at),
            "ok": not result.problem,
            "problem": result.problem,
            "since": since,
            "ok_at": _iso(at) if result.ran and not result.problem else str(before.get("ok_at", "")),
            "fetched": result.fetched,
            "published": result.published,
            "applied": result.applied,
        }
        stored.save(db, LAST, value)
        begun = _parse_time(since) if since else None
        if begun is not None and at - begun >= FAILED_AFTER:
            events.record(db, FAILED, date.today().isoformat())
    if result.problem and result.problem != before.get("problem"):
        log.warning("the sync round could not do its work")


def trouble(ws: Workspace) -> tuple[str, str] | None:
    """Why the rounds cannot do their work and since when, while the sync is on; None when they can (the Pano's
    alert, which must not read the folder on every load)."""
    if not config.load(ws.layout.settings).sync.folder:
        return None
    with ws.db() as db:
        last = stored.load(db, LAST)
    info = cast(dict[str, Any], last) if isinstance(last, dict) else {}
    problem, since = str(info.get("problem", "")), str(info.get("since", ""))
    return (problem, since) if problem and since else None


# --- what the Settings screen shows --------------------------------------------------------------------------


@dataclass(frozen=True)
class DeviceView:
    id: str
    name: str
    app: str
    system: str
    seen_at: str
    channels: tuple[str, ...]
    left: bool
    me: bool


@dataclass(frozen=True)
class Status:
    on: bool
    folder: str  # the sync folder; "" while off
    service: str  # the sync service whose folder holds it ("Google Drive"); "" when none known does
    device: str  # this computer's id; "" before it first turned the sync on
    name: str  # this computer's name as the others see it
    devices: list[DeviceView]  # every computer in the set of data, this one first
    senders: dict[str, str]  # channel → the id of the computer sending its notifications
    last_at: str  # when the last round ran
    ok_at: str  # when a round last did its work
    problem: str  # why the last round could not do its work; "" when it could
    since: str  # since when the problem lasts
    waiting_down: int  # documents whose originals are still to come
    waiting_up: int  # originals of this computer still to go into the folder
    documents: int  # documents in the shared data


def status(ws: Workspace) -> Status:
    settings = ws.fresh_settings()
    on = bool(settings.sync.folder)
    path = Path(settings.sync.folder) if on else None
    with ws.db() as db:
        me = _me(db)
        last = stored.load(db, LAST) if on else None
        rows = stored.every(db, [Kind.DOCUMENT, Kind.SENDER]) if on else {}
    info = cast(dict[str, Any], last) if isinstance(last, dict) else {}
    senders = {key: holder for (kind, key), r in rows.items() if kind == Kind.SENDER and (holder := _holder(r.value))}
    devices: list[DeviceView] = []
    waiting_down = waiting_up = documents = 0
    if path is not None and me is not None:
        for device in library.devices(path):
            d = library.read_device(path, device)
            if d is not None:
                devices.append(
                    DeviceView(d.id, d.name, d.app, d.system, d.seen_at, d.channels, d.left, d.id == me.device)
                )
        devices.sort(key=lambda d: (not d.me, d.left, d.name))
        kept = [key for (kind, key), r in rows.items() if kind == Kind.DOCUMENT and not removed_document(r.value)]
        documents = len(kept)
        waiting_down = sum(1 for sha in kept if not ws.vault.has(sha))
        folder_objects = _peers.setdefault(ws.home, _Peers()).listing(path)  # the rounds' listing while fresh
        waiting_up = sum(1 for sha in kept if ws.vault.has(sha) and sha not in folder_objects)
    place = known_places.kind_of(path, known_places.found()) if path else None
    return Status(
        on=on,
        folder=str(path) if path else "",
        service=place.label if place else "",
        device=me.device if me else "",
        name=device_name(settings),
        devices=devices,
        senders=senders,
        last_at=str(info.get("at", "")),
        ok_at=str(info.get("ok_at", "")),
        problem=str(info.get("problem", "")),
        since=str(info.get("since", "")),
        waiting_down=waiting_down,
        waiting_up=waiting_up,
        documents=documents,
    )


@dataclass(frozen=True)
class Place:
    """A place the sync folder can go, with what is there already."""

    service: str  # "Google Drive", "iCloud Drive", …; "" for a folder no known service mirrors
    account: str  # the account the service's folder belongs to, when it says one
    folder: str  # the sync folder: the one there, or the one that would be made
    exists: bool  # a set of data is there already: turning the sync on joins it
    devices: list[DeviceView]  # the computers in it
    usable: bool  # the folder can be used (its parent is there, it is empty or holds a set of data)
    problem: str  # why it cannot, when it cannot (Turkish)


def places(ws: Workspace) -> list[Place]:
    """The sync services' folders on this computer, each with the sync folder in it (made or to be made)."""
    return [inspect(p.root / library.DEFAULT_NAME, p.label, p.account) for p in known_places.found()]


def inspect(folder: Path | str, service: str = "", account: str = "") -> Place:
    """What turning the sync on in folder would do."""
    try:
        path = _folder(str(folder))
    except SyncError as exc:
        return Place(service, account, str(folder), False, [], False, str(exc))
    if not service:
        place = known_places.kind_of(path, known_places.found())
        service, account = (place.label, place.account) if place else ("", "")
    try:
        found = library.marker(path)
    except LibraryError as exc:
        return Place(service, account, str(path), False, [], False, str(exc))
    if found is not None:
        seen = [library.read_device(path, d) for d in library.devices(path)]
        views = [DeviceView(d.id, d.name, d.app, d.system, d.seen_at, d.channels, d.left, False) for d in seen if d]
        return Place(service, account, str(path), True, views, True, "")
    if path.exists() and not path.is_dir():
        return Place(service, account, str(path), False, [], False, f"{path.name} bir klasör değil")
    if path.is_dir() and any(not p.name.startswith(".") for p in path.iterdir()):
        problem = f"{path.name} klasörü boş değil; İplikçi Nedim için boş ya da yeni bir klasör seçin"
        return Place(service, account, str(path), False, [], False, problem)
    if not path.parent.is_dir():
        return Place(service, account, str(path), False, [], False, f"{path.parent} bulunamadı")
    if not os.access(path.parent, os.W_OK):
        return Place(service, account, str(path), False, [], False, f"{path.parent} klasörüne yazılamıyor")
    return Place(service, account, str(path), False, [], True, "")
