"""The user's own Telegram bot as a way in (ADR-0021, beside the notifications it carries, ADR-0010): the chat that
pairs with it, and the documents that chat sends it.

The bot's messages are read from where the last read stopped. The service's ear waits for them (long polling,
ingest.telegram); a pairing being checked reads them at once (the interface while its code is open, the command line).
Whichever reads them handles each message once, in one transaction with the offset, so neither a pairing code nor a
document is lost to the other reader. When both read at the same moment, Telegram cuts the waiting read short (a
conflict) and the ear reads again a little later.

- A "/start <code>" with the open pairing code pairs its chat, which the notifications then go to, and greets it.
- From the paired chat, one-to-one with the bot, a document is queued for the worker. The worker fetches it from
  Telegram and takes it in as an upload through the interface is taken in: its kind from its content, a company
  document refused, the same bytes noted as another arrival. Sending it is the consent, as dropping a file into the
  inbox is (F02); the worker then answers with what became of it. A photo, a file over the 20 MB Telegram lets a bot
  fetch and a document from a group are answered with what to do instead; words get a short help.
- Anything from another chat is passed over, unread and unanswered: the bot's name is no secret, and a stranger's file
  never reaches the computer.
"""

import hashlib
import hmac
import logging
import secrets as tokens
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from .. import egress
from ..domain.codes import Actor, Channel, DocumentStatus, SourceKind
from ..ingest.telegram import Heard
from ..notify import channels
from ..notify.channels import CONFLICT, FILE_LIMIT, TOO_LARGE, Fetch, Post, SendError, Update
from ..settings import config
from ..storage import audit, feed_state, jobs
from ..storage.db import Database
from . import intake, kinds, notify, uploads
from .notify import BOT, OFFSET, PAIRING, NotifyError, PostFor
from .workspace import Workspace

log = logging.getLogger("iplikci.telegram")

__all__ = ["Heard", "Pairing", "check_pairing", "listen", "read", "said", "set_documents", "start_pairing"]

PAIRING_TIME = timedelta(minutes=10)
WAIT = 25  # seconds a read of the bot's messages may wait for one (long polling)
DOCUMENTS_SET = "notify.telegram_documents"  # the audit log's name for turning the documents on or off
_FETCH_TIME = 120.0  # seconds a document may take to come from Telegram's file server
_SHOWN = 20  # documents an answer names one by one; a zip may hold more
_UNNAMED = "telegram-belgesi"  # a document sent without a name: what it is comes from its content anyway
_WHY = (DocumentStatus.UNREADABLE, DocumentStatus.UNPROCESSED)  # kept documents whose answer says why they gave no rows

type FetchFor = Callable[[str], Fetch]  # a bot's token → its downloads from Telegram's file server

_GREETING = "İplikçi Nedim bildirimleri artık bu sohbete gelecek."
_SEND_HERE = (
    "Bankalarınızdan indirdiğiniz belgeleri (kart ekstresi, hesap dökümü, dekont) bu sohbete dosya olarak "
    "gönderirseniz İplikçi Nedim onları okuyup arşive alır ve her birine ne olduğunu burada yazar."
)
_HELP = (
    "Bankanızdan indirdiğiniz belgeyi bu sohbete dosya olarak gönderin (ataç → Dosya): PDF, Excel, HTML, XML, ZIP ya "
    "da e-posta dosyası. İplikçi Nedim belgenin ne olduğunu içeriğinden anlar, arşive alır ve sonucu burada yazar. "
    "Bildirimler de bu sohbete gelir."
)
_OFF = (
    "Telegram'dan belge alma kapalı. İplikçi Nedim'in Bildirimler ekranında, Telegram kartından açabilirsiniz; "
    "belgeyi Belge ekle ekranından da ekleyebilirsiniz."
)
_GROUP = (
    "Belgeler yalnızca botla bire bir sohbetten alınır; bu sohbet bir grup. Belge göndermek için Bildirimler "
    "ekranındaki Telegram kartından botla kendi sohbetinizi eşleştirin."
)
_PHOTO = (
    "Fotoğraf okunamaz: İplikçi Nedim bankanın verdiği dosyayı okur. Belgeyi bankanızın uygulamasından ya da "
    "internet şubesinden PDF ya da Excel olarak indirip bu sohbete dosya olarak gönderin (ataç → Dosya)."
)
_TOO_LARGE = (
    f"Bu dosya {FILE_LIMIT >> 20} MB sınırından büyük: Telegram botların daha büyük dosya almasına izin vermiyor. "
    "Belgeyi İplikçi Nedim'in Belge ekle ekranından ekleyin."
)


def _now() -> datetime:
    return datetime.now().astimezone()


def _iso(at: datetime) -> str:
    return at.astimezone(UTC).replace(microsecond=0).isoformat()


def _settings(ws: Workspace) -> config.Settings:
    return config.load(ws.layout.settings)


@dataclass(frozen=True)
class _Answer:
    """A message to a chat, answering one of its messages (0: none)."""

    chat: int
    text: str
    to: int = 0


def _say(post: Post, answer: _Answer) -> None:
    """Send an answer; one that cannot go is let go: what it would tell is done, and the screens tell it too."""
    try:
        channels.reply(post, answer.chat, answer.text, answer.to)
    except SendError as exc:
        log.warning("an answer to the bot's chat could not be sent: %s", exc)


# --- pairing -------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Pairing:
    code: str
    expires: str  # UTC
    bot: str
    link: str  # opens the chat with the bot, the code ready to send; "" when the bot's name is not known


def start_pairing(ws: Workspace, at: datetime | None = None) -> Pairing:
    """A code the user sends the bot as "/start <code>" within ten minutes; the chat it comes from is then the one
    the notifications go to, and the one whose documents are taken."""
    with ws.db() as db:
        bot = feed_state.load(db, BOT)
        if bot is None or not notify.telegram_token():
            raise NotifyError("Önce Telegram bot belirtecini girin.")
        code = tokens.token_hex(4)
        expires = _iso((at or _now()) + PAIRING_TIME)
        feed_state.save(db, PAIRING, {"code": code, "expires": expires})
    name = bot if isinstance(bot, str) else ""
    return Pairing(code, expires, name, f"https://t.me/{name}?start={code}" if name else "")


def _open(pairing: object, at: datetime) -> bool:
    """A pairing that waits for its code."""
    if not isinstance(pairing, dict):
        return False
    found = cast(dict[str, Any], pairing)
    return not found.get("paired") and str(found.get("expires", "")) >= _iso(at)


def _paired(pairing: object) -> bool:
    """A pairing whose code came."""
    return isinstance(pairing, dict) and bool(cast(dict[str, Any], pairing).get("paired"))


def check_pairing(ws: Workspace, at: datetime | None = None, post_for: PostFor | None = None) -> bool:
    """Whether the open code came and its chat paired. The bot's new messages are read once here (nothing waits) and
    handled as the service's ear handles them. While the ear waits for them Telegram refuses this read, and the ear
    pairs the chat itself: the next check finds it paired."""
    at = at or _now()
    with ws.db() as db:
        pairing = feed_state.load(db, PAIRING)
    if _paired(pairing):
        return True
    if not _open(pairing, at):
        raise NotifyError("Açık bir eşleştirme kodu yok ya da süresi doldu; yeni bir kod alın.")
    token = notify.telegram_token()
    if not token:
        raise NotifyError("Önce Telegram bot belirtecini girin.")
    try:
        read(ws, (post_for or notify.bot_calls(_settings(ws)))(token), 0, at)
    except SendError as exc:
        if exc.status == CONFLICT:
            return False
        raise NotifyError(str(exc)) from None
    with ws.db() as db:
        return _paired(feed_state.load(db, PAIRING))


def _pair(ws: Workspace, db: Database, update: Update, at: datetime) -> bool:
    """Pair the chat that sent the open pairing's code; whether it did."""
    pairing = feed_state.load(db, PAIRING)
    if not _open(pairing, at):
        return False
    found = cast(dict[str, Any], pairing)
    if not hmac.compare_digest(update.start_code.encode(), str(found.get("code", "")).encode()):
        return False
    config.update(ws.layout.settings, "notify", {"telegram_chat": update.chat})
    feed_state.save(db, PAIRING, found | {"paired": True})
    notify.resume_channel(db, Channel.TELEGRAM)
    audit.record(db, Actor.USER, notify.TELEGRAM_PAIRED, "telegram")
    return True


# --- reading the bot's messages ------------------------------------------------------------------------


def _offset(db: Database) -> int:
    found = feed_state.load(db, OFFSET)
    return found if isinstance(found, int) else 0


def read(ws: Workspace, post: Post, wait: int, at: datetime | None = None) -> int:
    """Read the bot's messages since the last read, waiting up to wait seconds for one, and handle each once; the
    answers go out last. How many messages were new. SendError when Telegram refuses the read or cannot be reached."""
    with ws.db() as db:
        offset = _offset(db)
    found, after = channels.updates(post, offset, wait)
    answers, new = _handle(ws, found, after, at or _now())
    for answer in answers:
        _say(post, answer)
    return new


def _handle(ws: Workspace, found: Sequence[Update], after: int, at: datetime) -> tuple[list[_Answer], int]:
    """Each message not handled yet, in one transaction with the offset that follows them: a message another read
    handled meanwhile is passed over. The answers to send, and how many messages were new."""
    settings = _settings(ws)
    answers: list[_Answer] = []
    new = 0
    with ws.db() as db, db.transaction():
        done = _offset(db)
        chat = settings.notify.telegram_chat
        bot = str(feed_state.load(db, BOT) or "")
        for update in found:
            if update.update < done:
                continue
            new += 1
            if update.start_code and _pair(ws, db, update, at):
                chat = update.chat
                greeting = f"{_GREETING} {_SEND_HERE}" if settings.notify.telegram_documents else _GREETING
                answers.append(_Answer(update.chat, f"Telegram bağlandı\n{greeting}"))
            elif chat and update.chat == chat:
                answer = _from_paired(db, settings, bot, update)
                if answer is not None:
                    answers.append(answer)
        if after > done:
            feed_state.save(db, OFFSET, after)
    return answers, new


def _from_paired(db: Database, settings: config.Settings, bot: str, update: Update) -> _Answer | None:
    """A message of the paired chat: a document queued for the worker (it answers once the document is in), or the
    answer to anything else."""
    file = update.document
    if file is None and not update.photo:  # words: the help tells how to send documents, while they are taken
        words = update.private and update.text.strip() and not update.start_code
        return _Answer(update.chat, _HELP, update.message) if words and settings.notify.telegram_documents else None
    if not settings.notify.telegram_documents:
        return _Answer(update.chat, _OFF, update.message)
    if not update.private:
        return _Answer(update.chat, _GROUP, update.message)
    if file is None:
        return _Answer(update.chat, _PHOTO, update.message)
    if file.size > FILE_LIMIT:
        return _Answer(update.chat, _TOO_LARGE, update.message)
    payload = {"chat": update.chat, "message": update.message, "file": file.id, "name": file.name}
    jobs.add(db, kinds.TELEGRAM_DOCUMENT, payload, key=f"telegram:{bot}:{update.update}")
    return None


def _listening(db: Database, settings: config.Settings, at: datetime) -> bool:
    """Whether the bot's messages are read for anything: a paired chat that may send documents, or a pairing that
    waits for its code. Only then is the keyring read and Telegram asked."""
    if feed_state.load(db, BOT) is None or Channel.TELEGRAM in notify.stopped_channels(db):
        return False
    if settings.notify.telegram_chat and settings.notify.telegram_documents:
        return True
    return _open(feed_state.load(db, PAIRING), at)


def listen(ws: Workspace, wait: int = WAIT, post_for: PostFor | None = None) -> Heard:
    """One read for the service's ear: wait up to wait seconds for the bot's messages and handle what came. A token
    Telegram refuses stops the channel, as a refused notification does, until the user enters it anew."""
    settings = _settings(ws)
    with ws.db() as db:
        if not _listening(db, settings, _now()):
            return Heard.NOTHING
    token = notify.telegram_token()
    if not token:
        return Heard.NOTHING
    post = (post_for or notify.bot_calls(settings, wait + 15.0))(token)
    try:
        read(ws, post, wait)
    except SendError as exc:
        if exc.refused:
            with ws.db() as db:
                notify.stop_channel(db, Channel.TELEGRAM, str(exc))
            return Heard.NOTHING
        if exc.status == CONFLICT:
            return Heard.TAKEN
        log.warning("the bot's messages could not be read: %s", exc)
        return Heard.FAILED
    return Heard.READ


def set_documents(ws: Workspace, on: bool, actor: Actor) -> config.Settings:
    """Take the documents the paired chat sends the bot, or not; while off the service reads none of the bot's
    messages."""
    saved = config.update(ws.layout.settings, "notify", {"telegram_documents": on})
    with ws.db() as db:
        audit.record(db, actor, DOCUMENTS_SET, "telegram", on=on)
    return saved


# --- a document sent to the bot ------------------------------------------------------------------------


def file_calls(settings: config.Settings) -> FetchFor:
    """A bot's downloads from Telegram's file server, by its token: a byte more than a bot may fetch tells a file
    that is larger."""

    def calls(token: str) -> Fetch:
        def fetch(path: str) -> tuple[int, bytes]:
            where = f"/file/bot{token}/{path}"
            return egress.https_get(egress.TELEGRAM, where, settings, timeout=_FETCH_TIME, limit=FILE_LIMIT + 1)

        return fetch

    return calls


def _batch(payload: Mapping[str, Any]) -> str:
    """The upload batch of a message's document: the same on every attempt, so a document fetched once is not
    fetched again."""
    return hashlib.sha256(f"{payload['chat']}:{payload['message']}:{payload['file']}".encode()).hexdigest()[:16]


def _waiting(folder: Path) -> bool:
    """Whether the batch already holds the document, fetched by an earlier attempt."""
    return any(p.is_file() and not p.name.startswith(".") for p in folder.rglob("*"))


def _lasting(exc: SendError) -> bool:
    """A refusal that another attempt would meet again: the file is too large or Telegram does not know it."""
    return exc.status == TOO_LARGE or (400 <= exc.status < 500 and exc.status not in (408, 429))


def take_document(
    ws: Workspace, payload: Mapping[str, Any], post_for: PostFor | None = None, fetch_for: FetchFor | None = None
) -> int:
    """The worker's job: fetch a document the paired chat sent the bot, take it in as an upload through the
    interface is taken in, and answer the chat with what became of it. How many documents were kept.

    A chat that is no longer the paired one, or documents turned off meanwhile, leaves the document unfetched.
    Telegram out of reach fails the attempt, and the worker tries again later; a file Telegram will not give is
    answered with why."""
    chat, message = int(payload["chat"]), int(payload.get("message", 0))
    name = str(payload.get("name") or _UNNAMED)
    settings = _settings(ws)
    if chat != settings.notify.telegram_chat or not settings.notify.telegram_documents:
        log.info("a document sent to the bot was passed over: its chat is no longer paired, or documents are off")
        return 0
    token = notify.telegram_token()
    if not token:
        return 0
    post = (post_for or notify.bot_calls(settings))(token)
    _, folder = uploads.batch_folder(ws, _batch(payload))
    if not _waiting(folder):
        try:
            data = channels.download(post, (fetch_for or file_calls(settings))(token), str(payload["file"]))
        except SendError as exc:
            _drop_empty(folder)
            if exc.refused:  # the token: the channel stops until it is entered anew
                with ws.db() as db:
                    notify.stop_channel(db, Channel.TELEGRAM, str(exc))
                return 0
            if not _lasting(exc):
                raise  # out of reach for now: the worker tries again later
            _say(post, _Answer(chat, f"{name}: Telegram'dan alınamadı ({exc}).", message))
            return 0
        saved = _keep(folder, name, data)
        if saved.status == "reddedildi":
            _drop_empty(folder)
            _say(post, _Answer(chat, f"{name}: alınmadı; {saved.reason}.", message))
            return 0
    applied = intake.apply(ws, intake.plan_upload(ws, folder, SourceKind.TELEGRAM), Actor.USER)
    _say(post, _Answer(chat, said(ws, applied), message))
    return len(applied.stored)


def _keep(folder: Path, name: str, data: bytes) -> uploads.Upload:
    """The fetched document in its batch under its name made safe, or refused as an upload would be (no document,
    a hidden file)."""
    partial = uploads.partial_file(folder)
    try:
        partial.write_bytes(data)
    except OSError:
        partial.unlink(missing_ok=True)  # our own partial file, never a document
        raise
    return uploads.finish_upload(folder, name, partial, len(data))


def _drop_empty(folder: Path) -> None:
    """A batch's folder that holds nothing: removed, so no empty batch waits to be set aside."""
    if folder.is_dir() and not any(folder.iterdir()):
        folder.rmdir()


def said(ws: Workspace, applied: intake.Applied) -> str:
    """The answer to a document sent to the bot: what became of each document in it (a zip's, an e-mail's)."""
    lines = [_line(ws, c) for c in applied.items if c.verdict is not intake.Verdict.ARCHIVE]
    if not lines:
        return "Dosyada belge bulunamadı."
    shown = lines[:_SHOWN]
    if len(lines) > _SHOWN:
        shown.append(f"… ve {len(lines) - _SHOWN} belge daha; hepsi Belgeler ekranında.")
    return "\n".join(shown)


def _line(ws: Workspace, c: intake.Candidate) -> str:
    """A document's line: the name the archive gives it once read (its original name before), what became of it,
    and for a statement its rows and its check."""
    described = intake.describe(c, ws)
    name = str(described.get("target") or c.name)
    line = f"{name}: {intake.ACTION_DONE.get(c.action, c.action)}"
    document = described.get("document")
    if isinstance(document, dict):
        found = cast(dict[str, object], document)
        if found.get("kind") in ("ekstre", "hesap"):
            return f"{line} ({found['rows']} satır; {found['check']})"
    return f"{line} ({c.reason})" if c.reason and c.status in _WHY else line
