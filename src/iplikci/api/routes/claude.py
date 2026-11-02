"""Claude's connection (K23, ADR-0011): what the interface shows and copies so that Claude can be added without a
terminal, the API token behind its "Göster" button and the masking of MCP's answers. Only the interface changes the
masking; the token is given to a browser session's own pages alone (a write: Origin and X-Iplikci, ADR-0007)."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ...app import connection
from ...app.connection import Actor, SettingsError
from ..context import context_of
from ..guard import Principal
from ..problems import Problem
from .deps import only

router = APIRouter()

Masking = Literal["off", "accounts", "accounts_and_names"]


class ConnectionOut(BaseModel):
    address: str  # MCP's address: the service's /mcp
    name: str  # the server's name in Claude
    helper: str  # the headers helper's command line (Claude Code runs it in a shell)
    command: str  # the stdio bridge's program, for Claude Desktop
    arguments: list[str]
    claude_code: dict[str, Any]  # Claude Code's and claude-SAK's MCP JSON: HTTP with the headers helper
    claude_desktop: dict[str, Any]  # Claude Desktop's: the stdio bridge
    sak_add: str  # claude-SAK's command line, for those who use one
    sak_remove: str
    masking: Masking
    development: bool  # a development copy: the commands point at its Python


class TokenOut(BaseModel):
    token: str


class MaskingIn(BaseModel):
    masking: Masking


def _out(found: connection.Connection) -> ConnectionOut:
    level: Masking = (
        "accounts"
        if found.masking == "accounts"
        else "accounts_and_names"
        if found.masking == "accounts_and_names"
        else "off"
    )
    return ConnectionOut(
        address=found.address,
        name=found.name,
        helper=found.helper,
        command=found.command,
        arguments=list(found.arguments),
        claude_code=found.claude_code,
        claude_desktop=found.claude_desktop,
        sak_add=found.sak_add,
        sak_remove=found.sak_remove,
        masking=level,
        development=found.development,
    )


@router.get("/api/mcp/connection", dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])
def connection_view(request: Request) -> ConnectionOut:
    """The address, the commands and the ready configurations; never the token."""
    return _out(connection.connection(context_of(request).ws))


@router.post("/api/mcp/token", dependencies=[Depends(only(Principal.BROWSER))])
def token_view(request: Request) -> TokenOut:
    """The API token, for the user to copy into a client that takes a header (K23: it may be shown)."""
    return TokenOut(token=context_of(request).token)


@router.put("/api/mcp/masking", dependencies=[Depends(only(Principal.BROWSER))])
def masking_change(request: Request, body: MaskingIn) -> ConnectionOut:
    """What MCP's answers hide from now on: account numbers and IBANs, and people's names too."""
    try:
        return _out(connection.set_masking(context_of(request).ws, body.masking, Actor.USER))
    except SettingsError as exc:
        raise Problem(400, "settings_refused", str(exc)) from exc
