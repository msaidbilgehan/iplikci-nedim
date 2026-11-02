"""The stdio bridge's first way (ADR-0011): while the service runs, each message a client writes on stdin goes to the
service's /mcp with the API token from the keyring, and its answer comes back on stdout, one line each.

HTTP carries the protocol version the client agreed on in a header: the bridge reads it from the answer to
`initialize` and sends it with every message after. A message the service cannot take back is answered with a
JSON-RPC error, so the client knows; a notification is never answered.
"""

import json
import os
import sys
from collections.abc import Iterable
from typing import IO, Any, cast

from ..app.workspace import Workspace
from ..service.client import ServiceError, mcp_message

PARSE_ERROR = -32700
INTERNAL_ERROR = -32603
UNREACHABLE = "İplikçi Nedim'in servisine ulaşılamadı"


def claim_stdout() -> IO[str]:
    """The stream the answers go to: the process's stdout, kept for them alone. From here on anything else printed (by
    a library or a child process) goes to stderr."""
    out = os.fdopen(os.dup(1), "w", encoding="utf-8", newline="\n")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    return out


def forward(ws: Workspace, stdin: Iterable[str], stdout: IO[str]) -> int:
    """Pass the client's messages to the service until the client closes stdin."""
    protocol: str | None = None
    for line in stdin:
        text = line.strip()
        if not text:
            continue
        try:
            message: Any = json.loads(text)
        except ValueError:
            _write(stdout, _error(None, PARSE_ERROR, "JSON okunamadı"))
            continue
        asked = _object(message)
        mid, method = asked.get("id"), asked.get("method")
        try:
            status, body = mcp_message(ws, text.encode("utf-8"), protocol)
        except ServiceError as exc:
            if mid is not None:
                _write(stdout, _error(mid, INTERNAL_ERROR, f"{UNREACHABLE}: {exc}"))
            continue
        reply = _object(_json(body))
        if "jsonrpc" not in reply:
            if mid is not None:  # the gate's refusal, or an empty answer to a request
                _write(stdout, _error(mid, INTERNAL_ERROR, f"{UNREACHABLE}: {_refusal(status, reply)}"))
            continue
        if method == "initialize":
            protocol = str(_object(reply.get("result")).get("protocolVersion") or "") or None
        _write(stdout, reply)
    return 0


def _json(body: bytes) -> Any:
    try:
        return json.loads(body) if body.strip() else None
    except ValueError:
        return None


def _object(value: Any) -> dict[str, Any]:
    """A parsed JSON object; an empty one for anything else."""
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _refusal(status: int, found: dict[str, Any]) -> str:
    title = found.get("title")
    return str(title) if title else f"yanıt {status}"


def _error(mid: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def _write(stdout: IO[str], message: dict[str, Any]) -> None:
    stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    stdout.flush()
