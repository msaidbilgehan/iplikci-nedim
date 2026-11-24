"""What the computers share through the sync folder, piece by piece (ADR-0025): how this computer's own value of each
piece reads, and how a value that won the merge is put in place here.

Shared: the documents (kept or removed, with their names and arrivals; the bytes travel beside the state), the user's
annotations, account names and closed accounts, Claude's notes, the category and alert rule files and the settings that
make the numbers (the user's names and company names, the senders, the notification preferences, the rate providers,
MCP's masking). Each computer keeps its own: what the readers read (made again from the documents), the analysis and the
feed made from them, the event log and notifications, the e-mail account and the browser extension's pairing, the
Telegram bot's token, the service's port, the backups and the update mode.

A value put in place is read back as this computer's own value; the digest of that is what the next round compares
with. So a value this version cannot hold whole (a newer version's field) is not taken for a change of its own, and two
computers that write a value a little differently never answer each other's changes forever.
"""

import json
import logging
import re
import tomllib
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, cast

from .. import rulefile
from ..domain.codes import Actor, DocumentStatus, MemoryKind, Necessity, SourceKind
from ..notify import rules as alert_rules
from ..settings import config, locks
from ..storage import aliases, annotations, audit, closures, documents, memories, readings
from ..storage.aliases import Alias
from ..storage.annotations import Annotation, Part, Subject
from ..storage.closures import Closure
from ..storage.db import Database
from ..storage.documents import DocumentRow, Source
from ..storage.memories import Memory
from ..sync.state import Entry, Kind, canonical, digest
from .workspace import Workspace

log = logging.getLogger("iplikci.sync")

# The settings every computer shares: they decide what the documents say and how the user is told. The rest is the
# computer's own (its port, its e-mail account, its channels, its backups, its updates, its sync folder), and so are
# the two that guard it: whether a sender must be verified (DMARC) and what MCP masks. Whoever can write into the sync
# folder must never be able to turn those off on every computer.
SHARED_SETTINGS: tuple[tuple[str, str], ...] = (
    ("identity", "names"),
    ("identity", "business_names"),
    ("mail", "bank_senders"),
    ("mail", "other_senders"),
    ("notify", "quiet_hours"),
    ("notify", "detail"),
    ("fx", "providers"),
)
PERSONAL_RULES = "rules/personal.yaml"
ALERT_RULES = "rules/alerts.yaml"
REMOVED_BY_SYNC = "document.removed"  # the audit log's action, as a removal made here
KEPT_AGAIN = "document.kept_again"  # the audit log's action: a document removed here that the others keep
_RULES_WAIT = 30.0  # seconds a rule file's change may wait for another


# --- this computer's own values -----------------------------------------------------------------------------


def _annotation(a: Annotation) -> str:
    return canonical(
        {
            "subject": asdict(a.subject),
            "note": a.note,
            "tags": list(a.tags),
            "category": a.category,
            "necessity": a.necessity or "",
            "parts": [{"amount": p.amount, "category": p.category, "necessity": p.necessity or ""} for p in a.parts],
            "created_at": a.created_at,
            "updated_at": a.updated_at,
            "actor": a.actor.value,
        }
    )


def _alias(a: Alias) -> str:
    return canonical({"alias": a.alias, "updated_at": a.updated_at, "actor": a.actor.value})


def _closure(c: Closure) -> str:
    return canonical({"closed_on": c.closed_on, "updated_at": c.updated_at, "actor": c.actor.value})


def _memory(m: Memory) -> str:
    return canonical(
        {
            "kind": m.kind.value,
            "description": m.description,
            "body": m.body,
            "created_at": m.created_at,
            "updated_at": m.updated_at,
            "actor": m.actor.value,
        }
    )


def _document(d: DocumentRow) -> str:
    removed = d.status is DocumentStatus.REMOVED
    return canonical(
        {
            "name": d.name,
            "size": d.size,
            "added_at": d.added_at,
            "parent": d.parent,
            "removed": removed,
            "reason": d.reason if removed else "",
        }
    )


def source_key(sha256: str, s: Source) -> str:
    return canonical([sha256, s.kind.value, s.original, s.origin, s.message_id])


def _source(s: Source) -> str:
    return canonical({"sender": s.sender, "subject": s.subject, "sent_at": s.sent_at, "received_at": s.received_at})


def _settings_file(ws: Workspace) -> dict[str, Any]:
    try:
        with ws.layout.settings.open("rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}


def _plain(value: Any) -> Any:
    """A TOML value as JSON holds it (tomlkit's and tomllib's containers into plain ones)."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in cast(dict[Any, Any], value).items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in cast(list[Any], value)]
    return value


def setting_values(ws: Workspace) -> dict[str, str]:
    """The shared settings the file sets, by "section.name"; a setting left to the program's default has none."""
    data = _settings_file(ws)
    found: dict[str, str] = {}
    for section, name in SHARED_SETTINGS:
        table = data.get(section)
        if isinstance(table, dict) and name in table:
            found[f"{section}.{name}"] = canonical(_plain(cast(dict[str, Any], table)[name]))
    return found


def _rule_files(ws: Workspace) -> dict[str, Path]:
    return {PERSONAL_RULES: ws.layout.personal_rules, ALERT_RULES: ws.layout.alert_rules}


def file_values(ws: Workspace) -> dict[str, str]:
    """The rule files there are, by their place in the data folder."""
    found: dict[str, str] = {}
    for key, path in _rule_files(ws).items():
        try:
            found[key] = canonical({"text": path.read_text(encoding="utf-8")})
        except FileNotFoundError:
            continue
    return found


def db_values(db: Database) -> dict[tuple[str, str], str]:
    """This computer's own values of the pieces the database holds."""
    found: dict[tuple[str, str], str] = {}
    for fp, a in annotations.every(db).items():
        found[Kind.ANNOTATION, fp] = _annotation(a)
    for account, a in aliases.every(db).items():
        found[Kind.ALIAS, account] = _alias(a)
    for account, c in closures.every(db).items():
        found[Kind.CLOSURE, account] = _closure(c)
    for m in memories.every(db):
        found[Kind.MEMORY, m.name] = _memory(m)
    for d in documents.every(db):
        found[Kind.DOCUMENT, d.sha256] = _document(d)
    for sha256, s in documents.every_source(db):
        found[Kind.SOURCE, source_key(sha256, s)] = _source(s)
    return found


def file_kind_values(ws: Workspace) -> dict[tuple[str, str], str]:
    """This computer's own values of the pieces kept in files."""
    found: dict[tuple[str, str], str] = {(Kind.SETTING, k): v for k, v in setting_values(ws).items()}
    found |= {(Kind.FILE, k): v for k, v in file_values(ws).items()}
    return found


# Kinds whose piece is never taken away here: a document is removed by its value, an arrival stays recorded. A row
# missing here is one this computer has not put in place yet (a restored older database), never a removal.
KEPT_KINDS = frozenset({Kind.DOCUMENT, Kind.SOURCE})
DB_KINDS = frozenset({Kind.ANNOTATION, Kind.ALIAS, Kind.CLOSURE, Kind.MEMORY, Kind.DOCUMENT, Kind.SOURCE})
FILE_KINDS = frozenset({Kind.SETTING, Kind.FILE})
# Kinds no computer has a value of its own of: the sync itself changes them.
SYNC_KINDS = frozenset({Kind.SENDER})


def own_value(ws: Workspace, db: Database, kind: str, key: str) -> str | None:
    """This computer's own value of one piece now; None when it has none."""
    if kind == Kind.ANNOTATION:
        a = annotations.get(db, key)
        return None if a is None else _annotation(a)
    if kind == Kind.ALIAS:
        found = aliases.every(db).get(key)
        return None if found is None else _alias(found)
    if kind == Kind.CLOSURE:
        mark = closures.every(db).get(key)
        return None if mark is None else _closure(mark)
    if kind == Kind.MEMORY:
        m = memories.get(db, key)
        return None if m is None else _memory(m)
    if kind == Kind.DOCUMENT:
        d = documents.get(db, key)
        return None if d is None else _document(d)
    if kind == Kind.SOURCE:
        sha256, *rest = json.loads(key)
        for s in documents.sources(db, sha256):
            if [s.kind.value, s.original, s.origin, s.message_id] == rest:
                return _source(s)
        return None
    if kind == Kind.SETTING:
        return setting_values(ws).get(key)
    if kind == Kind.FILE:
        return file_values(ws).get(key)
    return None


# --- what another computer's piece must look like ----------------------------------------------------------

_SHA256 = re.compile(r"[0-9a-f]{64}")
_KEY_LONGEST = 500  # a fingerprint, an account's id, a note's name: short handles
_SOURCE_KEY_LONGEST = 5000  # an arrival's key holds its file's name, where it came from and the message's id


def _iso_day(text: str) -> bool:
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True


def _fields(value: str | None, shape: Mapping[str, type]) -> bool:
    """Whether value is a JSON object with at least these fields of these types (a newer version may add more)."""
    if value is None:
        return True
    try:
        found: Any = json.loads(value)
    except ValueError:
        return False
    if not isinstance(found, dict):
        return False
    data = cast(dict[str, Any], found)
    for name, kind in shape.items():
        if name not in data:
            return False
        field = data[name]
        if kind is bool:
            if not isinstance(field, bool):
                return False
        elif isinstance(field, bool) or not isinstance(field, kind):  # a bool is an int to isinstance
            return False
    return True


_ANNOTATION = {"subject": dict, "note": str, "tags": list, "category": str, "necessity": str, "parts": list,
               "created_at": str, "updated_at": str, "actor": str}  # fmt: skip
_ALIAS = {"alias": str, "updated_at": str, "actor": str}
_CLOSURE = {"closed_on": str, "updated_at": str, "actor": str}
_MEMORY = {"kind": str, "description": str, "body": str, "created_at": str, "updated_at": str, "actor": str}
_DOCUMENT = {"name": str, "size": int, "added_at": str, "parent": str, "removed": bool, "reason": str}
_SOURCE = {"sender": str, "subject": str, "sent_at": str, "received_at": str}
_SENDER = {"device": str, "since": str}
_FILE = {"text": str}


def _source_key(key: str) -> bool:
    try:
        found: Any = json.loads(key)
    except ValueError:
        return False
    if not isinstance(found, list):
        return False
    parts = cast(list[Any], found)
    return len(parts) == 5 and all(isinstance(p, str) for p in parts) and bool(_SHA256.fullmatch(parts[0]))


def valid(entry: Entry) -> bool:
    """Whether another computer's piece has its kind's shape: a damaged or forged file's pieces never reach the
    database. A kind this version does not know passes through as it is (a newer computer's)."""
    kind, key, value = entry.kind, entry.key, entry.value
    if not key or len(key) > (_SOURCE_KEY_LONGEST if kind == Kind.SOURCE else _KEY_LONGEST):
        return False
    if kind == Kind.ANNOTATION:
        return _fields(value, _ANNOTATION)
    if kind == Kind.ALIAS:
        return _fields(value, _ALIAS)
    if kind == Kind.CLOSURE:
        return _fields(value, _CLOSURE) and (value is None or _iso_day(json.loads(value)["closed_on"]))
    if kind == Kind.MEMORY:
        return _fields(value, _MEMORY)
    if kind == Kind.DOCUMENT:
        return bool(_SHA256.fullmatch(key)) and value is not None and _fields(value, _DOCUMENT)
    if kind == Kind.SOURCE:
        return _source_key(key) and value is not None and _fields(value, _SOURCE)
    if kind == Kind.SETTING:
        return tuple(key.split(".", 1)) in SHARED_SETTINGS
    if kind == Kind.FILE:
        return key in (PERSONAL_RULES, ALERT_RULES) and _fields(value, _FILE)
    if kind == Kind.SENDER:
        return key in ("telegram", "email") and _fields(value, _SENDER)
    return True


# --- putting a winner in place ----------------------------------------------------------------------------


@dataclass
class Applied:
    """What a round put in place here, by kind; documents whose bytes still wait are not among them."""

    counts: dict[str, int] = field(default_factory=dict[str, int])
    added: list[str] = field(default_factory=list[str])  # documents that came
    removed: list[str] = field(default_factory=list[str])  # documents removed
    files: list[str] = field(default_factory=list[str])  # the settings and rule files changed, by their keys
    settings: bool = False  # a shared setting changed here: the readers' company names follow

    def note(self, kind: str) -> None:
        self.counts[kind] = self.counts.get(kind, 0) + 1

    def take(self, other: "Applied") -> None:
        """What a piece put in place, once it is kept."""
        for kind, n in other.counts.items():
            self.counts[kind] = self.counts.get(kind, 0) + n
        self.added += other.added
        self.removed += other.removed
        self.files += other.files
        self.settings = self.settings or other.settings

    @property
    def any(self) -> bool:
        return bool(self.counts)

    @property
    def changes_numbers(self) -> bool:
        """Whether the analysis must be made again: anything but Claude's notes and the senders."""
        return any(k not in (Kind.MEMORY, Kind.SENDER) for k in self.counts)


class Waits(Exception):
    """The winner cannot be put in place yet (a document's bytes not here, a rule file this version refuses); it is
    tried again in the next round."""


def _subject(value: dict[str, Any]) -> Subject:
    return Subject(**value)


def put_db(ws: Workspace, db: Database, kind: str, key: str, value: str | None, applied: Applied) -> None:
    """Put a winner of a database kind in place, in the caller's transaction. Waits when it cannot be yet."""
    data: Any = None if value is None else json.loads(value)
    if kind == Kind.ANNOTATION:
        if data is None:
            annotations.drop(db, key)
        else:
            annotations.put(
                db,
                Annotation(
                    fingerprint=key,
                    subject=_subject(data["subject"]),
                    note=data["note"],
                    tags=tuple(data["tags"]),
                    category=data["category"],
                    necessity=Necessity(data["necessity"]) if data["necessity"] else None,
                    created_at=data["created_at"],
                    updated_at=data["updated_at"],
                    actor=Actor(data["actor"]),
                    parts=tuple(
                        Part(int(p["amount"]), p["category"], Necessity(p["necessity"]) if p["necessity"] else None)
                        for p in data["parts"]
                    ),
                ),
            )
    elif kind == Kind.ALIAS:
        if data is None:
            aliases.drop(db, key)
        else:
            aliases.put(db, Alias(key, data["alias"], data["updated_at"], Actor(data["actor"])))
    elif kind == Kind.CLOSURE:
        if data is None:
            closures.drop(db, key)
        else:
            closures.put(db, Closure(key, data["closed_on"], data["updated_at"], Actor(data["actor"])))
    elif kind == Kind.MEMORY:
        if data is None:
            memories.drop(db, key)
        else:
            memories.put(
                db,
                Memory(
                    key,
                    MemoryKind(data["kind"]),
                    data["description"],
                    data["body"],
                    data["created_at"],
                    data["updated_at"],
                    Actor(data["actor"]),
                ),
            )
    elif kind == Kind.DOCUMENT:
        if data is None:
            raise Waits("a document is never taken away")  # no computer writes one; kept as it is here
        _put_document(ws, db, key, data, applied)
    elif kind == Kind.SOURCE:
        if data is None:
            raise Waits("an arrival is never taken away")
        sha256, source_kind, original, origin, message_id = json.loads(key)
        if documents.get(db, sha256) is None:
            raise Waits("its document is not here yet")
        documents.put_source(
            db,
            sha256,
            Source(
                SourceKind(source_kind),
                original,
                origin,
                message_id,
                data["sender"],
                data["subject"],
                data["sent_at"],
                data["received_at"],
            ),
        )
    else:
        raise Waits(f"{kind} is not a database kind")
    applied.note(kind)


def _put_document(ws: Workspace, db: Database, sha256: str, data: dict[str, Any], applied: Applied) -> None:
    removed = bool(data["removed"])
    here = documents.get(db, sha256)
    row = DocumentRow(
        sha256=sha256,
        name=data["name"],
        size=int(data["size"]),
        status=DocumentStatus.REMOVED if removed else DocumentStatus.UNPROCESSED,
        reason=data["reason"] if removed else "",
        parent=data["parent"],
        added_at=data["added_at"],
    )
    if here is None:
        if not removed and not ws.vault.has(sha256):
            raise Waits("its bytes are not here yet")
        documents.arrive(db, row)
        if removed:
            applied.removed.append(sha256)  # bytes brought in before the removal came go to the Trash
        else:
            applied.added.append(sha256)
        return
    if not removed and here.status is DocumentStatus.REMOVED:
        # Kept by the others, removed here before this computer joined them: the folder's data wins (ADR-0025).
        if not ws.vault.has(sha256):
            raise Waits("its bytes are not here yet")
        documents.arrive(db, row)
        documents.reopen(db, sha256)
        audit.record(db, Actor.SYNC, KEPT_AGAIN, sha256)
        applied.added.append(sha256)
        return
    documents.arrive(db, row)  # the name, the time and the message it came in, as the winner says
    if removed and here.status is not DocumentStatus.REMOVED:
        # Removed on another computer (by the user, or as a company's document): its rows go now, its bytes to the
        # Trash once the round's changes are kept (ADR-0003), never while the database waits on the move.
        readings.clear(db, sha256)
        documents.set_status(db, sha256, DocumentStatus.REMOVED, row.reason)
        applied.removed.append(sha256)
    elif removed and here.reason != row.reason:
        documents.set_status(db, sha256, DocumentStatus.REMOVED, row.reason)


def put_file(ws: Workspace, kind: str, key: str, value: str | None, expected: str) -> str:
    """Put a winner of a file kind in place, unless the file changed since the round compared it (expected: the
    digest its value had then); the digest of the value written, taken under the file's lock, so a change the user
    makes right after is a change of this computer's own. Waits when it cannot be yet."""
    data: Any = None if value is None else json.loads(value)
    if kind == Kind.SETTING:
        section, name = key.split(".", 1)
        if (section, name) not in SHARED_SETTINGS:
            raise Waits(f"{key} is not a setting this version shares")

        def unchanged(tables: dict[str, Any]) -> bool:
            table = tables.get(section)
            here = canonical(_plain(table[name])) if isinstance(table, dict) and name in table else None
            return digest(here) == expected

        try:
            config.update(ws.layout.settings, section, {name: data}, guard=unchanged)
        except config.Changed as exc:
            raise Waits("changed here meanwhile") from exc
        except config.SettingsError as exc:  # a value this version does not take (a newer one's)
            raise Waits(str(exc)) from exc
        return digest(None if data is None else canonical(_plain(data)))
    if kind == Kind.FILE:
        paths = _rule_files(ws)
        if key not in paths:
            raise Waits(f"{key} is not a file this version shares")
        path = paths[key]
        text = None if data is None else str(data["text"])
        if text is not None:
            try:
                if key == PERSONAL_RULES:
                    rulefile.validate(text, path.name)
                else:
                    alert_rules.parse(text, path.name)
            except (ValueError, alert_rules.RulesError) as exc:
                raise Waits(f"{key}: {exc}") from exc
        try:
            with locks.held(path.with_name(f".{path.name}.kilit"), _RULES_WAIT):
                if digest(file_values(ws).get(key)) != expected:
                    raise Waits("changed here meanwhile")
                if text is not None:
                    rulefile.replace(path, text, ws.layout.rules_history)
                elif path.exists():
                    rulefile.retire(path, ws.layout.rules_history)
        except locks.LockTimeout as exc:
            raise Waits("the rule file is being changed here") from exc
        return digest(None if text is None else canonical({"text": text}))
    raise Waits(f"{kind} is not a file kind")
