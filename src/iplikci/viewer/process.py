"""The app's side of the viewing process: each request starts a process of its own (about a quarter of a second,
paid only when something is first shown: what it makes is kept with the document, see app/documents.py), sends the
document's bytes and reads one line of JSON back."""

import base64
import binascii
import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, cast

# -I: the viewing process never imports from the current folder or the PYTHON* variables, only the installed app.
COMMAND: tuple[str, ...] = (sys.executable, "-I", "-m", "iplikci.viewer.worker")
WAIT = 45  # seconds; the viewing process stops itself after its own limit (worker.TIME_LIMIT) and a margin


class ViewError(Exception):
    """The document cannot be shown this way; the message says why, in Turkish."""


def _ask(op: str, data: bytes, **args: object) -> dict[str, Any]:
    header = json.dumps({"op": op, "size": len(data), **args}).encode() + b"\n"
    try:
        done = subprocess.run(COMMAND, input=header + data, capture_output=True, timeout=WAIT, check=False)
    except subprocess.TimeoutExpired:
        raise ViewError("belge zamanında gösterilemedi") from None
    except OSError as exc:
        raise ViewError(f"gösterme süreci başlatılamadı ({type(exc).__name__})") from None
    try:
        reply = json.loads(done.stdout.decode("utf-8").strip().splitlines()[-1])
    except (UnicodeDecodeError, IndexError, ValueError):
        raise ViewError("gösterme süreci belgeyi gösterirken kapandı") from None
    if not isinstance(reply, dict):
        raise ViewError("gösterme sürecinin yanıtı anlaşılamadı")
    found = cast(dict[str, Any], reply)
    if "refused" in found:
        raise ViewError(str(found["refused"]))
    return found


def page_sizes(data: bytes) -> list[tuple[float, float]]:
    """A PDF's pages, each as (width, height) in points."""
    return [(float(w), float(h)) for w, h in _ask("pages", data)["pages"]]


@dataclass(frozen=True)
class Picture:
    png: bytes
    width: int
    height: int


def render_page(data: bytes, page: int, width: int) -> Picture:
    """A PDF's page (1-based) drawn about width pixels wide."""
    reply = _ask("render", data, page=page, width=width)
    try:
        return Picture(base64.b64decode(reply["png"], validate=True), int(reply["width"]), int(reply["height"]))
    except (KeyError, binascii.Error, ValueError, TypeError):
        raise ViewError("gösterme sürecinin yanıtı anlaşılamadı") from None


def page_lines(data: bytes, page: int) -> list[str]:
    """A PDF's page's text, line by line as the readers count its lines."""
    return [str(line) for line in _ask("lines", data, page=page)["lines"]]


@dataclass(frozen=True)
class Table:
    name: str  # the sheet's name; "" for an HTML export's table
    rows: list[list[str]]
    more: bool  # rows beyond those shown


def table(data: bytes) -> Table:
    reply = _ask("table", data)
    return Table(str(reply["name"]), [[str(c) for c in row] for row in reply["rows"]], bool(reply["more"]))


@dataclass(frozen=True)
class MailView:
    subject: str
    sender: str  # the domain of the From address
    sent: str  # ISO time in the sender's zone; "" when the message has no date
    lines: list[str]  # the body's text as a browser breaks it
    text: str  # the same text collapsed: a notice row's span counts in it
    html: str  # the body's HTML part, to show in a sandbox; "" without one


def message(data: bytes) -> MailView:
    r = _ask("message", data)
    return MailView(
        str(r["subject"]),
        str(r["sender"]),
        str(r["sent"]),
        [str(x) for x in r["lines"]],
        str(r["text"]),
        str(r["html"]),
    )


def text(data: bytes) -> str:
    return str(_ask("text", data)["text"])


def html_text(data: bytes) -> str:
    return str(_ask("html_text", data)["text"])
