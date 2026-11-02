"""The record of what Claude asked (ADR-0011): every MCP tool call goes into the audit log, with the names of its
arguments and whether it worked, never their values (architecture §21: identifiers and counts only).

A call answered while the service is down reads the database alone and writes nothing into it (Workspace.offline):
its entry waits in a file in the run folder, and the service takes it into the log, with its own time, when it starts.
"""

import json
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ..domain.codes import Actor
from ..storage import audit
from ..storage.db import now
from .workspace import Workspace

ACTION = "mcp.tool"
WAITING = "mcp-cagrilari.jsonl"  # the calls answered while the service was down
_log = logging.getLogger(__name__)


def record(ws: Workspace, tool: str, arguments: Iterable[str], ok: bool) -> None:
    """One tool call: its tool, the names of the arguments given and whether it worked."""
    detail: dict[str, Any] = {"arguments": sorted(arguments), "ok": ok}
    try:
        if ws.offline:
            with _waiting(ws).open("a", encoding="utf-8") as f:
                f.write(json.dumps({"at": now(), "tool": tool, **detail}, ensure_ascii=False) + "\n")
            return
        with ws.db() as db:
            audit.record(db, Actor.MCP, ACTION, tool, **detail)
    except OSError:  # the answer still goes out; what failed to be kept is said in the log
        _log.warning("an MCP call to %s could not be recorded", tool, exc_info=True)


def take_waiting(ws: Workspace) -> int:
    """The calls answered while the service was down, into the audit log with their own times; how many."""
    path = _waiting(ws)
    if not path.is_file():
        return 0
    entries: list[audit.Entry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            found: dict[str, Any] = json.loads(line)
            at, tool = str(found.pop("at")), str(found.pop("tool"))
        except (ValueError, KeyError, AttributeError):
            continue  # a line cut short when the bridge stopped
        entries.append(audit.Entry(at, Actor.MCP, ACTION, tool, found))
    with ws.db() as db:
        for entry in entries:
            audit.restore(db, entry)
    path.unlink()
    return len(entries)


def _waiting(ws: Workspace) -> Path:
    ws.run.mkdir(parents=True, exist_ok=True)
    return ws.run / WAITING
