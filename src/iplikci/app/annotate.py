"""The user's notes and corrections on the ledger's rows (architecture §7, "Kullanıcı düzeltmesi").

An annotation finds its row by fingerprint after every reading. A receipt's row that a statement confirmed leaves
the ledger, and its annotation moves to the statement's row. An annotation no row carries any more is an orphan:
it is kept and shown, never dropped on the program's own.

A corrected category brings its group and the necessity its rules give; a corrected necessity replaces that. The
row's kind stays: a rule in the user's rule file is the way to change how a merchant's rows are counted.

A split row (F04) leaves the ledger for its parts: each counts under its own category with its share of the amount,
the parts adding up to the row to the kuruş. They keep the row's day, account, kind, document and note, and are
found by the row's fingerprint with their number after it. The whole row stays in `Dataset.split`: a payment's
series, size and place in its document are the whole row's (analysis.payments).
"""

import difflib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal

from ..analysis import Dataset, payments
from ..categorize import OTHER_GROUP, Categorizer
from ..domain.codes import SPLITTABLE_KINDS, CategoryReason, Necessity
from ..domain.labels import NECESSITY, format_amount
from ..domain.models import Transaction
from ..domain.money import round_half_up
from ..domain.text import fold
from ..storage.annotations import Annotation, Part, Subject

MAX_PARTS = 20


def apply(ds: Dataset, found: Mapping[str, Annotation], categorizer: Categorizer) -> list[Annotation]:
    """Put every annotation on its row and split the rows the user split; returns the orphans, oldest first."""
    rows = {t.fingerprint: t for t in ds.transactions}
    moved = {line.txn.fingerprint: line.match.fingerprint for line in ds.receipts if line.match is not None}
    orphans: list[Annotation] = []
    split: dict[str, list[Transaction]] = {}
    for fp, annotation in found.items():
        target = fp if fp in rows else moved.get(fp, "")
        # The statement's row may carry an annotation of its own: that one is the user's word on it.
        if target not in rows or (target != fp and target in found):
            orphans.append(annotation)
            continue
        _put(rows[target], annotation, categorizer)
        parts = _parts(rows[target], annotation.parts, categorizer)
        if parts:
            split[target] = parts
    if split:
        ds.split = {fp: rows[fp] for fp in split}
        ds.transactions = [part for t in ds.transactions for part in split.get(t.fingerprint, (t,))]
    return orphans


def part_fingerprint(fingerprint: str, number: int) -> str:
    """A part's fingerprint: the row's, with the part's number (from 1) after it."""
    return f"{fingerprint}-{number}"


def _parts(t: Transaction, parts: Sequence[Part], categorizer: Categorizer) -> list[Transaction]:
    """The row's parts as rows of their own; none when it is not split or cannot be. A row whose amount moved since
    it was split (a foreign one valued at another rate) is shared out as its parts were."""
    total = abs(t.amount)
    given = sum(p.amount for p in parts)
    if len(parts) < 2 or t.kind not in SPLITTABLE_KINDS or not total or any(p.amount <= 0 for p in parts):
        return []
    amounts = [round_half_up(total * p.amount / given) for p in parts[:-1]]
    amounts.append(total - sum(amounts, Decimal(0)))  # the last part takes what rounding left: the sum is exact
    if any(amount <= 0 for amount in amounts):
        return []
    sign = 1 if t.amount > 0 else -1
    found: list[Transaction] = []
    for number, (part, amount) in enumerate(zip(parts, amounts, strict=True), start=1):
        row = replace(
            t,
            amount=sign * amount,
            category=part.category,
            group=categorizer.categories.get(part.category, OTHER_GROUP),
            fingerprint=part_fingerprint(t.fingerprint, number),
            split_of=t.fingerprint,
            reason=replace(t.reason, category=CategoryReason.SPLIT, rule="", layer=""),
        )
        row.necessity = part.necessity or categorizer.necessity_for(row)
        found.append(row)
    return found


@dataclass(frozen=True, slots=True)
class Share:
    """A part as the user gives it: its amount in TL (above zero, whichever way the row's money goes), its category
    as typed, and its necessity when the rules' is not wanted."""

    amount: Decimal
    category: str
    necessity: Necessity | None = None


def split(categorizer: Categorizer, t: Transaction, given: Sequence[Share]) -> tuple[Part, ...]:
    """The parts a row is to be split into, checked: two to MAX_PARTS of them, each in a category the rules know,
    adding up to the row. None given joins the row again."""
    if not given:
        return ()
    if t.kind not in SPLITTABLE_KINDS:
        raise ValueError("Yalnızca harcama, kişiye gönderilen para ve gelir bölünür; bu satırı türü belirliyor.")
    if not 2 <= len(given) <= MAX_PARTS:
        raise ValueError(f"Bir satır en az 2, en çok {MAX_PARTS} parçaya bölünür.")
    parts: list[Part] = []
    for share in given:
        minor = share.amount * 100
        if minor <= 0 or minor != minor.to_integral_value():
            raise ValueError("Her parçanın tutarı sıfırdan büyük, en çok iki ondalıklı bir tutar olmalı.")
        parts.append(Part(int(minor), category(categorizer, share.category), share.necessity))
    if sum(p.amount for p in parts) != round(abs(t.amount) * 100):
        raise ValueError(f"Parçaların toplamı satırın tutarına, {format_amount(abs(t.amount))} TL'ye eşit olmalı.")
    return tuple(parts)


def _put(t: Transaction, annotation: Annotation, categorizer: Categorizer) -> None:
    t.note, t.tags = annotation.note, annotation.tags
    if annotation.category:
        t.category = annotation.category
        t.group = categorizer.categories.get(annotation.category, OTHER_GROUP)
        t.necessity = categorizer.necessity_for(t)
        t.reason = replace(t.reason, category=CategoryReason.USER, rule="", layer="")
    if annotation.necessity:
        t.necessity = annotation.necessity


def subject(t: Transaction, label: str) -> Subject:
    """The row as the user sees it now, kept with its annotation."""
    return Subject(t.account, label, t.date.isoformat(), round(t.amount * 100), "TRY", t.description)


def find(ds: Dataset, prefix: str) -> Transaction:
    """The ledger row whose fingerprint starts with prefix (at least six characters, like a short commit id)."""
    prefix = prefix.strip().lower()
    if len(prefix) < 6:
        raise LookupError("parmak izinin en az ilk 6 karakterini yazın")
    hits = [t for t in payments(ds) if t.fingerprint.startswith(prefix)]
    if not hits:
        raise LookupError(f"{prefix} ile başlayan bir işlem yok")
    if len(hits) > 1:
        raise LookupError(f"{prefix} ile başlayan {len(hits)} işlem var; birkaç karakter daha yazın")
    return hits[0]


def necessity(text: str) -> Necessity:
    """A necessity level from its Turkish label ("isteğe bağlı", "istege-bagli") or its code."""
    wanted = fold(text.replace("-", " ").replace("_", " "))
    for code, label in NECESSITY.items():
        if wanted in (fold(label), fold(code.value)):
            return code
    raise ValueError(f"gereklilik şunlardan biri olmalı: {', '.join(NECESSITY.values())}")


def category(categorizer: Categorizer, text: str) -> str:
    """A category the rules know, written as they write it; a near miss is suggested."""
    wanted = fold(text)
    for name in categorizer.categories:
        if fold(name) == wanted:
            return name
    near = difflib.get_close_matches(text, list(categorizer.categories), n=3, cutoff=0.6)
    hint = f"; bunu mu demek istediniz: {', '.join(near)}" if near else ""
    raise ValueError(f"kurallarda {text!r} diye bir kategori yok{hint}")
