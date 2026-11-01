"""The browser extension's endpoints (ADR-0016): pairing, the proof that this is the paired service, the list of
paired extensions, and the mail intake that only a bridge's token opens."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, StringConstraints
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from ...app import bridge
from ...app.bridge import MAX_MESSAGE_BYTES
from ..context import context_of
from ..guard import Principal
from ..problems import Problem
from .deps import only

router = APIRouter()

# A page of the service starts pairing; an extension finishes it from its own origin (or a client without one).
_EXTENSION_ORIGINS = ("chrome-extension://",)


class PairingOut(BaseModel):
    code: str
    expires_in: int  # seconds


class PairIn(BaseModel):
    code: str = Field(min_length=4, max_length=20)
    name: str = Field(default="", max_length=80)  # the browser, as the extension names itself


class PairedOut(BaseModel):
    id: str
    token: str


class ProofOut(BaseModel):
    proof: str


class BridgeOut(BaseModel):
    id: str
    name: str
    created_at: str
    last_seen: str
    active: bool


class CursorOut(BaseModel):
    last_id: str
    last_date: str
    start_day: str
    senders: list[str]
    history_due: bool  # no finished scan of Gmail searched this start day and these senders: the extension scans


GmailId = Annotated[str, StringConstraints(pattern=r"^[0-9]{1,25}$")]  # Gmail's message id, in decimal
Day = Annotated[str, StringConstraints(pattern=r"^([0-9]{4}-[0-9]{2}-[0-9]{2})?$")]  # YYYY-MM-DD; "" for all
Domain = Annotated[str, StringConstraints(min_length=1, max_length=253)]


class KnownIn(BaseModel):
    ids: list[GmailId] = Field(max_length=1000)


class KnownOut(BaseModel):
    missing: list[str]  # the ids the service holds no message for, in the order asked


class ScannedIn(BaseModel):
    """What a finished scan of Gmail searched, as the cursor said when it began."""

    start_day: Day
    senders: list[Domain] = Field(max_length=500)


class ScannedOut(BaseModel):
    history_due: bool  # the settings changed while the scan ran: the history needs another one


class AlarmPageIn(BaseModel):
    """What a "Show original" page without the message showed: never its text, only its masked title."""

    length: int = Field(ge=0)
    title: str = Field(default="", max_length=80)
    download: bool  # the page has the "Download original" link
    raw_id: bool  # the page names the raw text's element


class AlarmIn(BaseModel):
    layer: int = Field(ge=1, le=3)  # 1: inbox feed, 2: full search, 3: raw message
    version: str = Field(default="", max_length=20)  # the extension's version: the fix comes with a newer one
    page: AlarmPageIn | None = None


class AlarmOut(BaseModel):
    news: bool  # false: this layer's alarm was told before for this version


class DeliveredOut(BaseModel):
    taken: str  # stored, known, unlisted, unverified, business, too_large
    documents: int


@router.post("/api/bridge/pairings", dependencies=[Depends(only(Principal.BROWSER))])
def start_pairing(request: Request) -> PairingOut:
    code, seconds = context_of(request).pairing.issue()
    return PairingOut(code=code, expires_in=int(seconds))


@router.post("/api/bridge/pair")
def pair(request: Request, body: PairIn) -> PairedOut:
    """Trade a pairing code for the bridge's token; only an extension (or a client without an origin) may."""
    origin = request.headers.get("origin", "")
    if origin and not origin.startswith(_EXTENSION_ORIGINS):
        raise Problem(403, "write_denied", "Eşleştirmeyi yalnızca tarayıcı eklentisi tamamlayabilir.")
    context = context_of(request)
    if not context.pairing.redeem(body.code):
        raise Problem(403, "pairing_code_invalid", "Eşleştirme kodu geçersiz ya da süresi dolmuş; yeni bir kod alın.")
    paired = bridge.pair(context.ws, body.name)
    return PairedOut(id=paired.id, token=paired.token)


@router.get("/api/bridge/hello")
def hello(
    request: Request,
    id: str = Query(min_length=1, max_length=40),
    nonce: str = Query(min_length=16, max_length=128),
) -> ProofOut:
    found = bridge.proof(context_of(request).ws, id, nonce)
    if found is None:
        raise Problem(404, "bridge_unknown", "Bu eklenti bu servisle eşleşmemiş ya da eşleşmesi iptal edilmiş.")
    return ProofOut(proof=found)


@router.get("/api/bridge", dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])
def paired_bridges(request: Request) -> list[BridgeOut]:
    return [
        BridgeOut(id=b.id, name=b.name, created_at=b.created_at, last_seen=b.last_seen, active=b.active)
        for b in bridge.every(context_of(request).ws)
    ]


@router.delete(
    "/api/bridge/{bridge_id}", status_code=204, dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))]
)
def revoke(request: Request, bridge_id: str) -> Response:
    if not bridge.revoke(context_of(request).ws, bridge_id):
        raise Problem(404, "bridge_unknown", "Böyle etkin bir eşleşme yok.")
    return Response(status_code=204)


@router.get("/api/ingest/mail/cursor")
def cursor(request: Request) -> CursorOut:
    found = bridge.cursor(context_of(request).ws)
    return CursorOut(
        last_id=found.last_id,
        last_date=found.last_date,
        start_day=found.start_day,
        senders=list(found.senders),
        history_due=found.history_due,
    )


@router.post("/api/ingest/mail/known")
def known(request: Request, body: KnownIn) -> KnownOut:
    """Which of the messages a scan of Gmail found the service holds already: only the missing are downloaded."""
    return KnownOut(missing=bridge.missing(context_of(request).ws, body.ids))


@router.post("/api/ingest/mail/scanned")
def scan_finished(request: Request, body: ScannedIn) -> ScannedOut:
    """A scan of Gmail finished; the service remembers what it searched, so the history is not scanned again until
    the start day or the senders change."""
    return ScannedOut(history_due=bridge.scanned(context_of(request).ws, body.start_day, body.senders))


@router.post("/api/ingest/mail/alarm")
def layer_alarm(request: Request, body: AlarmIn) -> AlarmOut:
    """A layer of the extension stopped on a Gmail page it does not know (ADR-0016's format alarm)."""
    page = None if body.page is None else body.page.model_dump()
    return AlarmOut(news=bridge.alarm(context_of(request).ws, body.layer, body.version, page))


@router.post("/api/ingest/mail")
async def deliver(request: Request) -> DeliveredOut:
    """One raw message (RFC 822) in the body; Gmail's id and date of it in X-Gmail-Id and X-Gmail-Date."""
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > MAX_MESSAGE_BYTES:
        raise Problem(413, "message_too_large", f"İleti {MAX_MESSAGE_BYTES >> 20} MB sınırından büyük.")
    raw = await request.body()
    if len(raw) > MAX_MESSAGE_BYTES:
        raise Problem(413, "message_too_large", f"İleti {MAX_MESSAGE_BYTES >> 20} MB sınırından büyük.")
    if not raw:
        raise Problem(400, "message_empty", "İleti boş.")
    gmail_id = request.headers.get("x-gmail-id", "")[:40]
    gmail_date = request.headers.get("x-gmail-date", "")[:40]
    outcome = await run_in_threadpool(bridge.deliver, context_of(request).ws, raw, gmail_id, gmail_date)
    return DeliveredOut(taken=str(outcome.taken), documents=outcome.documents)
