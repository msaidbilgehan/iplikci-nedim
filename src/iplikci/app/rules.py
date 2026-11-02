"""The category rules (F15), for the Rules screen and the quick decisions other screens offer ("bu işyerini her
zaman X say", "İptal ettim"): the user's rule file over the rules shipped with the app (docs/domain/categorization.md).
Every change is checked by building the rules from it and previewed against the ledger — which rows it moves, from
which category to which — before the file is written; the file before it goes to the history and the audit log says
who changed it."""

from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, cast

import yaml

from .. import rulefile
from ..analysis import Dataset, build
from ..categorize import DEFAULT_RULES, Categorizer, RuleSet, group_slot
from ..domain.codes import Actor, Necessity, TransactionKind
from ..domain.labels import NECESSITY
from ..domain.models import Transaction
from ..domain.money import round_half_up
from ..domain.text import fold
from ..storage import annotations, audit
from . import annotate, background
from .analysis import Current, ledger_input
from .workspace import Workspace

__all__ = [
    "Actor",
    "CategoryInfo",
    "Change",
    "Ended",
    "Example",
    "Labels",
    "Move",
    "Necessity",
    "RulesError",
    "RulesView",
    "TransactionKind",
    "commitment",
    "ended",
    "merchant_necessity",
    "merchant_rule",
    "not_ended",
    "preview",
    "read",
    "save",
]

RULES_CHANGED = "rules.categories_changed"
EXAMPLES = 15  # rows a change shows as examples
MOVES = 20  # category moves it lists


class RulesError(ValueError):
    """The change cannot be made; the message says why, in Turkish."""


@dataclass(frozen=True, slots=True)
class CategoryInfo:
    name: str
    group: str
    slot: int  # the group's colour slot: 1–8, 0 for "Diğer"
    necessity: Necessity | None  # the category's level; None: "Belirsiz" until a rule says
    regular: bool  # a commitment category (`_düzenli`): its payments are regular even when the amount changes
    own: bool  # the user's rule file names it (otherwise only the rules shipped with the app do)


@dataclass(frozen=True, slots=True)
class Ended:
    merchant: str  # as the rule file writes it
    month: str  # the last month with a payment, YYYY-MM
    own: bool  # the user's rule file says so (otherwise the rules shipped with the app)


@dataclass(frozen=True, slots=True)
class RulesView:
    content: str  # the user's rule file as it is; "" before the first change
    categories: list[CategoryInfo]  # in the order of the groups (their colours) and of the files
    ended: list[Ended]
    merchant_necessity: dict[str, Necessity]  # merchant as written -> its own level
    history: list[str]  # the rule file's earlier versions, newest first


@dataclass(frozen=True, slots=True)
class Labels:
    merchant: str
    category: str
    necessity: Necessity | None
    kind: TransactionKind


@dataclass(frozen=True, slots=True)
class Example:
    fingerprint: str
    day: date
    description: str
    amount: Decimal  # TL, above zero money leaving the user
    before: Labels
    after: Labels


@dataclass(frozen=True, slots=True)
class Move:
    before: str  # the category the rows had
    after: str  # the category they get
    count: int
    total: Decimal  # their amounts together, TL


@dataclass(frozen=True, slots=True)
class Change:
    content: str  # the rule file the change makes
    diff: str  # against the file now
    changed: int  # rows whose category, necessity, kind or merchant name it changes
    moves: list[Move]
    examples: list[Example]
    saved: bool
    backup: str  # the earlier version's name in the history; "" when nothing was saved or there was none


def _personal(ws: Workspace) -> str:
    return ws.rules.read_text(encoding="utf-8") if ws.rules.exists() else ""


def _layers(text: str, name: str) -> list[RuleSet]:
    """The user's rules (from text) over the rules shipped with the app."""
    return [RuleSet.parse(text, name), RuleSet.read(DEFAULT_RULES)]


def _section(text: str, folded: str) -> dict[str, Any]:
    """A `_…` section of a rule file as written (the parsed rules fold its keys)."""
    data: object = yaml.safe_load(text)
    if not isinstance(data, dict):
        return {}
    for key, value in cast(dict[object, object], data).items():
        if fold(str(key)) == folded and isinstance(value, dict):
            return {str(k): v for k, v in cast(dict[object, object], value).items()}
    return {}


def read(ws: Workspace) -> RulesView:
    """The rules as the Rules screen shows them. RulesError when the user's file cannot be read."""
    text = _personal(ws)
    shipped = DEFAULT_RULES.read_text(encoding="utf-8")
    try:
        layers = _layers(text, ws.rules.name)
    except (ValueError, yaml.YAMLError) as exc:
        raise RulesError(f"kişisel kurallar okunamadı: {exc}") from exc
    rules = Categorizer.from_layers(*layers)
    own = layers[0].categories
    categories = [
        CategoryInfo(
            name=category,
            group=group,
            slot=group_slot(rules.groups, group),
            necessity=rules.necessity.get(category),
            regular=category in rules.regular,
            own=category in own,
        )
        for group in rules.groups
        for category, home in rules.categories.items()
        if home == group
    ]
    ended = {fold(m): Ended(m, str(v)[:7], False) for m, v in _section(shipped, "_BITEN").items()}
    ended |= {fold(m): Ended(m, str(v)[:7], True) for m, v in _section(text, "_BITEN").items()}
    written = {fold(m): m for m in (*_section(shipped, "_GEREKLILIK_ISYERI"), *_section(text, "_GEREKLILIK_ISYERI"))}
    history = sorted(
        (p.name for p in ws.rules_history.glob(f"{ws.rules.stem} *{ws.rules.suffix}") if p.is_file()), reverse=True
    )
    return RulesView(
        content=text,
        categories=categories,
        ended=sorted(ended.values(), key=lambda e: (e.month, fold(e.merchant)), reverse=True),
        merchant_necessity={written.get(m, m): level for m, level in rules.merchant_necessity.items()},
        history=history,
    )


def _ledger(ws: Workspace, rules: Categorizer) -> Dataset:
    """The ledger as these rules would make it, the user's annotations on it (as app.analysis makes it)."""
    with ws.db() as db:
        found, _ = ledger_input(db)
        notes = annotations.every(db)
    names = list(ws.fresh_settings().identity.names)
    ds = build(found, rules, {"ad_soyad": names} if names else {})
    annotate.apply(ds, notes, rules)
    return ds


def _labels(t: Transaction) -> Labels:
    return Labels(t.merchant, t.category, t.necessity, t.kind)


def _effect(before: Dataset, after: Dataset) -> tuple[int, list[Move], list[Example]]:
    """The rows the change moves (by their fingerprints: a row is the same row whatever its rules say)."""
    old = {t.fingerprint: t for t in before.transactions}
    moves: Counter[tuple[str, str]] = Counter()
    totals: defaultdict[tuple[str, str], Decimal] = defaultdict(Decimal)
    examples: list[Example] = []
    for y in after.transactions:
        x = old.get(y.fingerprint)
        if x is None or _labels(x) == _labels(y):
            continue
        moves[(x.category, y.category)] += 1
        totals[(x.category, y.category)] += y.amount
        if len(examples) < EXAMPLES:
            examples.append(Example(y.fingerprint, y.date, y.description, y.amount, _labels(x), _labels(y)))
    listed = [Move(f, t, n, round_half_up(totals[(f, t)])) for (f, t), n in moves.most_common(MOVES)]
    return sum(moves.values()), listed, examples


def _checked(ws: Workspace, text: str) -> Categorizer:
    try:
        rulefile.validate(text, ws.rules.name)
        return Categorizer.from_layers(*_layers(text, ws.rules.name))
    except ValueError as exc:
        raise RulesError(str(exc)) from exc


def preview(ws: Workspace, before: Dataset, text: str) -> Change:
    """What text would change, against the ledger now (before); nothing is written. RulesError when the program
    could not read these rules."""
    old = _personal(ws)
    rules = _checked(ws, text)
    changed, moves, examples = _effect(before, _ledger(ws, rules))
    return Change(text, rulefile.diff(old, text, ws.rules.name), changed, moves, examples, False, "")


def save(ws: Workspace, current: Current, text: str, actor: Actor) -> Change:
    """Write text as the user's rules, the file before it kept in the history; what it changed. The analysis is made
    again now and the exports and the feed follow in the background. RulesError for no change or unreadable rules."""
    old = _personal(ws)
    if text == old:
        raise RulesError("değişiklik yok: kurallar zaten böyle")
    _checked(ws, text)
    before = current.get().dataset
    backup = rulefile.replace(ws.rules, text, ws.rules_history)
    with ws.db() as db:
        audit.record(db, actor, RULES_CHANGED, ws.rules.name, backup=backup.name if backup else "")
    changed, moves, examples = _effect(before, current.refresh(write=False).dataset)
    background.request_refresh(ws)
    return Change(
        text,
        rulefile.diff(old, text, ws.rules.name),
        changed,
        moves,
        examples,
        True,
        backup.name if backup else "",
    )


def _edited(edit: Callable[[], str]) -> str:
    try:
        return edit()
    except ValueError as exc:
        raise RulesError(str(exc)) from exc


def merchant_rule(
    ws: Workspace, category: str, merchant: str, patterns: list[str], necessity: Necessity | None = None
) -> str:
    """The user's rules with a named merchant under category ("bu işyerini her zaman X say"), and, when necessity is
    given, the merchant's own level of necessity."""
    homes = Categorizer.from_layers(*_layers(_personal(ws), ws.rules.name)).categories
    text = _edited(lambda: rulefile.add_merchant_rule(_personal(ws), category, merchant, patterns, homes))
    if necessity is not None:
        text = _edited(lambda: rulefile.set_merchant_necessity(text, merchant, NECESSITY[necessity]))
    return text


def merchant_necessity(ws: Workspace, merchant: str, necessity: Necessity | None) -> str:
    """The user's rules with the merchant's own level of necessity; None takes it back to its category's."""
    if necessity is None:
        return _edited(lambda: rulefile.remove_merchant_necessity(_personal(ws), merchant))
    return _edited(lambda: rulefile.set_merchant_necessity(_personal(ws), merchant, NECESSITY[necessity]))


def ended(ws: Workspace, ds: Dataset, merchant: str, month: str, note: str = "") -> str:
    """The user's rules with a payment ended ("İptal ettim"): no payment of merchant is expected after month. The
    merchant is named as the ledger names it."""
    names = {t.merchant for t in ds.transactions if t.merchant}
    match = next((m for m in names if fold(m) == fold(merchant)), None)
    if match is None:
        raise RulesError(f"'{merchant}' adlı işyeri işlemlerde yok; işlemlerde göründüğü adı kullanın")
    return _edited(lambda: rulefile.add_ended(_personal(ws), match, month, note))


def not_ended(ws: Workspace, merchant: str) -> str:
    """The user's rules with a payment expected again."""
    return _edited(lambda: rulefile.remove_ended(_personal(ws), merchant))


def commitment(ws: Workspace, category: str, on: bool) -> str:
    """The user's rules with category a commitment one (`_düzenli`), or no longer in the user's own list."""
    known = Categorizer.from_layers(*_layers(_personal(ws), ws.rules.name)).categories
    if on and not any(fold(c) == fold(category) for c in known):
        raise RulesError(f"'{category}' adlı kategori yok")
    if on:
        return _edited(lambda: rulefile.add_regular(_personal(ws), category))
    return _edited(lambda: rulefile.remove_regular(_personal(ws), category))
