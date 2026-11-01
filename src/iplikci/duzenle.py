"""File bank documents into a tidy folder tree and set the rest aside.

    Bankalar/<Banka>/<Hesap veya kart>/<tarih> <banka> <hesap> <belge türü>.<uzantı>

Personal card statements, account movement lists (brokerage statements and
passbooks too) and receipts are kept and renamed: a receipt carries a transfer
before the statement does, and once the statement comes it is the evidence the
month closed with (analysis.settle_receipts). Company documents, documents the
analysis does not use (forms, contracts, insurance policies) and duplicates are
moved to a recoverable trash folder. Nothing is touched unless apply=True.
"""

import csv
import hashlib
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .analysis import resolve_masked
from .models import ParseResult
from .pipeline import parse_all
from .sources import DOCUMENT_EXTENSIONS, Document, UnreadableArchive, _from_mbox, _from_zip, _is_mbox
from .textutil import nfc
from .vault import trash
from .vault.names import account_names, display_path
from .vault.trash import freedesktop_trash, move_to_system_trash

KEEP, DUPLICATE, BUSINESS, UNUSED, FAILED = "tut", "kopya", "is", "kullanilmayan", "hata"
ACTION_LABELS = {
    KEEP: "Düzenlendi",
    DUPLICATE: "Kopya — silindi",
    BUSINESS: "İş belgesi — silindi",
    UNUSED: "Kullanılmıyor — silindi",
    FAILED: "Okunamadı — elle bakın",
}
UNREADABLE_FOLDER = "Okunamayan belgeler"


@dataclass
class Item:
    """A file on disk, or a document inside an archive (archive set, path None)."""

    name: str
    sha256: str
    path: Path | None = None
    archive: Path | None = None
    data: bytes = b""
    action: str = ""
    target: Path | None = None
    reason: str = ""
    weight: int = 0  # prefer the richer copy when two files hold the same statement
    keys: list = field(default_factory=list)
    result: ParseResult | None = None  # what the parser read, to show it before anything moves


def _target(root: Path, result: ParseResult, ext: str) -> tuple[Path, list, int]:
    """Where a parsed document belongs, the identities it covers and how much data it holds."""
    path = root / display_path(result, ext)
    if result.statements:
        s = result.statements[0]
        return path, [("ekstre", s.account, s.cut_date, s.currency, s.start)], len(s.transactions)
    return path, [("dekont", result.receipt_key)], len(result.transactions)


def _walk(paths: list[Path]) -> tuple[list[Item], list[Path], list[Path]]:
    """Document items, archive files and other files under the given paths."""
    items, archives, others = [], [], []
    stack = list(paths)
    while stack:
        p = stack.pop()
        if p.is_dir():
            stack += sorted(c for c in p.iterdir() if not c.name.startswith("."))
            continue
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext == ".zip" or _is_mbox(p):
            if _is_mbox(p):
                members = _from_mbox(p)
            else:
                data = p.read_bytes()
                try:
                    members = _from_zip(data, nfc(str(p)))
                except UnreadableArchive:
                    # Damaged or password-protected: one unreadable document, never an emptied archive.
                    items.append(Item(nfc(p.name), hashlib.sha256(data).hexdigest(), path=p, data=data))
                    continue
            archives.append(p)
            for name, _, data in members:
                if os.path.splitext(name)[1].lower() in DOCUMENT_EXTENSIONS:
                    items.append(Item(name, hashlib.sha256(data).hexdigest(), archive=p, data=data))
        elif ext in DOCUMENT_EXTENSIONS:
            data = p.read_bytes()
            items.append(Item(nfc(p.name), hashlib.sha256(data).hexdigest(), path=p, data=data))
        else:
            others.append(p)
    return items, archives, others


def _inside(path: Path | None, folder: Path | None) -> bool:
    return path is not None and folder is not None and path.resolve().is_relative_to(folder.resolve())


def plan(
    sources: list[Path],
    root: Path,
    cache_dir: Path | None,
    progress=None,
    inbox: Path | None = None,
    extra: list[Item] | None = None,
) -> list[Item]:
    """Decide, without touching anything, what happens to every file under sources.

    inbox is a folder documents only pass through (uploads, the automatic import): its unreadable
    files move to the unreadable folder like failed archive members, so the inbox empties.
    extra are documents held in memory (e-mail attachments), planned like archive members.
    """
    items, archives, others = _walk(sources)
    items += extra or []
    unique: dict[str, Item] = {}
    for it in items:
        unique.setdefault(it.sha256, it)
    docs = [Document(it.name, str(it.path or it.archive), it.data, it.sha256) for it in unique.values()]
    parsed = {
        doc.sha256: (result, status) for doc, result, status in parse_all(docs, cache_dir, progress, keep_old=True)
    }
    resolve_masked(result for result, _ in parsed.values() if result)

    extracted: set[str] = set()
    resting = {it.sha256 for it in items if _inside(it.path, root)}
    for it in items:
        result, status = parsed[it.sha256]
        it.result = result
        ext = os.path.splitext(it.name)[1].lower() or ".pdf"
        if result is None:
            kind, it.reason = status or ("atlandi", "")
            it.action = {"is": BUSINESS, "hata": FAILED}.get(kind, UNUSED)
            # Never discard what could not be read: archive members (and inbox files) are moved
            # to one folder for a manual look, once.
            in_transit = it.archive is not None or _inside(it.path, inbox)
            if it.action == FAILED and in_transit:
                if it.sha256 in resting or it.sha256 in extracted:
                    if it.path:  # an archive member simply leaves with its archive
                        it.action, it.reason = DUPLICATE, "aynı belgenin bir kopyası tutuluyor"
                else:
                    it.target = root / UNREADABLE_FOLDER / it.name
                    extracted.add(it.sha256)
            continue
        it.target, it.keys, it.weight = _target(root, result, ext)
        it.action = KEEP

    # One file per statement / receipt: identical bytes or the same statement downloaded twice.
    best: dict = {}
    for it in sorted(
        (i for i in items if i.action == KEEP), key=lambda i: (i.path is None, -i.weight, i.target != i.path)
    ):
        key = it.keys[0] if it.keys else it.sha256
        if key in best or it.sha256 in best:
            it.action, it.reason = DUPLICATE, f"kopyası tutuldu: {best.get(key, best.get(it.sha256)).target.name}"
            it.target = None
            continue
        best[key] = best[it.sha256] = it

    # Two different documents must never share a file name (e.g. two receipts on one day).
    taken: set[Path] = set()
    for it in items:
        if it.target is None:
            continue
        stem, ext, n = it.target.stem, it.target.suffix, 2
        while it.target in taken:
            it.target = it.target.with_name(f"{stem} ({n}){ext}")
            n += 1
        taken.add(it.target)

    # Archive members that stay in the archive are listed too: they leave with it.
    plans = list(items)
    for p in others:
        plans.append(Item(nfc(p.name), "", path=p, action=UNUSED, reason="belge değil"))
    kept_from_archives = {it.sha256 for it in items if it.archive and it.action == KEEP}
    for a in archives:
        plans.append(
            Item(
                nfc(a.name),
                "",
                path=a,
                action=UNUSED,
                reason="arşiv: içindeki kişisel belgeler klasöre çıkarıldı" if kept_from_archives else "arşiv",
            )
        )
    return plans


def changes(plans: list[Item]) -> list[Item]:
    """Plan items that move, extract or set aside a file; documents already in place are left out."""
    out = []
    for it in plans:
        if it.target is not None:
            if not (it.path and it.path.resolve() == it.target.resolve()):
                out.append(it)
        elif it.action not in (KEEP, FAILED) and it.path is not None:
            out.append(it)
    return out


def apply(plans: list[Item], root: Path, trash: Path, log: Path, keep: tuple[Path, ...] = ()) -> dict:
    """Carry out a plan. Folders emptied by the moves are removed, except root and the folders in
    keep (the sources the user named: never remove ~/Downloads because its last file moved).
    The log lists what was done even when a move fails halfway."""
    counts: dict[str, int] = {}
    rows = []
    try:
        for it in plans:
            if it.target is not None:
                it.target.parent.mkdir(parents=True, exist_ok=True)
                if it.path and it.path.resolve() == it.target.resolve():
                    pass
                elif it.target.exists() and _sha256(it.target) == it.sha256:
                    it.action, it.reason = DUPLICATE, "hedefte aynı dosya zaten var"
                else:
                    # A different file under the same name (one not yet moved away) is never overwritten.
                    it.target = _free(it.target)
                    if it.path:
                        shutil.move(it.path, it.target)
                    else:
                        it.target.write_bytes(it.data)  # only inside an archive: extract it
            if it.action not in (KEEP, FAILED) and it.path and it.path.exists() and it.path.is_file():
                dest = _free(trash / _relative(it.path))
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(it.path, dest)
            counts[it.action] = counts.get(it.action, 0) + 1
            source = str(it.path or f"{it.archive} › {it.name}")
            rows.append([ACTION_LABELS[it.action], source, str(it.target or ""), it.reason])
    finally:
        _remove_empty_dirs({p.path.parent for p in plans if p.path}, {root, *keep})
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["İşlem", "Eski konum", "Yeni konum", "Neden"])
            w.writerows(sorted(rows))
    return counts


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _free(path: Path) -> Path:
    """path, or 'name (2).ext' etc. if it already exists (never overwrite)."""
    n = 2
    candidate = path
    while candidate.exists():
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
        n += 1
    return candidate


def _relative(path: Path) -> Path:
    parts = path.resolve().parts
    return Path(*parts[-3:]) if len(parts) > 3 else Path(path.name)


def _remove_empty_dirs(dirs: set[Path], keep: set[Path]) -> None:
    kept = {k.resolve() for k in keep}
    for d in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
        # Stop at a kept folder and at anything above one.
        while d.exists() and d.is_dir() and not any(k.is_relative_to(d.resolve()) for k in kept):
            leftovers = [c for c in d.iterdir() if c.name != ".DS_Store"]
            if leftovers:
                break
            for c in d.iterdir():
                c.unlink()
            d.rmdir()
            d = d.parent


def default_trash(root: Path) -> Path:
    return trash.default_folder(root.parent)


__all__ = ["account_names", "freedesktop_trash", "move_to_system_trash"]  # still imported from here until Phase 1 ends
