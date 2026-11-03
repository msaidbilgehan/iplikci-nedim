"""The exchange rates fetched on request (F12, architecture §15): the worker fetches now instead of at its next 16:30.
Where the rates stand is in /api/system's rates part; the rates themselves in /api/fx."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ...app import fx
from ..context import context_of
from ..guard import Principal
from ..problems import Problem
from .deps import only

router = APIRouter(dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])


class RatesFetchIn(BaseModel):
    history: bool = False  # true: every day of the history not asked for yet; false: the day's bulletin and the
    # business days missed since the newest one


class RatesQueuedOut(BaseModel):
    queued: bool


@router.post("/api/fx/fetch", status_code=202)
def fetch_now(request: Request, body: RatesFetchIn | None = None) -> RatesQueuedOut:
    """Ask the worker for a fetch; it starts within seconds, and the System screen shows how it went."""
    ws = context_of(request).ws
    if not fx.providers_of(ws):
        raise Problem(409, "fx_no_provider", "Ayarlarda kur sağlayıcısı yok: kurlar ağdan çekilmiyor.")
    fx.request(ws, history=body is not None and body.history)
    return RatesQueuedOut(queued=True)
