"""`iplikci mcp`: the MCP server for Claude over stdio, which the MCP client starts (ADR-0011); `iplikci mcp baslik`:
the headers helper Claude Code runs to connect to the service's /mcp (K23)."""

import argparse
import json
import sys
from pathlib import Path

from ..settings.paths import HOME_ENV
from .common import open_workspace


def mcp_command(argv: list[str]) -> int:
    if argv[:1] == ["baslik"]:
        return headers_command(argv[1:])
    from ..mcp import stdio

    parser = argparse.ArgumentParser(
        prog="iplikci mcp",
        description="Claude için MCP sunucusu (stdio). MCP istemcisi (Claude Code, Claude Desktop) kendisi başlatır: "
        "servis çalışıyorsa istekleri ona iletir, çalışmıyorsa veritabanını yalnızca okur. "
        "Claude Code'un başlık yardımcısı için: iplikci mcp baslik",
    )
    parser.add_argument("--klasor", help=f"veri klasörü (varsayılan: {HOME_ENV}, yoksa platformun veri klasörü)")
    args = parser.parse_args(argv)
    return stdio.serve(open_workspace(parser, Path(args.klasor) if args.klasor else None))


def headers_command(argv: list[str]) -> int:
    """Print the Authorization header for the service's /mcp as a JSON object: the API token from the keyring, so it
    never stands in Claude's settings file or on a command line."""
    from ..app import access

    parser = argparse.ArgumentParser(
        prog="iplikci mcp baslik",
        description="Claude Code'un başlık yardımcısı (headersHelper): API belirtecini anahtar zincirinden okur ve "
        "İplikçi Nedim'in MCP adresi için Authorization başlığını JSON olarak yazar.",
    )
    parser.parse_args(argv)
    token = access.api_token()
    if not token:
        print("API belirteci yok: İplikçi Nedim'in servisi bu bilgisayarda hiç çalışmadı.", file=sys.stderr)
        return 1
    print(json.dumps({"Authorization": f"Bearer {token}"}))
    return 0
