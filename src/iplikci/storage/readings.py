"""What the readers read, kept as tables (architecture §8): a document's accounts, statements with their rows
and securities, a receipt's rows, and a non-bank sender's bills and receipts. Saving replaces a document's previous reading; loading gives back the
reader's result as it was, for the ledger to combine in memory.
"""

import json
import sqlite3
from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from ..domain.codes import AccountType, InvoiceKind, TransactionKind
from ..domain.models import (
    TRY,
    Account,
    Invoice,
    InvoiceLine,
    ParseResult,
    Security,
    SourceRef,
    Statement,
    Transaction,
)
from ..domain.text import fold
from .db import Database
from .documents import DocumentRow

# Every currency the banks print has two decimals (domain.money.MINOR_DIGITS); so do gold grams as the lists
# print them.
_DIGITS = 2


def _to_minor(amount: Decimal) -> int:
    """An amount as stored: an exact count of the smallest unit. A reader keeps two decimals (ADR-0006); more is
    a reader's bug, refused rather than rounded away."""
    units = amount.scaleb(_DIGITS)
    if units != units.to_integral_value():
        raise ValueError(f"{amount} iki haneden fazla ondalık taşıyor; okuyucu tutarı yuvarlamalıydı")
    return int(units)


def _from_minor(units: int) -> Decimal:
    return Decimal(units).scaleb(-_DIGITS)


def _ref_text(ref: SourceRef | None) -> str:
    """A row's place in its document as stored: JSON of the fields it has, "" when the reader gave none."""
    if ref is None:
        return ""
    fields = {
        "page": ref.page,
        "box": list(ref.box) if ref.box else None,
        "line": ref.line,
        "sheet": ref.sheet,
        "row": ref.row,
        "span": list(ref.span) if ref.span else None,
    }
    return json.dumps({k: v for k, v in fields.items() if v is not None}, ensure_ascii=False, separators=(",", ":"))


def _ref(text: str) -> SourceRef | None:
    if not text:
        return None
    data = json.loads(text)
    box, span = data.get("box"), data.get("span")
    return SourceRef(
        page=data.get("page"),
        box=(box[0], box[1], box[2], box[3]) if box else None,
        line=data.get("line"),
        sheet=data.get("sheet"),
        row=data.get("row"),
        span=(span[0], span[1]) if span else None,
    )


def clear(db: Database, sha256: str) -> None:
    """Forget what was read from a document (its rows and their search entries)."""
    with db.transaction():
        db.execute("DELETE FROM search WHERE sha256 = ? AND kind != 'document'", (sha256,))
        db.execute(
            "DELETE FROM securities WHERE statement_id IN (SELECT id FROM statements WHERE sha256 = ?)", (sha256,)
        )
        db.execute("DELETE FROM transactions WHERE sha256 = ?", (sha256,))
        db.execute("DELETE FROM statements WHERE sha256 = ?", (sha256,))
        db.execute("DELETE FROM evidence WHERE sha256 = ?", (sha256,))
        db.execute("DELETE FROM invoices WHERE sha256 = ?", (sha256,))
        db.execute("DELETE FROM document_accounts WHERE sha256 = ?", (sha256,))


def save(db: Database, sha256: str, result: ParseResult) -> None:
    """Replace what was read from a document with result."""
    with db.transaction():
        clear(db, sha256)
        currencies: dict[str, str] = {}
        for i, a in enumerate(result.accounts):
            currencies.setdefault(a.id, a.currency)
            db.execute(
                "INSERT INTO document_accounts (sha256, position, id, label, bank, type, currency, number, note) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sha256, i, a.id, a.label, a.bank, a.type, a.currency, a.number, a.note),
            )
        for i, s in enumerate(result.statements):
            statement_id = db.execute(
                "INSERT INTO statements (sha256, position, account, cut_date, currency, source, previous, total, "
                "total_is_sum, start, checks_ok, checks_total, balances, one_off, due_date, minimum_payment, "
                "credit_limit, next_cut, empty) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    sha256,
                    i,
                    s.account,
                    s.cut_date.isoformat(),
                    s.currency,
                    s.source,
                    None if s.previous is None else _to_minor(s.previous),
                    None if s.total is None else _to_minor(s.total),
                    int(s.total_is_sum),
                    s.start.isoformat() if s.start else "",
                    s.checks_ok,
                    s.checks_total,
                    json.dumps({month: _to_minor(v) for month, v in s.balances.items()}),
                    int(s.one_off),
                    s.due_date.isoformat() if s.due_date else "",
                    None if s.minimum_payment is None else _to_minor(s.minimum_payment),
                    None if s.credit_limit is None else _to_minor(s.credit_limit),
                    s.next_cut.isoformat() if s.next_cut else "",
                    int(s.empty),
                ),
            ).lastrowid
            for j, sec in enumerate(s.securities):
                db.execute(
                    "INSERT INTO securities (statement_id, position, code, name, quantity, value, as_of) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        statement_id,
                        j,
                        sec.code,
                        sec.name,
                        str(sec.quantity),
                        _to_minor(sec.value),
                        sec.as_of.isoformat(),
                    ),
                )
            for j, t in enumerate(s.transactions):
                row_id = db.execute(
                    "INSERT INTO transactions (sha256, statement_id, position, date, description, amount, currency, "
                    "kind, account, original, installment, bank_category, counterparty, source, ref, balance) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (sha256, statement_id, j, *_row_values(t, s.currency)),
                ).lastrowid
                _index(db, sha256, "transaction", row_id, t)
        for i, t in enumerate(result.transactions):
            row_id = db.execute(
                "INSERT INTO evidence (sha256, position, date, description, amount, currency, kind, account, "
                "original, installment, bank_category, counterparty, source, ref, balance) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sha256, i, *_row_values(t, currencies.get(t.account, TRY))),
            ).lastrowid
            _index(db, sha256, "evidence", row_id, t)
        for i, invoice in enumerate(result.invoices):
            db.execute(
                "INSERT INTO invoices (sha256, position, kind, seller, seller_id, number, issued, due, total, "
                "currency, lines, ref) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    sha256,
                    i,
                    invoice.kind,
                    invoice.seller,
                    invoice.seller_id,
                    invoice.number,
                    invoice.issued.isoformat(),
                    invoice.due.isoformat() if invoice.due else "",
                    _to_minor(invoice.total),
                    invoice.currency,
                    json.dumps([_line_value(line) for line in invoice.lines], ensure_ascii=False),
                    _ref_text(invoice.ref),
                ),
            )


def _line_value(line: InvoiceLine) -> dict[str, str | int | None]:
    quantity = None if line.quantity is None else str(line.quantity)
    return {"description": line.description, "amount": _to_minor(line.amount), "quantity": quantity}


def _row_values(t: Transaction, currency: str) -> tuple[str | int | None, ...]:
    return (
        t.date.isoformat(),
        t.description,
        _to_minor(t.amount),
        currency,
        t.kind,
        t.account,
        t.original,
        t.installment,
        t.bank_category,
        t.counterparty,
        t.source,
        _ref_text(t.ref),
        None if t.balance is None else _to_minor(t.balance),
    )


def _index(db: Database, sha256: str, kind: str, row_id: int | None, t: Transaction) -> None:
    db.execute(
        "INSERT INTO search (text, sha256, kind, ref) VALUES (?, ?, ?, ?)",
        (fold(f"{t.description} {t.counterparty}"), sha256, kind, str(row_id)),
    )


def load(db: Database, documents: Iterable[DocumentRow]) -> dict[str, ParseResult]:
    """The readings of documents as reader results, by sha256."""
    results = {
        doc.sha256: ParseResult(doc.parser, receipt_key=doc.receipt_key, holder=doc.holder, title=doc.title)
        for doc in documents
    }
    wanted = list(results)
    if not wanted:
        return results
    marks = ",".join("?" * len(wanted))
    for r in db.rows(f"SELECT * FROM document_accounts WHERE sha256 IN ({marks}) ORDER BY sha256, position", wanted):
        results[r["sha256"]].accounts.append(
            Account(r["id"], r["label"], r["bank"], AccountType(r["type"]), r["currency"], r["number"], r["note"])
        )
    statements: dict[int, Statement] = {}
    for r in db.rows(f"SELECT * FROM statements WHERE sha256 IN ({marks}) ORDER BY sha256, position", wanted):
        s = Statement(
            account=r["account"],
            cut_date=date.fromisoformat(r["cut_date"]),
            currency=r["currency"],
            source=r["source"],
            previous=None if r["previous"] is None else _from_minor(r["previous"]),
            total=None if r["total"] is None else _from_minor(r["total"]),
            total_is_sum=bool(r["total_is_sum"]),
            start=date.fromisoformat(r["start"]) if r["start"] else None,
            checks_ok=r["checks_ok"],
            checks_total=r["checks_total"],
            balances={month: _from_minor(v) for month, v in json.loads(r["balances"]).items()},
            one_off=bool(r["one_off"]),
            due_date=date.fromisoformat(r["due_date"]) if r["due_date"] else None,
            minimum_payment=None if r["minimum_payment"] is None else _from_minor(r["minimum_payment"]),
            credit_limit=None if r["credit_limit"] is None else _from_minor(r["credit_limit"]),
            next_cut=date.fromisoformat(r["next_cut"]) if r["next_cut"] else None,
            empty=bool(r["empty"]),
        )
        statements[r["id"]] = s
        results[r["sha256"]].statements.append(s)
    if statements:
        ids = ",".join("?" * len(statements))
        for r in db.rows(
            f"SELECT * FROM securities WHERE statement_id IN ({ids}) ORDER BY statement_id, position", list(statements)
        ):
            statements[r["statement_id"]].securities.append(
                Security(
                    r["code"],
                    r["name"],
                    Decimal(r["quantity"]),
                    _from_minor(r["value"]),
                    date.fromisoformat(r["as_of"]),
                )
            )
        for r in db.rows(
            f"SELECT * FROM transactions WHERE statement_id IN ({ids}) ORDER BY statement_id, position",
            list(statements),
        ):
            statements[r["statement_id"]].transactions.append(_transaction(r))
    for r in db.rows(f"SELECT * FROM evidence WHERE sha256 IN ({marks}) ORDER BY sha256, position", wanted):
        results[r["sha256"]].transactions.append(_transaction(r))
    for r in db.rows(f"SELECT * FROM invoices WHERE sha256 IN ({marks}) ORDER BY sha256, position", wanted):
        results[r["sha256"]].invoices.append(_invoice(r))
    return results


def _invoice(r: sqlite3.Row) -> Invoice:
    return Invoice(
        kind=InvoiceKind(r["kind"]),
        seller=r["seller"],
        issued=date.fromisoformat(r["issued"]),
        total=_from_minor(r["total"]),
        currency=r["currency"],
        number=r["number"],
        due=date.fromisoformat(r["due"]) if r["due"] else None,
        seller_id=r["seller_id"],
        lines=[
            InvoiceLine(
                line["description"],
                _from_minor(line["amount"]),
                None if line["quantity"] is None else Decimal(line["quantity"]),
            )
            for line in json.loads(r["lines"])
        ],
        ref=_ref(r["ref"]),
    )


def _transaction(r: sqlite3.Row) -> Transaction:
    return Transaction(
        date=date.fromisoformat(r["date"]),
        description=r["description"],
        amount=_from_minor(r["amount"]),
        kind=TransactionKind(r["kind"]),
        account=r["account"],
        original=r["original"],
        installment=r["installment"],
        bank_category=r["bank_category"],
        counterparty=r["counterparty"],
        source=r["source"],
        ref=_ref(r["ref"]),
        balance=None if r["balance"] is None else _from_minor(r["balance"]),
    )


CopyKey = tuple[str, ...]


def copy_keys(result: ParseResult) -> list[CopyKey]:
    """What the ledger merges copies by (docs/domain/ledger.md): a statement's account, cut date, currency and
    first day, a receipt's key. The same statement arrives as different files (a re-sent e-mail, an archive copy)."""
    keys: list[CopyKey] = [
        ("statement", s.account, s.cut_date.isoformat(), s.currency, s.start.isoformat() if s.start else "")
        for s in result.statements
    ]
    if result.receipt_key:
        keys.append(("receipt", result.receipt_key))
    return keys


def kept_copy(db: Database, keys: Iterable[CopyKey]) -> str | None:
    """The name of a kept document that holds one of keys (copy_keys), if any."""
    for kind, *values in keys:
        if kind == "statement":
            sql = (
                "SELECT d.name FROM statements s JOIN documents d ON d.sha256 = s.sha256 WHERE s.account = ? "
                "AND s.cut_date = ? AND s.currency = ? AND s.start = ? AND d.status != 'removed' ORDER BY d.added_at"
            )
        else:
            sql = "SELECT name FROM documents WHERE receipt_key = ? AND status != 'removed' ORDER BY added_at"
        name: str | None = db.scalar(sql, tuple(values))
        if name is not None:
            return name
    return None


def search(db: Database, query: str, limit: int = 50) -> list[tuple[str, str, str]]:
    """(kind, ref, sha256) of the rows and documents whose text holds every word of query, as prefixes."""
    words = fold(query).split()
    if not words:
        return []
    match = " ".join('"' + w.replace('"', '""') + '"*' for w in words)
    rows = db.rows("SELECT kind, ref, sha256 FROM search WHERE search MATCH ? ORDER BY rank LIMIT ?", (match, limit))
    return [(r["kind"], r["ref"], r["sha256"]) for r in rows]
