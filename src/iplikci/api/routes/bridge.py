"""The browser extension's endpoints (ADR-0016): its folder for the browser to load (K20), pairing, the proof that
this is the paired service, the list of paired extensions, and what only a bridge's token opens: the mail intake, the
login link of its "İplikçi Nedim'i aç" (ADR-0019) and İplikçi Nedim's lines its window shows (ADR-0020)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, StringConstraints
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from ...app import bridge, dashboard, extension, sayings
from ...app.bridge import MAX_MESSAGE_BYTES
from ...app.workspace import Busy
from ..context import context_of
from ..guard import Principal
from ..models import LoginLink, SayingOut, saying_out
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


class ExtensionOut(BaseModel):
    available: bool  # this installation carries the extension
    version: str  # "" when it carries none
    folder: str  # where the browser loads it from, once made; "" before
    current: bool  # the folder holds the files of this version


class ExtensionFolderOut(BaseModel):
    folder: str
    version: str
    opened: bool  # the system's file manager shows the folder; otherwise the page gives its path


class SayingsOut(BaseModel):
    items: list[SayingOut]  # the one to show first, the rest for "Başka bir söz"


@router.get("/api/extension", dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])
def extension_state(request: Request) -> ExtensionOut:
    """The extension the program carries, and its folder in the data folder (K20: loaded unpacked)."""
    found = extension.state(context_of(request).ws)
    return ExtensionOut(
        available=found.available,
        version=found.version,
        folder=str(found.folder) if found.folder else "",
        current=found.current,
    )


@router.post("/api/extension/folder", dependencies=[Depends(only(Principal.BROWSER))])
def extension_folder(request: Request) -> ExtensionFolderOut:
    """Make the extension's folder, or bring it up to date, and show it in the system's file manager."""
    try:
        shown = extension.show(context_of(request).ws)
    except extension.FolderError as exc:
        raise Problem(409, "extension_folder_failed", str(exc)) from exc
    except extension.ExtensionError as exc:
        raise Problem(409, "extension_unavailable", str(exc)) from exc
    return ExtensionFolderOut(folder=str(shown.folder), version=shown.version, opened=shown.opened)


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


@router.post("/api/bridge/login-link", dependencies=[Depends(only(Principal.BRIDGE))])
def bridge_login_link(request: Request) -> LoginLink:
    """A one-time login link for the browser the paired extension runs in, as the command line gets one: its
    "İplikçi Nedim'i aç" opens the interface with it (ADR-0019). Two minutes, one use, on 127.0.0.1 only."""
    context = context_of(request)
    return LoginLink(url=context.login_url(context.keys.issue()))


@router.get("/api/bridge/sayings", dependencies=[Depends(only(Principal.BRIDGE))])
def bridge_sayings(request: Request) -> SayingsOut:
    """İplikçi Nedim's lines on the money as the Pano has them, for the paired extension's window (ADR-0020): words
    and shares only, never an amount, an account or a name."""
    context = context_of(request)
    try:
        a = context.analysis.get()
    except Busy as exc:
        raise Problem(503, "busy", str(exc)) from exc
    today = context.today()
    found = sayings.sayings(a, dashboard.dashboard(context.ws, a, today), today)
    return SayingsOut(items=[saying_out(s) for s in found])


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
