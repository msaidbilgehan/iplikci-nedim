"""The e-mail intake on request (ADR-0015): the IMAP connector fetches now instead of at its next quarter hour."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ...app import mail
from ..context import context_of
from ..guard import Principal
from ..problems import Problem
from .deps import only

router = APIRouter(dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])


class FetchQueuedOut(BaseModel):
    queued: bool


@router.post("/api/mail/fetch", status_code=202)
def fetch_now(request: Request) -> FetchQueuedOut:
    """Ask the worker for a fetch; it starts within seconds. The browser extension's messages come on their own."""
    ws = context_of(request).ws
    state = mail.status(ws)
    if state["connector"] == mail.BRIDGE:
        raise Problem(409, "mail_by_extension", "E-postayı tarayıcı eklentisi getiriyor; servis kutuyu kendisi okumaz.")
    if not state["configured"] or state["stopped"]:
        raise Problem(409, "mail_not_ready", "IMAP hesabı kurulu değil ya da girişi reddedildiği için durdu.")
    mail.request_fetch(ws)
    return FetchQueuedOut(queued=True)
