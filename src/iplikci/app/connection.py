"""Connecting Claude (K23, ADR-0011): what the interface shows and copies so that anyone can add İplikçi Nedim to their
Claude, with claude-SAK or without it.

- Claude Code reaches the service's /mcp. Its configuration names a headers helper, `iplikci mcp baslik`, which reads
  the API token from the keyring at each connection: the token never goes into Claude's settings file. The same JSON
  is what claude-SAK's "MCP JSON" import takes.
- Claude Desktop starts `iplikci mcp` itself (the stdio bridge): through the service while it runs, from the database
  alone while it is down.
- The commands are written for the copy that runs: the service's own Python, so the keyring's entry is read by the
  program that wrote it (macOS asks for a password when another one reads it).

The API token itself is shown only when the user asks (the "Göster" button); the user allowed it to be shown (K23).
It is never written into a file or a log.
"""

import json
import shlex
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..domain.codes import Actor
from ..service import manager
from ..settings import config
from ..settings.config import SettingsError
from ..storage import audit
from .workspace import Workspace

__all__ = ["Actor", "Connection", "SettingsError", "connection", "set_masking"]

NAME = "iplikci"  # the server's name in Claude's settings
MASKING_CHANGED = "settings.privacy_changed"
LEVELS = ("off", "accounts", "accounts_and_names")


@dataclass(frozen=True, slots=True)
class Connection:
    address: str  # MCP's address: the service's /mcp
    name: str  # the server's name in Claude
    helper: str  # the headers helper's command line, as Claude Code runs it in a shell
    command: str  # the stdio bridge's program (Claude Desktop starts it)
    arguments: tuple[str, ...]  # and its arguments
    claude_code: dict[str, Any]  # Claude Code's and claude-SAK's MCP JSON: HTTP with the headers helper
    claude_desktop: dict[str, Any]  # Claude Desktop's: the stdio bridge
    sak_add: str  # claude-SAK's command line, for those who use it
    sak_remove: str
    claude_add: str  # Claude Code's own command line, without claude-SAK
    masking: str  # the masking level the MCP answers have (settings [privacy] mcp_masking)
    development: bool  # this copy runs from a source folder: the commands point at its Python


def _program() -> list[str]:
    """How this copy runs: its Python, isolated (the service's own arguments, architecture §19)."""
    return [str(Path(sys.executable).absolute()), "-I", "-X", "utf8", "-m", "iplikci"]


def _shell(words: Sequence[str]) -> str:
    """A command line a shell takes as these words: Claude Code runs the headers helper in one."""
    return subprocess.list2cmdline(list(words)) if sys.platform == "win32" else shlex.join(words)


def connection(ws: Workspace) -> Connection:
    """What connects Claude to this data folder's service."""
    settings = ws.fresh_settings()
    address = f"http://127.0.0.1:{settings.server.port}/mcp"
    program = _program()
    helper = _shell([*program, "mcp", "baslik"])
    command, arguments = program[0], (*program[1:], "mcp", "--klasor", str(ws.home))
    http = {"type": "http", "url": address, "headersHelper": helper}
    stdio = {"command": command, "args": list(arguments)}
    return Connection(
        address=address,
        name=NAME,
        helper=helper,
        command=command,
        arguments=arguments,
        claude_code={"mcpServers": {NAME: http}},
        claude_desktop={"mcpServers": {NAME: stdio}},
        sak_add=_shell(
            ["sak", "store", "mcp", "add", NAME, "--url", address, "--headers-helper", helper, "--scope", "user"]
        ),
        sak_remove=_shell(["sak", "store", "mcp", "remove", NAME, "--scope", "user"]),
        claude_add=_shell(["claude", "mcp", "add-json", "--scope", "user", NAME, json.dumps(http, ensure_ascii=False)]),
        masking=settings.privacy.mcp_masking,
        development=manager.development_folder() is not None,
    )


def set_masking(ws: Workspace, level: str, actor: Actor) -> Connection:
    """What the MCP answers hide from now on; the next call reads it (mcp.tools.Session.mask)."""
    if level not in LEVELS:
        raise SettingsError(f"bilinmeyen maskeleme düzeyi: {level}")
    config.update(ws.layout.settings, "privacy", {"mcp_masking": level})
    with ws.db() as db:
        audit.record(db, actor, MASKING_CHANGED, "privacy", mcp_masking=level)
    return connection(ws)
