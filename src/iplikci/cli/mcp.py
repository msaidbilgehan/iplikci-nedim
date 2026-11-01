"""`iplikci mcp`: the MCP server for Claude, over stdio; the MCP client starts it."""

import argparse
from pathlib import Path

from ..settings.paths import HOME_ENV
from .common import open_workspace


def mcp_command(argv: list[str]) -> int:
    from .. import mcp_server

    parser = argparse.ArgumentParser(
        prog="iplikci mcp",
        description="Claude için MCP sunucusu (stdio). MCP istemcisi (Claude Code, Claude Desktop) kendisi başlatır.",
    )
    parser.add_argument("--klasor", help=f"veri klasörü (varsayılan: {HOME_ENV}, yoksa platformun veri klasörü)")
    args = parser.parse_args(argv)
    return mcp_server.serve(open_workspace(parser, Path(args.klasor) if args.klasor else None))
