"""The settings the interface changes (F17), one list at a time: so far the non-bank senders (F14). A browser changes
them only from the service's own pages (the guard); the API token reads them. Nothing of them goes to the log."""

from fastapi import APIRouter, Depends, Request

from ...app import senders
from ...app.senders import SenderRefused, SettingsError
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
