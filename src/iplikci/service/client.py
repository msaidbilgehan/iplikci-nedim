"""The command line's way to the running service: JSON over HTTP to 127.0.0.1 with the API token (ADR-0007). Never
through a proxy: the request stays on this computer."""

import json
import urllib.error
import urllib.request
from typing import Any, cast

from ..app import access
from ..app.workspace import Workspace

_TIMEOUT = 10.0
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class ServiceError(Exception):
    """The service could not be reached or refused the request; the message says why (Turkish)."""


class ServiceDown(ServiceError):
    pass


def call(ws: Workspace, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    token = access.api_token()
    if not token:
        raise ServiceError("API belirteci yok: servis bu bilgisayarda hiç çalıştırılmamış")
    request = urllib.request.Request(
        f"http://127.0.0.1:{ws.port}{path}",
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with _OPENER.open(request, timeout=_TIMEOUT) as response:
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise ServiceError(_problem_title(exc) or f"servis {exc.code} yanıtı verdi") from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise ServiceDown(f"servis 127.0.0.1:{ws.port} adresinde yanıt vermiyor") from exc
    return cast(dict[str, Any], json.loads(text)) if text else {}


# A tool may make the analysis again or read a document anew; the bridge waits as long as the client would.
_MCP_TIMEOUT = 300.0
_MCP_ACCEPT = "application/json, text/event-stream"


def mcp_message(ws: Workspace, body: bytes, protocol: str | None) -> tuple[int, bytes]:
    """One MCP message for the service's /mcp with the API token (the stdio bridge, ADR-0011): the answer's status
    and body, empty for a notification. protocol: the version the client agreed on, which HTTP carries in a header."""
    token = access.api_token()
    if not token:
        raise ServiceError("API belirteci okunamadı")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": _MCP_ACCEPT}
    if protocol:
        headers["MCP-Protocol-Version"] = protocol
    request = urllib.request.Request(f"http://127.0.0.1:{ws.port}/mcp", data=body, method="POST", headers=headers)
    try:
        with _OPENER.open(request, timeout=_MCP_TIMEOUT) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:  # a JSON-RPC error, or the gate's refusal: the bridge tells them apart
        return exc.code, exc.read()
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise ServiceDown(f"servis 127.0.0.1:{ws.port} adresinde yanıt vermiyor") from exc


def healthy(port: int) -> bool:
    """The service on this port answers its health check, which needs no token."""
    try:
        with _OPENER.open(f"http://127.0.0.1:{port}/healthz", timeout=2.0) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return False


def _problem_title(exc: urllib.error.HTTPError) -> str:
    try:
        found = json.loads(exc.read().decode("utf-8"))
    except (ValueError, UnicodeDecodeError, OSError):
        return ""
    return str(found.get("title", "")) if isinstance(found, dict) else ""  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType] - a parsed JSON object
