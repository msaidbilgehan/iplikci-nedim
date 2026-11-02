"""The settings the interface changes (F17): who the user is, how e-mail comes in, how long backups are kept. The setup
wizard and the Settings screen make the same calls; the command line makes the same changes through its own
commands. A secret is only taken in, never given back, and the e-mail address is shown masked (ADR-0015)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..domain.codes import Actor, Channel, DocumentStatus, SetupStep
from ..domain.labels import CHANNEL
from ..service import manager
from ..settings import config
from ..settings.config import SettingsError
from ..storage import audit, documents
from ..storage import mail as mail_store
from . import background, bridge, mail, notify
from .workspace import Workspace

__all__ = [
    "Actor",
    "ImapSetUp",
    "MailError",
    "MailView",
    "Progress",
    "SettingsError",
    "SettingsView",
    "SetupStep",
    "StepState",
    "remove_imap",
    "set_backup_days",
    "set_identity",
    "set_mail",
    "setup_imap",
    "view",
]

MailError = mail.MailError
IDENTITY_CHANGED = "settings.identity_changed"
BACKUP_CHANGED = "settings.backup_changed"
MAIL_CHANGED = "settings.mail_changed"
CONNECTORS = (mail.IMAP, mail.BRIDGE)
EARLIEST_START = date(2000, 1, 1)


@dataclass(frozen=True, slots=True)
class MailView:
    connector: str  # "imap" (an app password) or "browser_bridge" (the browser extension)
    configured: bool  # an IMAP account is set up; the extension's pairings are listed apart
    address: str  # masked: "k•••@example.com"; "" when none is set up
    start: date  # the day the mailbox is read from
    server: str  # the IMAP server; "" for the browser extension
    stopped: bool  # a refused login stopped the IMAP connector until it is set up again
    last_error: str


@dataclass(frozen=True, slots=True)
class SettingsView:
    home: str  # the data folder (F17's first step)
    port: int
    names: tuple[str, ...]  # the user's own names and their forms, to know transfers between own accounts
    business_names: tuple[str, ...]  # company names: their documents stay out
    mail: MailView
    bank_senders: tuple[str, ...]  # the banks' sender domains the program reads (shipped with it)
    backup_days: int  # how many days of daily backups are kept


def _masked(address: str) -> str:
    local, at, domain = address.partition("@")
    return f"{local[:1]}•••@{domain}" if at and local else ""


def view(ws: Workspace) -> SettingsView:
    """The settings as the screens show them. SettingsError when settings.toml cannot be read."""
    settings = config.load(ws.layout.settings)
    state = mail.status(ws)
    start = settings.mail.start_day or mail.default_start()
    return SettingsView(
        home=str(ws.home),
        port=settings.server.port,
        names=settings.identity.names,
        business_names=settings.identity.business_names,
        mail=MailView(
            connector=settings.mail.connector,
            configured=bool(state["configured"]),
            address=_masked(settings.mail.address) if settings.mail.connector == mail.IMAP else "",
            start=start,
            server=settings.mail.imap_host if settings.mail.connector == mail.IMAP else "",
            stopped=bool(state["stopped"]),
            last_error=str(state["lastError"] or ""),
        ),
        bank_senders=settings.mail.bank_senders,
        backup_days=settings.backup.keep_days,
    )


def _clean(values: Sequence[str]) -> tuple[str, ...]:
    """Each name once, trimmed; an empty one dropped."""
    found: list[str] = []
    for value in values:
        name = " ".join(value.split())
        if name and name.casefold() not in {f.casefold() for f in found}:
            found.append(name)
    return tuple(found)


def set_identity(ws: Workspace, names: Sequence[str], business_names: Sequence[str], actor: Actor) -> SettingsView:
    """The user's own names and the company names. Other company names make every document be read again with them:
    one that turns out to be a company's goes to the Trash (ADR-0003); the analysis follows in the background."""
    config.update(
        ws.layout.settings,
        "identity",
        {"names": _clean(names) or None, "business_names": _clean(business_names) or None},
    )
    ws.fresh_settings()  # this process reads with the new names at once; the others when they next read
    with ws.db() as db:
        audit.record(db, actor, IDENTITY_CHANGED, "identity")  # never the names themselves
    background.request_refresh(ws)
    return view(ws)


def set_backup_days(ws: Workspace, days: int, actor: Actor) -> SettingsView:
    config.update(ws.layout.settings, "backup", {"keep_days": days})
    with ws.db() as db:
        audit.record(db, actor, BACKUP_CHANGED, "backup", keep_days=days)
    return view(ws)


def _check_start(start: date | None) -> None:
    if start is not None and not EARLIEST_START <= start <= date.today():
        raise SettingsError(f"başlangıç günü {EARLIEST_START.year} ile bugün arasında olmalı")


def set_mail(ws: Workspace, connector: str | None, start: date | None, actor: Actor) -> SettingsView:
    """The way e-mail comes in (an IMAP account, or the browser extension of ADR-0016) and the day the mailbox is read
    from; the next fetch reads it again from that day."""
    if connector is not None and connector not in CONNECTORS:
        raise SettingsError(f"bilinmeyen e-posta bağlantısı: {connector}")
    if connector == mail.IMAP and not config.load(ws.layout.settings).mail.address:
        raise SettingsError("IMAP hesabı kurulu değil: önce adresini ve uygulama şifresini girin")
    _check_start(start)
    values: dict[str, object] = {}
    if connector is not None:
        values["connector"] = connector
    if start is not None:
        values["start_day"] = start
    if values:
        config.update(ws.layout.settings, "mail", values)
        with ws.db() as db:
            audit.record(db, actor, MAIL_CHANGED, "mail", connector=connector or "", start=str(start or ""))
        if connector == mail.IMAP or start is not None:
            mail.request_fetch(ws)
    return view(ws)


@dataclass(frozen=True, slots=True)
class ImapSetUp:
    folder: str  # the folder that will be read
    in_keyring: bool  # the password went to the keychain; false: only IPLIKCI_MAIL_PASSWORD can give it


def setup_imap(ws: Workspace, address: str, password: str, start: date | None, actor: Actor) -> ImapSetUp:
    """Log in once with the address and its app password, then keep them: the password only in the keychain. A
    refused login keeps nothing and is never tried again by the program (Google may lock the account); MailError
    says why, in Turkish."""
    _check_start(start)
    _, stored, folder = mail.setup_imap(ws, address, password, start)
    with ws.db() as db:
        audit.record(db, actor, MAIL_CHANGED, "mail", connector=mail.IMAP)  # never the address
    return ImapSetUp(folder, stored)


def remove_imap(ws: Workspace, actor: Actor) -> bool:
    """Forget the IMAP account: its password, its address and where it stood. False when none was set up."""
    removed = mail.remove(ws)
    if removed:
        with ws.db() as db:
            audit.record(db, actor, MAIL_CHANGED, "mail", removed=True)
    return removed


# --- where the setup stands (the wizard, F17) -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StepState:
    step: SetupStep
    done: bool
    optional: bool  # the wizard lets the user go on without it
    note: str  # where it stands, in Turkish


@dataclass(frozen=True, slots=True)
class Progress:
    steps: list[StepState]
    first_run: bool  # nothing set up yet: no name, no e-mail, no document; the interface opens the wizard


def registered_home() -> Path | None:
    """The data folder the service registered with this computer's service manager (launchd, systemd or Task
    Scheduler) runs for; None when none is registered."""
    try:
        found = manager.for_platform().registered()
    except manager.ManagerError:  # a system with no service manager this program knows
        return None
    return found.home if found is not None else None


def _service_step(ws: Workspace) -> StepState:
    """Registered for this data folder: one registered for another (a demo, a second folder) does not start this
    one."""
    registered = registered_home()
    if registered is None:
        return StepState(SetupStep.SERVICE, False, False, "Bu bilgisayara kayıtlı değil.")
    if registered.resolve() != ws.home.resolve():
        return StepState(SetupStep.SERVICE, False, False, "Bu bilgisayarda başka bir veri klasörü için kayıtlı.")
    return StepState(SetupStep.SERVICE, True, False, "Bilgisayar açılınca kendiliğinden başlar.")


def _mail_step(ws: Workspace, settings: config.Settings) -> StepState:
    if settings.mail.connector == mail.BRIDGE:
        paired = [b for b in bridge.every(ws) if b.active]
        note = "Tarayıcı eklentisi eşleşti." if paired else "Tarayıcı eklentisi seçildi; henüz eşleşmedi."
        return StepState(SetupStep.MAIL, bool(paired), False, note)
    if not settings.mail.address:
        return StepState(SetupStep.MAIL, False, False, "E-posta bağlantısı kurulmadı.")
    with ws.db() as db:
        stopped = mail_store.load(db, mail.IMAP).stopped
    if stopped:
        return StepState(SetupStep.MAIL, False, False, "E-posta girişi reddedildi; uygulama şifresini yeniden girin.")
    return StepState(SetupStep.MAIL, True, False, "IMAP hesabı kurulu.")


def progress(ws: Workspace) -> Progress:
    """Each step of the wizard, whether it is done and where it stands."""
    settings = config.load(ws.layout.settings)
    with ws.db() as db:
        kept = sum(d.status is not DocumentStatus.REMOVED for d in documents.every(db))
    ready = [c for c in notify.status(ws).channels if c.ready and c.channel is not Channel.IN_APP]
    names, companies = settings.identity.names, settings.identity.business_names
    others = settings.mail.other_senders
    steps = [
        StepState(SetupStep.DATA_FOLDER, True, False, str(ws.home)),
        StepState(SetupStep.NAMES, bool(names), False, f"{len(names)} ad" if names else "Henüz ad yok."),
        StepState(
            SetupStep.BUSINESS_NAMES, bool(companies), True, f"{len(companies)} şirket adı" if companies else "Yok."
        ),
        _mail_step(ws, settings),
        StepState(
            SetupStep.SENDERS,
            True,
            True,
            f"{len(settings.mail.bank_senders)} banka adresi, {len(others)} banka dışı gönderici",
        ),
        StepState(SetupStep.DOCUMENTS, kept > 0, False, f"{kept} belge" if kept else "Henüz belge yok."),
        StepState(
            SetupStep.NOTIFICATIONS,
            bool(ready),
            True,
            "Hazır: " + ", ".join(CHANNEL[c.channel] for c in ready) if ready else "Yalnızca uygulama içi.",
        ),
        _service_step(ws),
        StepState(
            SetupStep.REMOTE,
            settings.server.remote == "tailscale",
            True,
            "Tailscale ile açık." if settings.server.remote == "tailscale" else "Kapalı: yalnızca bu bilgisayardan.",
        ),
    ]
    mail_done = next(s.done for s in steps if s.step is SetupStep.MAIL)
    return Progress(steps, not names and not kept and not mail_done)
