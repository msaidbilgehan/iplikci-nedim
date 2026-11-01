"""The channels that carry a notification out of the app (ADR-0010). The interface's box needs none: it reads the
notifications kept in the database. Each channel says why it failed in Turkish, never with a secret in it.

- Desktop: macOS's `osascript`, or `notify-send` on Linux; the text goes as arguments, never into a script.
- Telegram: the user's own bot sends to the one chat that paired with it. The bot's token is in the keyring; the
  calls go through egress to the Bot API.
- E-mail: to the user's own address, over the mail server's SMTP with the IMAP connector's app password. A refused
  login stops the channel: trying again from a program may get the account locked.
"""

import json
import shutil
import smtplib
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any, Protocol, cast

from .. import egress
from .content import APP, Message

type Run = Callable[[list[str]], int]  # a program's arguments → its exit status
type Post = Callable[[str, Mapping[str, str]], tuple[int, bytes]]  # a Bot API method and its form → status, body
type Connect = Callable[[], smtplib.SMTP]  # an open, encrypted connection to the mail server that sends

TELEGRAM_LIMIT = 4096  # characters in a Telegram message
_FOOTER = "Ayrıntılar İplikçi Nedim'in Bildirimler ekranında."


class SendError(Exception):
    """A notification that could not be sent: the message says why. refused: the channel must not be tried again
    until the user sets it up anew (a refused login)."""

    def __init__(self, message: str, refused: bool = False) -> None:
        super().__init__(message)
        self.refused = refused


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
        raise SendError(f"Telegram reddetti: {reason}", refused=status in (401, 403, 404))
    return answer.get("result")


@dataclass(frozen=True)
class Telegram:
    post: Post
    chat: int

    def send(self, message: Message) -> None:
        text = f"{message.title}\n{message.body}"[:TELEGRAM_LIMIT]
        call(self.post, "sendMessage", {"chat_id": str(self.chat), "text": text, "disable_web_page_preview": "true"})


def bot_name(post: Post) -> str:
    """The bot's user name: the token works."""
    me = call(post, "getMe", {})
    return str(cast(dict[str, Any], me).get("username", "")) if isinstance(me, dict) else ""


@dataclass(frozen=True, slots=True)
class Start:
    """A "/start <code>" a chat sent the bot."""

    update: int
    chat: int
    code: str


def starts(post: Post, offset: int) -> tuple[list[Start], int]:
    """The "/start <code>" messages the bot received since offset, and the offset that follows them (Telegram then
    forgets them). Nothing waits: the call returns at once."""
    found = call(post, "getUpdates", {"offset": str(offset), "timeout": "0", "allowed_updates": '["message"]'})
    updates = cast(list[dict[str, Any]], found) if isinstance(found, list) else []
    out: list[Start] = []
    after = offset
    for update in updates:
        number = int(update.get("update_id", 0))
        after = max(after, number + 1)
        message = cast(dict[str, Any], update.get("message") or {})
        text, chat = str(message.get("text", "")), cast(dict[str, Any], message.get("chat") or {})
        command, _, code = text.strip().partition(" ")
        if command.split("@")[0] == "/start" and code.strip() and isinstance(chat.get("id"), int):
            out.append(Start(number, int(chat["id"]), code.strip()))
    return out, after


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
