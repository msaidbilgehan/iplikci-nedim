"""The channels that carry a notification out of the app (ADR-0010). The interface's box needs none: it reads the
notifications kept in the database. Each channel says why it failed in Turkish, never with a secret in it.

- Desktop: macOS's `osascript`, or `notify-send` on Linux; the text goes as arguments, never into a script.
- Telegram: the user's own bot sends to the one chat that paired with it. The bot's token is in the keyring; the
  calls go through egress to the Bot API. The bot's messages are read here too: the pairing's code, and the documents
  the paired chat sends it (ADR-0021), fetched from Telegram's file server.
- E-mail: to the user's own address, over the mail server's SMTP with the IMAP connector's app password. A refused
  login stops the channel: trying again from a program may get the account locked.
"""

import json
import shutil
import smtplib
import subprocess
import sys
import urllib.parse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any, Protocol, cast

from .. import egress
from .content import APP, Message

type Run = Callable[[list[str]], int]  # a program's arguments → its exit status
type Post = Callable[[str, Mapping[str, str]], tuple[int, bytes]]  # a Bot API method and its form → status, body
type Fetch = Callable[[str], tuple[int, bytes]]  # a file's path on Telegram's file server → status, body
type Connect = Callable[[], smtplib.SMTP]  # an open, encrypted connection to the mail server that sends

TELEGRAM_LIMIT = 4096  # characters in a Telegram message
FILE_LIMIT = 20 << 20  # the largest file the Bot API lets a bot download
CONFLICT = 409  # Telegram's answer to a read while another one waits for the same bot's messages
TOO_LARGE = 413  # the status of a file larger than a bot may fetch (Telegram itself refuses one with a 400)
_FOOTER = "Ayrıntılar İplikçi Nedim'in Bildirimler ekranında."


class SendError(Exception):
    """A notification, or another call on the bot, that could not be made: the message says why. refused: the
    channel must not be tried again until the user sets it up anew (a refused login or token). status: the HTTP status
    Telegram answered with; 0 when none came."""

    def __init__(self, message: str, refused: bool = False, status: int = 0) -> None:
        super().__init__(message)
        self.refused = refused
        self.status = status


class Sender(Protocol):
    def send(self, message: Message) -> None: ...


def _run(args: list[str]) -> int:
    done = subprocess.run(args, capture_output=True, timeout=15, check=False)
    return done.returncode


OSASCRIPT = "/usr/bin/osascript"
_SCRIPT = ("on run argv", "display notification (item 2 of argv) with title (item 1 of argv)", "end run")


@dataclass(frozen=True)
class Desktop:
    run: Run | None = None  # None: the program is run (looked up at each use, so a test can stand in for it)
    platform: str = sys.platform
    which: Callable[[str], str | None] = shutil.which

    def command(self, message: Message) -> list[str] | None:
        """The program and arguments that show the message; None where the system has no way."""
        title = f"{APP}: {message.title}"
        if self.platform == "darwin":
            return [OSASCRIPT, *(arg for line in _SCRIPT for arg in ("-e", line)), title, message.body]
        notify = self.which("notify-send") if self.platform.startswith("linux") else None
        return [notify, "--app-name", APP, title, message.body] if notify else None

    @property
    def available(self) -> bool:
        return self.command(Message("", "")) is not None

    def send(self, message: Message) -> None:
        args = self.command(message)
        if args is None:
            raise SendError("bu sistemde masaüstü bildirimi gösterilemiyor (macOS ya da notify-send'li Linux gerekir)")
        try:
            status = (self.run or _run)(args)
        except (OSError, subprocess.SubprocessError) as exc:
            raise SendError(f"masaüstü bildirimi gösterilemedi ({type(exc).__name__})") from None
        if status != 0:
            raise SendError(f"masaüstü bildirimi gösterilemedi (çıkış kodu {status})")


def call(post: Post, method: str, form: Mapping[str, str]) -> Any:
    """A Bot API method's result; SendError with Telegram's own reason when it refuses. A refused token (401, 404)
    or a chat that blocked the bot (403) stops the channel."""
    try:
        status, body = post(method, form)
    except (egress.Unreachable, egress.Refused) as exc:  # their messages name the host only, never the path
        raise SendError(f"Telegram'a ulaşılamadı: {exc}") from None
    except Exception as exc:  # noqa: BLE001 - anything else the network raises: its kind only, the path holds the token
        raise SendError(f"Telegram'a ulaşılamadı ({type(exc).__name__})") from None
    try:
        answer = cast(dict[str, Any], json.loads(body))
    except (ValueError, TypeError):
        raise SendError(f"Telegram anlaşılmayan bir yanıt verdi (HTTP {status})") from None
    if not answer.get("ok"):
        reason = str(answer.get("description", f"HTTP {status}"))[:200]
        raise SendError(f"Telegram reddetti: {reason}", refused=status in (401, 403, 404), status=status)
    return answer.get("result")


def reply(post: Post, chat: int, text: str, to: int = 0) -> None:
    """A message to the chat; to: the chat's message it answers (0: none), quoted when Telegram still has it."""
    form = {"chat_id": str(chat), "text": text[:TELEGRAM_LIMIT], "disable_web_page_preview": "true"}
    if to:
        form["reply_parameters"] = json.dumps({"message_id": to, "allow_sending_without_reply": True})
    call(post, "sendMessage", form)


@dataclass(frozen=True)
class Telegram:
    post: Post
    chat: int

    def send(self, message: Message) -> None:
        reply(self.post, self.chat, f"{message.title}\n{message.body}")


def bot_name(post: Post) -> str:
    """The bot's user name: the token works."""
    me = call(post, "getMe", {})
    return str(cast(dict[str, Any], me).get("username", "")) if isinstance(me, dict) else ""


@dataclass(frozen=True, slots=True)
class FileInfo:
    """A file a chat sent the bot as a document."""

    id: str  # what getFile takes
    name: str  # the name it was sent with; "" when Telegram gives none
    size: int  # in bytes, as Telegram tells it; 0 when it does not


@dataclass(frozen=True, slots=True)
class Update:
    """A message the bot received."""

    update: int  # Telegram's number for it: the next read starts after it
    chat: int
    private: bool  # a one-to-one chat with the bot, never a group or a channel
    sender: int  # the user who sent it; 0 when Telegram names none (a channel's post)
    message: int  # its number in the chat, for a reply
    text: str = ""
    document: FileInfo | None = None
    photo: bool = False  # a picture sent as a photo, not as a file

    @property
    def start_code(self) -> str:
        """The code of a "/start <code>" (or "/start@bot <code>"); "" for anything else."""
        command, _, code = self.text.strip().partition(" ")
        return code.strip() if command.split("@")[0] == "/start" else ""


def updates(post: Post, offset: int, wait: int = 0) -> tuple[list[Update], int]:
    """The messages the bot received since offset, and the offset after them: reading from there tells Telegram it
    may forget them. wait: how many seconds Telegram may hold the call for a first message (long polling); 0 answers
    at once. What is no message is passed over, its number counted."""
    found = call(post, "getUpdates", {"offset": str(offset), "timeout": str(wait), "allowed_updates": '["message"]'})
    out: list[Update] = []
    after = offset
    for update in cast(list[dict[str, Any]], found) if isinstance(found, list) else []:
        number = update.get("update_id")
        if not isinstance(number, int):
            continue
        after = max(after, number + 1)
        message = update.get("message")
        heard = _message(number, cast(dict[str, Any], message)) if isinstance(message, dict) else None
        if heard is not None:
            out.append(heard)
    return out, after


def _message(number: int, message: dict[str, Any]) -> Update | None:
    chat = cast(dict[str, Any], message.get("chat") or {})
    sender = cast(dict[str, Any], message.get("from") or {})
    if not isinstance(chat.get("id"), int):
        return None
    document = message.get("document")
    file = None
    if isinstance(document, dict):
        d = cast(dict[str, Any], document)
        size = d.get("file_size")
        file = FileInfo(str(d.get("file_id", "")), str(d.get("file_name", "")), size if isinstance(size, int) else 0)
    return Update(
        update=number,
        chat=int(chat["id"]),
        private=chat.get("type") == "private",
        sender=int(sender["id"]) if isinstance(sender.get("id"), int) else 0,
        message=int(message["message_id"]) if isinstance(message.get("message_id"), int) else 0,
        text=str(message.get("text", "")),
        document=file if file and file.id else None,
        photo=bool(message.get("photo")),
    )


def download(post: Post, fetch: Fetch, file: str, limit: int = FILE_LIMIT) -> bytes:
    """The bytes of a file a chat sent the bot. getFile names its place on Telegram's file server, valid for an hour;
    fetch brings it from there. SendError when Telegram refuses it, a file larger than limit among others, or cannot
    be reached; its message never holds the file's address, which carries the token."""
    found = call(post, "getFile", {"file_id": file})
    info = cast(dict[str, Any], found) if isinstance(found, dict) else {}
    path, size = str(info.get("file_path", "")), info.get("file_size")
    if not path:
        raise SendError("Telegram dosyanın yerini vermedi")
    if isinstance(size, int) and size > limit:
        raise SendError(f"dosya {limit >> 20} MB sınırından büyük", status=TOO_LARGE)
    try:
        status, body = fetch(urllib.parse.quote(path, safe="/"))
    except (egress.Unreachable, egress.Refused) as exc:  # their messages name the host only, never the path
        raise SendError(f"Telegram'a ulaşılamadı: {exc}") from None
    except Exception as exc:  # noqa: BLE001 - anything else the network raises: its kind only, the path holds the token
        raise SendError(f"Telegram'a ulaşılamadı ({type(exc).__name__})") from None
    if status != 200:
        raise SendError(f"Telegram dosyayı vermedi (HTTP {status})", status=status)
    if len(body) > limit:
        raise SendError(f"dosya {limit >> 20} MB sınırından büyük", status=TOO_LARGE)
    return body


@dataclass(frozen=True)
class Email:
    connect: Connect
    address: str
    password: str

    def send(self, message: Message) -> None:
        mail = EmailMessage()
        mail["From"] = mail["To"] = self.address
        mail["Subject"] = f"{APP}: {message.title}"
        mail.set_content(f"{message.body}\n\n{_FOOTER}\n")
        try:
            with self.connect() as server:
                server.login(self.address, self.password)
                server.send_message(mail)
        except smtplib.SMTPAuthenticationError:
            raise SendError(
                "e-posta sunucusu girişi reddetti; e-posta kanalı durdu (uygulama şifresini yenileyin)", refused=True
            ) from None
        except (smtplib.SMTPException, OSError) as exc:
            raise SendError(f"e-posta gönderilemedi ({type(exc).__name__})") from None
