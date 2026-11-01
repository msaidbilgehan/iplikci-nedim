"""Reading documents in a process of their own (ADR-0005): a document that hangs a reader, needs more memory than any
statement could, or crashes the process, is unreadable, and the app goes on.

One reading process reads the documents one after another, so its start (about a quarter of a second) is paid once,
not per document; after a failure, and after every _RECYCLE documents, a fresh one takes over. The app sends a
document's bytes with the company names from its settings; the process answers with one line of JSON: the result
(wire.py) or why there is none. Nothing crosses as pickle.

The time limit holds on every system. The memory limit caps the process's address space, which only Linux enforces:
macOS refuses the limit and Windows has none, so there a document can take as much memory as the system gives.
"""

import atexit
import json
import logging
import os
import queue
import signal
import subprocess
import sys
import threading
from contextlib import suppress
from typing import IO, Any, cast

from .. import parsers
from ..domain.models import ParseResult
from . import wire
from .common import Skipped, Unreadable, business_names, caused_by, set_business_names
from .contract import Document

TIME_LIMIT = 60.0  # seconds a document may take
MEMORY_LIMIT = 1 << 30  # bytes of address space for the reading process
_START_LIMIT = 60.0  # seconds a reading process may take to start
# Documents one process reads before a fresh one takes over, so that its memory never drifts far from a fresh one's.
_RECYCLE = 200
# -I: the reading process never imports from the current folder or the PYTHON* variables, only the installed app.
COMMAND: tuple[str, ...] = (sys.executable, "-I", "-m", "iplikci.parsers.worker")

MEMORY_REASON = f"okuma {MEMORY_LIMIT >> 30} GiB bellek sınırını aştı"
CRASH_REASON = "okuma süreci belgeyi okurken kapandı"
GARBLED_REASON = "okuma sürecinin yanıtı anlaşılamadı"


class WorkerError(RuntimeError):
    """The reading process cannot start: no document can be read, and none must be recorded as unreadable."""


# --- the app's side ---------------------------------------------------------------------------------------------


def parse_document(doc: Document) -> ParseResult:
    """parsers.parse_document in the reading process: the same result and the same exceptions, within the limits.

    A process that had read other documents before dying gets one more try in a fresh one: a document is unreadable
    for its own sake, never for what the documents before it left behind. Raises WorkerError when no reading process
    starts.
    """
    header = {
        "name": doc.name,
        "origin": doc.origin,
        "sha256": doc.sha256,
        "business": list(business_names()),
        "size": len(doc.data),
    }
    job = (json.dumps(header, ensure_ascii=False).encode() + b"\n", doc.data)
    with _lock:
        reply, fresh = _ask(job)
        if reply.get("again") is True and not fresh:
            reply, _ = _ask(job)
        return _answer(reply)


class _Process:
    """A reading process, with a thread that collects its replies: waiting for one with a time limit then works the
    same way on every system."""

    def __init__(self) -> None:
        try:
            self.popen = subprocess.Popen(
                COMMAND,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),  # Windows: no console window flashes up
            )
        except OSError as exc:
            raise WorkerError(f"okuma süreci başlatılamadı: {exc}") from exc
        self.replies: queue.Queue[bytes] = queue.Queue()
        self.served = 0  # documents it has read
        threading.Thread(target=self._collect, daemon=True).start()
        if _decode(self.wait(_START_LIMIT) or b"") != {"ready": True}:
            self.stop()
            raise WorkerError("okuma süreci başlatılamadı: hazır olduğunu bildirmeden kapandı")

    def _collect(self) -> None:
        stdout = self.popen.stdout
        assert stdout is not None
        with stdout:
            for line in stdout:
                self.replies.put(line)
        self.replies.put(b"")  # the process is gone

    def _send(self, job: tuple[bytes, bytes]) -> None:
        stdin = self.popen.stdin
        assert stdin is not None
        with suppress(OSError, ValueError):  # the process is gone (or was stopped): _collect says so
            stdin.write(job[0])
            stdin.write(job[1])
            stdin.flush()

    def wait(self, limit: float) -> bytes | None:
        """The next line the process writes; b"" once it is gone, None when limit seconds pass first."""
        try:
            return self.replies.get(timeout=limit)
        except queue.Empty:
            return None

    def ask(self, job: tuple[bytes, bytes]) -> bytes | None:
        # Sent from a thread of its own: a process that stops reading must not hold the app beyond the time limit.
        threading.Thread(target=self._send, args=(job,), daemon=True).start()
        return self.wait(TIME_LIMIT)

    def stop(self) -> None:
        self.popen.kill()
        self.popen.wait()
        if self.popen.stdin is not None:
            with suppress(OSError, ValueError):
                self.popen.stdin.close()


_lock = threading.Lock()
_current: _Process | None = None


def stop() -> None:
    """Stop the reading process; the next document starts a fresh one."""
    global _current
    if _current is not None:
        _current.stop()
        _current = None


atexit.register(stop)


def _ask(job: tuple[bytes, bytes]) -> tuple[dict[str, Any], bool]:
    """The reading process's reply to job, and whether that process was fresh. A process that failed is stopped; the
    next document gets a fresh one."""
    global _current
    if _current is None:
        _current = _Process()
    process = _current
    fresh = process.served == 0
    answered = False
    try:
        line = process.ask(job)
        answered = True
    finally:
        if not answered:  # interrupted (Ctrl+C): a late reply must never answer the next document
            stop()
    if line is None:
        stop()
        return {"unreadable": f"okuma {TIME_LIMIT:.0f} saniyede bitmedi", "parser": ""}, fresh
    if not line:
        stop()
        return {"unreadable": CRASH_REASON, "parser": "", "again": True}, fresh
    process.served += 1
    reply = _decode(line) or {}
    if reply.get("again") is True or process.served >= _RECYCLE:  # after a memory error the process quits anyway
        stop()
    return reply, fresh


def _decode(line: bytes) -> dict[str, Any] | None:
    try:
        reply = json.loads(line)
    except ValueError:  # JSONDecodeError and UnicodeDecodeError
        return None
    if not isinstance(reply, dict):
        return None
    return cast(dict[str, Any], reply)  # a JSON object's keys are strings


def _answer(reply: dict[str, Any]) -> ParseResult:
    """The result a reply carries, or the exception it names; a reply that is neither leaves the document
    unreadable."""
    parser = reply.get("parser")
    parser = parser if isinstance(parser, str) else ""
    if "result" in reply:
        try:
            return wire.load(reply["result"])
        except ValueError as exc:
            raise Unreadable(GARBLED_REASON) from exc
    if isinstance(skipped := reply.get("skipped"), str):
        raise Skipped(skipped, business=reply.get("business") is True, parser=parser)
    if isinstance(unreadable := reply.get("unreadable"), str):
        raise Unreadable(unreadable, parser=parser)
    raise Unreadable(GARBLED_REASON)


# --- the reading process's side ---------------------------------------------------------------------------------


def limit_memory(limit: int) -> bool:
    """Cap this process's address space at limit bytes; whether the system enforces such a cap."""
    try:
        import resource
    except ImportError:  # Windows has no resource limits
        return False
    _, hard = resource.getrlimit(resource.RLIMIT_AS)
    if hard != resource.RLIM_INFINITY and hard <= limit:
        return True  # capped tighter already
    try:
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    except (ValueError, OSError):  # macOS refuses an address-space limit
        return False
    return True


def _read(job: dict[str, Any], data: bytes) -> dict[str, Any]:
    set_business_names(job["business"])
    doc = Document(name=job["name"], origin=job["origin"], data=data, sha256=job["sha256"])
    try:
        return {"result": wire.dump(parsers.parse_document(doc))}
    except Exception as exc:  # whatever a document provokes leaves it unreadable  # noqa: BLE001
        return _failure(exc)


def _failure(exc: Exception) -> dict[str, Any]:
    parser = exc.parser if isinstance(exc, Skipped | Unreadable) else ""
    if caused_by(exc, MemoryError):  # also when a reader or pdfplumber hands it on inside an exception of its own
        return {"unreadable": MEMORY_REASON, "parser": parser, "again": True}
    if isinstance(exc, Skipped):
        return {"skipped": str(exc), "business": exc.business, "parser": parser}
    if isinstance(exc, Unreadable):
        return {"unreadable": str(exc), "parser": parser}
    return {"unreadable": f"{type(exc).__name__}: {exc}", "parser": ""}


def _write(out: IO[bytes], reply: dict[str, Any]) -> None:
    out.write(json.dumps(reply, ensure_ascii=False).encode() + b"\n")
    out.flush()


def _serve() -> None:
    """The reading process: documents in on stdin, one line of JSON per document out."""
    limit_memory(MEMORY_LIMIT)
    logging.getLogger("pdfminer").setLevel(logging.ERROR)  # as in the CLI: harmless font warnings
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # Ctrl+C is the app's to handle, and the app stops this process
    replies = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)  # whatever a library prints goes to stderr, never among the replies
    sys.stdout = sys.stderr
    requests = sys.stdin.buffer
    _write(replies, {"ready": True})
    while header := requests.readline():
        job = json.loads(header)
        data = requests.read(job["size"])
        if len(data) != job["size"]:
            return  # the app is gone
        # Should the app be gone while a document hangs, the process still ends: SIGALRM's default action stops it.
        if hasattr(signal, "alarm"):
            signal.alarm(int(TIME_LIMIT) + 10)
        reply = _read(job, data)
        if hasattr(signal, "alarm"):
            signal.alarm(0)
        _write(replies, reply)
        if reply.get("again") is True:
            return  # what a failed allocation leaves behind is no state to read on in


if __name__ == "__main__":
    _serve()
