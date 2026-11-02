"""The non-bank bills and receipts (F14), for the Bills screen: each with what the bank's rows say of it, from the
analysis the service keeps. Amounts are minor units with their currency (ADR-0006): a document's in its own currency,
the bank row's in TL. None of them changes a total."""

from decimal import Decimal

from fastapi import APIRouter, Depends, Request

from ...app import invoices
from ...app.analysis import Analysis, account_labels
from ...app.invoices import InvoiceStatus, InvoiceView
from ...app.workspace import Busy
from ..context import Context, context_of
from ..guard import Principal
from ..models import (
    AccountRefOut,
    BankRowOut,
    InvoiceCountsOut,
    InvoiceLineOut,
    InvoiceOut,
    InvoicesOut,
    MoneyOut,
    WindowOut,
)
from ..problems import Problem
from .deps import only

router = APIRouter(dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])


def _analysis(context: Context) -> Analysis:
    try:
        return context.analysis.get()
    except Busy as exc:
        raise Problem(503, "busy", str(exc)) from exc


def _money(value: Decimal, currency: str) -> MoneyOut:
    return MoneyOut(minor=invoices.minor(value, currency), currency=currency)


def _item(view: InvoiceView, labels: dict[str, str]) -> InvoiceOut:
    row = view.row
    return InvoiceOut(
        key=view.key,
        kind=view.kind,
        status=view.status,
        seller=view.seller,
        number=view.number,
        issued=view.issued,
        due=view.due,
        total=_money(view.total, view.currency),
        lines=[
            InvoiceLineOut(
                description=line.description,
                amount=_money(line.amount, view.currency),
                quantity=None if line.quantity is None else format(line.quantity, "f"),
            )
            for line in view.lines
        ],
        window=WindowOut(start=view.window[0], end=view.window[1]),
        document=view.document,
        sha256=view.sha256,
        row=(
            BankRowOut(
                fingerprint=row.fingerprint,
                day=row.day,
                account=AccountRefOut(id=row.account, label=labels.get(row.account, row.account)),
                amount=_money(row.amount, "TRY"),
                description=row.description,
            )
            if row
            else None
        ),
        reasons=list(view.reasons),
    )


@router.get("/api/invoices")
def invoice_list(request: Request) -> InvoicesOut:
    """Every bill and receipt non-bank senders mailed: the pending ones first by due date, then the unmatched
    (information only, with what may explain them), then the matched with the bank row that paid each, newest first;
    and how many have each status (F14)."""
    a = _analysis(context_of(request))
    found, labels = invoices.overview(a), account_labels(a)
    counts = found.counts
    return InvoicesOut(
        items=[_item(view, labels) for view in found.items],
        counts=InvoiceCountsOut(
            pending=counts[InvoiceStatus.PENDING],
            unmatched=counts[InvoiceStatus.UNMATCHED],
            matched=counts[InvoiceStatus.MATCHED],
        ),
    )
