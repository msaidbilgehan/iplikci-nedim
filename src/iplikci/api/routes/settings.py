"""The settings the interface changes (F17): the non-bank senders (F14), the user's and the company names, how e-mail
comes in (an IMAP account with its app password, or the browser extension), the start day, how long backups are kept.
A browser changes them only from the service's own pages (the guard); the API token reads them. Nothing of them goes
to the log, and a password is only taken in."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ...app import senders, setup
from ...app.senders import SenderRefused, SettingsError
from ...app.setup import Actor, SetupStep
from ..context import context_of
from ..guard import Principal
from ..models import OtherSendersIn, OtherSendersOut
from ..problems import Problem
from .deps import only

router = APIRouter()

OTHER_SENDERS = "/api/settings/mail/other-senders"


@router.get(OTHER_SENDERS, dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])
def other_senders(request: Request) -> OtherSendersOut:
    """The domains whose bills and receipts are taken in beside the banks' messages."""
    try:
        found = senders.other_senders(context_of(request).ws)
    except SettingsError as exc:
        raise Problem(409, "settings_invalid", str(exc)) from exc
    return OtherSendersOut(domains=list(found))


@router.put(OTHER_SENDERS, dependencies=[Depends(only(Principal.BROWSER))])
def set_other_senders(request: Request, body: OtherSendersIn) -> OtherSendersOut:
    """Replace the list. A bank's domain, a domain named twice or a value that is no domain is refused, and nothing
    is saved. Messages are taken from the new list only when their sender passes DMARC; the history is read again."""
    try:
        saved = senders.set_other_senders(context_of(request).ws, body.domains)
    except SenderRefused as exc:
        raise Problem(400, "sender_invalid", str(exc)) from exc
    except SettingsError as exc:
        raise Problem(409, "settings_invalid", str(exc)) from exc
    return OtherSendersOut(domains=list(saved))


# --- the settings of the setup wizard and the Settings screen (F17) ---------------------------------------------


class MailSettingsOut(BaseModel):
    connector: Literal["imap", "browser_bridge"]  # an app password, or the browser extension (ADR-0016)
    configured: bool  # an IMAP account is set up (the extension's pairings are listed under /api/bridge)
    address: str  # masked, "k•••@example.com"; "" when none is set up
    start: date  # the day the mailbox is read from
    server: str  # the IMAP server; "" for the browser extension
    stopped: bool  # a refused login stopped the IMAP connector until it is set up again
    last_error: str


class SettingsOut(BaseModel):
    home: str  # the data folder
    port: int
    names: list[str]  # the user's own names and their forms
    business_names: list[str]  # company names: their documents stay out
    mail: MailSettingsOut
    bank_senders: list[str]  # the banks' sender domains the program reads (shipped with it)
    backup_days: int


NAME = r"^[^\x00-\x1f\x7f]*$"  # no control characters


class IdentityIn(BaseModel):
    names: list[Annotated[str, Field(max_length=100, pattern=NAME)]] = Field(max_length=20)
    business_names: list[Annotated[str, Field(max_length=150, pattern=NAME)]] = Field(max_length=20)


class BackupSettingsIn(BaseModel):
    keep_days: int = Field(ge=1, le=365)


class MailSettingsIn(BaseModel):
    connector: Literal["imap", "browser_bridge"] | None = None
    start: date | None = None  # read the mailbox from this day on


class ImapIn(BaseModel):
    """An account that allows app passwords: its address and app password, tried once."""

    address: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)  # goes to the keychain only; never stored or logged here
    start: date | None = None


class ImapOut(BaseModel):
    folder: str  # the folder that will be read
    in_keyring: bool  # false: this computer has no keychain, and the password was not kept


def _settings_out(found: setup.SettingsView) -> SettingsOut:
    m = found.mail
    return SettingsOut(
        home=found.home,
        port=found.port,
        names=list(found.names),
        business_names=list(found.business_names),
        mail=MailSettingsOut(
            connector="browser_bridge" if m.connector == "browser_bridge" else "imap",
            configured=m.configured,
            address=m.address,
            start=m.start,
            server=m.server,
            stopped=m.stopped,
            last_error=m.last_error,
        ),
        bank_senders=list(found.bank_senders),
        backup_days=found.backup_days,
    )


def _refused(exc: Exception) -> Problem:
    return Problem(409, "settings_invalid", str(exc))


@router.get("/api/settings", dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])
def settings_view(request: Request) -> SettingsOut:
    """The settings as the wizard and the Settings screen show them; no secret, the e-mail address masked."""
    try:
        return _settings_out(setup.view(context_of(request).ws))
    except setup.SettingsError as exc:
        raise _refused(exc) from exc


@router.put("/api/settings/identity", dependencies=[Depends(only(Principal.BROWSER))])
def settings_identity(request: Request, body: IdentityIn) -> SettingsOut:
    """The user's names and the company names. Other company names make the documents be read again with them."""
    try:
        return _settings_out(setup.set_identity(context_of(request).ws, body.names, body.business_names, Actor.USER))
    except setup.SettingsError as exc:
        raise Problem(400, "settings_refused", str(exc)) from exc


@router.put("/api/settings/backup", dependencies=[Depends(only(Principal.BROWSER))])
def settings_backup(request: Request, body: BackupSettingsIn) -> SettingsOut:
    try:
        return _settings_out(setup.set_backup_days(context_of(request).ws, body.keep_days, Actor.USER))
    except setup.SettingsError as exc:
        raise Problem(400, "settings_refused", str(exc)) from exc


@router.put("/api/settings/mail", dependencies=[Depends(only(Principal.BROWSER))])
def settings_mail(request: Request, body: MailSettingsIn) -> SettingsOut:
    """The way e-mail comes in and the day the mailbox is read from."""
    try:
        return _settings_out(setup.set_mail(context_of(request).ws, body.connector, body.start, Actor.USER))
    except setup.SettingsError as exc:
        raise Problem(400, "settings_refused", str(exc)) from exc


@router.post("/api/settings/mail/imap", dependencies=[Depends(only(Principal.BROWSER))])
def settings_imap(request: Request, body: ImapIn) -> ImapOut:
    """Set an IMAP account up: one login with its app password, then the password goes to the keychain. A refused
    login keeps nothing and is never tried again by the program."""
    try:
        found = setup.setup_imap(context_of(request).ws, body.address, body.password, body.start, Actor.USER)
    except setup.MailError as exc:
        raise Problem(400, "mail_refused", str(exc)) from exc
    except setup.SettingsError as exc:
        raise _refused(exc) from exc
    return ImapOut(folder=found.folder, in_keyring=found.in_keyring)


@router.delete("/api/settings/mail/imap", status_code=204, dependencies=[Depends(only(Principal.BROWSER))])
def settings_imap_remove(request: Request) -> None:
    """Forget the IMAP account and its password."""
    if not setup.remove_imap(context_of(request).ws, Actor.USER):
        raise Problem(404, "mail_not_set_up", "Kurulu bir IMAP hesabı yok.")


class SetupStepOut(BaseModel):
    step: SetupStep
    done: bool
    optional: bool  # the wizard lets the user go on without it
    note: str


class SetupOut(BaseModel):
    steps: list[SetupStepOut]  # in the wizard's order
    first_run: bool  # nothing set up yet: the interface opens the wizard


@router.get("/api/setup", dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])
def setup_progress(request: Request) -> SetupOut:
    """Where each step of the setup wizard stands (F17)."""
    try:
        found = setup.progress(context_of(request).ws)
    except setup.SettingsError as exc:
        raise _refused(exc) from exc
    return SetupOut(
        steps=[SetupStepOut(step=s.step, done=s.done, optional=s.optional, note=s.note) for s in found.steps],
        first_run=found.first_run,
    )
