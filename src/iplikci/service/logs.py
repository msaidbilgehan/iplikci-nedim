"""The service's log (architecture §22): JSON lines in logs/servis.log, rotated at 10 MB with four older files kept.
The log calls write ids and numbers only, never an amount, a name, an address or a description. What the process
itself prints (its start line, or a crash before its log opened) goes to logs/servis-cikti.log, where the service
manager sends it."""

import json
import logging
import logging.handlers
import sys
import threading
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

LOG_NAME = "servis.log"
OUTPUT_NAME = "servis-cikti.log"
MAX_BYTES = 10 * 1024 * 1024
BACKUPS = 4  # five files in all

log = logging.getLogger("iplikci.service")


class JsonLines(logging.Formatter):
    """One JSON object per record: its time in UTC, level, logger and message, and the traceback of an error."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["traceback"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


@contextmanager
def kept(folder: Path) -> Generator[None]:
    """Send the log records to the service's log file while the block runs, and to the terminal when the service
    runs in one. A thread that dies of an error leaves its traceback in the log too."""
    folder.mkdir(parents=True, exist_ok=True)
    trim(folder / OUTPUT_NAME)
    handlers: list[logging.Handler] = [
        logging.handlers.RotatingFileHandler(
            folder / LOG_NAME, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8"
        )
    ]
    handlers[0].setFormatter(JsonLines())
    if sys.stderr is not None and sys.stderr.isatty():
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        handlers.append(console)
    root, own = logging.getLogger(), logging.getLogger("iplikci")
    levels, hook = (root.level, own.level), threading.excepthook
    for handler in handlers:
        root.addHandler(handler)
    root.setLevel(logging.WARNING)  # the libraries: their warnings and errors
    own.setLevel(logging.INFO)
    threading.excepthook = _thread_died
    try:
        yield
    finally:
        threading.excepthook = hook
        root.setLevel(levels[0])
        own.setLevel(levels[1])
        for handler in handlers:
            root.removeHandler(handler)
            handler.close()


def trim(output: Path) -> None:
    """Keep what the process printed to one older file when it grew past the limit (a service that crashes at start
    again and again prints a traceback each time)."""
    if output.exists() and output.stat().st_size > MAX_BYTES:
        output.replace(output.with_name(output.name + ".1"))


def _thread_died(args: threading.ExceptHookArgs) -> None:
    if args.exc_type is SystemExit:  # a thread may end itself so, as Python's own hook knows
        return
    name = args.thread.name if args.thread is not None else "?"
    log.error("thread %s stopped on an error", name, exc_info=args.exc_value)
