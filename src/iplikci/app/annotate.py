"""The user's notes and corrections on the ledger's rows (architecture §7, "Kullanıcı düzeltmesi").

An annotation finds its row by fingerprint after every reading. A receipt's row that a statement confirmed leaves
the ledger, and its annotation moves to the statement's row. An annotation no row carries any more is an orphan:
it is kept and shown, never dropped on the program's own.

A corrected category brings its group and the necessity its rules give; a corrected necessity replaces that. The
row's kind stays: a rule in the user's rule file is the way to change how a merchant's rows are counted.
"""

import difflib
from collections.abc import Mapping
from dataclasses import replace

from ..analysis import Dataset
from ..categorize import OTHER_GROUP, Categorizer
from ..domain.codes import CategoryReason, Necessity
from ..domain.labels import NECESSITY
from ..domain.models import Transaction
from ..domain.text import fold
from ..storage.annotations import Annotation, Subject


def apply(ds: Dataset, found: Mapping[str, Annotation], categorizer: Categorizer) -> list[Annotation]:
    """Put every annotation on its row; returns the orphans, oldest first."""
    rows = {t.fingerprint: t for t in ds.transactions}
    moved = {line.txn.fingerprint: line.match.fingerprint for line in ds.receipts if line.match is not None}
    orphans: list[Annotation] = []
    for fp, annotation in found.items():
        target = fp if fp in rows else moved.get(fp, "")
        # The statement's row may carry an annotation of its own: that one is the user's word on it.
        if target not in rows or (target != fp and target in found):
            orphans.append(annotation)
            continue
        _put(rows[target], annotation, categorizer)
    return orphans


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
    hits = [t for t in ds.transactions if t.fingerprint.startswith(prefix)]
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
