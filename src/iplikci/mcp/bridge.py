"""The stdio bridge (ADR-0011): a client that starts the server itself (Claude Desktop) talks to `iplikci mcp` on stdin
and stdout, and each of its messages is answered by the service while it runs, or here from the database opened only
to read while it is down.

The choice is made for every message, not once: a client keeps the bridge for as long as it runs, and the service may
start after it (at login) or stop for a while (an update). While the service answers, every message goes to its /mcp
with the API token from the keyring: one analysis, one set of plans, the same answers as the screens. When it cannot
be reached, the local server answers. It is started the first time it is needed and greeted with the client's own
`initialize`, so it knows the client as the service did; its tools that only read work, and those that would change
something say why they cannot (tools.OFFLINE).

HTTP carries the protocol version the client agreed on in a header: the bridge reads it from the answer to
`initialize`, whichever server gave it, and sends it with every message after. A message neither can take is answered
with a JSON-RPC error, so the client knows; a notification is never answered.

The SDK's stdio transport owns the process's standard streams while the bridge serves: anything else printed (by a
library or a child process) goes to stderr, never into the messages, and no child process reads the client's stdin.
"""

import json
import logging
from contextlib import AsyncExitStack
from dataclasses import replace
from typing import Any, TypeGuard, cast

import anyio
import anyio.to_thread
import mcp_types as types
from mcp.server.stdio import stdio_server
from mcp.shared.memory import MessageStream, create_client_server_memory_streams
from mcp.shared.message import SessionMessage
from mcp_types.jsonrpc import INTERNAL_ERROR, PARSE_ERROR
from pydantic import ValidationError

from ..app.workspace import Workspace
from ..service.client import ServiceDown, ServiceError, healthy, mcp_message
from .server import build
from .tools import Session

_log = logging.getLogger(__name__)

UNREACHABLE = "İplikçi Nedim'in servisine ulaşılamadı"
UNREADABLE = "JSON-RPC iletisi okunamadı"
INITIALIZE = "initialize"
_GREETING_ID = "iplikci-kopru-selam"  # the local server's own initialize: its answer is the bridge's alone


async def relay(
    ws: Workspace, stdin: anyio.AsyncFile[str] | None = None, stdout: anyio.AsyncFile[str] | None = None
) -> None:
    """Answer the client's messages until it closes stdin: on the process's own streams, or on those given (tests)."""
    async with AsyncExitStack() as stack:
        incoming, outgoing = await stack.enter_async_context(stdio_server(stdin, stdout))
        bridge = _Bridge(ws, _Local(ws, stack))
        async with outgoing:
            async for item in incoming:
                for reply in await bridge.answer(item):
                    await outgoing.send(reply)


class _Bridge:
    """Where each message goes, and what the client agreed on."""

    def __init__(self, ws: Workspace, local: "_Local") -> None:
        self._ws = ws
        self._local = local
        self._protocol: str | None = None  # the version the client and the first server agreed on
        self._tokenless = False  # the token could not be read: said once, then the database alone

    async def answer(self, item: SessionMessage | Exception) -> list[SessionMessage]:
        if isinstance(item, Exception):  # a line that is no JSON-RPC message: its id cannot be known
            return [_error(None, PARSE_ERROR, UNREADABLE)]
        message = item.message
        if _is_initialize(message):
            self._local.greeting = message
        replies = await self._service(message)
        if replies is None:
            replies = await self._local.answer(message)
        if _is_initialize(message):
            self._protocol = _agreed(replies) or self._protocol
        return replies

    async def _service(self, message: types.JSONRPCMessage) -> list[SessionMessage] | None:
        """The service's answer, none to a notification; None while it cannot be reached and the database answers."""
        if self._tokenless:
            return None
        body = message.model_dump_json(by_alias=True, exclude_unset=True).encode("utf-8")
        try:
            status, answer = await anyio.to_thread.run_sync(mcp_message, self._ws, body, self._protocol)
        except ServiceDown as exc:
            if not await anyio.to_thread.run_sync(healthy, self._ws.port):
                return None
            return _failed(message, f"{UNREACHABLE}: {exc}")  # it runs, but did not answer this one in time
        except ServiceError as exc:  # the API token could not be read
            _log.warning("%s: answering from the database alone", exc)
            self._tokenless = True
            return None
        reply = _message(answer)
        if reply is None:  # the gate's refusal, or an empty answer: a notification's is
            return _failed(message, f"{UNREACHABLE}: {_refusal(status, answer)}")
        return [SessionMessage(reply)]


class _Local:
    """The server on the database alone, opened only to read: started the first time the service cannot answer."""

    def __init__(self, ws: Workspace, stack: AsyncExitStack) -> None:
        self._ws = ws
        self._stack = stack
        self._streams: MessageStream | None = None
        self.greeting: types.JSONRPCRequest | None = None  # the client's initialize, which the service may have taken

    async def answer(self, message: types.JSONRPCMessage) -> list[SessionMessage]:
        """What the local server says to the message: its answer to a request and anything it sends before."""
        streams = await self._open(message)
        await streams[1].send(SessionMessage(message))
        if not isinstance(message, types.JSONRPCRequest):
            return []
        return await _until_answered(streams, message.id)

    async def _open(self, first: types.JSONRPCMessage) -> MessageStream:
        if self._streams is not None:
            return self._streams
        group = await self._stack.enter_async_context(anyio.create_task_group())
        client, (server_receive, server_send) = await self._stack.enter_async_context(
            create_client_server_memory_streams()
        )
        server = build(Session(replace(self._ws, offline=True), offline=True))
        group.start_soon(server.run, server_receive, server_send, server.create_initialization_options())
        self._streams = client
        if self.greeting is not None and not _is_initialize(first):  # the client greeted the service, not this one
            await client[1].send(SessionMessage(self.greeting.model_copy(update={"id": _GREETING_ID})))
            await _until_answered(client, _GREETING_ID)
            initialized = types.JSONRPCNotification(jsonrpc="2.0", method="notifications/initialized")
            await client[1].send(SessionMessage(initialized))
        return client


async def _until_answered(streams: MessageStream, wanted: types.RequestId) -> list[SessionMessage]:
    """The server's messages up to and with its answer to the request with this id."""
    said: list[SessionMessage] = []
    while True:
        item = await streams[0].receive()
        if isinstance(item, Exception):  # pragma: no cover - a server sends messages only
            continue
        said.append(item)
        found = item.message
        if isinstance(found, types.JSONRPCResponse | types.JSONRPCError) and found.id == wanted:
            return said


def _is_initialize(message: types.JSONRPCMessage) -> TypeGuard[types.JSONRPCRequest]:
    return isinstance(message, types.JSONRPCRequest) and message.method == INITIALIZE


def _agreed(replies: list[SessionMessage]) -> str | None:
    """The protocol version an answer to initialize names."""
    for reply in replies:
        found = reply.message
        if isinstance(found, types.JSONRPCResponse):
            version = found.result.get("protocolVersion")
            return str(version) if version else None
    return None


def _message(body: bytes) -> types.JSONRPCMessage | None:
    if not body.strip():
        return None
    try:
        return types.jsonrpc_message_adapter.validate_json(body, by_name=False)
    except ValidationError:
        return None


def _failed(message: types.JSONRPCMessage, text: str) -> list[SessionMessage]:
    """An error for a request; a notification gets no answer, not even this."""
    if not isinstance(message, types.JSONRPCRequest):
        return []
    return [_error(message.id, INTERNAL_ERROR, text)]


def _refusal(status: int, body: bytes) -> str:
    try:
        found: Any = json.loads(body)
    except ValueError:
        found = None
    title = cast(dict[str, Any], found).get("title") if isinstance(found, dict) else None
    return str(title) if title else f"yanıt {status}"


def _error(mid: types.RequestId | None, code: int, text: str) -> SessionMessage:
    return SessionMessage(types.JSONRPCError(jsonrpc="2.0", id=mid, error=types.ErrorData(code=code, message=text)))
