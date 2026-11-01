"""A reader's result as JSON, for its way back from the reading process (ADR-0005, worker.py).

Nothing is pickled: the reading process reads untrusted documents, so it sends back plain data, and every value's
type is checked while the models are built again. Only what readers fill crosses; the fields that categorizing and
the analysis fill later keep their defaults.
"""

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

from ..domain.codes import AccountType, TransactionKind
from ..domain.models import Account, ParseResult, Security, SourceRef, Statement, Transaction

type Json = dict[str, Any]


def dump(result: ParseResult) -> Json:
    return {
        "parser": result.parser,
        "accounts": [
            {
                "id": a.id,
                "label": a.label,
                "bank": a.bank,
                "type": a.type.value,
                "currency": a.currency,
                "number": a.number,
                "note": a.note,
            }
            for a in result.accounts
        ],
        "statements": [_statement(s) for s in result.statements],
        "transactions": [_transaction(t) for t in result.transactions],
        "receipt_key": result.receipt_key,
        "holder": result.holder,
        "title": result.title,
    }


def load(data: Any) -> ParseResult:
    """The result dump() made. Raises ValueError for anything else: a missing field or a value of the wrong type."""
    try:
        return ParseResult(
            parser=_str(data["parser"]),
            accounts=[
                Account(
                    _str(a["id"]),
                    _str(a["label"]),
                    _str(a["bank"]),
                    AccountType(_str(a["type"])),
                    _str(a["currency"]),
                    _str(a["number"]),
                    _str(a["note"]),
                )
                for a in data["accounts"]
            ],
            statements=[_statement_from(s) for s in data["statements"]],
            transactions=[_transaction_from(t) for t in data["transactions"]],
            receipt_key=_str(data["receipt_key"]),
            holder=_str(data["holder"]),
            title=_str(data["title"]),
        )
    except (AttributeError, KeyError, IndexError, TypeError, ArithmeticError) as exc:  # decimal.InvalidOperation
        raise ValueError(f"not a reader's result: {exc!r}") from exc


# --- the values ---------------------------------------------------------------------------------------------------


def _str(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError(f"expected a string, got {type(value).__name__}")
    return value


def _int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"expected an integer, got {type(value).__name__}")
    return value


def _float(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"expected a number, got {type(value).__name__}")
    return float(value)


def _optional[T](load: Callable[[Any], T], value: Any) -> T | None:
    return None if value is None else load(value)


def _money(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _decimal(value: Any) -> Decimal:
    number = Decimal(_str(value))
    if not number.is_finite():
        raise ValueError(f"not an amount: {value!r}")
    return number


def _date(value: Any) -> date:
    return date.fromisoformat(_str(value))


# --- the models ---------------------------------------------------------------------------------------------------


def _ref(ref: SourceRef | None) -> Json | None:
    if ref is None:
        return None
    return {
        "page": ref.page,
        "box": list(ref.box) if ref.box is not None else None,
        "line": ref.line,
        "sheet": ref.sheet,
        "row": ref.row,
        "span": list(ref.span) if ref.span is not None else None,
    }


def _box(value: Any) -> tuple[float, float, float, float]:
    x0, top, x1, bottom = (_float(v) for v in value)
    return x0, top, x1, bottom


def _span(value: Any) -> tuple[int, int]:
    start, end = (_int(v) for v in value)
    return start, end


def _ref_from(data: Any) -> SourceRef | None:
    if data is None:
        return None
    return SourceRef(
        page=_optional(_int, data["page"]),
        box=_optional(_box, data["box"]),
        line=_optional(_int, data["line"]),
        sheet=_optional(_str, data["sheet"]),
        row=_optional(_int, data["row"]),
        span=_optional(_span, data["span"]),
    )


def _transaction(t: Transaction) -> Json:
    return {
        "date": t.date.isoformat(),
        "description": t.description,
        "amount": str(t.amount),
        "kind": t.kind.value,
        "account": t.account,
        "original": t.original,
        "installment": t.installment,
        "bank_category": t.bank_category,
        "counterparty": t.counterparty,
        "source": t.source,
        "ref": _ref(t.ref),
        "balance": _money(t.balance),
    }


def _transaction_from(data: Any) -> Transaction:
    return Transaction(
        date=_date(data["date"]),
        description=_str(data["description"]),
        amount=_decimal(data["amount"]),
        kind=TransactionKind(_str(data["kind"])),
        account=_str(data["account"]),
        original=_str(data["original"]),
        installment=_str(data["installment"]),
        bank_category=_str(data["bank_category"]),
        counterparty=_str(data["counterparty"]),
        source=_str(data["source"]),
        ref=_ref_from(data["ref"]),
        balance=_optional(_decimal, data["balance"]),
    )


def _statement(s: Statement) -> Json:
    return {
        "account": s.account,
        "cut_date": s.cut_date.isoformat(),
        "currency": s.currency,
        "source": s.source,
        "previous": _money(s.previous),
        "total": _money(s.total),
        "transactions": [_transaction(t) for t in s.transactions],
        "total_is_sum": s.total_is_sum,
        "start": s.start.isoformat() if s.start else None,
        "checks_ok": s.checks_ok,
        "checks_total": s.checks_total,
        "balances": {month: str(v) for month, v in s.balances.items()},
        "one_off": s.one_off,
        "securities": [
            {
                "code": x.code,
                "name": x.name,
                "quantity": str(x.quantity),
                "value": str(x.value),
                "as_of": x.as_of.isoformat(),
            }
            for x in s.securities
        ],
    }


def _statement_from(data: Any) -> Statement:
    total_is_sum, one_off = data["total_is_sum"], data["one_off"]
    if not isinstance(total_is_sum, bool) or not isinstance(one_off, bool):
        raise TypeError(f"expected booleans, got {type(total_is_sum).__name__} and {type(one_off).__name__}")
    return Statement(
        account=_str(data["account"]),
        cut_date=_date(data["cut_date"]),
        currency=_str(data["currency"]),
        source=_str(data["source"]),
        previous=_optional(_decimal, data["previous"]),
        total=_optional(_decimal, data["total"]),
        transactions=[_transaction_from(t) for t in data["transactions"]],
        total_is_sum=total_is_sum,
        start=_optional(_date, data["start"]),
        checks_ok=_int(data["checks_ok"]),
        checks_total=_int(data["checks_total"]),
        balances={_str(month): _decimal(v) for month, v in data["balances"].items()},
        one_off=one_off,
        securities=[
            Security(_str(x["code"]), _str(x["name"]), _decimal(x["quantity"]), _decimal(x["value"]), _date(x["as_of"]))
            for x in data["securities"]
        ],
    )
