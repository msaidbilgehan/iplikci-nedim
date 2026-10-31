"""Collect, parse (with an on-disk cache) and categorize."""

import json
import os
from pathlib import Path

from .analysis import Dataset, build
from .categorize import Categorizer
from .models import ParseResult
from .parsers import PARSER_VERSION, Skipped, Unreadable, parse_document
from .parsers.common import business_names_signature
from .sources import Document, collect

CACHE_NAME = ".onbellek.json"


def _load_cache(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    # Other company names in the settings make other documents company documents: read them all again.
    fresh = data.get("version") == PARSER_VERSION and data.get("business", "") == business_names_signature()
    return data.get("entries", {}) if fresh else {}


def _save_cache(path: Path, entries: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # The panel, the MCP server and the automatic run may save at the same time: one temp file each.
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    data = {"version": PARSER_VERSION, "business": business_names_signature(), "entries": entries}
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def parse_all(docs: list[Document], cache_dir: Path | None, progress=None, keep_old: bool = False) -> list[tuple]:
    """Parse documents, reusing cached results. Returns (doc, ParseResult | None, status) tuples;
    status is None or [kind, detail] with kind "atlandi", "is" (business) or "hata"."""
    cache_path = cache_dir / CACHE_NAME if cache_dir else None
    cache = _load_cache(cache_path) if cache_path else {}
    fresh: dict = dict(cache) if keep_old else {}
    results = []
    for i, doc in enumerate(docs, 1):
        entry = cache.get(doc.sha256)
        if entry is None:
            if progress:
                progress(i, len(docs), doc.name)
            try:
                entry = {"result": parse_document(doc).to_dict(), "status": None}
            except Skipped as exc:
                entry = {"result": None, "status": ["is" if exc.business else "atlandi", str(exc)]}
            except Unreadable as exc:
                entry = {"result": None, "status": ["hata", str(exc)]}
            except Exception as exc:  # a broken document must not stop the whole run  # noqa: BLE001
                entry = {"result": None, "status": ["hata", f"{type(exc).__name__}: {exc}"]}
        fresh[doc.sha256] = entry
        result = ParseResult.from_dict(entry["result"]) if entry["result"] else None
        results.append((doc, result, entry["status"]))
    if cache_path:
        _save_cache(cache_path, fresh)
    return results


def run(sources: list[Path], rules: Path, cache_dir: Path | None, progress=None, settings: dict | None = None) -> tuple[Dataset, dict]:
    docs, duplicates = collect(sources)
    results = parse_all(docs, cache_dir, progress)
    dataset = build(results, Categorizer(rules), settings or {})
    stats = {"documents": len(docs), "duplicates": duplicates}
    return dataset, stats
